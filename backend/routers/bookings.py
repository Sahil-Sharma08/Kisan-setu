import json
import random
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Booking, Center, QueueEntry
from backend.schemas import BookingCreateRequest, BookingResponse, TokenResponse
from backend.qr_security import create_signed_token_payload, generate_digital_signature

router = APIRouter(tags=["Slot Bookings & Digital Tokens"])

def _format_booking(b: Booking) -> dict:
    # Build signed QR payload dictionary
    signed_payload = create_signed_token_payload(
        token_id=b.token_id,
        farmer_id=b.farmer_id or "USR-FARMER-01",
        farmer_name=b.farmer_name,
        vehicle_no=b.vehicle_number,
        center_id=b.center_id,
        commodity=b.commodity,
        quantity_qtl=b.quantity_qtl,
        booking_date=b.booking_date,
        time_slot=b.time_slot
    )
    
    return {
        "bookingId": b.id,
        "id": b.id,
        "tokenId": b.token_id,
        "farmerId": b.farmer_id,
        "farmerName": b.farmer_name,
        "farmerPhone": b.farmer_phone,
        "phone": b.farmer_phone,
        "centerId": b.center_id,
        "centerName": b.center_name,
        "district": b.district,
        "commodity": b.commodity,
        "bookingDate": b.booking_date,
        "timeSlot": b.time_slot,
        "quantityQuintals": b.quantity_qtl,
        "vehicleNumber": b.vehicle_number,
        "status": b.status,
        "arrivalStatus": b.arrival_status,
        "queuePosition": b.queue_position,
        "currentStage": getattr(b, "current_stage", "BOOKED") or "BOOKED",
        "digitalSig": b.digital_sig or signed_payload.get("digitalSig"),
        "timeWindow": signed_payload.get("timeWindow"),
        "signedPayload": signed_payload,
        "qrPayload": json.dumps(signed_payload),
        "jFormId": getattr(b, "j_form_id", None),
        "jFormData": getattr(b, "j_form_data", None),
        "grossWeightKg": getattr(b, "gross_weight_kg", 0.0),
        "tareWeightKg": getattr(b, "tare_weight_kg", 0.0),
        "netWeightKg": getattr(b, "net_weight_kg", 0.0),
        "unloadingBayId": getattr(b, "unloading_bay_id", None),
        "transitDelayReason": getattr(b, "transit_delay_reason", None)
    }

@router.post("/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreateRequest, db: Session = Depends(get_db)):
    """
    Schedule guaranteed procurement arrival slot and generate tamper-proof Digital Token
    """
    center = db.query(Center).filter(Center.id == payload.center_id.strip().upper()).first()
    if not center:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Center {payload.center_id} not found.")

    rand_suffix = random.randint(1000, 9999)
    booking_id = f"KS-BOOK-{rand_suffix}"
    token_id = f"KS-TKN-{rand_suffix}"

    # Calculate queue position
    active_in_queue = db.query(QueueEntry).filter(QueueEntry.center_id == center.id).count()
    queue_pos = active_in_queue + 1

    signed_payload = create_signed_token_payload(
        token_id=token_id,
        farmer_id="USR-FARMER-01",
        farmer_name=payload.farmer_name or "Demo Farmer",
        vehicle_no=payload.vehicle_number,
        center_id=center.id,
        commodity=payload.commodity,
        quantity_qtl=payload.quantity_qtl,
        booking_date=payload.booking_date,
        time_slot=payload.time_slot
    )

    booking = Booking(
        id=booking_id,
        token_id=token_id,
        farmer_id="USR-FARMER-01",
        farmer_name=payload.farmer_name or "Demo Farmer",
        farmer_phone=payload.farmer_phone or "+91 98765 43210",
        center_id=center.id,
        center_name=center.name,
        district=center.district,
        commodity=payload.commodity,
        booking_date=payload.booking_date,
        time_slot=payload.time_slot,
        quantity_qtl=payload.quantity_qtl,
        vehicle_number=payload.vehicle_number,
        status="CONFIRMED",
        arrival_status="pending",
        queue_position=queue_pos,
        current_stage="BOOKED",
        digital_sig=signed_payload.get("digitalSig")
    )
    db.add(booking)

    # Automatically add to live queue monitor
    queue_entry = QueueEntry(
        booking_id=booking_id,
        token_id=token_id,
        center_id=center.id,
        farmer_name=booking.farmer_name,
        phone=booking.farmer_phone,
        commodity=booking.commodity,
        time_slot=booking.time_slot,
        queue_position=queue_pos,
        total_vehicles_ahead=max(0, queue_pos - 1),
        estimated_wait_minutes=queue_pos * 5,
        arrival_status="pending",
        status="कन्फर्म (Slot Scheduled)"
    )
    db.add(queue_entry)

    # Increment center vehicle counter
    center.current_queue_vehicles += 1
    db.commit()
    db.refresh(booking)

    return {
        "success": True,
        "message": "Slot booking successfully confirmed! Digital token generated.",
        "data": _format_booking(booking)
    }

@router.get("/bookings")
def list_bookings(
    center_id: Optional[str] = None,
    farmer_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List bookings with optional filters
    """
    query = db.query(Booking)
    if center_id:
        query = query.filter(Booking.center_id == center_id.strip().upper())
    if farmer_id:
        query = query.filter(Booking.farmer_id == farmer_id.strip())
    if status_filter:
        query = query.filter(Booking.status.ilike(status_filter.strip()))

    bookings = query.order_by(Booking.created_at.desc()).all()
    return {
        "success": True,
        "total": len(bookings),
        "data": [_format_booking(b) for b in bookings]
    }

@router.get("/bookings/{booking_id}")
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    """
    Get booking details by ID or Token ID
    """
    clean_id = booking_id.strip().upper()
    booking = db.query(Booking).filter((Booking.id == clean_id) | (Booking.token_id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking {booking_id} not found.")

    return {
        "success": True,
        "data": _format_booking(booking)
    }

@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: str, db: Session = Depends(get_db)):
    """
    Cancel an active slot booking
    """
    clean_id = booking_id.strip().upper()
    booking = db.query(Booking).filter(Booking.id == clean_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Booking {booking_id} not found.")

    booking.status = "CANCELLED"
    booking.arrival_status = "cancelled"

    # Remove from active queue
    queue_item = db.query(QueueEntry).filter(QueueEntry.booking_id == clean_id).first()
    if queue_item:
        db.delete(queue_item)

    db.commit()
    return {
        "success": True,
        "message": f"Booking {booking_id} has been cancelled."
    }

@router.get("/tokens/{token_id}")
def get_token_details(token_id: str, db: Session = Depends(get_db)):
    """
    Retrieve live token details and QR code payload for gate verification
    """
    clean_id = token_id.strip().upper()
    booking = db.query(Booking).filter((Booking.token_id == clean_id) | (Booking.id == clean_id)).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Token {token_id} not found.")

    queue_entry = db.query(QueueEntry).filter(QueueEntry.token_id == booking.token_id).first()
    queue_pos = queue_entry.queue_position if queue_entry else booking.queue_position
    est_wait = queue_entry.estimated_wait_minutes if queue_entry else 15

    qr_payload = f"KISANSETU|TOKEN:{booking.token_id}|BOOKING:{booking.id}|CENTER:{booking.center_id}|CROP:{booking.commodity}|VEHICLE:{booking.vehicle_number}"

    return {
        "success": True,
        "data": {
            "tokenId": booking.token_id,
            "bookingId": booking.id,
            "farmerName": booking.farmer_name,
            "farmerPhone": booking.farmer_phone,
            "centerId": booking.center_id,
            "centerName": booking.center_name,
            "district": booking.district,
            "commodity": booking.commodity,
            "bookingDate": booking.booking_date,
            "timeSlot": booking.time_slot,
            "vehicleNumber": booking.vehicle_number,
            "status": booking.status,
            "arrivalStatus": booking.arrival_status,
            "queuePosition": queue_pos,
            "estimatedWaitMinutes": est_wait,
            "qrPayload": qr_payload
        }
    }
