import unittest
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base, Center, Booking, QueueEntry, CircuitBreakerEvent, JFormRecord
from backend.throughput_engine import (
    calculate_hourly_capacity,
    get_capacity_tier,
    get_center_throughput_schedule,
    find_low_load_alternative_centers
)
from backend.state_machine import (
    validate_state_transition,
    transition_token_state,
    STAGE_METADATA,
    ALLOWED_TRANSITIONS
)
from backend.qr_security import (
    canonical_string,
    generate_digital_signature,
    verify_digital_signature,
    validate_arrival_window,
    create_signed_token_payload
)
from backend.j_form_service import (
    calculate_j_form_metrics,
    generate_statutory_j_form,
    get_crop_msp_rate
)

class TestThroughputEngine(unittest.TestCase):
    """Unit tests for Dynamic Mandi Throughput Engine"""

    def test_capacity_formula(self):
        # 2 weighbridges * 10/hr + (-2 buffer) = 18
        cap = calculate_hourly_capacity(active_weighbridges=2, avg_weighing_rate_per_hr=10, buffer_adjustment=-2)
        self.assertEqual(cap, 18)

        # 4 weighbridges * 12/hr + (-4 buffer) = 44
        cap2 = calculate_hourly_capacity(active_weighbridges=4, avg_weighing_rate_per_hr=12, buffer_adjustment=-4)
        self.assertEqual(cap2, 44)

        # Minimum floor test: should not go below 5
        cap_low = calculate_hourly_capacity(active_weighbridges=1, avg_weighing_rate_per_hr=2, buffer_adjustment=-5)
        self.assertGreaterEqual(cap_low, 5)

    def test_capacity_tiers(self):
        # Green tier (< 60%)
        tier_green = get_capacity_tier(45.0)
        self.assertEqual(tier_green["tier"], "GREEN")
        self.assertFalse(tier_green["isLocked"])

        # Amber tier (60% - 85%)
        tier_amber = get_capacity_tier(72.5)
        self.assertEqual(tier_amber["tier"], "AMBER")
        self.assertFalse(tier_amber["isLocked"])

        # Red tier (> 85%)
        tier_red = get_capacity_tier(88.0)
        self.assertEqual(tier_red["tier"], "RED")
        self.assertTrue(tier_red["isLocked"])

        tier_red_boundary = get_capacity_tier(85.1)
        self.assertEqual(tier_red_boundary["tier"], "RED")
        self.assertTrue(tier_red_boundary["isLocked"])

    def test_center_throughput_schedule(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        center = Center(
            id="CTR-TEST-01",
            name="Test Mandi",
            district="Karnal",
            state="Haryana",
            address="Near Railway Station, Karnal",
            commodity="Wheat (गेहूं)",
            daily_capacity_mt=600,
            active_weighbridges=3,
            avg_weighing_rate_per_hr=10,
            buffer_adjustment=-2
        )
        db.add(center)
        db.commit()

        schedule = get_center_throughput_schedule(center, "2026-09-15", db)
        self.assertEqual(schedule["centerId"], "CTR-TEST-01")
        # 3 * 10 - 2 = 28 capacity/hr
        self.assertEqual(schedule["hardwareMetrics"]["effectiveHourlyCapacity"], 28)
        self.assertEqual(len(schedule["slots"]), 8)
        for slot in schedule["slots"]:
            self.assertIn("tier", slot)
            self.assertIn("availableCapacity", slot)
            self.assertIn("hourlyCapacity", slot)

        db.close()

    def test_find_low_load_alternatives(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        c1 = Center(id="CTR-KARNAL-01", name="Karnal Main", district="Karnal", state="Haryana", address="GT Road Karnal", commodity="Wheat (गेहूं)", load_status="high", current_queue_vehicles=25)
        c2 = Center(id="CTR-TARAORI-02", name="Taraori Yard", district="Karnal", state="Haryana", address="Taraori Anaj Mandi", commodity="Wheat (गेहूं)", load_status="low", current_queue_vehicles=3)
        c3 = Center(id="CTR-GHARAUNDA-03", name="Gharaunda Depo", district="Karnal", state="Haryana", address="Gharaunda Station Rd", commodity="Wheat (गेहूं)", load_status="medium", current_queue_vehicles=8)
        db.add_all([c1, c2, c3])
        db.commit()

        alternatives = find_low_load_alternative_centers("CTR-KARNAL-01", db)
        self.assertGreaterEqual(len(alternatives), 1)
        self.assertTrue(all(alt["centerId"] != "CTR-KARNAL-01" for alt in alternatives))
        # First alternative should be low load
        self.assertIn(alternatives[0]["centerId"], ["CTR-TARAORI-02", "CTR-GHARAUNDA-03"])

        db.close()


class TestStateMachine(unittest.TestCase):
    """Unit tests for Deterministic Mandi State Machine"""

    def test_valid_lifecycle_transitions(self):
        # 1. BOOKED -> GATE_SCANNED
        ok, _ = validate_state_transition("BOOKED", "GATE_SCANNED")
        self.assertTrue(ok)

        # 2. GATE_SCANNED -> ASSAY_TESTING
        ok, _ = validate_state_transition("GATE_SCANNED", "ASSAY_TESTING")
        self.assertTrue(ok)

        # 3. ASSAY_TESTING -> WEIGHBRIDGE_IN
        ok, _ = validate_state_transition("ASSAY_TESTING", "WEIGHBRIDGE_IN")
        self.assertTrue(ok)

        # 4. WEIGHBRIDGE_IN -> WEIGHBRIDGE_OUT
        ok, _ = validate_state_transition("WEIGHBRIDGE_IN", "WEIGHBRIDGE_OUT")
        self.assertTrue(ok)

        # 5. WEIGHBRIDGE_OUT -> DBT_DISPATCHED
        ok, _ = validate_state_transition("WEIGHBRIDGE_OUT", "DBT_DISPATCHED")
        self.assertTrue(ok)

    def test_illegal_transitions_rejected(self):
        # Cannot skip stages: BOOKED -> WEIGHBRIDGE_OUT
        ok, msg = validate_state_transition("BOOKED", "WEIGHBRIDGE_OUT")
        self.assertFalse(ok)
        self.assertIn("Invalid transition", msg)

        # Cannot skip assay: GATE_SCANNED -> DBT_DISPATCHED
        ok, msg = validate_state_transition("GATE_SCANNED", "DBT_DISPATCHED")
        self.assertFalse(ok)

        # Cannot reverse from terminal state: DBT_DISPATCHED -> BOOKED
        ok, msg = validate_state_transition("DBT_DISPATCHED", "BOOKED")
        self.assertFalse(ok)

    def test_standby_and_quality_rejection(self):
        # Buffer overdue standby can be admitted after gate check
        ok, _ = validate_state_transition("BOOKED", "STANDBY_OVERDUE")
        self.assertTrue(ok)
        ok, _ = validate_state_transition("STANDBY_OVERDUE", "GATE_SCANNED")
        self.assertTrue(ok)

        # Moisture rejection during assay testing
        ok, _ = validate_state_transition("ASSAY_TESTING", "REJECTED_QUALITY")
        self.assertTrue(ok)

        # Retest after drying/aeration
        ok, _ = validate_state_transition("REJECTED_QUALITY", "ASSAY_TESTING")
        self.assertTrue(ok)

    def test_transition_token_state_audit_trail(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        center = Center(
            id="CTR-TEST-01",
            name="Test Mandi",
            district="Karnal",
            state="Haryana",
            address="Mandi Road",
            commodity="Wheat (गेहूं)",
            daily_capacity_mt=500
        )
        db.add(center)

        booking = Booking(
            id="BKG-TEST-100",
            token_id="KS-TKN-100",
            farmer_id="FARM-01",
            farmer_name="Sukhwinder Singh",
            farmer_phone="9876543210",
            center_id="CTR-TEST-01",
            center_name="Test Mandi",
            district="Karnal",
            commodity="Wheat",
            quantity_qtl=50.0,
            vehicle_number="HR-05-AA-1122",
            booking_date="2026-09-15",
            time_slot="09:00 AM – 10:00 AM",
            current_stage="BOOKED",
            stage_history="[]"
        )
        db.add(booking)
        db.commit()

        # Perform transition: BOOKED -> GATE_SCANNED
        res = transition_token_state(
            booking=booking,
            next_stage="GATE_SCANNED",
            metadata={"operator": "OP-RAMESH", "notes": "Tractor trolley arrived on schedule"},
            db=db
        )

        self.assertEqual(booking.current_stage, "GATE_SCANNED")
        self.assertEqual(res["currentStage"], "GATE_SCANNED")

        # Verify audit history
        history = json.loads(booking.stage_history)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["fromStage"], "BOOKED")
        self.assertEqual(history[0]["toStage"], "GATE_SCANNED")
        self.assertEqual(history[0]["operator"], "OP-RAMESH")

        # Verify invalid transition raises ValueError
        with self.assertRaises(ValueError):
            transition_token_state(
                booking=booking,
                next_stage="DBT_DISPATCHED",  # Invalid jump
                metadata={},
                db=db
            )

        db.close()

    def test_two_stage_weighment_lifecycle_and_aliases(self):
        # Physical 8-Stage Cycle:
        # [BOOKED] -> [GATE_SCANNED] -> [ASSAY_TESTING] -> [GROSS_WEIGHED]
        # -> [UNLOADING_BAY] -> [TARE_WEIGHED] -> [J_FORM_ISSUED] -> [DBT_DISPATCHED]
        stages = [
            ("BOOKED", "GATE_SCANNED"),
            ("GATE_SCANNED", "ASSAY_TESTING"),
            ("ASSAY_TESTING", "GROSS_WEIGHED"),
            ("GROSS_WEIGHED", "UNLOADING_BAY"),
            ("UNLOADING_BAY", "TARE_WEIGHED"),
            ("TARE_WEIGHED", "J_FORM_ISSUED"),
            ("J_FORM_ISSUED", "DBT_DISPATCHED")
        ]
        for src, dst in stages:
            ok, msg = validate_state_transition(src, dst)
            self.assertTrue(ok, f"Transition {src} -> {dst} failed: {msg}")

        # Test Backward Compatible Aliases
        ok, _ = validate_state_transition("ASSAY_TESTING", "WEIGHBRIDGE_IN")
        self.assertTrue(ok)
        ok, _ = validate_state_transition("WEIGHBRIDGE_IN", "UNLOADING_BAY")
        self.assertTrue(ok)
        ok, _ = validate_state_transition("UNLOADING_BAY", "WEIGHBRIDGE_OUT")
        self.assertTrue(ok)

    def test_reversed_weight_anomaly(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        booking = Booking(
            id="BKG-ANOMALY-01",
            token_id="KS-TKN-ANOMALY",
            farmer_id="FARM-02",
            farmer_name="Rameshwar Dayal",
            farmer_phone="9876543211",
            center_id="CTR-KARNAL-01",
            center_name="Karnal Mandi",
            district="Karnal",
            commodity="Wheat",
            quantity_qtl=50.0,
            vehicle_number="HR-05-ZZ-9999",
            booking_date="2026-09-15",
            time_slot="09:00 AM – 10:00 AM",
            current_stage="UNLOADING_BAY",
            gross_weight_kg=20000.0,
            stage_history="[]"
        )
        db.add(booking)
        db.commit()

        # Tare weight (25000 kg) > Gross weight (20000 kg) is physically impossible
        with self.assertRaises(ValueError) as ctx:
            transition_token_state(
                booking=booking,
                next_stage="TARE_WEIGHED",
                metadata={"tare_weight_kg": 25000.0, "gross_weight_kg": 20000.0},
                db=db
            )
        self.assertIn("ANOMALY_WEIGHT_REVERSED", str(ctx.exception))
        db.close()

    def test_unloading_bay_sequence_enforcement(self):
        # Skipping UNLOADING_BAY directly from GROSS_WEIGHED to TARE_WEIGHED is disallowed
        ok, msg = validate_state_transition("GROSS_WEIGHED", "TARE_WEIGHED")
        self.assertFalse(ok)
        self.assertIn("Invalid transition", msg)

    def test_jform_gating_before_dbt_dispatched(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        booking = Booking(
            id="BKG-NO-JFORM",
            token_id="KS-TKN-NOJF",
            farmer_id="FARM-03",
            farmer_name="Kuldeep Singh",
            center_id="CTR-KARNAL-01",
            center_name="Karnal Mandi",
            commodity="Wheat",
            booking_date="2026-09-15",
            time_slot="09:00 AM – 10:00 AM",
            current_stage="J_FORM_ISSUED",
            j_form_id=None,  # No J-Form generated
            stage_history="[]"
        )
        db.add(booking)
        db.commit()

        # Cannot dispatch DBT if legal J-Form receipt was not generated
        with self.assertRaises(ValueError) as ctx:
            transition_token_state(
                booking=booking,
                next_stage="DBT_DISPATCHED",
                metadata={},
                db=db
            )
        self.assertIn("J_FORM_REQUIRED", str(ctx.exception))
        db.close()

    def test_transit_delay_and_standby_transitions(self):
        # Farmer reporting transit delay
        ok, _ = validate_state_transition("BOOKED", "TRANSIT_DELAYED")
        self.assertTrue(ok)
        # Transit delayed vehicle arriving and admitted at gate
        ok, _ = validate_state_transition("TRANSIT_DELAYED", "GATE_SCANNED")
        self.assertTrue(ok)

        # Standby overdue admitted by supervisor override
        ok, _ = validate_state_transition("STANDBY_OVERDUE", "GATE_SCANNED")
        self.assertTrue(ok)


class TestJFormService(unittest.TestCase):
    """Unit tests for Statutory Digital J-Form (e-JForm) & MSP Procurement Receipt Engine"""

    def test_metric_calculations_standard(self):
        # 5,000 kg net grain = 50.00 Quintals
        # MSP = ₹2,425.00/Qtl
        # Gross = 50 * 2425 = ₹1,21,250.00
        # Moisture 11.2% (under 12.0% ceiling) -> 0 dockage
        metrics = calculate_j_form_metrics(
            net_weight_kg=5000.0,
            msp_per_quintal=2425.0,
            moisture_percent=11.2,
            quality_grade="Grade A (FAQ)"
        )
        self.assertEqual(metrics["netQuintals"], 50.0)
        self.assertEqual(metrics["grossAmount"], 121250.0)
        self.assertEqual(metrics["moistureDeduction"], 0.0)
        self.assertEqual(metrics["totalDeductions"], 0.0)
        self.assertEqual(metrics["netPayableAmount"], 121250.0)

    def test_metric_calculations_moisture_dockage(self):
        # 5,000 kg net grain = 50.00 Quintals @ ₹2,425.00 = ₹1,21,250.00
        # Moisture 13.0% (1.0% excess over 12.0%)
        # Dockage = 1.0% excess * 0.5% = 0.5% of gross
        # 121,250 * 0.005 = ₹606.25
        # Net Payable = 121,250 - 606.25 = ₹1,20,643.75
        metrics = calculate_j_form_metrics(
            net_weight_kg=5000.0,
            msp_per_quintal=2425.0,
            moisture_percent=13.0,
            quality_grade="Grade A"
        )
        self.assertEqual(metrics["netQuintals"], 50.0)
        self.assertEqual(metrics["grossAmount"], 121250.0)
        self.assertEqual(metrics["moistureDeduction"], 606.25)
        self.assertEqual(metrics["totalDeductions"], 606.25)
        self.assertEqual(metrics["netPayableAmount"], 120643.75)

    def test_j_form_db_generation_and_persistence(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        center = Center(
            id="CTR-KARNAL-01",
            name="Karnal Mandi",
            district="Karnal",
            state="Haryana",
            address="GT Road",
            commodity="Wheat (गेहूं)"
        )
        db.add(center)

        booking = Booking(
            id="BKG-JF-TEST-01",
            token_id="KS-TKN-90210",
            farmer_id="FARM-99",
            farmer_name="Harbhajan Singh",
            farmer_phone="9876543299",
            center_id="CTR-KARNAL-01",
            center_name="Karnal Mandi",
            district="Karnal",
            commodity="Wheat",
            quantity_qtl=50.0,
            vehicle_number="HR-05-AA-5544",
            booking_date="2026-09-15",
            time_slot="09:00 AM – 10:00 AM",
            current_stage="UNLOADING_BAY",
            gross_weight_kg=35000.0,
            tare_weight_kg=15000.0,
            assay_moisture=11.5,
            stage_history="[]"
        )
        db.add(booking)
        db.commit()

        # Generate statutory J-Form
        jf_data = generate_statutory_j_form(booking, db, operator_id="OP-WEIGH-02")
        self.assertIsNotNone(jf_data)
        self.assertEqual(jf_data["jFormNumber"], "JF-HR-2026-90210")
        self.assertEqual(booking.net_weight_kg, 20000.0)
        self.assertEqual(jf_data["weighment"]["netQuintals"], 200.0)
        self.assertIn("signature", jf_data["digitalVerification"])

        # Check DB JFormRecord persistence
        record = db.query(JFormRecord).filter(JFormRecord.id == "JF-HR-2026-90210").first()
        self.assertIsNotNone(record)
        self.assertEqual(record.net_weight_kg, 20000.0)
        self.assertEqual(record.farmer_name, "Harbhajan Singh")
        self.assertTrue(len(record.digital_signature) > 10)

        db.close()


class TestQRSecurity(unittest.TestCase):
    """Unit tests for HMAC Digital Signatures and Arrival Window Buffer Validation"""

    def setUp(self):
        self.sample_payload = {
            "tokenId": "TKN-20260915-001",
            "farmerId": "FARMER-9988",
            "vehicleNo": "HR05-AK-9921",
            "centerId": "CTR-KARNAL-01",
            "commodity": "Wheat (Sharbati)",
            "quantityQtl": 75.0,
            "timeWindow": ["2026-09-15T09:00:00", "2026-09-15T10:00:00"]
        }

    def test_signature_generation_and_verification(self):
        sig = generate_digital_signature(self.sample_payload)
        self.assertTrue(isinstance(sig, str))
        self.assertEqual(len(sig), 24)

        # Verification succeeds on identical payload
        self.assertTrue(verify_digital_signature(self.sample_payload, sig))

    def test_anti_forgery_tamper_detection(self):
        sig = generate_digital_signature(self.sample_payload)

        # Tamper with vehicle number
        tampered_payload = dict(self.sample_payload)
        tampered_payload["vehicleNo"] = "HR05-XX-0000"
        self.assertFalse(verify_digital_signature(tampered_payload, sig))

        # Tamper with commodity
        tampered_commodity = dict(self.sample_payload)
        tampered_commodity["commodity"] = "Basmati Rice"
        self.assertFalse(verify_digital_signature(tampered_commodity, sig))

        # Tamper with quantity
        tampered_qty = dict(self.sample_payload)
        tampered_qty["quantityQtl"] = 250.0
        self.assertFalse(verify_digital_signature(tampered_qty, sig))

    def test_arrival_window_validation(self):
        # Slot: 10:00 to 11:00. Buffer: ±45 min (Allowed: 09:15 to 11:45)
        slot_window = ["2026-09-15T10:00:00", "2026-09-15T11:00:00"]

        # Case 1: Exactly on time at 10:15
        on_time = datetime.fromisoformat("2026-09-15T10:15:00")
        valid, status, delta = validate_arrival_window(slot_window, on_time, buffer_minutes=45)
        self.assertTrue(valid)
        self.assertEqual(status, "ON_TIME")

        # Case 2: Early arrival within 45m buffer at 09:30 (Allowed!)
        early_buffered = datetime.fromisoformat("2026-09-15T09:30:00")
        valid, status, delta = validate_arrival_window(slot_window, early_buffered, buffer_minutes=45)
        self.assertTrue(valid)
        self.assertEqual(status, "ON_TIME")

        # Case 3: Too early at 08:30 (< 09:15 allowed start)
        too_early = datetime.fromisoformat("2026-09-15T08:30:00")
        valid, status, delta = validate_arrival_window(slot_window, too_early, buffer_minutes=45)
        self.assertFalse(valid)
        self.assertEqual(status, "EARLY_ARRIVAL")

        # Case 4: Standby overdue at 12:00 (> 11:45 allowed end)
        overdue = datetime.fromisoformat("2026-09-15T12:00:00")
        valid, status, delta = validate_arrival_window(slot_window, overdue, buffer_minutes=45)
        self.assertFalse(valid)
        self.assertEqual(status, "STANDBY_OVERDUE")
        self.assertEqual(delta, 15)  # 15 minutes overdue past buffer

    def test_create_signed_token_payload(self):
        payload = create_signed_token_payload(
            token_id="TKN-12345",
            farmer_id="FARM-44",
            farmer_name="Gurdev Singh",
            vehicle_no="HR08-B-1122",
            center_id="CTR-KARNAL-01",
            commodity="Paddy",
            quantity_qtl=60.0,
            booking_date="2026-09-15",
            time_slot="10:00 AM – 11:00 AM"
        )
        self.assertIn("digitalSig", payload)
        self.assertTrue(verify_digital_signature(payload, payload["digitalSig"]))
        self.assertEqual(len(payload["timeWindow"]), 2)

    def test_signature_empty_or_none(self):
        self.assertFalse(verify_digital_signature(self.sample_payload, ""))
        self.assertFalse(verify_digital_signature(self.sample_payload, None))


class TestCircuitBreaker(unittest.TestCase):
    """Unit tests for Superintendent Circuit Breaker functionality"""

    def test_circuit_breaker_event_lifecycle(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        center = Center(
            id="CTR-TEST-CB",
            name="Test Mandi CB",
            district="Karnal",
            state="Haryana",
            address="Karnal GT Rd",
            commodity="Wheat (गेहूं)"
        )
        db.add(center)
        db.commit()

        # Halt intake event
        cb_event = CircuitBreakerEvent(
            id="CB-TEST-001",
            center_id="CTR-TEST-CB",
            center_name="Test Mandi CB",
            is_halted=True,
            reason="RAIN",
            reason_label="अचानक भारी बारिश व जलभराव",
            defer_hours=3,
            sms_count_sent=45,
            operator_notes="Covering godown grain piles"
        )
        db.add(cb_event)
        db.commit()

        # Query active halted event
        active = (
            db.query(CircuitBreakerEvent)
            .filter(CircuitBreakerEvent.center_id == "CTR-TEST-CB")
            .filter(CircuitBreakerEvent.is_halted == True)
            .first()
        )
        self.assertIsNotNone(active)
        self.assertEqual(active.reason, "RAIN")
        self.assertEqual(active.defer_hours, 3)
        self.assertEqual(active.sms_count_sent, 45)

        # Resume intake event
        active.is_halted = False
        db.commit()

        active_resumed = (
            db.query(CircuitBreakerEvent)
            .filter(CircuitBreakerEvent.center_id == "CTR-TEST-CB")
            .filter(CircuitBreakerEvent.is_halted == True)
            .first()
        )
        self.assertIsNone(active_resumed)

        db.close()


if __name__ == "__main__":
    unittest.main()
