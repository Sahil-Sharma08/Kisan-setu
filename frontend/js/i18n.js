/**
 * KisanSetu — Bilingual UI Scaffolding & Rural-First i18n Engine
 * Clean key-value dictionary routing supporting English and Hindi.
 */

(function (window) {
  'use strict';

  const STORAGE_KEY = "kisan_setu_language";

  const DICTIONARY = {
    // Brand & Navigation
    "app.title": { hi: "किसान सेतु", en: "KisanSetu" },
    "app.subtitle": { hi: "स्मार्ट कृषि खरीद एवं कतार प्रबंधन", en: "Smart Agricultural Logistics Platform" },
    "nav.dashboard": { hi: "डैशबोर्ड", en: "Dashboard" },
    "nav.centers": { hi: "खरीद केंद्र", en: "Procurement Centers" },
    "nav.booking": { hi: "स्लॉट बुकिंग", en: "Slot Booking" },
    "nav.token": { hi: "डिजिटल टोकन", en: "Digital Token" },
    "nav.queue": { hi: "लाइव कतार", en: "Live Queue" },
    "nav.logout": { hi: "लॉगआउट", en: "Logout" },
    "nav.commandCenter": { hi: "कमांड सेंटर", en: "Command Center" },
    "nav.yardScreen": { hi: "यार्ड डिस्प्ले स्क्रीन", en: "Yard Display" },

    // Throughput & Slots
    "throughput.title": { hi: "डायनामिक मंडी थ्रूपुट इंजन", en: "Dynamic Mandi Throughput Engine" },
    "throughput.formula": { hi: "क्षमता गणना सूत्र", en: "Capacity Formula" },
    "throughput.weighbridges": { hi: "सक्रिय वेईब्रिज", en: "Active Weighbridges" },
    "throughput.rate": { hi: "प्रति घंटा तौल दर", en: "Hourly Weighing Rate" },
    "throughput.selectSlot": { hi: "समय स्लॉट चुनें", en: "Select Time Slot" },
    "throughput.greenTier": { hi: "कम भीड़ (सुगम प्रवेश)", en: "Low Load (Fast-Track)" },
    "throughput.amberTier": { hi: "मध्यम भीड़ (सामान्य प्रतीक्षा)", en: "Moderate Load (Normal)" },
    "throughput.redTier": { hi: "अत्यधिक भीड़ (स्लॉट लॉक)", en: "Heavy Congestion (Locked)" },
    "throughput.alternativeTitle": { hi: "कम भीड़ वाले नजदीकी खरीद केंद्र", en: "Nearby Low-Load Alternative Centers" },
    "throughput.divertBtn": { hi: "यहाँ स्लॉट बुक करें", en: "Book at This Mandi" },

    // Gate Verification & Security
    "gate.title": { hi: "प्रवेश द्वार सत्यापन डेस्क", en: "Gate Verification Station" },
    "gate.scanQR": { hi: "QR टोकन स्कैन करें", en: "Scan QR Token" },
    "gate.tokenNumber": { hi: "टोकन संख्या", en: "Token Number" },
    "gate.verify": { hi: "सत्यापित करें", en: "Verify Entry" },
    "gate.bufferValid": { hi: "समय पर आगमन • वैध", en: "On-Time Arrival (Valid)" },
    "gate.bufferOverdue": { hi: "समय सीमा समाप्त • प्रतीक्षा लेन", en: "Buffer Overdue (Standby Lane)" },
    "gate.tamperAlert": { hi: "सुरक्षा चेतावनी: फर्जी/अवैध पास!", en: "SECURITY ALERT: Forged/Hoarded Pass!" },

    // State Machine Stages
    "stage.booked": { hi: "स्लॉट बुक हुआ", en: "Slot Booked" },
    "stage.gateScanned": { hi: "गेट सत्यापन पूर्ण", en: "Gate Verified" },
    "stage.assayTesting": { hi: "नमी एवं गुणवत्ता जांच", en: "Moisture & Assay Testing" },
    "stage.weighbridgeIn": { hi: "सकल इलेक्ट्रॉनिक तौल (Gross)", en: "Weighbridge Gross In" },
    "stage.weighbridgeOut": { hi: "खाली वजन व शुद्ध अनाज (Net Tare)", en: "Weighbridge Net Tare" },
    "stage.dbtDispatched": { hi: "DBT बैंक भुगतान पूर्ण", en: "DBT Payment Dispatched" },

    // Superintendent & Alerts
    "supt.title": { hi: "मंडी अधीक्षक नियंत्रण कक्ष", en: "Mandi Superintendent Command Center" },
    "supt.tonnage": { hi: "दैनिक टन भार मापक (Tonnage Gauge)", en: "Real-Time Tonnage Gauge" },
    "supt.bottleneck": { hi: "चरण विलंबता एवं रुकावट ट्रैकर", en: "Stage Latency & Bottleneck Tracker" },
    "supt.circuitBreaker": { hi: "आपातकालीन सर्किट ब्रेकर", en: "Emergency Circuit Breaker" },
    "supt.haltUpcoming": { hi: "आगामी स्लॉट स्थगित करें (Halt)", en: "Halt Upcoming Slots" },
    "supt.resumeOps": { hi: "सामान्य संचालन पुनः शुरू करें", en: "Resume Normal Operations" }
  };

  let currentLang = localStorage.getItem(STORAGE_KEY) || "hi";

  const KisanI18n = {
    getLanguage() {
      return currentLang;
    },

    setLanguage(lang) {
      if (lang !== "hi" && lang !== "en") return;
      currentLang = lang;
      localStorage.setItem(STORAGE_KEY, lang);
      document.documentElement.lang = lang;
      this.applyTranslations();
      this.updateSwitcherUI();
    },

    toggleLanguage() {
      this.setLanguage(currentLang === "hi" ? "en" : "hi");
    },

    t(key) {
      const entry = DICTIONARY[key];
      if (!entry) return key;
      return entry[currentLang] || entry["hi"] || key;
    },

    applyTranslations() {
      document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        const translation = this.t(key);
        if (translation) {
          if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
            el.placeholder = translation;
          } else {
            el.textContent = translation;
          }
        }
      });
    },

    updateSwitcherUI() {
      document.querySelectorAll(".kisan-lang-btn").forEach(btn => {
        btn.textContent = currentLang === "hi" ? "English" : "हिन्दी";
        btn.setAttribute("title", currentLang === "hi" ? "Switch to English" : "हिन्दी में बदलें");
      });
    },

    renderLanguageSwitchButton() {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "kisan-lang-btn px-2.5 py-1 rounded-md text-xs font-bold border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-all shadow-2xs cursor-pointer";
      btn.textContent = currentLang === "hi" ? "English" : "हिन्दी";
      btn.onclick = () => this.toggleLanguage();
      return btn;
    }
  };

  // Auto apply on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    KisanI18n.applyTranslations();
  });

  window.KisanI18n = KisanI18n;
})(window);
