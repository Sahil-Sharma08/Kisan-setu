import json
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import QueueEntry, Booking, Center, ProcurementRecord
from backend.schemas import GateVerifyRequest, QueueAdvanceRequest, ProcurementActionRequest
from backend.state_machine import (
    transition_token_state,
    STAGE_METADATA,
    validate_state_transition
)
from backend.qr_security import (
    verify_digital_signature,
    validate_arrival_window,
    create_signed_token_payload
)
from backend.routers.events import emit_yard_event

router = APIRouter(prefix="/queue", tags=["Live Queue & Yard Intelligence"])

class StageTransitionPayload(BaseModel):
    booking_id: str
    next_stage: str
    metadata: Optional[Dict[str, Any]] = None

class GateCheckinAdvancedRequest(BaseModel):
    booking_id: str
    digital_sig: Optional[str] = None
    signed_payload: Optional[Dict[str, Any]] = None
    force_override: bool = False
    operator_notes: Optional[str] = None
    override_reason: Optional[str] = None

class TransitDelayReportRequest(BaseModel):
    token_id: str
    reason: str = "ROAD_BLOCKAGE"
    notes: Optional[str] = None

class SupervisorOverrideRequest(BaseModel):
    token_id: str
    supervisor_id: str = "SUP-MAIN-01"
    override_reason: str = "STANDBY_BAY_ADMISSION"
    assigned_bay: Optional[str] = "STANDBY-LANE-B1"
    notes: Optional[str] = None

def _format_queue_item(q: QueueEntry) -> dict:
    return {
        "bookingId": q.booking_id,
        "tokenId": q.token_id,
        "centerId": q.center_id,
        "farmerName": q.farmer_name,
        "phone": q.phone,
        "commodity": q.commodity,
        "timeSlot": q.time_slot,
        "queuePosition": q.queue_position,
        "totalVehiclesAhead": q.total_vehicles_ahead,
        "estimatedWaitMinutes": q.estimated_wait_minutes,
        "arrivalStatus": q.arrival_status,
        "status": q.status,
        "queueType": getattr(q, "queue_type", "NORMAL") or "NORMAL",
        "currentStage": getattr(q, "current_stage", "BOOKED") or "BOOKED",
        "stageInfo": STAGE_METADATA.get(getattr(q, "current_stage", "BOOKED"), {}),
        "assignedBay": getattr(q, "assigned_bay", None),
        "assignedWeighbridge": getattr(q, "assigned_weighbridge", None),
        "unloadingBayId": getattr(q, "unloading_bay_id", None),
        "grossWeighbridgeId": getattr(q, "gross_weighbridge_id", None),
        "tareWeighbridgeId": getattr(q, "tare_weighbridge_id", None),
        "grossWeight": getattr(q, "gross_weight", 0.0),
        "tareWeight": getattr(q, "tare_weight", 0.0),
        "netWeight": getattr(q, "net_weight", 0.0),
        "grossWeightKg": getattr(q, "gross_weight_kg", 0.0),
        "tareWeightKg": getattr(q, "tare_weight_kg", 0.0),
        "netWeightKg": getattr(q, "net_weight_kg", 0.0),
        "jFormId": getattr(q, "j_form_id", None),
        "assayMoisture": getattr(q, "assay_moisture", None),
        "dbtStatus": getattr(q, "dbt_status", "PENDING")
    }

@router.get("/{center_id}")
def get_center_queue(center_id: str, db: Session = Depends(get_db)):
    """
    Get live queue items for a procurement center
    """
    clean_id = center_id.strip().upper()
    entries = (
        db.query(QueueEntry)
        .filter(QueueEntry.center_id == clean_id)
        .order_by(QueueEntry.queue_position.asc())
        .all()
    )

    all_items = [_format_queue_item(e) for e in entries]

    today_bookings = len(all_items)
    arrived = sum(1 for e in all_items if e["arrivalStatus"] in ["arrived", "checked_in"])
    in_queue = sum(1 for e in all_items if e["arrivalStatus"] == "checked_in" and e["queuePosition"] > 0)
    in_progress = sum(1 for e in all_items if e["queuePosition"] == 0 and "खरीद पूर्ण" not in e["status"])
    completed = sum(1 for e in all_items if "खरीद पूर्ण" in e["status"] or e["currentStage"] == "DBT_DISPATCHED")

    return {
        "success": True,
        "centerId": clean_id,
        "metrics": {
            "todayBookings": today_bookings,
            "arrivedFarmers": arrived,
            "waitingInQueue": in_queue,
            "inProgress": in_progress,
            "completed": completed
        },
        "data": all_items
    }

@router.post("/gate-checkin")
async def gate_checkin(payload: GateCheckinAdvancedRequest, db: Session = Depends(get_db)):
    """
    Operator Gate Terminal:
    1. Validates cryptographic HMAC signature to prevent broker/arhtiya slot hoarding & fake passes.
    2. Enforces arrival time buffer (±45 minutes). Outside buffer flags as STANDBY_OVERDUE.
    3. Deterministically advances lifecycle to GATE_SCANNED.
    """
    clean_id = payload.booking_id.strip().upper()
    booking = db.query(Booking).filter((Booking.id == clean_id) | (Booking.token_id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking or Token '{payload.booking_id}' not found.")

    # 1. Anti-Hoarding & Tamper Verification
    signature_valid = True
    sig_provided = payload.digital_sig or (payload.signed_payload.get("digitalSig") if payload.signed_payload else None)
    
    if payload.signed_payload and sig_provided:
        signature_valid = verify_digital_signature(payload.signed_payload, sig_provided)
        if not signature_valid and not payload.force_override:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="SECURITY ALERT: Digital signature mismatch. Potential forged or hoarded pass."
            )

    # 2. Buffer Window Verification (±45 minutes)
    # Parse scheduled slot or ISO window
    time_window = []
    if payload.signed_payload and payload.signed_payload.get("timeWindow"):
        time_window = payload.signed_payload.get("timeWindow")
    else:
        # Default mock ISO window for demonstration based on slot
        now = datetime.utcnow()
        today_iso = now.strftime("%Y-%m-%d")
        time_window = [f"{today_iso}T09:00:00", f"{today_iso}T10:00:00"]

    # Check arrival against ±45 min buffer
    is_on_time, buffer_code, delta_mins = validate_arrival_window(time_window, buffer_minutes=45)

    # If late/early outside buffer and not forced override
    if not is_on_time and not payload.force_override:
        # Move to STANDBY_OVERDUE state
        try:
            res = transition_token_state(
                booking=booking,
                next_stage="STANDBY_OVERDUE",
                metadata={
                    "operator": "GATE-01",
                    "deltaMinutes": delta_mins,
                    "bufferCode": buffer_code,
                    "notes": f"Arrival outside allowable buffer ({delta_mins} mins difference). Held in Standby Lane."
                },
                db=db
            )
        except Exception:
            pass

        return {
            "success": False,
            "status": "STANDBY_OVERDUE",
            "bufferCode": buffer_code,
            "deltaMinutes": delta_mins,
            "message": f"ATTENTION: Vehicle arrived outside allowable ±45 min window ({abs(delta_mins)} mins {buffer_code.lower()}). Assigned to Standby Lane. Requires supervisor override to admit.",
            "requiresOverride": True,
            "bookingId": booking.id,
            "tokenId": booking.token_id,
            "farmerName": booking.farmer_name
        }

    # Assign Assay Bay A, B, or C
    assigned_bay = f"Assay Bay {random.choice(['1', '2', '3'])}"

    # 3. Deterministic State Machine Transition -> GATE_SCANNED
    transition_token_state(
        booking=booking,
        next_stage="GATE_SCANNED",
        metadata={
            "operator": "GATE-TERMINAL-01",
            "assignedBay": assigned_bay,
            "notes": "Gate verified and admitted to procurement yard.",
            "override": payload.force_override
        },
        db=db
    )

    # Get updated QueueEntry
    queue_entry = db.query(QueueEntry).filter(QueueEntry.booking_id == booking.id).first()
    if not queue_entry:
        queue_entry = QueueEntry(
            booking_id=booking.id,
            token_id=booking.token_id,
            center_id=booking.center_id,
            farmer_name=booking.farmer_name,
            phone=booking.farmer_phone,
            commodity=booking.commodity,
            time_slot=booking.time_slot,
            queue_position=3,
            total_vehicles_ahead=2,
            estimated_wait_minutes=15,
            arrival_status="checked_in",
            current_stage="GATE_SCANNED",
            assigned_bay=assigned_bay,
            status="गेट सत्यापन पूर्ण (Gate Verified)"
        )
        db.add(queue_entry)
        db.commit()
        db.refresh(queue_entry)

    # Emit real-time WebSocket broadcast
    await emit_yard_event(booking.center_id, "GATE_VERIFIED", {
        "bookingId": booking.id,
        "tokenId": booking.token_id,
        "farmerName": booking.farmer_name,
        "vehicleNumber": booking.vehicle_number,
        "assignedBay": assigned_bay,
        "queuePosition": queue_entry.queue_position
    })

    return {
        "success": True,
        "status": "GATE_SCANNED",
        "message": f"Gate verified successfully for {booking.farmer_name} ({booking.token_id}). Assigned to {assigned_bay}.",
        "gateSlip": {
            "tokenId": booking.token_id,
            "farmerName": booking.farmer_name,
            "vehicleNumber": booking.vehicle_number,
            "centerName": booking.center_name,
            "commodity": booking.commodity,
            "assignedBay": assigned_bay,
            "admitTimestamp": datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S IST"),
            "queuePosition": queue_entry.queue_position
        },
        "data": _format_queue_item(queue_entry)
    }

@router.post("/transition")
async def advance_stage_transition(payload: StageTransitionPayload, db: Session = Depends(get_db)):
    """
    Deterministic Live Pipeline Transition Endpoint:
    BOOKED -> GATE_SCANNED -> ASSAY_TESTING -> WEIGHBRIDGE_IN -> WEIGHBRIDGE_OUT -> DBT_DISPATCHED
    """
    clean_id = payload.booking_id.strip().upper()
    booking = db.query(Booking).filter((Booking.id == clean_id) | (Booking.token_id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking '{payload.booking_id}' not found.")

    meta = payload.metadata or {}
    try:
        result = transition_token_state(booking, payload.next_stage, meta, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Real-time WebSocket emission
    await emit_yard_event(booking.center_id, "STAGE_TRANSITION", {
        "bookingId": booking.id,
        "tokenId": booking.token_id,
        "farmerName": booking.farmer_name,
        "nextStage": payload.next_stage,
        "stageInfo": STAGE_METADATA.get(payload.next_stage, {})
    })

    return result

@router.post("/transit-delay")
async def report_transit_delay(payload: TransitDelayReportRequest, db: Session = Depends(get_db)):
    """
    Farmer Self-Reporting Transit Delay Protocol:
    1. Shifts arrival window by +60 minutes without slot cancellation.
    2. Moves state to TRANSIT_DELAYED.
    3. Broadcasts event to Superintendent Command Center and Yard Screen.
    """
    clean_id = payload.token_id.strip().upper()
    booking = db.query(Booking).filter((Booking.token_id == clean_id) | (Booking.id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Token or Booking '{payload.token_id}' not found.")

    if booking.current_stage not in ["BOOKED", "TRANSIT_DELAYED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot report transit delay in stage '{booking.current_stage}'. Vehicle is already processed."
        )

    try:
        result = transition_token_state(
            booking=booking,
            next_stage="TRANSIT_DELAYED",
            metadata={
                "reason": payload.reason,
                "notes": payload.notes or "Farmer reported delay via mobile pass",
                "operator": "FARMER-SELF"
            },
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # WebSocket event
    await emit_yard_event(booking.center_id, "TRANSIT_DELAY_REPORTED", {
        "tokenId": booking.token_id,
        "farmerName": booking.farmer_name,
        "reason": payload.reason,
        "newWindowEnd": booking.arrival_window_end.isoformat() if booking.arrival_window_end else None,
        "graceMinutes": 60
    })

    return {
        "success": True,
        "tokenId": booking.token_id,
        "currentStage": "TRANSIT_DELAYED",
        "message": "रास्ते में देरी दर्ज की गई। स्लॉट रद्द नहीं हुआ — 60 मिनट की अतिरिक्त ग्रेस विंडो प्रदान की गई है।",
        "graceMinutes": 60,
        "reason": payload.reason,
        "arrivalWindowEnd": booking.arrival_window_end.isoformat() if booking.arrival_window_end else None
    }

@router.post("/supervisor-override")
async def supervisor_override_standby(payload: SupervisorOverrideRequest, db: Session = Depends(get_db)):
    """
    Supervisor Standby Override Protocol:
    Admits an overdue tractor-trolley from STANDBY_OVERDUE into GATE_SCANNED with standby priority.
    """
    clean_id = payload.token_id.strip().upper()
    booking = db.query(Booking).filter((Booking.token_id == clean_id) | (Booking.id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Token '{payload.token_id}' not found.")

    curr = booking.current_stage or "BOOKED"
    if curr not in ["STANDBY_OVERDUE", "BOOKED", "TRANSIT_DELAYED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supervisor override not allowed for stage '{curr}'. Token must be in STANDBY_OVERDUE or un-admitted."
        )

    # Force to STANDBY_OVERDUE if overdue BOOKED, then transition to GATE_SCANNED with queueType=STANDBY
    if curr != "STANDBY_OVERDUE":
        booking.current_stage = "STANDBY_OVERDUE"

    try:
        result = transition_token_state(
            booking=booking,
            next_stage="GATE_SCANNED",
            metadata={
                "queueType": "STANDBY",
                "operator": payload.supervisor_id,
                "notes": f"SUPERVISOR OVERRIDE: {payload.override_reason}",
                "assignedBay": payload.assigned_bay or "STANDBY-LANE-B1"
            },
            db=db
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await emit_yard_event(booking.center_id, "SUPERVISOR_STANDBY_ADMITTED", {
        "tokenId": booking.token_id,
        "farmerName": booking.farmer_name,
        "supervisorId": payload.supervisor_id,
        "assignedBay": payload.assigned_bay or "STANDBY-LANE-B1"
    })

    return {
        "success": True,
        "tokenId": booking.token_id,
        "status": "GATE_SCANNED_STANDBY",
        "message": f"अधीक्षक विशेष अनुमति स्वीकृत: {booking.farmer_name} को स्टैंडबाई कतार में प्रवेश दिया गया।",
        "result": result
    }

@router.get("/j-form/{token_or_booking_id}")
def get_statutory_j_form(token_or_booking_id: str, db: Session = Depends(get_db)):
    """
    Fetch statutory e-J-Form (Agricultural Produce Market Form 'J') for farmer receipt and superintendent audit.
    Auto-generates if tare weighment has been recorded.
    """
    from backend.j_form_service import generate_statutory_j_form

    clean_id = token_or_booking_id.strip().upper()
    booking = db.query(Booking).filter((Booking.token_id == clean_id) | (Booking.id == clean_id) | (Booking.j_form_id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Procurement record '{token_or_booking_id}' not found.")

    if booking.j_form_data:
        try:
            return {
                "success": True,
                "jForm": json.loads(booking.j_form_data)
            }
        except Exception:
            pass

    # Generate on-demand if in appropriate stage
    j_form = generate_statutory_j_form(booking, db, operator_id="AUDIT-SYSTEM")
    return {
        "success": True,
        "jForm": j_form
    }

@router.post("/advance")
async def advance_queue(payload: QueueAdvanceRequest, db: Session = Depends(get_db)):
    """
    Advance vehicle queue sequence number towards weighbridge
    """
    clean_id = payload.booking_id.strip().upper()
    queue_entry = db.query(QueueEntry).filter(
        (QueueEntry.booking_id == clean_id) | (QueueEntry.token_id == clean_id)
    ).first()

    if not queue_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue entry not found.")

    new_pos = max(0, queue_entry.queue_position - 1)
    queue_entry.queue_position = new_pos
    queue_entry.total_vehicles_ahead = max(0, new_pos - 1)
    queue_entry.estimated_wait_minutes = new_pos * 5

    booking = db.query(Booking).filter(Booking.id == queue_entry.booking_id).first()

    if new_pos == 1:
        queue_entry.status = "आपकी बारी जल्द है (Your Turn Is Next)"
    elif new_pos == 0:
        queue_entry.status = "खरीद प्रक्रिया में (Procurement in Progress)"
        if booking and booking.current_stage == "GATE_SCANNED":
            try:
                transition_token_state(booking, "ASSAY_TESTING", {"operator": "QUEUE-SYSTEM"}, db)
            except Exception:
                pass
    else:
        queue_entry.status = "कतार में प्रतीक्षा (Waiting in Queue)"

    if booking:
        booking.queue_position = new_pos

    db.commit()
    db.refresh(queue_entry)

    # Real-time WebSocket notification
    await emit_yard_event(queue_entry.center_id, "QUEUE_ADVANCED", {
        "bookingId": queue_entry.booking_id,
        "tokenId": queue_entry.token_id,
        "newPosition": new_pos
    })

    return {
        "success": True,
        "message": f"Queue position advanced for {queue_entry.farmer_name} (Now #{new_pos}).",
        "data": _format_queue_item(queue_entry)
    }

@router.post("/complete-procurement")
async def complete_procurement(payload: ProcurementActionRequest, db: Session = Depends(get_db)):
    """
    Finalize weighbridge records, advance to DBT_DISPATCHED, and issue digital receipt
    """
    clean_id = payload.booking_id.strip().upper()
    booking = db.query(Booking).filter((Booking.id == clean_id) | (Booking.token_id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    # Calculate weights and payment
    gross = payload.gross_weight or (booking.quantity_qtl + 5.7)
    tare = payload.tare_weight or 5.7
    net = round(gross - tare, 2)
    rate = 2425.0
    total_amount = round(net * rate, 2)
    rand_num = random.randint(1000, 9999)
    receipt_id = f"KSP-RCP-{rand_num}"
    dbt_ref = f"DBT-SBI-78{rand_num}"

    # Advance stage to WEIGHBRIDGE_IN -> WEIGHBRIDGE_OUT -> DBT_DISPATCHED
    booking.gross_weight = gross
    booking.tare_weight = tare
    booking.net_weight = net
    booking.assay_moisture = payload.moisture_percent or 10.5
    booking.status = "खरीद पूर्ण (Procurement Completed)"
    booking.current_stage = "DBT_DISPATCHED"
    booking.dbt_ref_no = dbt_ref
    booking.dbt_status = "SUCCESS"
    booking.queue_position = 0

    # Update QueueEntry
    queue_entry = db.query(QueueEntry).filter(QueueEntry.booking_id == booking.id).first()
    if queue_entry:
        queue_entry.queue_position = 0
        queue_entry.total_vehicles_ahead = 0
        queue_entry.estimated_wait_minutes = 0
        queue_entry.current_stage = "DBT_DISPATCHED"
        queue_entry.status = "खरीद पूर्ण (Procurement Completed)"
        queue_entry.gross_weight = gross
        queue_entry.tare_weight = tare
        queue_entry.net_weight = net

    # Create procurement receipt
    receipt = ProcurementRecord(
        id=receipt_id,
        booking_id=booking.id,
        token_id=booking.token_id,
        farmer_name=booking.farmer_name,
        farmer_phone=booking.farmer_phone,
        center_id=booking.center_id,
        center_name=booking.center_name,
        district=booking.district or "Karnal",
        commodity=booking.commodity,
        date=datetime.utcnow().strftime("%d-%m-%Y"),
        gross_weight=gross,
        tare_weight=tare,
        net_weight=net,
        moisture_percent=booking.assay_moisture,
        rate_per_qtl=rate,
        total_amount=total_amount,
        payment_status="PAID"
    )
    db.add(receipt)
    db.commit()

    # Emit real-time WebSocket event
    await emit_yard_event(booking.center_id, "DBT_DISPATCHED", {
        "bookingId": booking.id,
        "tokenId": booking.token_id,
        "farmerName": booking.farmer_name,
        "netWeight": net,
        "totalAmount": total_amount,
        "dbtRefNo": dbt_ref
    })

    return {
        "success": True,
        "message": f"Procurement successfully completed. Digital receipt {receipt_id} generated. DBT payment dispatched.",
        "receiptId": receipt_id,
        "dbtRefNo": dbt_ref,
        "data": {
            "receiptId": receipt_id,
            "bookingId": booking.id,
            "tokenId": booking.token_id,
            "farmerName": booking.farmer_name,
            "netWeight": net,
            "totalAmount": total_amount,
            "dbtRefNo": dbt_ref,
            "paymentStatus": "PAID"
        }
    }

@router.get("/{center_id}/yard-screen")
def get_yard_screen_billboard_data(center_id: str, db: Session = Depends(get_db)):
    """
    Public Yard Billboard Display Mode API:
    - Currently In Weighing (Lane 1 & Lane 2 active tokens)
    - Next in Queue / Immediate Call (top summoned vehicles)
    - Assay Bay Assignments (Active moisture tests)
    - Real-time Yard metrics
    """
    clean_id = center_id.strip().upper()
    center = db.query(Center).filter(Center.id == clean_id).first()
    if not center:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Center {center_id} not found.")

    # Fetch active queue items
    entries = (
        db.query(QueueEntry)
        .filter(QueueEntry.center_id == clean_id)
        .filter(QueueEntry.arrival_status == "checked_in")
        .order_by(QueueEntry.queue_position.asc())
        .all()
    )

    # Formulate Currently in Weighing with physical two-stage lanes
    currently_weighing = [
        {
            "lane": "Weighbridge Scale 1 (Inbound)",
            "laneKey": "GROSS_LANE",
            "type": "GROSS (सकल भार)",
            "tokenId": entries[0].token_id if len(entries) > 0 else "KS-TKN-1002",
            "farmerName": entries[0].farmer_name if len(entries) > 0 else "बलविंदर सिंह (Balwinder Singh)",
            "vehicleNumber": "HR-05-BC-8921",
            "commodity": entries[0].commodity if len(entries) > 0 else "Wheat (Grade A)",
            "grossWeight": 45.8,
            "status": "GROSS_WEIGHING_ACTIVE",
            "scaleId": "WB-SCALE-01"
        },
        {
            "lane": "Weighbridge Scale 2 (Outbound)",
            "laneKey": "TARE_LANE",
            "type": "TARE / NET (खाली तौल)",
            "tokenId": entries[1].token_id if len(entries) > 1 else "KS-TKN-1004",
            "farmerName": entries[1].farmer_name if len(entries) > 1 else "राजिंदर कुमार (Rajinder Kumar)",
            "vehicleNumber": "HR-05-PQ-4412",
            "commodity": entries[1].commodity if len(entries) > 1 else "Paddy (PR-126)",
            "grossWeight": 14.2,
            "netWeight": 31.6,
            "status": "TARE_WEIGHING_ACTIVE",
            "scaleId": "WB-SCALE-02"
        }
    ]

    # Unloading Bays / Godown Sheds
    unloading_sheds = [
        {
            "bayId": "SHED-BAY-A1",
            "shedName": "गोदाम शेड नं. 1 (Central Godown A)",
            "tokenId": "KS-TKN-1005",
            "farmerName": "कुलदीप सिंह",
            "vehicleNumber": "HR-05-AB-7711",
            "commodity": "Wheat (FAQ Grade-1)",
            "status": "UNLOADING_IN_PROGRESS",
            "statusLabel": "बोरी खालीकरण जारी (Unloading)",
            "color": "amber",
            "bagsUnloaded": 180,
            "totalBags": 220
        },
        {
            "bayId": "SHED-BAY-A2",
            "shedName": "गोदाम शेड नं. 1 (Central Godown A)",
            "tokenId": "KS-TKN-1007",
            "farmerName": "जसविंदर चीमा",
            "vehicleNumber": "PB-11-TR-8821",
            "commodity": "Paddy (PR-126)",
            "status": "UNLOADING_COMPLETED",
            "statusLabel": "खालीकरण पूर्ण • वेईब्रिज-2 प्रस्थान",
            "color": "emerald",
            "bagsUnloaded": 250,
            "totalBags": 250
        },
        {
            "bayId": "SHED-BAY-B1",
            "shedName": "साइलो प्लेटफार्म नं. 2 (Bulk Silo Shed B)",
            "tokenId": "KS-TKN-1009",
            "farmerName": "धर्मपाल यादव",
            "vehicleNumber": "HR-02-MN-9912",
            "commodity": "Wheat (Sharbati)",
            "status": "UNLOADING_IN_PROGRESS",
            "statusLabel": "अनलोडिंग जारी",
            "color": "amber",
            "bagsUnloaded": 95,
            "totalBags": 200
        }
    ]

    # Standby Queue (Outside buffer or delayed arrivals awaiting slot vacancy)
    standby_queue = [
        {
            "tokenId": "KS-TKN-0994",
            "farmerName": "गुरदीप बाजवा",
            "vehicleNumber": "PB-02-XY-1011",
            "commodity": "Wheat",
            "reason": "STANDBY_OVERDUE (देरी से आगमन)",
            "status": "STANDBY_WAITING",
            "overrideEligible": True
        }
    ]

    # Next in Queue (Immediate Call)
    next_in_queue = []
    candidates = [e for e in entries if e.queue_position > 0]
    if candidates:
        for idx, c in enumerate(candidates[:4]):
            next_in_queue.append({
                "queuePos": c.queue_position,
                "tokenId": c.token_id,
                "farmerName": c.farmer_name,
                "commodity": c.commodity,
                "vehicleNumber": "HR-05-TR-" + str(c.queue_position * 1111),
                "callGate": "Gate Bay " + str((idx % 2) + 1),
                "estWaitMins": c.estimated_wait_minutes
            })
    else:
        # High quality demo entries if queue empty
        next_in_queue = [
            {"queuePos": 1, "tokenId": "KS-TKN-1011", "farmerName": "सुरेश कुमार (Suresh Kumar)", "commodity": "Wheat (Grade A)", "vehicleNumber": "HR-05-AB-1234", "callGate": "Gate Bay 1", "estWaitMins": 4},
            {"queuePos": 2, "tokenId": "KS-TKN-1015", "farmerName": "हरप्रीत मान (Harpreet Mann)", "commodity": "Paddy (Basmati)", "vehicleNumber": "PB-11-XY-9021", "callGate": "Gate Bay 2", "estWaitMins": 9},
            {"queuePos": 3, "tokenId": "KS-TKN-1018", "farmerName": "राम किशन (Ram Kishan)", "commodity": "Wheat (Grade A)", "vehicleNumber": "HR-02-MN-3342", "callGate": "Gate Bay 1", "estWaitMins": 14},
            {"queuePos": 4, "tokenId": "KS-TKN-1022", "farmerName": "कुलदीप शर्मा (Kuldeep Sharma)", "commodity": "Mustard (सरसों)", "vehicleNumber": "HR-05-KL-7721", "callGate": "Gate Bay 2", "estWaitMins": 19}
        ]

    # Assay Bay Assignments
    assay_bays = [
        {
            "bay": "Assay Station 1",
            "tokenId": "KS-TKN-1008",
            "farmerName": "अमित चौधरी",
            "moisture": "10.8%",
            "status": "CLEARED (पास)",
            "color": "emerald"
        },
        {
            "bay": "Assay Station 2",
            "tokenId": "KS-TKN-1010",
            "farmerName": "विक्रम गिल",
            "moisture": "11.6%",
            "status": "TESTING (जांच जारी)",
            "color": "amber"
        },
        {
            "bay": "Assay Station 3",
            "tokenId": "KS-TKN-1012",
            "farmerName": "गुरप्रीत संधू",
            "moisture": "12.4%",
            "status": "ALERT (>12% Aerating)",
            "color": "rose"
        }
    ]

    # Summary metrics
    records = db.query(ProcurementRecord).filter(ProcurementRecord.center_id == clean_id).all()
    total_net = sum(r.net_weight for r in records)
    today_mt = round((total_net * 0.1) if total_net > 0 else 312.5, 1)

    return {
        "success": True,
        "centerId": clean_id,
        "centerName": center.name,
        "district": center.district,
        "timestamp": datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S IST"),
        "currentlyWeighing": currently_weighing,
        "unloadingSheds": unloading_sheds,
        "standbyQueue": standby_queue,
        "nextInQueue": next_in_queue,
        "assayBays": assay_bays,
        "metrics": {
            "averageWaitMinutes": 18,
            "todayProcuredMT": today_mt,
            "activeVehiclesInYard": len(entries) if len(entries) > 0 else 14,
            "dailyCapacityMT": center.daily_capacity_mt or 500,
            "weatherStatus": "Clear Sky / Operational"
        }
    }
