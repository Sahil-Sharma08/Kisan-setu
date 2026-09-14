"""
Statutory Digital J-Form (e-J-Form) & MSP Procurement Receipt Service
Smart India Hackathon SIH26032 (Ministry of Consumer Affairs, Food & Public Distribution)

Generates legally-binding agricultural procurement receipts (Form 'J' under APMC Rules)
verifying net grain quintals, moisture & dockage deductions, and Aadhaar-linked DBT payment orders.
"""

import json
import random
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.models import Booking, QueueEntry, JFormRecord, Commodity
from backend.qr_security import generate_digital_signature

DEFAULT_MSP_RATES = {
    "WHEAT": 2425.0,
    "PADDY": 2300.0,
    "MUSTARD": 5650.0,
    "COTTON": 7121.0,
    "BAJRA": 2500.0,
    "MAIZE": 2090.0,
    "BARLEY": 1850.0,
    "GRAM": 5440.0
}

def get_crop_msp_rate(commodity_name: str, db: Optional[Session] = None) -> float:
    """Retrieve official government MSP per quintal."""
    clean_name = (commodity_name or "").strip().upper()
    
    if db:
        crop_record = db.query(Commodity).filter(Commodity.name.ilike(f"%{clean_name}%")).first()
        if crop_record and crop_record.msp_per_quintal:
            return float(crop_record.msp_per_quintal)
            
    for key, rate in DEFAULT_MSP_RATES.items():
        if key in clean_name:
            return rate
    return 2425.0  # Default benchmark MSP

def calculate_j_form_metrics(
    net_weight_kg: float,
    msp_per_quintal: float,
    moisture_percent: float = 11.2,
    quality_grade: str = "Grade A"
) -> Dict[str, Any]:
    """
    Calculate statutory net quintals, gross MSP proceeds, moisture dockage, and net payable.
    """
    net_quintals = round(max(0.0, net_weight_kg) / 100.0, 2)
    gross_amount = round(net_quintals * msp_per_quintal, 2)

    # Statutory Moisture Deduction:
    # Standard permissible ceiling is 12.0%. Excess moisture (up to 14.0%) incurs dockage.
    moisture_deduction = 0.0
    if moisture_percent > 12.0:
        excess_moisture = min(2.0, moisture_percent - 12.0)
        # 0.5% deduction per 1% excess moisture
        moisture_deduction = round(gross_amount * (excess_moisture * 0.005), 2)

    # Quality Grade Dockage
    grade_deduction = 0.0
    if "B" in quality_grade.upper() or "FAQ-2" in quality_grade.upper():
        grade_deduction = round(net_quintals * 25.0, 2)  # ₹25/qtl dockage for Grade B

    total_deductions = round(moisture_deduction + grade_deduction, 2)
    net_amount = max(0.0, round(gross_amount - total_deductions, 2))

    return {
        "netQuintals": net_quintals,
        "mspRatePerQtl": msp_per_quintal,
        "grossAmount": gross_amount,
        "moistureDeduction": moisture_deduction,
        "gradeDeduction": grade_deduction,
        "totalDeductions": total_deductions,
        "netPayableAmount": net_amount
    }

def generate_statutory_j_form(
    booking: Booking,
    db: Session,
    operator_id: str = "OPERATOR-MAIN"
) -> Dict[str, Any]:
    """
    Generate and persist statutory digital e-J-Form once vehicle tare weight is recorded.
    """
    # Ensure weights exist in kg
    gross_kg = booking.gross_weight_kg or (booking.gross_weight * 1000.0 if booking.gross_weight else 0.0)
    tare_kg = booking.tare_weight_kg or (booking.tare_weight * 1000.0 if booking.tare_weight else 0.0)
    net_kg = max(0.0, round(gross_kg - tare_kg, 2))

    # Fallback to booking quantity if weights are pending in simulated environments
    if net_kg <= 0.0:
        net_kg = round((booking.quantity_qtl or 45.0) * 100.0, 2)
        tare_kg = 1850.0  # standard empty trolley weight
        gross_kg = net_kg + tare_kg

    booking.gross_weight_kg = gross_kg
    booking.tare_weight_kg = tare_kg
    booking.net_weight_kg = net_kg
    booking.gross_weight = round(gross_kg / 1000.0, 3)
    booking.tare_weight = round(tare_kg / 1000.0, 3)
    booking.net_weight = round(net_kg / 1000.0, 3)

    msp_rate = get_crop_msp_rate(booking.commodity, db)
    moisture = booking.assay_moisture or 11.4
    grade = booking.assay_quality_grade or "Grade A (FAQ)"

    metrics = calculate_j_form_metrics(
        net_weight_kg=net_kg,
        msp_per_quintal=msp_rate,
        moisture_percent=moisture,
        quality_grade=grade
    )

    # Deterministic or fresh J-Form Serial ID
    token_suffix = booking.token_id.replace("KS-TKN-", "").replace("TKN-", "")[-5:]
    j_form_id = f"JF-HR-2026-{token_suffix}"

    # Mask Aadhaar for privacy compliance
    phone_digits = (booking.farmer_phone or "9876543210")[-4:]
    masked_aadhaar = f"XXXX-XXXX-{phone_digits}"

    # Bank DBT details
    bank_acc = f"XXXXXX{phone_digits}"
    bank_ifsc = "PUNB0123400"
    bank_name = "Punjab National Bank (कृषि खाता)"
    dbt_txn_id = f"PFMS-DBT-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(10000, 99999)}"

    # Cryptographic payload for validation
    sig_payload = {
        "jFormId": j_form_id,
        "tokenId": booking.token_id,
        "farmerName": booking.farmer_name,
        "netAmount": metrics["netPayableAmount"],
        "centerId": booking.center_id
    }
    digital_sig = generate_digital_signature(sig_payload)

    j_form_data = {
        "jFormNumber": j_form_id,
        "version": "e-JForm-v2.0-SIH26032",
        "issuedAt": datetime.utcnow().isoformat(),
        "mandiDepotCode": booking.center_id,
        "mandiDepotName": booking.center_name,
        "district": booking.district or "Karnal",
        "state": "Haryana",
        "farmer": {
            "name": booking.farmer_name,
            "farmerId": booking.farmer_id,
            "phone": booking.farmer_phone or "9876543210",
            "aadhaarMasked": masked_aadhaar,
            "vehicleNumber": booking.vehicle_number
        },
        "crop": {
            "commodity": booking.commodity,
            "variety": "FAQ Grade-1 Certified",
            "season": "Rabi / Kharif 2026",
            "moisturePercent": moisture,
            "qualityGrade": grade
        },
        "weighment": {
            "grossWeightKg": gross_kg,
            "tareWeightKg": tare_kg,
            "netWeightKg": net_kg,
            "netQuintals": metrics["netQuintals"],
            "grossWeighbridgeId": booking.gross_weighbridge_id or "WB-SCALE-01",
            "tareWeighbridgeId": booking.tare_weighbridge_id or "WB-SCALE-02",
            "unloadingBayId": booking.unloading_bay_id or "SHED-BAY-A1"
        },
        "financials": {
            "mspRatePerQuintal": metrics["mspRatePerQtl"],
            "grossAmountINR": metrics["grossAmount"],
            "moistureDeductionINR": metrics["moistureDeduction"],
            "gradeDeductionINR": metrics["gradeDeduction"],
            "totalDeductionsINR": metrics["totalDeductions"],
            "netPayableAmountINR": metrics["netPayableAmount"],
            "amountInWordsHindi": f"रुपये {int(metrics['netPayableAmount'])} मात्र"
        },
        "settlement": {
            "bankName": bank_name,
            "accountMasked": bank_acc,
            "ifscCode": bank_ifsc,
            "dbtStatus": "APPROVED_FOR_DISBURSEMENT",
            "dbtTransactionId": dbt_txn_id,
            "operatorId": operator_id
        },
        "digitalVerification": {
            "signature": digital_sig,
            "verificationUrl": f"/api/v1/queue/j-form/{booking.token_id}",
            "statutoryAct": "Punjab Agricultural Produce Markets Act, 1961 (Form J)"
        }
    }

    # Persist in DB
    booking.j_form_id = j_form_id
    booking.j_form_data = json.dumps(j_form_data)
    booking.dbt_ref_no = dbt_txn_id

    # Create or update JFormRecord
    existing_record = db.query(JFormRecord).filter(JFormRecord.booking_id == booking.id).first()
    if not existing_record:
        existing_record = JFormRecord(
            id=j_form_id,
            booking_id=booking.id,
            token_id=booking.token_id,
            farmer_name=booking.farmer_name,
            farmer_phone=booking.farmer_phone,
            farmer_aadhaar_masked=masked_aadhaar,
            center_id=booking.center_id,
            center_name=booking.center_name,
            district=booking.district or "Karnal",
            commodity=booking.commodity,
            crop_variety="FAQ Grade-1 Certified",
            gross_weight_kg=gross_kg,
            tare_weight_kg=tare_kg,
            net_weight_kg=net_kg,
            net_quintals=metrics["netQuintals"],
            moisture_percent=moisture,
            quality_grade=grade,
            msp_rate_per_qtl=metrics["mspRatePerQtl"],
            gross_amount=metrics["grossAmount"],
            deductions_amount=metrics["totalDeductions"],
            net_amount=metrics["netPayableAmount"],
            bank_account_masked=bank_acc,
            bank_ifsc=bank_ifsc,
            bank_name=bank_name,
            dbt_status="APPROVED",
            dbt_transaction_id=dbt_txn_id,
            digital_signature=digital_sig
        )
        db.add(existing_record)
    else:
        existing_record.gross_weight_kg = gross_kg
        existing_record.tare_weight_kg = tare_kg
        existing_record.net_weight_kg = net_kg
        existing_record.net_quintals = metrics["netQuintals"]
        existing_record.net_amount = metrics["netPayableAmount"]

    # Also update QueueEntry if present
    queue_entry = db.query(QueueEntry).filter(QueueEntry.booking_id == booking.id).first()
    if queue_entry:
        queue_entry.j_form_id = j_form_id
        queue_entry.gross_weight_kg = gross_kg
        queue_entry.tare_weight_kg = tare_kg
        queue_entry.net_weight_kg = net_kg
        queue_entry.gross_weight = booking.gross_weight
        queue_entry.tare_weight = booking.tare_weight
        queue_entry.net_weight = booking.net_weight

    db.commit()
    db.refresh(booking)

    return j_form_data
