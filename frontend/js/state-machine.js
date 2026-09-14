/**
 * KisanSetu — Deterministic State Machine (Live Mandi Flow)
 * Strict Physical Mandi Cycle (SIH26032):
 * BOOKED -> GATE_SCANNED -> ASSAY_TESTING -> GROSS_WEIGHED -> UNLOADING_BAY -> TARE_WEIGHED -> J_FORM_ISSUED -> DBT_DISPATCHED
 * Grace / Edge States: TRANSIT_DELAYED, STANDBY_OVERDUE, REJECTED_QUALITY, CANCELLED
 */

(function (window) {
  'use strict';

  const STAGES = {
    "BOOKED": {
      key: "BOOKED",
      step: 1,
      titleEn: "Slot Booked & Pass Issued",
      titleHi: "स्लॉट बुक हुआ • गेट पास जारी",
      icon: "📅",
      badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
      accentColor: "#2563eb",
      descriptionEn: "Digital token generated with tamper-evident HMAC QR payload.",
      descriptionHi: "डिजिटल टोकन जारी, गेट पर सत्यापन हेतु तैयार।"
    },
    "TRANSIT_DELAYED": {
      key: "TRANSIT_DELAYED",
      step: 1.2,
      titleEn: "Transit Delayed (+60m Grace Window)",
      titleHi: "रास्ते में देरी • 60 मिनट ग्रेस विंडो",
      icon: "🚨",
      badgeClass: "bg-amber-50 text-amber-900 border-amber-300 font-bold",
      accentColor: "#d97706",
      descriptionEn: "Farmer reported en-route transit delay. +60m arrival buffer granted; slot priority preserved.",
      descriptionHi: "रास्ते में देरी दर्ज। स्लॉट रद्द नहीं हुआ — 60 मिनट का अतिरिक्त समय स्वीकृत।"
    },
    "STANDBY_OVERDUE": {
      key: "STANDBY_OVERDUE",
      step: 1.5,
      titleEn: "Standby Lane (Buffer Overdue)",
      titleHi: "प्रतीक्षा लेन (समय सीमा समाप्त)",
      icon: "⚠️",
      badgeClass: "bg-amber-100 text-amber-900 border-amber-300",
      accentColor: "#d97706",
      descriptionEn: "Vehicle arrived outside ±45m scheduled buffer. Held in standby lane awaiting supervisor admission.",
      descriptionHi: "वाहन निर्धारित समय स्लॉट के बाहर आया। अधीक्षक अनुमति प्रतीक्षारत।"
    },
    "GATE_SCANNED": {
      key: "GATE_SCANNED",
      step: 2,
      titleEn: "Gate Verified & Yard Entry",
      titleHi: "गेट सत्यापन पूर्ण • यार्ड प्रवेश",
      icon: "🚜",
      badgeClass: "bg-teal-50 text-teal-800 border-teal-200",
      accentColor: "#0f766e",
      descriptionEn: "QR code verified at gate; admitted to yard and assigned assay bay.",
      descriptionHi: "गेट पर सत्यापन पूर्ण, परीक्षण बे आवंटित।"
    },
    "ASSAY_TESTING": {
      key: "ASSAY_TESTING",
      step: 3,
      titleEn: "Quality & Moisture Assay",
      titleHi: "गुणवत्ता एवं नमी परीक्षण (Assay Lab)",
      icon: "🧪",
      badgeClass: "bg-purple-50 text-purple-800 border-purple-200",
      accentColor: "#7e22ce",
      descriptionEn: "Grain sample inspected for moisture content & FAQ grade standards.",
      descriptionHi: "नमी और गुणवत्ता का परीक्षण जारी (FCI मानक)।"
    },
    "REJECTED_QUALITY": {
      key: "REJECTED_QUALITY",
      step: 3.5,
      titleEn: "Quality Assay Rejected",
      titleHi: "गुणवत्ता परीक्षण में अस्वीकृत",
      icon: "❌",
      badgeClass: "bg-rose-100 text-rose-800 border-rose-300",
      accentColor: "#e11d48",
      descriptionEn: "Moisture exceeded 12% ceiling. Advised aeration before re-test.",
      descriptionHi: "नमी 12% से अधिक, सुखाने के उपरांत पुनः परीक्षण संभव।"
    },
    "GROSS_WEIGHED": {
      key: "GROSS_WEIGHED",
      step: 4,
      titleEn: "Gross Weighing (Loaded)",
      titleHi: "सकल इलेक्ट्रॉनिक तौल (Gross)",
      icon: "⚖️",
      badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
      accentColor: "#4338ca",
      descriptionEn: "Loaded tractor-trolley weighed on electronic weighbridge (Scale 1).",
      descriptionHi: "लोड वाहन का वजन दर्ज किया गया।"
    },
    "WEIGHBRIDGE_IN": {
      key: "GROSS_WEIGHED",
      step: 4,
      titleEn: "Gross Weighing (Loaded)",
      titleHi: "सकल इलेक्ट्रॉनिक तौल (Gross)",
      icon: "⚖️",
      badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
      accentColor: "#4338ca",
      descriptionEn: "Loaded tractor-trolley weighed on electronic weighbridge (Scale 1).",
      descriptionHi: "लोड वाहन का वजन दर्ज किया गया।"
    },
    "UNLOADING_BAY": {
      key: "UNLOADING_BAY",
      step: 5,
      titleEn: "Unloading Bay / Shed",
      titleHi: "अनलोडिंग शेड • बोरी खालीकरण",
      icon: "📦",
      badgeClass: "bg-amber-50 text-amber-800 border-amber-200",
      accentColor: "#b45309",
      descriptionEn: "Grain sacks unloaded at designated godown storage shed / silo platform.",
      descriptionHi: "निर्धारित गोदाम शेड पर बोरियां खाली की जा रही हैं।"
    },
    "TARE_WEIGHED": {
      key: "TARE_WEIGHED",
      step: 6,
      titleEn: "Tare Weighing (Empty)",
      titleHi: "खाली वाहन तौल (Tare Tare)",
      icon: "🌾",
      badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
      accentColor: "#059669",
      descriptionEn: "Empty vehicle re-weighed on weighbridge (Scale 2) to compute net grain weight.",
      descriptionHi: "खाली ट्रॉली का वजन दर्ज, शुद्ध उपज (Net Weight) की गणना पूर्ण।"
    },
    "WEIGHBRIDGE_OUT": {
      key: "TARE_WEIGHED",
      step: 6,
      titleEn: "Tare Weighing (Empty)",
      titleHi: "खाली वाहन तौल (Tare Tare)",
      icon: "🌾",
      badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
      accentColor: "#059669",
      descriptionEn: "Empty vehicle re-weighed on weighbridge (Scale 2) to compute net grain weight.",
      descriptionHi: "खाली ट्रॉली का वजन दर्ज, शुद्ध उपज की गणना पूर्ण।"
    },
    "J_FORM_ISSUED": {
      key: "J_FORM_ISSUED",
      step: 7,
      titleEn: "Statutory e-J-Form Generated",
      titleHi: "डिजिटल जे-फॉर्म जारी (MSP रसीद)",
      icon: "📜",
      badgeClass: "bg-cyan-50 text-cyan-800 border-cyan-300 font-bold",
      accentColor: "#0891b2",
      descriptionEn: "Official APMC Form 'J' procurement receipt issued with MSP rate, deductions & bank details.",
      descriptionHi: "कृषि उपज मंडी नियम अंतर्गत कानूनी जे-फॉर्म खरीद रसीद जारी।"
    },
    "DBT_DISPATCHED": {
      key: "DBT_DISPATCHED",
      step: 8,
      titleEn: "DBT Payment Dispatched",
      titleHi: "प्रत्यक्ष लाभ अंतरण (DBT भुगतान पूर्ण)",
      icon: "🏦",
      badgeClass: "bg-emerald-100 text-emerald-900 border-emerald-400 font-bold",
      accentColor: "#15803d",
      descriptionEn: "MSP funds disbursed directly to farmer bank account via PFMS/DBT.",
      descriptionHi: "किसान के बैंक खाते में सीधा MSP भुगतान क्रेडिट।"
    },
    "CANCELLED": {
      key: "CANCELLED",
      step: 0,
      titleEn: "Cancelled",
      titleHi: "रद्द (Cancelled)",
      icon: "🚫",
      badgeClass: "bg-slate-100 text-slate-600 border-slate-200",
      accentColor: "#64748b",
      descriptionEn: "Booking slot was cancelled.",
      descriptionHi: "स्लॉट बुकिंग रद्द कर दी गई है।"
    }
  };

  const PIPELINE_STEPS = [
    "BOOKED",
    "GATE_SCANNED",
    "ASSAY_TESTING",
    "GROSS_WEIGHED",
    "UNLOADING_BAY",
    "TARE_WEIGHED",
    "J_FORM_ISSUED",
    "DBT_DISPATCHED"
  ];

  const ALLOWED_TRANSITIONS = {
    "BOOKED": ["TRANSIT_DELAYED", "GATE_SCANNED", "STANDBY_OVERDUE", "CANCELLED"],
    "TRANSIT_DELAYED": ["GATE_SCANNED", "STANDBY_OVERDUE", "CANCELLED"],
    "STANDBY_OVERDUE": ["GATE_SCANNED", "CANCELLED"],
    "GATE_SCANNED": ["ASSAY_TESTING", "CANCELLED"],
    "ASSAY_TESTING": ["GROSS_WEIGHED", "WEIGHBRIDGE_IN", "REJECTED_QUALITY", "CANCELLED"],
    "REJECTED_QUALITY": ["ASSAY_TESTING", "CANCELLED"],
    "GROSS_WEIGHED": ["UNLOADING_BAY", "CANCELLED"],
    "WEIGHBRIDGE_IN": ["UNLOADING_BAY", "WEIGHBRIDGE_OUT", "CANCELLED"],
    "UNLOADING_BAY": ["TARE_WEIGHED", "WEIGHBRIDGE_OUT", "CANCELLED"],
    "TARE_WEIGHED": ["J_FORM_ISSUED", "DBT_DISPATCHED"],
    "WEIGHBRIDGE_OUT": ["TARE_WEIGHED", "J_FORM_ISSUED", "DBT_DISPATCHED"],
    "J_FORM_ISSUED": ["DBT_DISPATCHED"],
    "DBT_DISPATCHED": [],
    "CANCELLED": []
  };

  const KisanStateMachine = {
    STAGES,
    PIPELINE_STEPS,
    ALLOWED_TRANSITIONS,

    getStage(stageKey) {
      const k = (stageKey || "BOOKED").toUpperCase();
      // Handle aliases
      if (k === "WEIGHBRIDGE_IN") return STAGES["GROSS_WEIGHED"];
      if (k === "WEIGHBRIDGE_OUT") return STAGES["TARE_WEIGHED"];
      return STAGES[k] || STAGES["BOOKED"];
    },

    canTransition(currentStage, targetStage) {
      const c = (currentStage || "BOOKED").toUpperCase();
      const t = (targetStage || "").toUpperCase();
      const allowed = ALLOWED_TRANSITIONS[c] || [];
      return allowed.includes(t);
    },

    renderStageBadge(stageKey) {
      const s = this.getStage(stageKey);
      return `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${s.badgeClass}">
          <span>${s.icon}</span>
          <span>${s.titleHi}</span>
        </span>
      `;
    },

    renderProgressBar(currentStageKey) {
      const activeStage = this.getStage(currentStageKey);
      let stepKey = activeStage.key;
      if (stepKey === "TRANSIT_DELAYED" || stepKey === "STANDBY_OVERDUE") {
        stepKey = "BOOKED";
      } else if (stepKey === "REJECTED_QUALITY") {
        stepKey = "ASSAY_TESTING";
      }

      const activeStepIndex = PIPELINE_STEPS.indexOf(stepKey);

      const stepsHtml = PIPELINE_STEPS.map((key, index) => {
        const stage = STAGES[key];
        const isCompleted = activeStepIndex > index || activeStage.key === "DBT_DISPATCHED";
        const isCurrent = activeStage.key === key && activeStage.key !== "DBT_DISPATCHED";

        let dotClass = "bg-slate-200 text-slate-500 border-slate-300";
        let textClass = "text-slate-400";

        if (isCompleted) {
          dotClass = "bg-emerald-600 text-white border-emerald-600 ring-2 ring-emerald-100";
          textClass = "text-emerald-800 font-bold";
        } else if (isCurrent) {
          dotClass = "bg-[#15803d] text-white border-[#15803d] ring-4 ring-emerald-200 animate-pulse";
          textClass = "text-[#15803d] font-black";
        }

        return `
          <div class="flex-1 flex flex-col items-center relative text-center min-w-[65px]">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-all ${dotClass} z-10 bg-white">
              ${isCompleted ? '✔' : stage.icon}
            </div>
            <div class="mt-1 text-[10px] leading-tight ${textClass}">
              <div class="font-bold truncate max-w-[75px]">${stage.titleHi.split('•')[0].trim()}</div>
            </div>
          </div>
        `;
      }).join(`
        <div class="flex-1 h-0.5 bg-slate-200 -mt-6 relative z-0 min-w-[8px]">
          <div class="h-full bg-emerald-600 transition-all duration-500" style="width: ${Math.max(0, Math.min(100, (activeStepIndex / (PIPELINE_STEPS.length - 1)) * 100))}%;"></div>
        </div>
      `);

      return `
        <div class="p-4 bg-white rounded-xl border border-slate-200 shadow-xs">
          <div class="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-ping"></span>
              <span class="text-xs font-bold text-slate-800">भौतिक मंडी चक्र (Physical Mandi Cycle)</span>
            </div>
            <span class="text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
              चरण ${activeStage.step} of 8 • ${activeStage.titleEn.split('(')[0].trim()}
            </span>
          </div>
          <div class="flex items-center justify-between overflow-x-auto py-2">
            ${stepsHtml}
          </div>
        </div>
      `;
    },

    async transitionStage(bookingId, nextStage, metadata = {}) {
      try {
        const res = await fetch("/api/v1/queue/transition", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            booking_id: bookingId,
            next_stage: nextStage,
            metadata: metadata
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP Error ${res.status}`);
        }
        const data = await res.json();
        
        // Dispatch across local tab event bus
        if (window.KisanEventBus) {
          window.KisanEventBus.publish("STAGE_TRANSITION", data);
        }
        return data;
      } catch (err) {
        console.warn("KisanStateMachine.transitionStage fallback:", err.message);
        throw err;
      }
    }
  };

  window.KisanStateMachine = KisanStateMachine;
})(window);
