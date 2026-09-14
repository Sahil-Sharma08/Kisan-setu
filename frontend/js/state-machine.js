/**
 * KisanSetu — Deterministic State Machine (Live Pipeline Flow)
 * Strict deterministic lifecycle:
 * BOOKED -> GATE_SCANNED -> ASSAY_TESTING -> WEIGHBRIDGE_IN -> WEIGHBRIDGE_OUT -> DBT_DISPATCHED
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
    "STANDBY_OVERDUE": {
      key: "STANDBY_OVERDUE",
      step: 1.5,
      titleEn: "Standby (Buffer Overdue)",
      titleHi: "प्रतीक्षा लेन (समय सीमा समाप्त)",
      icon: "⚠️",
      badgeClass: "bg-amber-100 text-amber-900 border-amber-300",
      accentColor: "#d97706",
      descriptionEn: "Vehicle arrived outside ±45m scheduled buffer. Held in standby lane.",
      descriptionHi: "वाहन निर्धारित समय स्लॉट के बाहर आया। ऑपरेटर अनुमति प्रतीक्षारत।"
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
    "WEIGHBRIDGE_IN": {
      key: "WEIGHBRIDGE_IN",
      step: 4,
      titleEn: "Weighbridge In (Gross Weight)",
      titleHi: "वेईब्रिज इन (सकल भार - Gross)",
      icon: "⚖️",
      badgeClass: "bg-indigo-50 text-indigo-800 border-indigo-200",
      accentColor: "#4338ca",
      descriptionEn: "Loaded tractor-trolley weighed on calibrated electronic weighbridge.",
      descriptionHi: "लोड वाहन का वजन दर्ज किया जा रहा है।"
    },
    "WEIGHBRIDGE_OUT": {
      key: "WEIGHBRIDGE_OUT",
      step: 5,
      titleEn: "Weighbridge Out (Net Tare)",
      titleHi: "वेईब्रिज आउट (खाली वजन - Net Tare)",
      icon: "🌾",
      badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
      accentColor: "#059669",
      descriptionEn: "Empty vehicle re-weighed to determine net grain weight.",
      descriptionHi: "खाली ट्रॉली का वजन दर्ज, शुद्ध उपज की गणना पूर्ण।"
    },
    "DBT_DISPATCHED": {
      key: "DBT_DISPATCHED",
      step: 6,
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
    "WEIGHBRIDGE_IN",
    "WEIGHBRIDGE_OUT",
    "DBT_DISPATCHED"
  ];

  const ALLOWED_TRANSITIONS = {
    "BOOKED": ["GATE_SCANNED", "STANDBY_OVERDUE", "CANCELLED"],
    "STANDBY_OVERDUE": ["GATE_SCANNED", "CANCELLED"],
    "GATE_SCANNED": ["ASSAY_TESTING", "CANCELLED"],
    "ASSAY_TESTING": ["WEIGHBRIDGE_IN", "REJECTED_QUALITY", "CANCELLED"],
    "REJECTED_QUALITY": ["ASSAY_TESTING", "CANCELLED"],
    "WEIGHBRIDGE_IN": ["WEIGHBRIDGE_OUT"],
    "WEIGHBRIDGE_OUT": ["DBT_DISPATCHED"],
    "DBT_DISPATCHED": [],
    "CANCELLED": []
  };

  const KisanStateMachine = {
    STAGES,
    PIPELINE_STEPS,
    ALLOWED_TRANSITIONS,

    getStage(stageKey) {
      const k = (stageKey || "BOOKED").toUpperCase();
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
      const activeStepIndex = PIPELINE_STEPS.indexOf(activeStage.key);

      const stepsHtml = PIPELINE_STEPS.map((key, index) => {
        const stage = STAGES[key];
        const isCompleted = activeStepIndex > index || activeStage.key === "DBT_DISPATCHED";
        const isCurrent = activeStage.key === key && activeStage.key !== "DBT_DISPATCHED";
        const isUpcoming = !isCompleted && !isCurrent;

        let dotClass = "bg-slate-200 text-slate-500 border-slate-300";
        let textClass = "text-slate-400";
        let checkMark = index + 1;

        if (isCompleted) {
          dotClass = "bg-emerald-600 text-white border-emerald-600 ring-2 ring-emerald-100";
          textClass = "text-emerald-800 font-bold";
          checkMark = "✔";
        } else if (isCurrent) {
          dotClass = "bg-[#15803d] text-white border-[#15803d] ring-4 ring-emerald-200 animate-pulse";
          textClass = "text-[#15803d] font-black";
        }

        return `
          <div class="flex-1 flex flex-col items-center relative text-center min-w-[70px]">
            <div class="w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-all ${dotClass} z-10 bg-white">
              ${isCompleted ? '✔' : stage.icon}
            </div>
            <div class="mt-1.5 text-[11px] leading-tight ${textClass}">
              <div class="font-bold">${stage.titleHi.split('•')[0].trim()}</div>
              <div class="text-[9px] text-slate-400 font-normal hidden sm:block">${stage.titleEn.split('(')[0].trim()}</div>
            </div>
          </div>
        `;
      }).join(`
        <div class="flex-1 h-0.5 bg-slate-200 -mt-7 relative z-0">
          <div class="h-full bg-emerald-600 transition-all duration-500" style="width: ${Math.max(0, Math.min(100, (activeStepIndex / (PIPELINE_STEPS.length - 1)) * 100))}%;"></div>
        </div>
      `);

      return `
        <div class="p-4 sm:p-5 bg-white rounded-xl border border-slate-200 shadow-xs">
          <div class="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-ping"></span>
              <span class="text-xs font-bold text-slate-800">लाइव प्रगति स्थिति (Live Pipeline Progress)</span>
            </div>
            <span class="text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
              चरण ${activeStage.step} of 6
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
