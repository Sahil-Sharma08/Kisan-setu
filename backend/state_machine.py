"""
Deterministic State Machine for Kisan-Setu Mandi Flow
Lifecycle:
  BOOKED -> GATE_SCANNED -> ASSAY_TESTING -> WEIGHBRIDGE_IN -> WEIGHBRIDGE_OUT -> DBT_DISPATCHED
Edge states:
  STANDBY_OVERDUE, REJECTED_QUALITY, CANCELLED
"""

import json
from datetime import datetime
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
    "STANDBY_OVERDUE": {
        "titleEn": "Standby / Buffer Overdue",
        "titleHi": "प्रतीक्षा / समय सीमा समाप्त",
        "step": 1.5,
        "icon": "⚠️",
        "color": "amber",
        "description": "Vehicle arrived outside the ±45 min slot window. Held in standby lane."
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
    "WEIGHBRIDGE_IN": {
        "titleEn": "Weighbridge In (Gross Weight)",
        "titleHi": "वेईब्रिज इन (सकल भार - Gross)",
        "step": 4,
        "icon": "⚖️",
        "color": "indigo",
        "description": "Loaded vehicle weighed on calibrated electronic weighbridge."
    },
    "WEIGHBRIDGE_OUT": {
        "titleEn": "Weighbridge Out (Net Tare)",
        "titleHi": "वेईब्रिज आउट (खाली वाहन - Net Tare)",
        "step": 5,
        "icon": "🌾",
        "color": "emerald",
        "description": "Unloaded vehicle re-weighed to determine net grain weight."
    },
    "DBT_DISPATCHED": {
        "titleEn": "DBT Payment Dispatched",
        "titleHi": "प्रत्यक्ष लाभ अंतरण (DBT भुगतान पूर्ण)",
        "step": 6,
        "icon": "🏦",
        "color": "green",
        "description": "MSP proceeds transferred directly to farmer Aadhaar-linked bank account."
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
    "BOOKED": ["GATE_SCANNED", "STANDBY_OVERDUE", "CANCELLED"],
    "STANDBY_OVERDUE": ["GATE_SCANNED", "CANCELLED"],
    "GATE_SCANNED": ["ASSAY_TESTING", "CANCELLED"],
    "ASSAY_TESTING": ["WEIGHBRIDGE_IN", "REJECTED_QUALITY", "CANCELLED"],
    "REJECTED_QUALITY": ["ASSAY_TESTING", "CANCELLED"],  # Allow re-test after aeration
    "WEIGHBRIDGE_IN": ["WEIGHBRIDGE_OUT"],
    "WEIGHBRIDGE_OUT": ["DBT_DISPATCHED"],
    "DBT_DISPATCHED": [],
    "CANCELLED": []
}

STAGE_LATENCY_BENCHMARKS = {
    "GATE_SCANNED": {"expectedMinutes": 4.0, "thresholdWarning": 8.0},
    "ASSAY_TESTING": {"expectedMinutes": 15.0, "thresholdWarning": 25.0},
    "WEIGHBRIDGE_IN": {"expectedMinutes": 6.0, "thresholdWarning": 12.0},
    "WEIGHBRIDGE_OUT": {"expectedMinutes": 5.0, "thresholdWarning": 10.0},
    "DBT_DISPATCHED": {"expectedMinutes": 10.0, "thresholdWarning": 30.0}
}

def validate_state_transition(current_stage: str, next_stage: str) -> Tuple[bool, str]:
    """
    Strict validation of deterministic state machine pipeline.
    Rejects illegal stage hops.
    """
    current = (current_stage or "BOOKED").strip().upper()
    target = next_stage.strip().upper()

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
    """
    curr = booking.current_stage or "BOOKED"
    is_valid, msg = validate_state_transition(curr, next_stage)
    if not is_valid:
        raise ValueError(msg)

    now_iso = datetime.utcnow().isoformat()
    target = next_stage.strip().upper()

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

    # Apply stage-specific updates
    if target == "GATE_SCANNED":
        booking.arrival_status = "checked_in"
        booking.status = "गेट सत्यापन पूर्ण (Gate Scanned)"
        if metadata.get("assignedBay"):
            booking.assigned_bay = metadata.get("assignedBay")

    elif target == "STANDBY_OVERDUE":
        booking.arrival_status = "standby_overdue"
        booking.status = "समय-सीमा समाप्त (Standby Overdue)"

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

    elif target == "WEIGHBRIDGE_IN":
        booking.status = "सकल भार प्रक्रिया (Weighbridge Gross In)"
        if metadata.get("assignedWeighbridge"):
            booking.assigned_weighbridge = metadata.get("assignedWeighbridge")
        if metadata.get("grossWeight"):
            booking.gross_weight = float(metadata.get("grossWeight"))

    elif target == "WEIGHBRIDGE_OUT":
        booking.status = "खाली भार प्रक्रिया (Weighbridge Net Tare)"
        if metadata.get("tareWeight"):
            booking.tare_weight = float(metadata.get("tareWeight"))
            booking.net_weight = max(0.0, round(booking.gross_weight - booking.tare_weight, 2))

    elif target == "DBT_DISPATCHED":
        booking.status = "खरीद एवं भुगतान पूर्ण (DBT Dispatched)"
        booking.dbt_status = "SUCCESS"
        booking.dbt_ref_no = metadata.get("dbtRefNo", f"DBT-SBI-{now_iso[-6:]}")

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
        queue_entry.assay_moisture = booking.assay_moisture
        queue_entry.dbt_status = booking.dbt_status

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
        "stageInfo": STAGE_METADATA.get(target, {}),
        "history": history
    }
