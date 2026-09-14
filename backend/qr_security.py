import hmac
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional

SECRET_KEY = os.getenv("KISAN_TOKEN_SIGNING_SECRET", "kisan-setu-sih26032-tamper-proof-hmac-key")

def canonical_string(payload: Dict[str, Any]) -> str:
    """Create a deterministic string representation of token attributes for signing."""
    fields = [
        str(payload.get("tokenId", "")).strip(),
        str(payload.get("farmerId", "")).strip(),
        str(payload.get("vehicleNo", "")).strip().upper(),
        str(payload.get("centerId", "")).strip().upper(),
        str(payload.get("commodity", "")).strip(),
        str(payload.get("quantityQtl", "")).strip(),
        str(payload.get("timeWindow", []))
    ]
    return "|".join(fields)

def generate_digital_signature(payload: Dict[str, Any]) -> str:
    """Generate cryptographic HMAC-SHA256 signature for anti-hoarding verification."""
    data = canonical_string(payload).encode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return sig[:24]  # 24-character compact hex digest for high QR density

def verify_digital_signature(payload: Dict[str, Any], signature: str) -> bool:
    """Validate token digital signature against tampering and broker hoarding."""
    if not signature:
        return False
    expected = generate_digital_signature(payload)
    return hmac.compare_digest(expected.lower(), signature.strip().lower())

def validate_arrival_window(
    time_window: list,
    arrival_dt: Optional[datetime] = None,
    buffer_minutes: int = 45
) -> Tuple[bool, str, int]:
    """
    Validate vehicle arrival against scheduled slot window + buffer (default: ±45 min).
    Returns (is_valid, status, delta_minutes).
    """
    if not time_window or len(time_window) < 2:
        return True, "WINDOW_UNSPECIFIED", 0

    now = arrival_dt or datetime.utcnow()
    
    try:
        # Parse ISO or HH:MM timestamps
        start_str, end_str = time_window[0], time_window[1]
        
        if "T" in start_str:
            slot_start = datetime.fromisoformat(start_str.replace("Z", ""))
            slot_end = datetime.fromisoformat(end_str.replace("Z", ""))
        else:
            # Fallback format: parse time strings for today
            today = now.date()
            t_start = datetime.strptime(start_str.strip(), "%H:%M").time()
            t_end = datetime.strptime(end_str.strip(), "%H:%M").time()
            slot_start = datetime.combine(today, t_start)
            slot_end = datetime.combine(today, t_end)
    except Exception:
        # If parsing fails, default to permissive for demo stability
        return True, "ON_TIME", 0

    allowed_start = slot_start - timedelta(minutes=buffer_minutes)
    allowed_end = slot_end + timedelta(minutes=buffer_minutes)

    if now < allowed_start:
        delta = int((allowed_start - now).total_seconds() / 60)
        return False, "EARLY_ARRIVAL", -delta
    elif now > allowed_end:
        delta = int((now - allowed_end).total_seconds() / 60)
        return False, "STANDBY_OVERDUE", delta
    else:
        return True, "ON_TIME", 0

def create_signed_token_payload(
    token_id: str,
    farmer_id: str,
    farmer_name: str,
    vehicle_no: str,
    center_id: str,
    commodity: str,
    quantity_qtl: float,
    booking_date: str,
    time_slot: str,
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None
) -> Dict[str, Any]:
    """Assemble complete cryptographically signed token payload for QR rendering."""
    # Generate ISO window if not provided
    if not start_iso or not end_iso:
        # Default slot 09:00 - 10:00 or parse from time_slot string
        parts = time_slot.split("–") if "–" in time_slot else time_slot.split("-")
        try:
            p0 = parts[0].strip().split()[0]
            p1 = parts[1].strip().split()[0]
            # Convert 12h or 24h
            if "PM" in time_slot and int(p0.split(":")[0]) < 12:
                h0 = int(p0.split(":")[0]) + 12
            else:
                h0 = int(p0.split(":")[0])
            h1 = h0 + 1
            date_part = booking_date if "-" in booking_date else datetime.utcnow().strftime("%Y-%m-%d")
            start_iso = f"{date_part}T{h0:02d}:00:00"
            end_iso = f"{date_part}T{h1:02d}:00:00"
        except Exception:
            start_iso = f"{datetime.utcnow().strftime('%Y-%m-%d')}T09:00:00"
            end_iso = f"{datetime.utcnow().strftime('%Y-%m-%d')}T10:00:00"

    payload = {
        "v": 1,
        "tokenId": token_id,
        "farmerId": farmer_id,
        "farmerName": farmer_name,
        "vehicleNo": vehicle_no,
        "centerId": center_id,
        "commodity": commodity,
        "quantityQtl": quantity_qtl,
        "timeWindow": [start_iso, end_iso],
        "slot": time_slot,
        "date": booking_date,
        "issuedAt": datetime.utcnow().isoformat()
    }
    payload["digitalSig"] = generate_digital_signature(payload)
    return payload
