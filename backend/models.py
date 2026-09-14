import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'farmer', 'operator', 'district_admin', 'super_admin'
    center_id = Column(String, nullable=True)
    center_name = Column(String, nullable=True)
    district = Column(String, nullable=True)
    state = Column(String, nullable=True)
    village = Column(String, nullable=True)
    land_area = Column(Float, nullable=True)
    crop = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    ifsc = Column(String, nullable=True)
    profile_completed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Center(Base):
    __tablename__ = "centers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False, index=True)
    state = Column(String, nullable=False, index=True)
    address = Column(String, nullable=False)
    operating_hours = Column(String, default="09:00 AM – 05:00 PM")
    commodity = Column(String, nullable=False)
    accepted_crops = Column(Text, default="[]")  # JSON string
    facilities = Column(Text, default="[]")      # JSON string
    daily_capacity_mt = Column(Integer, default=500)
    slot_duration = Column(String, default="60 मिनट")
    current_queue_vehicles = Column(Integer, default=0)
    estimated_wait_minutes = Column(Integer, default=0)
    load_status = Column(String, default="low")  # 'low', 'medium', 'high'
    active_weighbridges = Column(Integer, default=2)
    avg_weighing_rate_per_hr = Column(Integer, default=10)
    buffer_adjustment = Column(Integer, default=-2)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Commodity(Base):
    __tablename__ = "commodities"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    name_english = Column(String, nullable=True)
    hindi_name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    season = Column(String, nullable=False)
    unit = Column(String, default="QTL")
    demo_rate = Column(Float, nullable=False)
    msp_per_quintal = Column(Float, nullable=False)
    moisture_max_percent = Column(Float, nullable=False)

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, index=True)          # e.g. KS-BOOK-1011
    token_id = Column(String, unique=True, index=True)          # e.g. KS-TKN-1011
    farmer_id = Column(String, nullable=True, index=True)
    farmer_name = Column(String, nullable=False)
    farmer_phone = Column(String, nullable=True)
    center_id = Column(String, ForeignKey("centers.id"), index=True)
    center_name = Column(String, nullable=False)
    district = Column(String, nullable=True)
    commodity = Column(String, nullable=False)
    booking_date = Column(String, nullable=False)
    time_slot = Column(String, nullable=False)
    quantity_qtl = Column(Float, default=40.0)
    vehicle_number = Column(String, default="HR-05-AB-1234")
    status = Column(String, default="CONFIRMED")                # 'CONFIRMED', 'ARRIVED', 'CHECKED_IN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'
    arrival_status = Column(String, default="pending")          # 'pending', 'arrived', 'checked_in'
    queue_position = Column(Integer, default=0)

    # State-Machine & Anti-Hoarding Fields
    current_stage = Column(String, default="BOOKED")            # 'BOOKED', 'TRANSIT_DELAYED', 'STANDBY_OVERDUE', 'GATE_SCANNED', 'ASSAY_TESTING', 'REJECTED_QUALITY', 'GROSS_WEIGHED', 'UNLOADING_BAY', 'TARE_WEIGHED', 'J_FORM_ISSUED', 'DBT_DISPATCHED', 'CANCELLED'
    arrival_window_start = Column(DateTime, nullable=True)
    arrival_window_end = Column(DateTime, nullable=True)
    digital_sig = Column(String, nullable=True)
    assigned_bay = Column(String, nullable=True)
    assigned_weighbridge = Column(String, nullable=True)
    gross_weight = Column(Float, default=0.0)
    tare_weight = Column(Float, default=0.0)
    net_weight = Column(Float, default=0.0)

    # Physical Two-Stage Weighment & Unloading Cycle
    gross_weight_kg = Column(Float, default=0.0)
    tare_weight_kg = Column(Float, default=0.0)
    net_weight_kg = Column(Float, default=0.0)
    unloading_bay_id = Column(String, nullable=True)
    gross_weighbridge_id = Column(String, nullable=True)
    tare_weighbridge_id = Column(String, nullable=True)

    # Statutory e-J-Form (MSP Receipt)
    j_form_id = Column(String, nullable=True)
    j_form_data = Column(Text, nullable=True)                  # JSON representation of legal J-Form

    # Transit Delay Grace Protocol
    transit_delay_reason = Column(String, nullable=True)
    transit_delay_reported_at = Column(DateTime, nullable=True)

    assay_moisture = Column(Float, nullable=True)
    assay_quality_grade = Column(String, nullable=True)
    dbt_ref_no = Column(String, nullable=True)
    dbt_status = Column(String, default="PENDING")
    stage_history = Column(Text, default="[]")                  # JSON array of stage transitions with timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String, index=True, nullable=False)
    token_id = Column(String, index=True, nullable=False)
    center_id = Column(String, index=True, nullable=False)
    farmer_name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    commodity = Column(String, nullable=False)
    time_slot = Column(String, nullable=False)
    queue_position = Column(Integer, default=1)
    total_vehicles_ahead = Column(Integer, default=0)
    estimated_wait_minutes = Column(Integer, default=15)
    arrival_status = Column(String, default="checked_in")
    status = Column(String, default="कतार में प्रतीक्षा (Waiting in Queue)")

    # State-Machine Sync & Physical Mandi Cycle
    current_stage = Column(String, default="BOOKED")
    queue_type = Column(String, default="NORMAL")               # 'NORMAL' or 'STANDBY'
    assigned_bay = Column(String, nullable=True)
    assigned_weighbridge = Column(String, nullable=True)
    gross_weight = Column(Float, default=0.0)
    tare_weight = Column(Float, default=0.0)
    net_weight = Column(Float, default=0.0)
    gross_weight_kg = Column(Float, default=0.0)
    tare_weight_kg = Column(Float, default=0.0)
    net_weight_kg = Column(Float, default=0.0)
    unloading_bay_id = Column(String, nullable=True)
    gross_weighbridge_id = Column(String, nullable=True)
    tare_weighbridge_id = Column(String, nullable=True)
    j_form_id = Column(String, nullable=True)
    assay_moisture = Column(Float, nullable=True)
    dbt_status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class JFormRecord(Base):
    __tablename__ = "j_form_records"

    id = Column(String, primary_key=True, index=True)           # e.g. JF-HR-2026-10492
    booking_id = Column(String, index=True, nullable=False)
    token_id = Column(String, index=True, nullable=False)
    farmer_name = Column(String, nullable=False)
    farmer_phone = Column(String, nullable=True)
    farmer_aadhaar_masked = Column(String, nullable=False)
    center_id = Column(String, index=True, nullable=False)
    center_name = Column(String, nullable=False)
    district = Column(String, nullable=False)
    commodity = Column(String, nullable=False)
    crop_variety = Column(String, default="FAQ Grade-1")
    gross_weight_kg = Column(Float, default=0.0)
    tare_weight_kg = Column(Float, default=0.0)
    net_weight_kg = Column(Float, default=0.0)
    net_quintals = Column(Float, default=0.0)
    moisture_percent = Column(Float, default=10.0)
    quality_grade = Column(String, default="Grade A")
    msp_rate_per_qtl = Column(Float, default=2425.0)
    gross_amount = Column(Float, default=0.0)
    deductions_amount = Column(Float, default=0.0)
    net_amount = Column(Float, default=0.0)
    bank_account_masked = Column(String, default="XXXXXX4819")
    bank_ifsc = Column(String, default="PUNB0123400")
    bank_name = Column(String, default="Punjab National Bank")
    dbt_status = Column(String, default="INITIATED")
    dbt_transaction_id = Column(String, nullable=True)
    digital_signature = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ProcurementRecord(Base):
    __tablename__ = "procurement_records"

    id = Column(String, primary_key=True, index=True)           # e.g. KSP-RCP-1005
    booking_id = Column(String, index=True, nullable=False)
    token_id = Column(String, index=True, nullable=False)
    farmer_name = Column(String, nullable=False)
    farmer_phone = Column(String, nullable=True)
    center_id = Column(String, index=True, nullable=False)
    center_name = Column(String, nullable=False)
    district = Column(String, nullable=False)
    commodity = Column(String, nullable=False)
    date = Column(String, nullable=False)
    gross_weight = Column(Float, default=0.0)
    tare_weight = Column(Float, default=0.0)
    net_weight = Column(Float, default=0.0)
    moisture_percent = Column(Float, default=10.0)
    rate_per_qtl = Column(Float, default=2425.0)
    total_amount = Column(Float, default=0.0)
    payment_status = Column(String, default="PAID")
    receipt_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(String, primary_key=True, index=True)           # e.g. CMP-2026-001
    complainant_name = Column(String, nullable=False)
    complainant_phone = Column(String, nullable=True)
    category = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    center_id = Column(String, nullable=True, index=True)
    center_name = Column(String, nullable=True)
    booking_id = Column(String, nullable=True)
    level = Column(String, default="OPERATOR")                  # 'OPERATOR', 'DISTRICT_ADMIN', 'SUPER_ADMIN'
    priority = Column(String, default="MEDIUM")                 # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    status = Column(String, default="OPEN")                     # 'OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'ESCALATED', 'CLOSED'
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class SoilTestRecord(Base):
    __tablename__ = "soil_tests"

    id = Column(String, primary_key=True, index=True)           # e.g. ST-2026-101
    sample_id = Column(String, unique=True, index=True)         # e.g. SMP-HR-7821
    farmer_id = Column(String, index=True, nullable=False)
    farmer_name = Column(String, nullable=False)
    farmer_phone = Column(String, index=True, nullable=False)
    district = Column(String, nullable=False)
    state = Column(String, default="Haryana")
    village = Column(String, nullable=True)
    center_id = Column(String, nullable=True, index=True)
    center_name = Column(String, nullable=True)
    booking_date = Column(String, nullable=False)
    time_slot = Column(String, nullable=False)
    crop_planned = Column(String, nullable=False, default="Wheat (Grade A)")
    land_area_acres = Column(Float, default=5.0)
    soil_type = Column(String, default="Alluvial Loam (दोमट मिट्टी)")
    status = Column(String, default="COMPLETED")                # 'BOOKED', 'SAMPLE_COLLECTED', 'IN_TESTING', 'COMPLETED'
    
    # Soil Health Card Parameters
    ph_level = Column(Float, default=7.2)
    ec_level = Column(Float, default=0.45)                      # dS/m
    organic_carbon_percent = Column(Float, default=0.52)        # %
    nitrogen_kg_ha = Column(Float, default=240.0)               # Available N kg/ha
    phosphorus_kg_ha = Column(Float, default=16.5)              # Available P kg/ha
    potassium_kg_ha = Column(Float, default=210.0)              # Available K kg/ha
    zinc_ppm = Column(Float, default=0.55)                      # Zinc ppm
    sulphur_ppm = Column(Float, default=8.2)                    # Sulphur ppm
    
    # Health Assessment & Advisories
    health_status = Column(String, default="MODERATE")          # 'EXCELLENT', 'GOOD', 'MODERATE', 'POOR'
    advisory_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    tested_at = Column(DateTime, default=datetime.datetime.utcnow)

class CircuitBreakerEvent(Base):
    __tablename__ = "circuit_breaker_events"

    id = Column(String, primary_key=True, index=True)          # e.g. CB-2026-001
    center_id = Column(String, ForeignKey("centers.id"), index=True)
    center_name = Column(String, nullable=False)
    is_halted = Column(Boolean, default=True)
    reason = Column(String, nullable=False)                    # 'RAIN', 'MACHINE_BREAKDOWN', 'GODOWN_SATURATED', 'OTHER'
    reason_label = Column(String, nullable=False)              # e.g. 'अचानक भारी बारिश (Sudden Heavy Rain)'
    affected_slots = Column(Text, default="[]")                # JSON array of slot strings
    defer_hours = Column(Integer, default=2)
    sms_count_sent = Column(Integer, default=0)
    operator_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

