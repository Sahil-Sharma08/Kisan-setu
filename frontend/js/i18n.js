/**
 * KisanSetu — Bilingual UI Scaffolding & Rural-First i18n Engine
 * Clean key-value dictionary routing supporting English (default) and Hindi.
 */

(function (window) {
  'use strict';

  const STORAGE_KEY = "kisan_setu_language";
  const COMPAT_KEY = "kisansetu_language";
  const EXPLICIT_FLAG = "kisan_lang_explicit_choice";

  const DICTIONARY = {
    // Brand & App
    "app.title": { en: "KisanSetu", hi: "किसान सेतु" },
    "app.subtitle": { en: "Smart Agricultural Logistics & Procurement Platform", hi: "स्मार्ट कृषि खरीद एवं कतार प्रबंधन" },
    "app.tagline": { en: "Digital Mandi Platform", hi: "डिजिटल मंडी प्लेटफॉर्म" },

    // Navigation Links
    "nav.home": { en: "Home", hi: "मुख्य पृष्ठ" },
    "nav.crops": { en: "Crops", hi: "फसलें" },
    "nav.centers": { en: "Procurement Centers", hi: "खरीद केंद्र" },
    "nav.farmerPortal": { en: "Farmer Portal", hi: "किसान पोर्टल" },
    "nav.farmerPortalSub": { en: "Farmer Procurement & Queue Portal", hi: "किसान खरीद एवं कतार प्रबंधन पोर्टल" },
    "nav.login": { en: "Login", hi: "लॉगिन" },
    "nav.register": { en: "Register", hi: "पंजीकरण" },
    "nav.logout": { en: "Logout", hi: "लॉगआउट" },
    "nav.dashboard": { en: "Dashboard", hi: "डैशबोर्ड" },
    "nav.more": { en: "More", hi: "और देखें" },
    "nav.journey": { en: "7-Step Process", hi: "7-चरणीय प्रक्रिया" },
    "nav.compare": { en: "Comparison", hi: "तुलना" },
    "nav.faq": { en: "FAQ", hi: "सामान्य प्रश्न" },
    "nav.about": { en: "Platform Details", hi: "प्लेटफ़ॉर्म विवरण" },
    "nav.voiceAssistant": { en: "Kisan Vani AI", hi: "किसान वाणी AI" },
    "nav.soilTesting": { en: "Soil Health", hi: "मृदा परीक्षण" },
    "nav.salesHistory": { en: "Sales History", hi: "विक्रय इतिहास" },
    "nav.myBookings": { en: "My Bookings", hi: "मेरी बुकिंग" },
    "nav.booking": { en: "Slot Booking", hi: "स्लॉट बुकिंग" },
    "nav.token": { en: "Digital Pass", hi: "डिजिटल टोकन" },
    "nav.queue": { en: "Live Queue", hi: "लाइव कतार" },
    "nav.complaints": { en: "Complaints", hi: "शिकायतें" },
    "nav.activeSession": { en: "Active Session", hi: "सक्रिय सत्र" },
    "nav.commandCenter": { en: "Command Center", hi: "कमांड सेंटर" },
    "nav.yardScreen": { en: "Live Yard Billboard", hi: "लाइव यार्ड डिस्प्ले" },
    "nav.adminOverview": { en: "Admin Overview", hi: "व्यवस्थापक अवलोकन" },
    "nav.operatorQueue": { en: "Operator Queue", hi: "ऑपरेटर कतार" },
    "nav.gateVerification": { en: "Gate Verification", hi: "गेट सत्यापन" },
    "nav.procurementOps": { en: "Procurement Operations", hi: "खरीद संचालन" },
    "nav.queueMgmt": { en: "Queue Management", hi: "कतार प्रबंधन" },
    "nav.districtConsole": { en: "District Oversight Console", hi: "जिला निगरानी कंसोल" },

    // Common UI Text
    "common.loading": { en: "Loading...", hi: "लोड हो रहा है..." },
    "common.active": { en: "Active", hi: "सक्रिय" },
    "common.liveMandiRates": { en: "Live Mandi Rates", hi: "लाइव मंडी भाव" },
    "common.agroWeather": { en: "Local Agro-Weather", hi: "स्थानीय कृषि मौसम" },
    "common.search": { en: "Search", hi: "खोजें" },
    "common.filter": { en: "Filter", hi: "फ़िल्टर" },
    "common.reset": { en: "Reset", hi: "रीसेट" },
    "common.submit": { en: "Submit", hi: "जमा करें" },
    "common.cancel": { en: "Cancel", hi: "रद्द करें" },
    "common.view": { en: "View", hi: "देखें" },
    "common.back": { en: "Back", hi: "वापस" },
    "common.status": { en: "Status", hi: "स्थिति" },
    "common.date": { en: "Date", hi: "दिनांक" },
    "common.time": { en: "Time", hi: "समय" },
    "common.action": { en: "Action", hi: "कार्रवाई" },
    "common.download": { en: "Download", hi: "डाउनलोड" },
    "common.print": { en: "Print", hi: "प्रिंट करें" },
    "common.verified": { en: "Verified", hi: "सत्यापित" },
    "common.pending": { en: "Pending", hi: "लंबित" },
    "common.refresh": { en: "Refresh", hi: "रिफ्रेश करें" },
    "common.language": { en: "Language", hi: "भाषा" },
    "common.switchLang": { en: "Switch Language", hi: "भाषा बदलें" },

    // Farmer Portal Features
    "farmer.greeting": { en: "Namaste, Farmer Brother!", hi: "नमस्ते, किसान भाई!" },
    "farmer.welcomeSub": { en: "Track mandi arrivals, book weighbridge slots, and monitor live queue status.", hi: "मंडी आवक ट्रैक करें, तौल स्लॉट बुक करें और कतार की स्थिति देखें।" },
    "farmer.quickActions": { en: "Quick Actions", hi: "त्वरित कार्य" },
    "farmer.bookNewSlot": { en: "Book Delivery Slot", hi: "नया स्लॉट बुक करें" },
    "farmer.viewToken": { en: "View Digital Pass", hi: "डिजिटल टोकन देखें" },
    "farmer.activeBooking": { en: "Active Booking & Pass", hi: "सक्रिय बुकिंग व डिजिटल पर्ची" },
    "farmer.noActiveBooking": { en: "No Active Booking", hi: "कोई सक्रिय बुकिंग नहीं" },
    "farmer.noActiveBookingSub": { en: "You have no upcoming procurement slots or active tokens. Find a center to book a slot.", hi: "वर्तमान में आपकी कोई आगामी खरीद बुकिंग या सक्रिय डिजिटल टोकन पर्ची नहीं है। केंद्र खोजें और समय चुनें।" },
    "farmer.findCenters": { en: "Find Procurement Center", hi: "खरीद केंद्र खोजें" },
    "farmer.salesSummary": { en: "Sales & Procurement Summary", hi: "विक्रय एवं खरीद सारांश" },
    "farmer.totalCropSold": { en: "Total Crop Sold", hi: "कुल बेची गई फसल" },
    "farmer.completedSales": { en: "Completed Transactions", hi: "पूर्ण खरीद लेनदेन" },
    "farmer.totalPayment": { en: "Total Payment Released", hi: "कुल भुगतान राशि" },
    "farmer.helpline": { en: "Kisan Helpline & Support", hi: "किसान हेल्पलाइन व सहायता" },
    "farmer.tollFree": { en: "Toll-Free Helpline", hi: "टोल-फ्री हेल्पलाइन" },
    "farmer.hours": { en: "7:00 AM – 7:00 PM (Monday to Saturday)", hi: "प्रातः 7:00 – सायं 7:00 (सोमवार से शनिवार)" },
    "farmer.profileDetails": { en: "Farmer Profile", hi: "किसान प्रोफ़ाइल" },

    // Throughput & Slots
    "throughput.title": { en: "Dynamic Mandi Throughput Engine", hi: "डायनामिक मंडी थ्रूपुट इंजन" },
    "throughput.formula": { en: "Capacity Formula", hi: "क्षमता गणना सूत्र" },
    "throughput.weighbridges": { en: "Active Weighbridges", hi: "सक्रिय वेईब्रिज" },
    "throughput.rate": { en: "Hourly Weighing Rate", hi: "प्रति घंटा तौल दर" },
    "throughput.selectSlot": { en: "Select Time Slot", hi: "समय स्लॉट चुनें" },
    "throughput.greenTier": { en: "Low Load (Fast-Track)", hi: "कम भीड़ (सुगम प्रवेश)" },
    "throughput.amberTier": { en: "Moderate Load (Normal)", hi: "मध्यम भीड़ (सामान्य प्रतीक्षा)" },
    "throughput.redTier": { en: "Heavy Congestion (Locked)", hi: "अत्यधिक भीड़ (स्लॉट लॉक)" },
    "throughput.alternativeTitle": { en: "Nearby Low-Load Alternative Centers", hi: "कम भीड़ वाले नजदीकी खरीद केंद्र" },
    "throughput.divertBtn": { en: "Book at This Mandi", hi: "यहाँ स्लॉट बुक करें" },

    // Gate Verification & Security
    "gate.title": { en: "Gate Verification Station", hi: "प्रवेश द्वार सत्यापन डेस्क" },
    "gate.scanQR": { en: "Scan QR Token", hi: "QR टोकन स्कैन करें" },
    "gate.tokenNumber": { en: "Token Number", hi: "टोकन संख्या" },
    "gate.verify": { en: "Verify Entry", hi: "सत्यापित करें" },
    "gate.bufferValid": { en: "On-Time Arrival (Valid)", hi: "समय पर आगमन • वैध" },
    "gate.bufferOverdue": { en: "Buffer Overdue (Standby Lane)", hi: "समय सीमा समाप्त • प्रतीक्षा लेन" },
    "gate.tamperAlert": { en: "SECURITY ALERT: Forged/Hoarded Pass!", hi: "सुरक्षा चेतावनी: फर्जी/अवैध पास!" },
    "gate.callTokenPA": { en: "Call Token (PA)", hi: "टोकन बुलाएं (PA)" },
    "gate.audioChime": { en: "Audio Chime", hi: "ऑडियो घंटी" },
    "gate.speakToken": { en: "Calling token over public address system...", hi: "सार्वजनिक उद्घोषणा प्रणाली पर टोकन बुलाया जा रहा है..." },

    // State Machine Stages
    "stage.booked": { en: "Slot Booked", hi: "स्लॉट बुक हुआ" },
    "stage.gateScanned": { en: "Gate Verified", hi: "गेट सत्यापन पूर्ण" },
    "stage.assayTesting": { en: "Moisture & Assay Testing", hi: "नमी एवं गुणवत्ता जांच" },
    "stage.weighbridgeIn": { en: "Weighbridge Gross In", hi: "सकल इलेक्ट्रॉनिक तौल (Gross)" },
    "stage.weighbridgeOut": { en: "Weighbridge Net Tare", hi: "खाली वजन व शुद्ध अनाज (Net Tare)" },
    "stage.dbtDispatched": { en: "DBT Payment Dispatched", hi: "DBT बैंक भुगतान पूर्ण" },

    // Superintendent & Command Center
    "supt.title": { en: "Mandi Superintendent Command Center", hi: "मंडी अधीक्षक नियंत्रण कक्ष" },
    "supt.controlRoom": { en: "CONTROL ROOM", hi: "नियंत्रण कक्ष" },
    "supt.tonnageGauge": { en: "Real-Time Mandi Yard Tonnage Gauge", hi: "दैनिक टन भार मापक (Tonnage Gauge)" },
    "supt.realtimeIntake": { en: "Inbound Tonnage Saturation vs Mandi Threshold", hi: "दैनिक आवक संतृप्ति दर (Real-Time Intake)" },
    "supt.targetCap": { en: "Target Daily Intake Capacity", hi: "दैनिक लक्ष्य आवक क्षमता" },
    "supt.weighed": { en: "Weighed Inbound (Gate-In)", hi: "तौला गया अनाज (प्रवेश)" },
    "supt.enroute": { en: "En-Route / Scheduled Bookings", hi: "मार्गस्थ / निर्धारित बुकिंग" },
    "supt.cumProgress": { en: "Cumulative Inbound Progress", hi: "कुल आवक प्रगति" },
    "supt.emergencyBreaker": { en: "Emergency Circuit Breaker", hi: "आपातकालीन सर्किट ब्रेकर" },
    "supt.breakerDesc": { 
      en: "Instantly halt incoming traffic and upcoming slots in case of sudden weather changes, machinery breakdown, or godown saturation.", 
      hi: "अचानक मौसम परिवर्तन, मशीनरी खराबी या गोदाम भरने की स्थिति में आगामी स्लॉट व आवक तुरंत रोकें।" 
    },
    "supt.reasonHalt": { en: "Reason for Halt", hi: "स्थगित करने का कारण" },
    "supt.deferDuration": { en: "Deferral Duration", hi: "स्थगित अवधि" },
    "supt.haltBtn": { en: "Halt Upcoming Slots & Send Mass SMS", hi: "आगामी स्लॉट स्थगित करें व एसएमएस भेजें" },
    "supt.resumeBtn": { en: "Resume Normal Yard Intake", hi: "सामान्य यार्ड आवक पुनः शुरू करें" },
    "supt.stageLatency": { en: "End-to-End Turnaround Analytics", hi: "टर्नअराउंड विश्लेषिकी" },
    "supt.stageLatencyTitle": { en: "Stage Latency & Bottleneck Detector", hi: "चरण विलंबता एवं रुकावट ट्रैकर" },
    "supt.liveIntake": { en: "Live Intake Stream", hi: "लाइव आवक स्ट्रीम" },
    "supt.yardTelemetry": { en: "Mandi Yard Telemetry & Vehicle Pipeline", hi: "मंडी यार्ड टेलीमेट्री एवं वाहन पाइपलाइन" },
    "supt.refreshBtn": { en: "Refresh Telemetry", hi: "टेलीमेट्री रिफ्रेश करें" },

    // Table Headers
    "th.tokenBooking": { en: "Token & Booking", hi: "टोकन व बुकिंग" },
    "th.farmerDetails": { en: "Farmer Details", hi: "किसान विवरण" },
    "th.vehicleCrop": { en: "Vehicle & Crop", hi: "वाहन व फसल" },
    "th.scheduledSlot": { en: "Scheduled Slot", hi: "निर्धारित स्लॉट" },
    "th.currentStage": { en: "Current Pipeline Stage", hi: "वर्तमान चरण" },
    "th.allocatedBay": { en: "Allocated Bay / WB", hi: "आवंटित बे / वेईब्रिज" },
    "th.waitTime": { en: "Wait Time", hi: "प्रतीक्षा समय" },
    "th.action": { en: "Superintendent Action", hi: "अधीक्षक कार्रवाई" }
  };

  // Language Resolution: Default to "en" (English)
  function resolveInitialLanguage() {
    const userHasChosen = sessionStorage.getItem(EXPLICIT_FLAG) === "true";
    if (userHasChosen) {
      const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(COMPAT_KEY);
      if (stored === "hi" || stored === "en") return stored;
    }
    // Default to English as requested
    localStorage.setItem(STORAGE_KEY, "en");
    localStorage.setItem(COMPAT_KEY, "en");
    return "en";
  }

  let currentLang = resolveInitialLanguage();

  const KisanI18n = {
    getLanguage() {
      return currentLang;
    },

    setLanguage(lang) {
      if (lang !== "hi" && lang !== "en") return;
      currentLang = lang;
      sessionStorage.setItem(EXPLICIT_FLAG, "true");
      localStorage.setItem(STORAGE_KEY, lang);
      localStorage.setItem(COMPAT_KEY, lang);
      document.documentElement.lang = lang;
      this.applyTranslations();
      this.updateSwitcherUI();

      // Broadcast event for dynamic components (telemetry, charts, Voice Assistant)
      window.dispatchEvent(new CustomEvent('kisan_language_changed', { detail: { lang } }));
    },

    toggleLanguage() {
      this.setLanguage(currentLang === "hi" ? "en" : "hi");
    },

    t(key) {
      const entry = DICTIONARY[key];
      if (!entry) return key;
      return entry[currentLang] || entry["en"] || key;
    },

    applyTranslations() {
      // 1. Elements with data-i18n dictionary keys
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

      // 2. Direct bilingual inline attributes: data-i18n-en and data-i18n-hi
      document.querySelectorAll("[data-i18n-en]").forEach(el => {
        const text = currentLang === "hi" 
          ? (el.getAttribute("data-i18n-hi") || el.getAttribute("data-i18n-en"))
          : el.getAttribute("data-i18n-en");
        if (text) {
          if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
            el.placeholder = text;
          } else {
            el.textContent = text;
          }
        }
      });

      // 3. Document Title if meta tag provided
      const docTitleKey = document.querySelector("meta[name='i18n-title-key']");
      if (docTitleKey) {
        const t = this.t(docTitleKey.getAttribute("content"));
        if (t) document.title = `${t} | KisanSetu`;
      }
    },

    updateSwitcherUI() {
      const isEnglish = currentLang === "en";

      // A. Update all segmented option switchers (.kisan-lang-switcher)
      document.querySelectorAll(".kisan-lang-switcher").forEach(container => {
        const enBtn = container.querySelector('[data-lang="en"]');
        const hiBtn = container.querySelector('[data-lang="hi"]');
        const isDark = container.closest('.bg-slate-900, .bg-slate-950, [data-theme="dark"]');

        if (enBtn && hiBtn) {
          if (isEnglish) {
            // EN is active
            enBtn.className = isDark
              ? "px-2.5 py-1 rounded-md text-xs font-bold bg-teal-600 text-white shadow-xs transition-all cursor-pointer"
              : "px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-600 text-white shadow-xs transition-all cursor-pointer";
            hiBtn.className = isDark
              ? "px-2.5 py-1 rounded-md text-xs font-medium text-slate-400 hover:text-white transition-all cursor-pointer"
              : "px-2.5 py-1 rounded-md text-xs font-medium text-slate-600 hover:text-slate-900 transition-all cursor-pointer";
          } else {
            // HI is active
            hiBtn.className = isDark
              ? "px-2.5 py-1 rounded-md text-xs font-bold bg-teal-600 text-white shadow-xs transition-all cursor-pointer"
              : "px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-600 text-white shadow-xs transition-all cursor-pointer";
            enBtn.className = isDark
              ? "px-2.5 py-1 rounded-md text-xs font-medium text-slate-400 hover:text-white transition-all cursor-pointer"
              : "px-2.5 py-1 rounded-md text-xs font-medium text-slate-600 hover:text-slate-900 transition-all cursor-pointer";
          }
        }
      });

      // B. Update all single toggle buttons (.kisan-lang-btn)
      document.querySelectorAll(".kisan-lang-btn").forEach(btn => {
        const label = isEnglish ? "English (EN)" : "हिन्दी (HI)";
        const title = isEnglish ? "Switch to Hindi / हिन्दी में बदलें" : "Switch to English / अंग्रेजी में बदलें";
        
        const labelSpan = btn.querySelector(".lang-text");
        if (labelSpan) {
          labelSpan.textContent = label;
        } else {
          btn.textContent = `🌐 ${label}`;
        }
        btn.setAttribute("title", title);
        btn.setAttribute("aria-label", `Current language: ${label}. Click to switch.`);
      });

      // C. Update select dropdowns (.kisan-lang-select)
      document.querySelectorAll(".kisan-lang-select").forEach(sel => {
        sel.value = currentLang;
      });
    },

    renderLanguageSwitchButton() {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "kisan-lang-btn px-2.5 py-1.5 rounded-lg text-xs font-bold border border-slate-700 bg-slate-800 text-teal-300 hover:bg-slate-700 transition-all shadow-xs cursor-pointer flex items-center gap-1.5";
      btn.innerHTML = `<span>🌐</span><span class="lang-text">${currentLang === "en" ? "English (EN)" : "हिन्दी (HI)"}</span>`;
      btn.title = currentLang === "en" ? "Switch to Hindi / हिन्दी में बदलें" : "Switch to English / अंग्रेजी में बदलें";
      btn.onclick = () => this.toggleLanguage();
      return btn;
    }
  };

  // Auto apply on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.lang = currentLang;
    KisanI18n.applyTranslations();
    KisanI18n.updateSwitcherUI();
  });

  window.KisanI18n = KisanI18n;
})(window);
