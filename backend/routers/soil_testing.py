import datetime
import random
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import SoilTestRecord, User, Center

router = APIRouter(prefix="/soil-testing", tags=["Soil Testing & Fertilizer Advisory"])

# -------------------------------------------------------------
# PYDANTIC SCHEMAS
# -------------------------------------------------------------
class SoilTestBookingRequest(BaseModel):
    farmer_id: Optional[str] = "USR-FARMER-01"
    farmer_name: str
    farmer_phone: str
    district: Optional[str] = "Karnal"
    state: Optional[str] = "Haryana"
    village: Optional[str] = "Kachhwa"
    center_id: Optional[str] = "CTR-HR-01"
    center_name: Optional[str] = "Karnal Central Procurement Center"
    lab_name: Optional[str] = None
    booking_date: str
    time_slot: Optional[str] = "10:00 AM – 11:30 AM"
    preferred_slot: Optional[str] = None
    crop_planned: Optional[str] = "Wheat (Grade A)"
    land_area_acres: Optional[float] = 5.0
    soil_type: Optional[str] = "Alluvial Loam (दोमट मिट्टी)"

class SoilTestUpdateRequest(BaseModel):
    record_id: Optional[str] = None
    sample_id: Optional[str] = None
    farmer_phone: Optional[str] = None
    ph: Optional[float] = None
    ph_level: Optional[float] = None
    ec_level: Optional[float] = 0.45
    electrical_conductivity: Optional[float] = None
    organic_carbon_percent: Optional[float] = 0.55
    nitrogen_kg_ha: Optional[float] = 280.0
    phosphorus_kg_ha: Optional[float] = 22.0
    potassium_kg_ha: Optional[float] = 210.0
    zinc_ppm: Optional[float] = 0.55
    sulphur_ppm: Optional[float] = 8.2
    health_status: Optional[str] = "MODERATE"
    status: Optional[str] = "COMPLETED"
    advisory_notes: Optional[str] = ""

# -------------------------------------------------------------
# CROP AGRONOMIC ADVISORY ENGINE
# -------------------------------------------------------------
CROP_ADVISORY_DB = {
    "wheat": {
        "crop_name": "Wheat (गेहूं)",
        "ideal_ph": "6.5 – 7.8",
        "fertilizers": [
            {
                "name": "DAP (Di-Ammonium Phosphate)",
                "per_acre_kg": 55,
                "application_timing": "बुआई के समय बेसल ड्रेसिंग (At Sowing - Basal)",
                "purpose": "जड़ों के प्रारंभिक विकास और कल्ले फूटने (Tillering) के लिए फास्फोरस आपूर्ति।"
            },
            {
                "name": "यूरिया (Urea - 46% N)",
                "per_acre_kg": 110,
                "application_timing": "दो बराबर किस्तों में (1st split at 21 days with 1st irrigation; 2nd split at 45 days)",
                "purpose": "पौधे के वानस्पतिक विकास और कल्लों की संख्या बढ़ाने हेतु।"
            },
            {
                "name": "MOP (Muriate of Potash)",
                "per_acre_kg": 20,
                "application_timing": "बुआई के समय बेसल (At Sowing)",
                "purpose": "तने को मजबूती देने, रोग प्रतिरोधक क्षमता और दाने के भराव (Grain weight) के लिए।"
            },
            {
                "name": "जिंक सल्फेट (Zinc Sulphate 33%)",
                "per_acre_kg": 6,
                "application_timing": "पहली सिंचाई पर यूरिया के साथ अलग से (With 1st Irrigation)",
                "purpose": "जिंक की कमी से होने वाले खैरा रोग व पत्तियों के पीलेपन से बचाव।"
            }
        ],
        "pesticides": [
            {
                "name": "प्रोपिकोनाजोल 25% EC (Tilt)",
                "dosage_per_acre": "200 ml (200 लीटर पानी में)",
                "target_pest": "पीला रतुआ (Yellow Rust) व करनाल बंट",
                "safety_interval": "लक्षण दिखते ही शाम के समय छिड़काव करें।"
            },
            {
                "name": "इमिडाक्लोप्रिड 17.8% SL (Confidor)",
                "dosage_per_acre": "60 ml (150 लीटर पानी में)",
                "target_pest": "माहू / चेपा (Aphids) कीट",
                "safety_interval": "दिसंबर-जनवरी में जब माहू की संख्या 5-10 कीट प्रति बाली हो।"
            }
        ],
        "when_not_to_use": [
            "❌ **फूल आने या बालियां निकलने (Flowering / Heading) के बाद यूरिया कभी न डालें**: इससे फसल गिर (Lodging) जाती है, दाना पतला रह जाता है और फफूंद रोग बढ़ते हैं।",
            "❌ **DAP और जिंक सल्फेट को कभी एक साथ मिलाकर न डालें**: दोनों के मिलने से जिंक फॉस्फेट बन जाता है जो पौधे को नहीं मिलता और खाद व्यर्थ हो जाती है।",
            "❌ **सूखी जमीन या तेज धूप / गर्म हवा में यूरिया न छिड़कें**: अमोनिया गैस बनकर उड़ जाती है और पत्तियों पर खाद जलने (Burn) के धब्बे पड़ जाते हैं।",
            "❌ **भारी वर्षा की संभावना होने पर नाइट्रोजन न डालें**: पानी के बहाव के साथ सारा खाद बह जाता है।"
        ]
    },
    "mustard": {
        "crop_name": "Mustard (सरसों / राया)",
        "ideal_ph": "6.0 – 7.5",
        "fertilizers": [
            {
                "name": "DAP (Di-Ammonium Phosphate)",
                "per_acre_kg": 35,
                "application_timing": "बुआई के समय (Basal at sowing)",
                "purpose": "जड़ों की मजबूती व शाखाएं बढ़ाने के लिए।"
            },
            {
                "name": "यूरिया (Urea)",
                "per_acre_kg": 50,
                "application_timing": "पहली सिंचाई (30-35 दिन) के समय",
                "purpose": "फूल आने से पहले शाखाओं के प्रसार हेतु।"
            },
            {
                "name": "बेंटोनाइट सल्फर 90% (Sulphur)",
                "per_acre_kg": 10,
                "application_timing": "बुआई के समय मिट्टी में मिलाएं",
                "purpose": "सरसों में तेल की मात्रा (Oil Content) 2-3% बढ़ाने हेतु अनिवार्य।"
            }
        ],
        "pesticides": [
            {
                "name": "डाइमेथोएट 30% EC (Rogor) या थायमेथोक्सम 25% WG",
                "dosage_per_acre": "250 ml या 40 ग्राम प्रति एकड़",
                "target_pest": "सरसों का चेपा / माहू (Mustard Aphid)",
                "safety_interval": "दिसंबर-जनवरी में बादल छाए रहने पर तुरंत छिड़काव करें।"
            },
            {
                "name": "मैंकोजेब 75% WP (Dithane M-45)",
                "dosage_per_acre": "600 ग्राम (200 लीटर पानी में)",
                "target_pest": "सफेद रतुआ (White Rust) व अल्टरनेरिया पत्ती धब्बा",
                "safety_interval": "सुबह ओस सूखने के बाद ही छिड़कें।"
            }
        ],
        "when_not_to_use": [
            "❌ **फूल आने की पूर्ण अवस्था (Full Flowering Stage) में यूरिया न डालें**: इससे माहू (चेपा) का प्रकोप कई गुना बढ़ जाता है और फलियां देर से पकती हैं।",
            "❌ **सल्फर का प्रयोग बिना मिट्टी जांच के अत्यधिक मात्रा में न करें**: अत्यधिक सल्फर से मृदा अम्लीय हो सकती है।",
            "❌ **ओस गीली पत्तियों पर दानेदार खाद न फेंकें**: यूरिया पत्तियों पर चिपक कर उन्हें झुलसा (Scorch) देता है।"
        ]
    },
    "paddy": {
        "crop_name": "Paddy (धान / चावल)",
        "ideal_ph": "6.0 – 7.2",
        "fertilizers": [
            {
                "name": "DAP",
                "per_acre_kg": 40,
                "application_timing": "अंतिम कद्दू (Puddling) के समय",
                "purpose": "प्रारंभिक जड़ स्थापना और फुटाव।"
            },
            {
                "name": "यूरिया (Urea)",
                "per_acre_kg": 90,
                "application_timing": "3 बराबर किस्तों में (रोपाई के 7 दिन, 21 दिन और 42 दिन बाद)",
                "purpose": "समान वानस्पतिक बढ़वार और कल्ले।"
            },
            {
                "name": "जिंक सल्फेट 33%",
                "per_acre_kg": 6,
                "application_timing": "रोपाई के 15-20 दिन बाद यूरिया के साथ",
                "purpose": "धान के खैरा रोग (Khaira Disease) की अचूक रोकथाम।"
            }
        ],
        "pesticides": [
            {
                "name": "कार्टाप हाइड्रोक्लोराइड 4G (Padan)",
                "dosage_per_acre": "7.5 kg प्रति एकड़ (खेत में पानी खड़ा हो)",
                "target_pest": "तना छेदक (Stem Borer) व पत्ता लपेटक (Leaf Folder)",
                "safety_interval": "रोपाई के 25-30 दिन बाद डालें।"
            },
            {
                "name": "स्ट्रेप्टोसाइक्लिन (6g) + कॉपर ऑक्सीक्लोराइड (500g)",
                "dosage_per_acre": "प्रति एकड़ 200 लीटर पानी में",
                "target_pest": "जीवाणु झुलसा (Bacterial Leaf Blight)",
                "safety_interval": "पत्तियों के किनारे पीले-सफेद पड़ने पर तुरंत प्रयोग करें।"
            }
        ],
        "when_not_to_use": [
            "❌ **खेत में 5 सेमी से अधिक गहरा पानी भरा होने पर यूरिया न डालें**: इससे पानी बहने या गहराई में रिसाव (Leaching) से खाद बर्बाद हो जाती है। पानी कम होने पर ही खाद डालें।",
            "❌ **खेत से पानी निकालते (Drainage) समय कभी खाद न डालें**: सारी खाद खेत से बाहर बह जाएगी।",
            "❌ **गोभ निकलने या बाली निकलने (Panicle Emergence) के बाद यूरिया न डालें**: इससे गर्दन तोड़ (Neck Blast) रोग और दाने में कालापन आता है।"
        ]
    },
    "cotton": {
        "crop_name": "Cotton (कपास / नरमा)",
        "ideal_ph": "6.5 – 8.0",
        "fertilizers": [
            {
                "name": "DAP",
                "per_acre_kg": 40,
                "application_timing": "बुआई के समय कतारों में (At Sowing)",
                "purpose": "जड़ विकास और मजबूत तना।"
            },
            {
                "name": "यूरिया (Urea)",
                "per_acre_kg": 95,
                "application_timing": "3 किस्तों में (पहली निराई, फूल आने पर, और टिंडे बनते समय)",
                "purpose": "टिंडों की संख्या और वजन में वृद्धि।"
            },
            {
                "name": "मैग्नीशियम सल्फेट",
                "per_acre_kg": 10,
                "application_timing": "टिंडे बनने के समय (Boll formation)",
                "purpose": "पत्तियों का लाल होना (Red Leaf Disease) रोकने हेतु।"
            }
        ],
        "pesticides": [
            {
                "name": "फ्लोनिकामिड 50% WG (Ulala)",
                "dosage_per_acre": "80 ग्राम (150 लीटर पानी में)",
                "target_pest": "सफेद मक्खी (Whitefly) व हरा तेला (Jassid)",
                "safety_interval": "कीटों का आर्थिक नुकसान स्तर (ETL) पार होने पर छिड़कें।"
            },
            {
                "name": "स्पिनटोरम 11.7% SC",
                "dosage_per_acre": "170 ml प्रति एकड़",
                "target_pest": "गुलाबी सुंडी (Pink Bollworm)",
                "safety_interval": "फूलों में रोसेट फूल (Rosette flower) दिखने पर छिड़काव करें।"
            }
        ],
        "when_not_to_use": [
            "❌ **जब पौधे बहुत तेजी से केवल पत्ते और कद बढ़ा रहे हों (Rank Growth), तब यूरिया बिल्कुल न डालें**: इससे फूल और टिंडे झड़ जाते हैं तथा सफेद मक्खी का हमला बढ़ता है।",
            "❌ **जलभराव (Waterlogging) वाली स्थिति में खाद न डालें**: जब तक खेत से अतिरिक्त पानी न निकले, खाद डालने से पौधे की जड़ें सड़ने लगती हैं।",
            "❌ **कीटनाशक और खरपतवारनाशक को खाद में बिना कृषि विशेषज्ञ की सलाह के मिलाकर न डालें**।"
        ]
    },
    "gram": {
        "crop_name": "Gram (चना / Chickpea)",
        "ideal_ph": "6.0 – 7.8",
        "fertilizers": [
            {
                "name": "DAP",
                "per_acre_kg": 30,
                "application_timing": "बुआई के समय (Basal at Sowing)",
                "purpose": "दलहनी फसल में जड़ों की ग्रंथियों (Nodules) के विकास के लिए प्रारंभिक नाइट्रोजन व फास्फोरस।"
            },
            {
                "name": "जिप्सम (Gypsum)",
                "per_acre_kg": 50,
                "application_timing": "खेत की अंतिम तैयारी के समय",
                "purpose": "सल्फर और कैल्शियम की आपूर्ति जिससे दाना चमकदार बनता है।"
            }
        ],
        "pesticides": [
            {
                "name": "एमामेक्टिन बेंजोएट 5% SG (Proclaim)",
                "dosage_per_acre": "100 ग्राम (150 लीटर पानी में)",
                "target_pest": "फली छेदक सुंडी (Gram Pod Borer - Helicoverpa)",
                "safety_interval": "फूल से फली बनते समय जब छोटी सुंडी दिखे।"
            }
        ],
        "when_not_to_use": [
            "❌ **चने की फसल में बाद में टॉप-ड्रेसिंग यूरिया कभी न डालें**: चना एक दलहनी फसल है जो वायुमंडल से स्वयं नाइट्रोजन ग्रहण करती है। यूरिया डालने से गांठें बनना बंद हो जाती हैं, केवल पत्ते बढ़ते हैं और फली नहीं लगती!",
            "❌ **उकठा (Wilt) रोगग्रस्त खेत में नाइट्रोजन युक्त खाद न डालें**: इससे फफूंद तेजी से फैलती है।"
        ]
    },
    "bajra": {
        "crop_name": "Bajra (बाजरा / Pearl Millet)",
        "ideal_ph": "6.5 – 8.5",
        "fertilizers": [
            {
                "name": "DAP",
                "per_acre_kg": 30,
                "application_timing": "बुआई के समय",
                "purpose": "जड़ों की मजबूती हेतु।"
            },
            {
                "name": "यूरिया",
                "per_acre_kg": 45,
                "application_timing": "पहली सिंचाई / बारिश के बाद (25-30 दिन)",
                "purpose": "कल्ले बढ़ाने और सिट्टे की लंबाई हेतु।"
            }
        ],
        "pesticides": [
            {
                "name": "क्लोरोपायरीफॉस 20% EC",
                "dosage_per_acre": "1 लीटर प्रति एकड़ (सिंचाई के साथ)",
                "target_pest": "दीमक (Termite) व तना मक्खी",
                "safety_interval": "बुआई के समय या पहली सिंचाई पर।"
            }
        ],
        "when_not_to_use": [
            "❌ **सूखा पड़ने (Drought / Moister stress) के दौरान यूरिया कभी न डालें**: बिना पानी के खाद डालने से पौधे की जड़ें जल जाती हैं और फसल सूख जाती है।",
            "❌ **सिट्टा (Earhead) पकने की अवस्था में खाद न डालें**।"
        ]
    }
}

def _calculate_crop_advisory(crop_key: str, land_area_acres: float, soil_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    key = "wheat"
    ck = crop_key.lower()
    for k in CROP_ADVISORY_DB:
        if k in ck:
            key = k
            break

    crop_info = CROP_ADVISORY_DB[key]
    acres = max(0.5, float(land_area_acres))

    # Calculate exact fertilizer bags & totals for the land area
    fertilizer_list = []
    for f in crop_info["fertilizers"]:
        total_kg = round(f["per_acre_kg"] * acres, 1)
        bags_50kg = round(total_kg / 50.0, 1)
        bags_45kg = round(total_kg / 45.0, 1) # Urea standard bag is 45kg in India
        is_urea = "यूरिया" in f["name"] or "Urea" in f["name"]
        bag_count = bags_45kg if is_urea else bags_50kg
        bag_weight = 45 if is_urea else 50

        # Adjust recommendation if soil test data is available
        adjustment_note = "मानक वैज्ञानिक मात्रा (Recommended Dosage)"
        if soil_data:
            n_val = soil_data.get("nitrogen_kg_ha", 240)
            p_val = soil_data.get("phosphorus_kg_ha", 16.5)
            k_val = soil_data.get("potassium_kg_ha", 210)
            ph = soil_data.get("ph_level", 7.2)

            if is_urea:
                if n_val > 500:
                    total_kg = round(total_kg * 0.75, 1)
                    bag_count = round(total_kg / bag_weight, 1)
                    adjustment_note = "⚠️ मिट्टी में नाइट्रोजन उच्च (>500 kg/ha) होने के कारण यूरिया 25% कम किया गया।"
                elif n_val < 200:
                    total_kg = round(total_kg * 1.15, 1)
                    bag_count = round(total_kg / bag_weight, 1)
                    adjustment_note = "ℹ️ मिट्टी में नाइट्रोजन कम (<200 kg/ha) होने से 15% अतिरिक्त यूरिया अनुशंसित।"
            elif "DAP" in f["name"]:
                if p_val > 25:
                    total_kg = round(total_kg * 0.8, 1)
                    bag_count = round(total_kg / bag_weight, 1)
                    adjustment_note = "⚠️ मिट्टी में फास्फोरस प्रचुर मात्रा में है; DAP 20% घटाया गया।"
            elif "MOP" in f["name"]:
                if k_val > 280:
                    total_kg = round(total_kg * 0.5, 1)
                    bag_count = round(total_kg / bag_weight, 1)
                    adjustment_note = "ℹ️ मिट्टी में पोटाश भरपूर (>280 kg/ha) है; MOP 50% घटाया गया।"

        fertilizer_list.append({
            "fertilizer_name": f["name"],
            "dose_per_acre": f"{f['per_acre_kg']} kg/एकड़",
            "total_quantity_kg": total_kg,
            "total_bags": f"{bag_count} बोरी ({bag_weight} kg प्रति बोरी)",
            "timing": f["application_timing"],
            "purpose": f["purpose"],
            "adjustment_note": adjustment_note
        })

    # Pesticide dosage
    pesticide_list = []
    for p in crop_info["pesticides"]:
        pesticide_list.append({
            "name": p["name"],
            "dosage_per_acre": p["dosage_per_acre"],
            "target_pest": p["target_pest"],
            "safety_interval": p["safety_interval"]
        })

    urea_bags_50kg = 0.0
    dap_bags_50kg = 0.0
    mop_bags_50kg = 0.0
    for f in fertilizer_list:
        fname = f["fertilizer_name"].lower()
        if "यूरिया" in f["fertilizer_name"] or "urea" in fname:
            urea_bags_50kg = round(f["total_quantity_kg"] / 50.0, 1)
        elif "dap" in fname or "डीएपी" in f["fertilizer_name"]:
            dap_bags_50kg = round(f["total_quantity_kg"] / 50.0, 1)
        elif "mop" in fname or "पोटाश" in f["fertilizer_name"] or "potash" in fname:
            mop_bags_50kg = round(f["total_quantity_kg"] / 50.0, 1)

    fertilizers_dict = {
        "urea_50kg_bags": urea_bags_50kg,
        "dap_50kg_bags": dap_bags_50kg,
        "mop_50kg_bags": mop_bags_50kg,
        "items": fertilizer_list
    }

    return {
        "crop_key": key,
        "crop_display_name": crop_info["crop_name"],
        "land_area_acres": acres,
        "ideal_ph_range": crop_info["ideal_ph"],
        "fertilizers": fertilizers_dict,
        "fertilizer_recommendations": fertilizer_list,
        "pesticides_schedule": pesticide_list,
        "pesticide_recommendations": pesticide_list,
        "when_not_to_use": crop_info["when_not_to_use"],
        "when_not_to_use_fertilizers": crop_info["when_not_to_use"]
    }

# -------------------------------------------------------------
# API ENDPOINTS
# -------------------------------------------------------------

@router.get("/advisory")
def get_crop_advisory(
    crop: str = "Wheat",
    land_area: Optional[float] = None,
    acres: Optional[float] = None,
    farmer_phone: Optional[str] = None,
    ph: Optional[float] = None,
    n: Optional[float] = None,
    p: Optional[float] = None,
    k: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Compute real-time crop fertilizer dosage, pesticides, and "When NOT to use" restrictions
    """
    effective_acres = acres if acres is not None else (land_area if land_area is not None else 1.0)
    soil_data = None
    if farmer_phone:
        clean_p = farmer_phone.replace(" ", "").replace("+91", "").strip()
        rec = db.query(SoilTestRecord).filter(
            (SoilTestRecord.farmer_phone == clean_p) | (SoilTestRecord.farmer_id == clean_p)
        ).order_by(SoilTestRecord.created_at.desc()).first()
        if rec and rec.status == "COMPLETED":
            soil_data = {
                "ph_level": rec.ph_level,
                "nitrogen_kg_ha": rec.nitrogen_kg_ha,
                "phosphorus_kg_ha": rec.phosphorus_kg_ha,
                "potassium_kg_ha": rec.potassium_kg_ha
            }

    if not soil_data and (ph is not None or n is not None or p is not None or k is not None):
        soil_data = {
            "ph_level": ph or 7.2,
            "nitrogen_kg_ha": n or 240.0,
            "phosphorus_kg_ha": p or 16.5,
            "potassium_kg_ha": k or 210.0
        }

    adv = _calculate_crop_advisory(crop, effective_acres, soil_data)
    return {
        "success": True,
        "advisory": adv,
        "fertilizers": adv["fertilizers"],
        "pesticides_schedule": adv["pesticides_schedule"],
        "when_not_to_use_fertilizers": adv["when_not_to_use_fertilizers"]
    }

@router.post("/book")
def book_soil_testing_slot(req: SoilTestBookingRequest, db: Session = Depends(get_db)):
    """
    Farmer books a soil testing appointment and sample submission slot
    """
    clean_phone = req.farmer_phone.replace(" ", "").replace("+91", "").strip()
    record_id = f"ST-2026-{random.randint(1000, 9999)}"
    sample_id = f"SMP-HR-{random.randint(5000, 9999)}"

    # Create new booking entry
    record = SoilTestRecord(
        id=record_id,
        sample_id=sample_id,
        farmer_id=req.farmer_id or f"USR-FARMER-{clean_phone[-4:]}",
        farmer_name=req.farmer_name,
        farmer_phone=clean_phone,
        district=req.district or "Karnal",
        state=req.state or "Haryana",
        village=req.village or "Kachhwa",
        center_id=req.center_id or "CTR-HR-01",
        center_name=req.lab_name or req.center_name or "Karnal Central Procurement Center",
        booking_date=req.booking_date,
        time_slot=req.preferred_slot or req.time_slot or "10:00 AM – 11:30 AM",
        crop_planned=req.crop_planned or "Wheat (Grade A)",
        land_area_acres=req.land_area_acres,
        soil_type=req.soil_type or "Alluvial Loam (दोमट मिट्टी)",
        status="BOOKED",
        # Default placeholder values until tested in lab
        ph_level=7.2,
        ec_level=0.45,
        organic_carbon_percent=0.52,
        nitrogen_kg_ha=240.0,
        phosphorus_kg_ha=16.5,
        potassium_kg_ha=210.0,
        zinc_ppm=0.55,
        sulphur_ppm=8.2,
        health_status="PENDING_TEST",
        advisory_notes="सैंपल प्रयोगशाला में जमा करने के 24-48 घंटों में मृदा स्वास्थ्य कार्ड रिपोर्ट जारी होगी।",
        created_at=datetime.datetime.utcnow(),
        tested_at=datetime.datetime.utcnow()
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "success": True,
        "sample_id": record.sample_id,
        "message": "मृदा परीक्षण स्लॉट सफलतापूर्वक बुक किया गया! (Soil testing slot booked successfully)",
        "booking": {
            "record_id": record.id,
            "sample_id": record.sample_id,
            "farmer_name": record.farmer_name,
            "center_name": record.center_name,
            "date": record.booking_date,
            "time_slot": record.time_slot,
            "crop": record.crop_planned,
            "land_area": record.land_area_acres,
            "status": record.status
        }
    }

@router.get("/farmer/{farmer_id_or_phone}")
def get_farmer_soil_status(farmer_id_or_phone: str, crop_override: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Check: Did farmer have soil testing done or not?
    Returns active Soil Health Card, test values, and tailored crop fertilizer/pesticide advisory.
    """
    clean_val = farmer_id_or_phone.replace(" ", "").replace("+91", "").strip()

    # Search by phone or ID - prefer COMPLETED record if available so farmer gets lab advisory
    records = db.query(SoilTestRecord).filter(
        (SoilTestRecord.farmer_phone == clean_val) |
        (SoilTestRecord.farmer_id == clean_val) |
        (SoilTestRecord.farmer_phone.like(f"%{clean_val}%"))
    ).order_by(SoilTestRecord.created_at.desc()).all()

    if not records:
        return {
            "success": True,
            "has_soil_test": False,
            "tested": False,
            "is_completed": False,
            "status": "NOT_DONE",
            "test_status": "NOT_DONE",
            "status_label": "परीक्षण नहीं हुआ (Soil Testing NOT Done)",
            "message": "इस किसान का कोई पंजीकृत मृदा परीक्षण रिकॉर्ड नहीं मिला। कृपया परीक्षण स्लॉट बुक करें।"
        }

    record = next((r for r in records if r.status == "COMPLETED"), records[0])

    target_crop = crop_override or record.crop_planned
    soil_data = {
        "ph_level": record.ph_level,
        "organic_carbon_percent": record.organic_carbon_percent,
        "nitrogen_kg_ha": record.nitrogen_kg_ha,
        "phosphorus_kg_ha": record.phosphorus_kg_ha,
        "potassium_kg_ha": record.potassium_kg_ha,
        "zinc_ppm": record.zinc_ppm,
        "sulphur_ppm": record.sulphur_ppm
    }

    advisory = _calculate_crop_advisory(target_crop, record.land_area_acres, soil_data)
    is_completed = record.status == "COMPLETED"
    test_status = "Completed" if is_completed else ("In Progress" if record.status in ["BOOKED", "SAMPLE_COLLECTED", "IN_PROGRESS", "IN_TESTING"] else record.status)

    return {
        "success": True,
        "has_soil_test": True,
        "tested": is_completed,
        "is_completed": is_completed,
        "status": record.status,
        "test_status": test_status,
        "record_id": record.id,
        "sample_id": record.sample_id,
        "farmer_name": record.farmer_name,
        "farmer_phone": record.farmer_phone,
        "district": record.district,
        "center_name": record.center_name,
        "test_date": record.tested_at.strftime("%d-%m-%Y") if record.tested_at else record.booking_date,
        "crop_planned": target_crop,
        "land_area_acres": record.land_area_acres,
        "soil_type": record.soil_type,
        "status_label": "परीक्षण संपन्न (Soil Testing Completed)" if is_completed else "प्रक्रियाधीन (Sample In Lab)",
        "soil_health_card": {
            "ph_level": record.ph_level,
            "ph_status": "सामान्य (Neutral)" if 6.5 <= record.ph_level <= 7.8 else ("अम्लीय (Acidic)" if record.ph_level < 6.5 else "क्षारीय (Alkaline)"),
            "ec_level": record.ec_level,
            "organic_carbon_percent": record.organic_carbon_percent,
            "oc_status": "मध्यम (Medium)" if record.organic_carbon_percent >= 0.5 else "निम्न (Low)",
            "nitrogen_kg_ha": record.nitrogen_kg_ha,
            "n_status": "निम्न (Low)" if record.nitrogen_kg_ha < 280 else ("मध्यम (Medium)" if record.nitrogen_kg_ha <= 560 else "उच्च (High)"),
            "phosphorus_kg_ha": record.phosphorus_kg_ha,
            "p_status": "मध्यम (Medium)" if 10 <= record.phosphorus_kg_ha <= 25 else ("निम्न (Low)" if record.phosphorus_kg_ha < 10 else "उच्च (High)"),
            "potassium_kg_ha": record.potassium_kg_ha,
            "k_status": "मध्यम (Medium)" if 110 <= record.potassium_kg_ha <= 280 else ("निम्न (Low)" if record.potassium_kg_ha < 110 else "उच्च (High)"),
            "zinc_ppm": record.zinc_ppm,
            "zinc_status": "कमी (Deficient)" if record.zinc_ppm < 0.6 else "पर्याप्त (Sufficient)",
            "sulphur_ppm": record.sulphur_ppm,
            "health_grade": record.health_status
        },
        "latest_record": {
            "sample_id": record.sample_id,
            "lab_name": record.center_name,
            "test_date": record.tested_at.strftime("%d-%m-%Y") if record.tested_at else record.booking_date,
            "overall_health_grade": record.health_status or "A",
            "ph": record.ph_level,
            "nitrogen_kg_ha": record.nitrogen_kg_ha,
            "phosphorus_kg_ha": record.phosphorus_kg_ha,
            "potassium_kg_ha": record.potassium_kg_ha,
            "organic_carbon_percent": record.organic_carbon_percent,
            "electrical_conductivity": record.ec_level,
            "zinc_ppm": record.zinc_ppm,
            "sulphur_ppm": record.sulphur_ppm
        },
        "advisory": advisory
    }

@router.get("/records")
def list_soil_test_records(
    q: Optional[str] = None,
    status: Optional[str] = None,
    district: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Operator and Admin search across all farmer soil test records
    """
    query = db.query(SoilTestRecord)
    if q:
        clean_q = q.strip()
        query = query.filter(
            (SoilTestRecord.farmer_name.ilike(f"%{clean_q}%")) |
            (SoilTestRecord.farmer_phone.ilike(f"%{clean_q}%")) |
            (SoilTestRecord.sample_id.ilike(f"%{clean_q}%")) |
            (SoilTestRecord.id.ilike(f"%{clean_q}%"))
        )
    if status:
        query = query.filter(SoilTestRecord.status == status.strip().upper())
    if district:
        query = query.filter(SoilTestRecord.district.ilike(f"%{district.strip()}%"))

    records = query.order_by(SoilTestRecord.created_at.desc()).all()

    formatted = []
    for r in records:
        formatted.append({
            "record_id": r.id,
            "sample_id": r.sample_id,
            "farmer_name": r.farmer_name,
            "farmer_phone": r.farmer_phone,
            "district": r.district,
            "center_name": r.center_name,
            "crop_planned": r.crop_planned,
            "land_area": r.land_area_acres,
            "status": r.status,
            "ph": r.ph_level,
            "nitrogen": r.nitrogen_kg_ha,
            "phosphorus": r.phosphorus_kg_ha,
            "potassium": r.potassium_kg_ha,
            "date": r.booking_date,
            "health_status": r.health_status
        })

    return {
        "success": True,
        "total": len(formatted),
        "data": formatted
    }

@router.post("/update-report")
def update_soil_test_report(req: SoilTestUpdateRequest, db: Session = Depends(get_db)):
    """
    Operator records laboratory testing values and marks soil health card as completed
    """
    lookup_id = (req.record_id or req.sample_id or "").strip()
    record = None

    if lookup_id:
        record = db.query(SoilTestRecord).filter(
            (SoilTestRecord.id == lookup_id) |
            (SoilTestRecord.sample_id == lookup_id)
        ).first()

    if not record and req.farmer_phone:
        clean_phone = req.farmer_phone.replace(" ", "").replace("+91", "").strip()
        record = db.query(SoilTestRecord).filter(
            (SoilTestRecord.farmer_phone == clean_phone) |
            (SoilTestRecord.farmer_phone.like(f"%{clean_phone}%"))
        ).order_by(SoilTestRecord.created_at.desc()).first()

    if not record:
        # Create a new completed record if none existed
        import uuid
        farmer_phone = (req.farmer_phone or "9876543210").strip()
        farmer = db.query(User).filter(User.phone == farmer_phone).first()
        record = SoilTestRecord(
            id=f"STR-{uuid.uuid4().hex[:8].upper()}",
            sample_id=req.sample_id or f"SHC-2026-{random.randint(1000, 9999)}",
            farmer_id=farmer.id if farmer else "USR-FARMER-01",
            farmer_name=farmer.name if farmer else "किसान",
            farmer_phone=farmer_phone,
            district="Karnal",
            state="Haryana",
            center_name="Karnal Central Soil Testing Lab",
            booking_date=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
            crop_planned="Wheat (Grade A)",
            land_area_acres=2.5,
            soil_type="Alluvial Loam"
        )
        db.add(record)

    ph_val = req.ph if req.ph is not None else (req.ph_level if req.ph_level is not None else 7.2)
    ec_val = req.electrical_conductivity if req.electrical_conductivity is not None else (req.ec_level if req.ec_level is not None else 0.45)

    record.ph_level = ph_val
    record.ec_level = ec_val
    record.organic_carbon_percent = req.organic_carbon_percent if req.organic_carbon_percent is not None else 0.55
    record.nitrogen_kg_ha = req.nitrogen_kg_ha if req.nitrogen_kg_ha is not None else 280.0
    record.phosphorus_kg_ha = req.phosphorus_kg_ha if req.phosphorus_kg_ha is not None else 22.0
    record.potassium_kg_ha = req.potassium_kg_ha if req.potassium_kg_ha is not None else 210.0
    record.zinc_ppm = req.zinc_ppm if req.zinc_ppm is not None else 0.55
    record.sulphur_ppm = req.sulphur_ppm if req.sulphur_ppm is not None else 8.2
    record.health_status = req.health_status or "GOOD"
    record.status = "COMPLETED"
    record.tested_at = datetime.datetime.utcnow()
    record.advisory_notes = req.advisory_notes or "परीक्षण पूर्ण। अनुशंसित उर्वरक मात्रा का ही प्रयोग करें।"

    db.commit()
    db.refresh(record)

    return {
        "success": True,
        "message": "मृदा परीक्षण रिपोर्ट सफलतापूर्वक अपडेट की गई!",
        "record_id": record.id,
        "sample_id": record.sample_id,
        "status": record.status
    }
