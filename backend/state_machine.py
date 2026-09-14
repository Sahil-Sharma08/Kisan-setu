"""
Deterministic State Machine for Kisan-Setu Mandi Flow
Refined for SIH26032 (Ministry of Consumer Affairs, Food & Public Distribution):
Strict Physical Mandi Lifecycle:
  BOOKED -> GATE_SCANNED -> ASSAY_TESTING -> GROSS_WEIGHED -> UNLOADING_BAY -> TARE_WEIGHED -> J_FORM_ISSUED -> DBT_DISPATCHED
Grace & Edge states:
  TRANSIT_DELAYED (Farmer self-reported +60m window shift)
  STANDBY_OVERDUE (Outside buffer, admitted via supervisor override)
  REJECTED_QUALITY (Moisture ceiling exceeded)
  CANCELLED
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from backend.models import Booking, QueueEntry, ProcurementRecord

# Deterministic Stages Configuration
STAGE_METADATA = {
    "BOOKED": {
        "titleEn": "Slot Booked & Pass Issued",
        "titleHi": "स्लॉट बुक हुआ • गेट पास जारी",
        "step": 1,
        "icon": "📅",
        "color": "blue",
        "description": "Digital token issued with tamper-evident HMAC QR payload."
    },
    "TRANSIT_DELAYED": {
        "titleEn": "Transit Delayed (+60m Grace Window)",
        "titleHi": "रास्ते में देरी दर्ज • 60 मिनट ग्रेस विंडो",
        "step": 1.2,
        "icon": "🚨",
        "color": "amber",
        "description": "Farmer self-reported transit delay (breakdown/weather/traffic). Arrival window extended by 60 mins."
    },
    "STANDBY_OVERDUE": {
        "titleEn": "Standby Lane (Buffer Overdue)",
        "titleHi": "प्रतीक्षा लेन • समय सीमा समाप्त",
        "step": 1.5,
        "icon": "⚠️",
        "color": "amber",
        "description": "Vehicle arrived outside the scheduled window buffer. Held in standby lane awaiting supervisor admission."
    },
    "GATE_SCANNED": {
        "titleEn": "Gate Verified & Yard Entry",
        "titleHi": "गेट सत्यापन पूर्ण • यार्ड में प्रवेश",
        "step": 2,
        "icon": "🚜",
        "color": "teal",
        "description": "Tractor-trolley scanned at gate terminal; admitted into procurement yard."
    },
    "ASSAY_TESTING": {
        "titleEn": "Quality & Moisture Assay",
        "titleHi": "गुणवत्ता एवं नमी परीक्षण (Assay Lab)",
        "step": 3,
        "icon": "🧪",
        "color": "purple",
        "description": "Sample collected and tested for moisture content & FAQ grade standards."
    },
    "REJECTED_QUALITY": {
        "titleEn": "Quality Assay Rejected",
        "titleHi": "गुणवत्ता परीक्षण में अस्वीकृत",
        "step": 3.5,
        "icon": "❌",
        "color": "rose",
        "description": "Moisture above FCI maximum tolerance threshold (>12.0%). Intake halted."
    },
    "GROSS_WEIGHED": {
        "titleEn": "Gross Weighing (Loaded Vehicle)",
        "titleHi": "सकल इलेक्ट्रॉनिक तौल (Gross Weighment)",
        "step": 4,
        "icon": "⚖️",
        "color": "indigo",
        "description": "Loaded vehicle weighed on calibrated electronic weighbridge (Scale 1)."
    },
    "WEIGHBRIDGE_IN": {
        "titleEn": "Gross Weighing (Loaded Vehicle)",
        "titleHi": "सकल इलेक्ट्रॉनिक तौल (Gross Weighment)",
        "step": 4,
        "icon": "⚖️",
        "color": "indigo",
        "description": "Alias for GROSS_WEIGHED."
    },
    "UNLOADING_BAY": {
        "titleEn": "Unloading Bay / Shed",
        "titleHi": "अनलोडिंग शेड • बोरी खालीकरण",
        "step": 5,
        "icon": "📦",
        "color": "amber",
        "description": "Grain unloaded at designated warehouse bay/platform."
    },
    "TARE_WEIGHED": {
        "titleEn": "Tare Weighing (Empty Vehicle)",
        "titleHi": "खाली वाहन तौल (Tare Weighment)",
        "step": 6,
        "icon": "🌾",
        "color": "emerald",
        "description": "Empty vehicle re-weighed on weighbridge (Scale 2) to compute net grain weight."
    },
    "WEIGHBRIDGE_OUT": {
        "titleEn": "Tare Weighing (Empty Vehicle)",
        "titleHi": "खाली वाहन तौल (Tare Weighment)",
        "step": 6,
        "icon": "🌾",
        "color": "emerald",
        "description": "Alias for TARE_WEIGHED."
    },
    "J_FORM_ISSUED": {
        "titleEn": "Statutory e-J-Form Generated",
        "titleHi": "डिजिटल जे-फॉर्म जारी (MSP खरीद रसीद)",
        "step": 7,
        "icon": "📜",
        "color": "cyan",
        "description": "Legally-binding APMC Form 'J' procurement receipt issued with MSP and dockage breakdown."
    },
    "DBT_DISPATCHED": {
        "titleEn": "DBT Payment Dispatched",
        "titleHi": "प्रत्यक्ष लाभ अंतरण (DBT भुगतान पूर्ण)",
        "step": 8,
        "icon": "🏦",
        "color": "green",
        "description": "MSP proceeds transferred directly to farmer Aadhaar-linked bank account via PFMS/DBT."
    },
    "CANCELLED": {
        "titleEn": "Booking Cancelled",
        "titleHi": "बुकिंग रद्द (Cancelled)",
        "step": 0,
        "icon": "🚫",
        "color": "slate",
        "description": "Booking was cancelled prior to yard intake."
    }
}

ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "BOOKED": ["TRANSIT_DELAYED", "GATE_SCANNED", "STANDBY_OVERDUE", "CANCELLED"],
    "TRANSIT_DELAYED": ["GATE_SCANNED", "STANDBY_OVERDUE", "CANCELLED"],
    "STANDBY_OVERDUE": ["GATE_SCANNED", "CANCELLED"],
    "GATE_SCANNED": ["ASSAY_TESTING", "CANCELLED"],
    "ASSAY_TESTING": ["GROSS_WEIGHED", "WEIGHBRIDGE_IN", "REJECTED_QUALITY", "CANCELLED"],
    "REJECTED_QUALITY": ["ASSAY_TESTING", "CANCELLED"],
    "GROSS_WEIGHED": ["UNLOADING_BAY", "WEIGHBRIDGE_OUT", "CANCELLED"],
    "WEIGHBRIDGE_IN": ["UNLOADING_BAY", "GROSS_WEIGHED", "WEIGHBRIDGE_OUT", "CANCELLED"],
    "UNLOADING_BAY": ["TARE_WEIGHED", "WEIGHBRIDGE_OUT", "CANCELLED"],
    "TARE_WEIGHED": ["J_FORM_ISSUED", "DBT_DISPATCHED"],
    "WEIGHBRIDGE_OUT": ["TARE_WEIGHED", "J_FORM_ISSUED", "DBT_DISPATCHED"],
    "J_FORM_ISSUED": ["DBT_DISPATCHED"],
    "DBT_DISPATCHED": [],
    "CANCELLED": []
}

STAGE_LATENCY_BENCHMARKS = {
    "GATE_SCANNED": {"expectedMinutes": 4.0, "thresholdWarning": 8.0},
    "ASSAY_TESTING": {"expectedMinutes": 15.0, "thresholdWarning": 25.0},
    "GROSS_WEIGHED": {"expectedMinutes": 6.0, "thresholdWarning": 12.0},
    "WEIGHBRIDGE_IN": {"expectedMinutes": 6.0, "thresholdWarning": 12.0},
    "UNLOADING_BAY": {"expectedMinutes": 12.0, "thresholdWarning": 20.0},
    "TARE_WEIGHED": {"expectedMinutes": 5.0, "thresholdWarning": 10.0},
    "WEIGHBRIDGE_OUT": {"expectedMinutes": 5.0, "thresholdWarning": 10.0},
    "J_FORM_ISSUED": {"expectedMinutes": 2.0, "thresholdWarning": 5.0},
    "DBT_DISPATCHED": {"expectedMinutes": 10.0, "thresholdWarning": 30.0}
}

def normalize_stage_name(stage: str) -> str:
    """Normalize legacy and alias stage names."""
    s = (stage or "BOOKED").strip().upper()
    return s

def validate_state_transition(current_stage: str, next_stage: str) -> Tuple[bool, str]:
    """
    Strict validation of deterministic state machine pipeline.
    Rejects illegal stage hops.
    """
    current = normalize_stage_name(current_stage)
    target = normalize_stage_name(next_stage)

    if target not in STAGE_METADATA:
        return False, f"Unknown target stage '{target}'."

    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        return False, (
            f"Invalid transition from '{current}' to '{target}'. "
            f"Permitted next stages are: {', '.join(allowed) if allowed else 'None (Terminal Stage)'}."
        )

    return True, "Valid transition."

def transition_token_state(
    booking: Booking,
    next_stage: str,
    metadata: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """
    Execute deterministic state machine transition on Booking and QueueEntry.
    Maintains append-only stage history audit trail with timestamps.
    Enforces statutory J-Form generation and tare/gross weight integrity checks.
    """
    from backend.j_form_service import generate_statutory_j_form

    curr = normalize_stage_name(booking.current_stage)
    target = normalize_stage_name(next_stage)

    is_valid, msg = validate_state_transition(curr, target)
    if not is_valid:
        raise ValueError(msg)

    # 1. Weight Integrity Rule: Check Tare vs Gross
    if target in ["TARE_WEIGHED", "WEIGHBRIDGE_OUT"]:
        gross_kg = booking.gross_weight_kg or (booking.gross_weight * 1000.0 if booking.gross_weight else 0.0)
        gross_input = metadata.get("grossWeightKg") or metadata.get("gross_weight_kg") or metadata.get("grossWeight") or metadata.get("gross_weight")
        if gross_kg <= 0.0 and gross_input:
            gross_kg = float(gross_input)
            booking.gross_weight_kg = gross_kg
            booking.gross_weight = round(gross_kg / 1000.0, 3)

        if gross_kg <= 0.0:
            raise ValueError("INVALID_WEIGHT_STATE: Gross weight must be recorded (> 0 kg) before empty tare weighment.")

        # Extract tare weight from metadata (support camelCase and snake_case)
        tare_input = metadata.get("tareWeightKg") or metadata.get("tare_weight_kg") or metadata.get("tareWeight") or metadata.get("tare_weight")
        if tare_input is not None:
            tare_val = float(tare_input)
            # If in MT (< 50) convert to kg
            tare_kg = tare_val * 1000.0 if (tare_val < 50.0 and gross_kg > 500.0) else tare_val
            if tare_kg >= gross_kg:
                raise ValueError(
                    f"ANOMALY_WEIGHT_REVERSED: Tare weight ({tare_kg} kg) must be strictly less than gross weight ({gross_kg} kg)."
                )

    # 2. Gate Clearance Rule: DBT requires statutory e-J-Form
    if target == "DBT_DISPATCHED":
        if not booking.j_form_id and not metadata.get("jFormId"):
            raise ValueError("J_FORM_REQUIRED: Cannot dispatch DBT settlement without an issued statutory e-J-Form.")

    now_iso = datetime.utcnow().isoformat()

    # Parse existing stage history
    try:
        history = json.loads(booking.stage_history or "[]")
    except Exception:
        history = []

    history_entry = {
        "fromStage": curr,
        "toStage": target,
        "timestamp": now_iso,
        "operator": metadata.get("operator", "OPERATOR-MAIN"),
        "notes": metadata.get("notes", ""),
        "metadata": metadata
    }
    history.append(history_entry)

    # Update Booking record
    booking.current_stage = target
    booking.stage_history = json.dumps(history)

    # Apply stage-specific logic
    if target == "TRANSIT_DELAYED":
        booking.status = "रास्ते में देरी (+60 मिनट ग्रेस)"
        reason = metadata.get("reason", "ROAD_BLOCKAGE")
        booking.transit_delay_reason = reason
        booking.transit_delay_reported_at = datetime.utcnow()
        if booking.arrival_window_end:
            booking.arrival_window_end = booking.arrival_window_end + timedelta(minutes=60)

    elif target == "STANDBY_OVERDUE":
        booking.arrival_status = "standby_overdue"
        booking.status = "समय-सीमा समाप्त (Standby Lane)"

    elif target == "GATE_SCANNED":
        booking.arrival_status = "checked_in"
        queue_type = metadata.get("queueType", "NORMAL")
        if queue_type == "STANDBY" or curr == "STANDBY_OVERDUE":
            booking.status = "गेट प्रवेश (स्टैंडबाई अनुमति)"
        else:
            booking.status = "गेट सत्यापन पूर्ण (Gate Scanned)"
        if metadata.get("assignedBay"):
            booking.assigned_bay = metadata.get("assignedBay")

    elif target == "ASSAY_TESTING":
        booking.status = "गुणवत्ता जांच जारी (Assay Testing)"
        if metadata.get("assignedBay"):
            booking.assigned_bay = metadata.get("assignedBay")
        if metadata.get("moisture"):
            booking.assay_moisture = float(metadata.get("moisture"))
        if metadata.get("grade"):
            booking.assay_quality_grade = metadata.get("grade")

    elif target == "REJECTED_QUALITY":
        booking.status = "अस्वीकृत (Quality Assay Failed)"
        if metadata.get("moisture"):
            booking.assay_moisture = float(metadata.get("moisture"))

    elif target in ["GROSS_WEIGHED", "WEIGHBRIDGE_IN"]:
        booking.status = "सकल भार प्रक्रिया पूर्ण (Gross Weighed)"
        wb_id = metadata.get("grossWeighbridgeId") or metadata.get("assignedWeighbridge", "WB-SCALE-01")
        booking.gross_weighbridge_id = wb_id
        booking.assigned_weighbridge = wb_id
        gross_in = metadata.get("grossWeightKg") or metadata.get("grossWeight")
        if gross_in:
            val = float(gross_in)
            gross_kg = val * 1000.0 if val < 50.0 else val
            booking.gross_weight_kg = gross_kg
            booking.gross_weight = round(gross_kg / 1000.0, 3)

    elif target == "UNLOADING_BAY":
        booking.status = "अनलोडिंग जारी (Unloading Bay)"
        bay_id = metadata.get("unloadingBayId") or metadata.get("assignedBay", "SHED-BAY-A1")
        booking.unloading_bay_id = bay_id
        booking.assigned_bay = bay_id

    elif target in ["TARE_WEIGHED", "WEIGHBRIDGE_OUT"]:
        booking.status = "खाली भार प्रक्रिया पूर्ण (Tare Weighed)"
        wb_id = metadata.get("tareWeighbridgeId") or "WB-SCALE-02"
        booking.tare_weighbridge_id = wb_id
        tare_in = metadata.get("tareWeightKg") or metadata.get("tareWeight")
        if tare_in:
            val = float(tare_in)
            tare_kg = val * 1000.0 if val < 50.0 else val
            booking.tare_weight_kg = tare_kg
            booking.tare_weight = round(tare_kg / 1000.0, 3)
            gross_kg = booking.gross_weight_kg or (booking.gross_weight * 1000.0)
            booking.net_weight_kg = max(0.0, round(gross_kg - tare_kg, 2))
            booking.net_weight = round(booking.net_weight_kg / 1000.0, 3)

        # Auto-issue statutory J-Form if not yet generated
        generate_statutory_j_form(booking, db, operator_id=metadata.get("operator", "OPERATOR-MAIN"))

    elif target == "J_FORM_ISSUED":
        booking.status = "डिजिटल जे-फॉर्म जारी (e-JForm Issued)"
        generate_statutory_j_form(booking, db, operator_id=metadata.get("operator", "OPERATOR-MAIN"))

    elif target == "DBT_DISPATCHED":
        booking.status = "खरीद एवं भुगतान पूर्ण (DBT Dispatched)"
        booking.dbt_status = "SUCCESS"
        booking.dbt_ref_no = metadata.get("dbtRefNo", booking.dbt_ref_no or f"PFMS-SBI-{now_iso[-6:]}")

    # Synchronize live QueueEntry
    queue_entry = db.query(QueueEntry).filter(QueueEntry.booking_id == booking.id).first()
    if queue_entry:
        queue_entry.current_stage = target
        queue_entry.status = booking.status
        queue_entry.assigned_bay = booking.assigned_bay
        queue_entry.assigned_weighbridge = booking.assigned_weighbridge
        queue_entry.gross_weight = booking.gross_weight
        queue_entry.tare_weight = booking.tare_weight
        queue_entry.net_weight = booking.net_weight
        queue_entry.gross_weight_kg = booking.gross_weight_kg
        queue_entry.tare_weight_kg = booking.tare_weight_kg
        queue_entry.net_weight_kg = booking.net_weight_kg
        queue_entry.unloading_bay_id = booking.unloading_bay_id
        queue_entry.gross_weighbridge_id = booking.gross_weighbridge_id
        queue_entry.tare_weighbridge_id = booking.tare_weighbridge_id
        queue_entry.j_form_id = booking.j_form_id
        queue_entry.assay_moisture = booking.assay_moisture
        queue_entry.dbt_status = booking.dbt_status
        if metadata.get("queueType"):
            queue_entry.queue_type = metadata.get("queueType")

        if target == "DBT_DISPATCHED":
            queue_entry.queue_position = 0
            queue_entry.total_vehicles_ahead = 0
            queue_entry.estimated_wait_minutes = 0

    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "bookingId": booking.id,
        "tokenId": booking.token_id,
        "previousStage": curr,
        "currentStage": target,
        "jFormId": booking.j_form_id,
        "stageInfo": STAGE_METADATA.get(target, {}),
        "history": history
    }
