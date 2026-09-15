/**
 * KisanSetu — Kisan Vani (किसान वाणी) AI Voice Assistant & Chatbot
 * Non-blocking floating popup widget with Speech-to-Text (STT) & Text-to-Speech (TTS).
 * Answers questions about Crop Prices (MSP), Procurement Starting Dates/Schedules,
 * Mandi Centers, Slot Booking, Live Queues, and Farmer Grievance Redressal.
 */

(function () {
  'use strict';

  // Prevent multiple initializations
  if (window.KisanVoiceAssistant) return;

  // Determine base path for relative URLs
  function getBasePath() {
    const p = window.location.pathname;
    if (p.includes('/farmer/') || p.includes('/admin/') || p.includes('/operator/') || p.includes('/pages/')) {
      return '../';
    }
    return './';
  }

  const BASE = getBasePath();

  // Assistant State
  const State = {
    isOpen: false,
    isMinimized: false,
    isListening: false,
    isSpeaking: false,
    ttsEnabled: true,
    hasSpokenWelcome: false,
    welcomeAudioText: '',
    currentLanguage: 'hi-IN', // 'hi-IN' or 'en-IN'
    activeUtterance: null,
    recognition: null,
    messages: []
  };

  // Offline/Fallback Knowledge for 100% Reliability
  const LOCAL_KNOWLEDGE = {
    wheat: {
      crop: "गेहूं (Wheat Grade A)",
      msp: "₹2,275 / क्विंटल",
      demo: "₹2,425 / क्विंटल",
      start: "1 अप्रैल 2026",
      end: "15 मई 2026",
      season: "रबी 2026",
      moisture: "12% अधिकतम",
      desc: "गेहूं की सरकारी खरीद 1 अप्रैल से 15 मई 2026 तक चलेगी। न्यूनतम समर्थन मूल्य ₹2,275 प्रति क्विंटल है।"
    },
    mustard: {
      crop: "सरसों (Mustard)",
      msp: "₹5,650 / क्विंटल",
      demo: "₹5,650 / क्विंटल",
      start: "15 मार्च 2026",
      end: "30 अप्रैल 2026",
      season: "रबी 2026",
      moisture: "9% अधिकतम",
      desc: "सरसों की खरीद 15 मार्च 2026 से शुरू हो चुकी है और 30 अप्रैल तक चलेगी। एमएसपी ₹5,650 प्रति क्विंटल है।"
    },
    gram: {
      crop: "चना (Gram)",
      msp: "₹5,440 / क्विंटल",
      demo: "₹5,440 / क्विंटल",
      start: "1 अप्रैल 2026",
      end: "15 मई 2026",
      season: "रबी 2026",
      moisture: "10% अधिकतम",
      desc: "चने की खरीद 1 अप्रैल से 15 मई 2026 तक निर्धारित है। समर्थन मूल्य ₹5,440 प्रति क्विंटल है।"
    },
    barley: {
      crop: "जौ (Barley)",
      msp: "₹1,850 / क्विंटल",
      demo: "₹1,980 / क्विंटल",
      start: "1 अप्रैल 2026",
      end: "15 मई 2026",
      season: "रबी 2026",
      moisture: "12% अधिकतम",
      desc: "जौ की खरीद 1 अप्रैल से 15 मई 2026 तक चलेगी। एमएसपी ₹1,850 प्रति क्विंटल है।"
    },
    paddy: {
      crop: "धान (Paddy Common)",
      msp: "₹2,183 / क्विंटल",
      demo: "₹2,320 / क्विंटल",
      start: "1 अक्टूबर 2026",
      end: "15 नवंबर 2026",
      season: "खरीफ 2026",
      moisture: "17% अधिकतम",
      desc: "धान की सरकारी खरीद 1 अक्टूबर 2026 से 15 नवंबर 2026 तक चलेगी। एमएसपी ₹2,183 प्रति क्विंटल है।"
    },
    bajra: {
      crop: "बाजरा (Bajra)",
      msp: "₹2,500 / क्विंटल",
      demo: "₹2,625 / क्विंटल",
      start: "1 अक्टूबर 2026",
      end: "15 नवंबर 2026",
      season: "खरीफ 2026",
      moisture: "12% अधिकतम",
      desc: "बाजरा खरीद 1 अक्टूबर से 15 नवंबर 2026 तक होगी। समर्थन मूल्य ₹2,500 प्रति क्विंटल है।"
    },
    cotton: {
      crop: "कपास (Cotton)",
      msp: "₹6,620 / क्विंटल",
      demo: "₹7,122 / क्विंटल",
      start: "15 अक्टूबर 2026",
      end: "31 दिसंबर 2026",
      season: "खरीफ 2026",
      moisture: "8.5% अधिकतम",
      desc: "कपास खरीद 15 अक्टूबर 2026 से 31 दिसंबर 2026 तक होगी। एमएसपी ₹6,620 प्रति क्विंटल है।"
    }
  };

  // UI Elements container
  let UI = {};

  // -------------------------------------------------------------
  // 1. INJECT STYLESHEET IF MISSING
  // -------------------------------------------------------------
  function ensureStylesheet() {
    const existing = document.getElementById('kisan-voice-assistant-css');
    if (!existing) {
      const link = document.createElement('link');
      link.id = 'kisan-voice-assistant-css';
      link.rel = 'stylesheet';
      link.href = BASE + 'css/voice-assistant.css';
      document.head.appendChild(link);
    }
  }

  // -------------------------------------------------------------
  // 2. INJECT WIDGET DOM
  // -------------------------------------------------------------
  function createWidgetDOM() {
    ensureStylesheet();

    // Launcher container
    const launcherContainer = document.createElement('div');
    launcherContainer.className = 'kv-launcher-container';
    launcherContainer.id = 'kv-launcher-root';
    launcherContainer.innerHTML = `
      <button type="button" class="kv-launcher-btn" id="kv-launcher-btn" aria-label="किसान वाणी AI Voice Assistant">
        <div class="kv-launcher-pulse"></div>
        <div class="kv-launcher-avatar">
          <span>🌾</span>
        </div>
        <div class="kv-launcher-text-box">
          <div class="kv-launcher-title">
            <span>किसान वाणी</span>
            <span class="kv-launcher-mic-badge">AI Voice</span>
          </div>
          <span class="kv-launcher-sub">भाव, तारीखें व मंडी सहायता</span>
        </div>
      </button>
    `;

    // Popup window
    const popupWindow = document.createElement('div');
    popupWindow.className = 'kv-popup-window';
    popupWindow.id = 'kv-popup-window';
    popupWindow.setAttribute('role', 'dialog');
    popupWindow.setAttribute('aria-label', 'Kisan Vani Chatbot');
    popupWindow.innerHTML = `
      <!-- Header -->
      <div class="kv-header" id="kv-header">
        <div class="kv-header-profile">
          <div class="kv-header-avatar">
            <span>🌾</span>
            <div class="kv-header-online-dot"></div>
          </div>
          <div class="kv-header-title-box">
            <div class="kv-header-title">
              <span>किसान वाणी</span>
              <span class="kv-header-badge">AI Assistant</span>
              <div class="kv-equalizer" id="kv-header-equalizer" style="display: none;">
                <div class="kv-eq-bar"></div>
                <div class="kv-eq-bar"></div>
                <div class="kv-eq-bar"></div>
                <div class="kv-eq-bar"></div>
              </div>
            </div>
            <span class="kv-header-sub">भाव • खरीद तारीखें • स्लॉट सहायता</span>
          </div>
        </div>
        <div class="kv-header-actions">
          <button type="button" class="kv-icon-btn" id="kv-tts-toggle-btn" title="आवाज ऑन/ऑफ (Toggle Audio)">
            🔊
          </button>
          <button type="button" class="kv-icon-btn" id="kv-reset-btn" title="बातचीत रीसेट करें (Clear)">
            🔄
          </button>
          <button type="button" class="kv-icon-btn" id="kv-minimize-btn" title="छोटा करें (Minimize)">
            ➖
          </button>
          <button type="button" class="kv-icon-btn" id="kv-close-btn" title="बंद करें (Close)">
            ✕
          </button>
        </div>
      </div>

      <!-- Status banner (Listening / Speaking) -->
      <div class="kv-status-banner" id="kv-status-banner" style="display: none;">
        <span id="kv-status-text">🎤 सुन रहे हैं... कृपया बोलिए</span>
        <button type="button" id="kv-status-cancel-btn" style="background:none;border:none;cursor:pointer;font-weight:700;color:inherit;">✕</button>
      </div>

      <!-- Chat Body -->
      <div class="kv-chat-body" id="kv-chat-body">
        <!-- Messages will be injected here -->
      </div>

      <!-- Footer / Input -->
      <div class="kv-chat-footer">
        <div class="kv-input-row">
          <button type="button" class="kv-mic-btn" id="kv-mic-btn" title="माइक से बोलें (Click to Speak)">
            🎙️
          </button>
          <input type="text" class="kv-text-input" id="kv-text-input" placeholder="अपना सवाल पूछें या माइक दबाकर बोलें..." autocomplete="off" />
          <button type="button" class="kv-send-btn" id="kv-send-btn" title="भेजें (Send)">
            ➤
          </button>
        </div>
        <div class="kv-footer-sub">
          <span class="kv-lang-indicator">
            <span>🇮🇳</span> <span id="kv-lang-label">हिन्दी / English</span>
          </span>
          <span>वेबसाइट का साथ-साथ प्रयोग करें 🌐</span>
        </div>
      </div>
    `;

    document.body.appendChild(launcherContainer);
    document.body.appendChild(popupWindow);

    // Bind UI references
    UI = {
      launcher: document.getElementById('kv-launcher-btn'),
      popup: document.getElementById('kv-popup-window'),
      chatBody: document.getElementById('kv-chat-body'),
      textInput: document.getElementById('kv-text-input'),
      sendBtn: document.getElementById('kv-send-btn'),
      micBtn: document.getElementById('kv-mic-btn'),
      closeBtn: document.getElementById('kv-close-btn'),
      minimizeBtn: document.getElementById('kv-minimize-btn'),
      resetBtn: document.getElementById('kv-reset-btn'),
      ttsToggleBtn: document.getElementById('kv-tts-toggle-btn'),
      statusBanner: document.getElementById('kv-status-banner'),
      statusText: document.getElementById('kv-status-text'),
      statusCancelBtn: document.getElementById('kv-status-cancel-btn'),
      headerEqualizer: document.getElementById('kv-header-equalizer')
    };

    bindEvents();
    initSpeechRecognition();
    showWelcomeMessage();
  }

  // -------------------------------------------------------------
  // 3. SPEECH RECOGNITION (STT) SETUP
  // -------------------------------------------------------------
  function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("KisanVoiceAssistant: Web Speech Recognition API not supported in this browser.");
      if (UI.micBtn) {
        UI.micBtn.title = "इस ब्राउज़र में वॉइस इनपुट समर्थित नहीं है (Type instead)";
      }
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = State.currentLanguage;

    rec.onstart = () => {
      State.isListening = true;
      UI.micBtn.classList.add('kv-listening');
      UI.statusBanner.className = 'kv-status-banner kv-listening';
      UI.statusBanner.style.display = 'flex';
      UI.statusText.textContent = '🎤 सुन रहे हैं... कृपया बोलिए (Listening...)';
      stopSpeaking();
    };

    rec.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }

      if (interim) {
        UI.textInput.value = interim;
      }
      if (final) {
        UI.textInput.value = final;
        stopListening();
        submitQuery(final);
      }
    };

    rec.onerror = (event) => {
      console.warn("Speech recognition error:", event.error);
      stopListening();
      if (event.error === 'not-allowed') {
        alert("माइक्रोफ़ोन अनुमति अस्वीकार कर दी गई है। कृपया ब्राउज़र सेटिंग्स में माइक्रोफ़ोन की अनुमति दें।");
      }
    };

    rec.onend = () => {
      stopListening();
    };

    State.recognition = rec;
  }

  function startListening() {
    if (!State.recognition) {
      alert("आपके ब्राउज़र में वॉइस रिकॉग्निशन समर्थित नहीं है। कृपया लिखकर सवाल पूछें।");
      return;
    }
    try {
      State.recognition.lang = State.currentLanguage;
      State.recognition.start();
    } catch (err) {
      console.warn("Failed to start speech recognition:", err);
      stopListening();
    }
  }

  function stopListening() {
    State.isListening = false;
    if (UI.micBtn) UI.micBtn.classList.remove('kv-listening');
    if (UI.statusBanner && !State.isSpeaking) UI.statusBanner.style.display = 'none';
    if (State.recognition) {
      try {
        State.recognition.abort();
      } catch (e) {
        try { State.recognition.stop(); } catch (err) {}
      }
    }
  }

  // -------------------------------------------------------------
  // 4. TEXT TO SPEECH (TTS) SETUP
  // -------------------------------------------------------------
  function speakText(text) {
    // Only speak when assistant popup is open and TTS is enabled
    if (!State.isOpen) return;
    if (!State.ttsEnabled || !window.speechSynthesis) return;

    stopSpeaking();

    // Clean markdown characters for pleasant speech
    const cleanSpeech = text
      .replace(/[*_#`~[\]()•]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanSpeech) return;

    const utterance = new SpeechSynthesisUtterance(cleanSpeech);
    utterance.lang = State.currentLanguage;
    utterance.rate = 0.95; // Friendly cadence
    utterance.pitch = 1.0;

    // Pick a natural Indian/Hindi voice if available
    const voices = window.speechSynthesis.getVoices();
    const hindiVoice = voices.find(v => v.lang && (v.lang.startsWith('hi') || v.lang.includes('IN')));
    if (hindiVoice) {
      utterance.voice = hindiVoice;
    }

    utterance.onstart = () => {
      // If closed between trigger and speech start, halt immediately
      if (!State.isOpen) {
        stopSpeaking();
        return;
      }
      State.isSpeaking = true;
      if (UI.headerEqualizer) UI.headerEqualizer.style.display = 'inline-flex';
      if (UI.statusBanner) {
        UI.statusBanner.className = 'kv-status-banner kv-speaking';
        UI.statusBanner.style.display = 'flex';
        UI.statusText.innerHTML = '🔊 किसान वाणी बोल रही है... (Playing Voice)';
      }
    };

    utterance.onend = () => {
      State.isSpeaking = false;
      if (UI.headerEqualizer) UI.headerEqualizer.style.display = 'none';
      if (UI.statusBanner && !State.isListening) UI.statusBanner.style.display = 'none';
      document.querySelectorAll('.kv-read-btn.kv-playing').forEach(btn => {
        btn.classList.remove('kv-playing');
        btn.innerHTML = '🔊 सुनो (Listen)';
      });
    };

    utterance.onerror = () => {
      State.isSpeaking = false;
      if (UI.headerEqualizer) UI.headerEqualizer.style.display = 'none';
      if (UI.statusBanner && !State.isListening) UI.statusBanner.style.display = 'none';
      document.querySelectorAll('.kv-read-btn.kv-playing').forEach(btn => {
        btn.classList.remove('kv-playing');
        btn.innerHTML = '🔊 सुनो (Listen)';
      });
    };

    State.activeUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    State.isSpeaking = false;

    if (State.activeUtterance) {
      State.activeUtterance.onstart = null;
      State.activeUtterance.onend = null;
      State.activeUtterance.onerror = null;
      State.activeUtterance = null;
    }

    if (window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
        // Chromium flush workaround for pending or active speech
        if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
          window.speechSynthesis.pause();
          window.speechSynthesis.cancel();
          window.speechSynthesis.resume();
          window.speechSynthesis.cancel();
        }
      } catch (e) {
        console.warn("speechSynthesis cancel error:", e);
      }
    }

    if (UI.headerEqualizer) UI.headerEqualizer.style.display = 'none';
    if (UI.statusBanner && !State.isListening) UI.statusBanner.style.display = 'none';
    document.querySelectorAll('.kv-read-btn.kv-playing').forEach(btn => {
      btn.classList.remove('kv-playing');
      btn.innerHTML = '🔊 सुनो (Listen)';
    });
  }

  // -------------------------------------------------------------
  // 5. MESSAGE RENDERING & CHAT UI
  // -------------------------------------------------------------
  function getTimeString() {
    const d = new Date();
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatMarkdown(text) {
    let html = text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n• /g, '<br>• ')
      .replace(/\n/g, '<br>');
    return `<p>${html}</p>`;
  }

  function appendUserMessage(text) {
    const msgEl = document.createElement('div');
    msgEl.className = 'kv-msg kv-msg-user';
    msgEl.innerHTML = `
      <div class="kv-bubble">${text}</div>
      <span class="kv-msg-time">${getTimeString()}</span>
    `;
    UI.chatBody.appendChild(msgEl);
    scrollToBottom();
  }

  function appendBotMessage(data, autoSpeak = true) {
    const msgEl = document.createElement('div');
    msgEl.className = 'kv-msg kv-msg-bot';

    // Format body
    const bodyHtml = formatMarkdown(data.response);

    // Format action chips
    let actionChipsHtml = '';
    if (data.quick_actions && data.quick_actions.length > 0) {
      actionChipsHtml = `
        <div class="kv-action-chips">
          ${data.quick_actions.map(act => {
            let targetUrl = act.url;
            if (!targetUrl.startsWith('http') && !targetUrl.startsWith('#')) {
              targetUrl = BASE + targetUrl;
            }
            return `<a href="${targetUrl}" class="kv-action-link">${act.label} &rarr;</a>`;
          }).join('')}
        </div>
      `;
    }

    const audioTextEscaped = (data.audio_text || data.response).replace(/"/g, '&quot;');

    msgEl.innerHTML = `
      <div class="kv-bubble">
        ${bodyHtml}
        ${actionChipsHtml}
        <button type="button" class="kv-read-btn" data-audio="${audioTextEscaped}">
          🔊 सुनो (Listen)
        </button>
      </div>
      <span class="kv-msg-time">किसान वाणी • ${getTimeString()}</span>
    `;

    UI.chatBody.appendChild(msgEl);

    // Bind speech replay button
    const readBtn = msgEl.querySelector('.kv-read-btn');
    readBtn.addEventListener('click', () => {
      if (readBtn.classList.contains('kv-playing')) {
        stopSpeaking();
      } else {
        document.querySelectorAll('.kv-read-btn.kv-playing').forEach(b => {
          b.classList.remove('kv-playing');
          b.innerHTML = '🔊 सुनो (Listen)';
        });
        readBtn.classList.add('kv-playing');
        readBtn.innerHTML = '⏹️ रोकें (Stop)';
        speakText(data.audio_text || data.response);
      }
    });

    // Render suggestions if present
    if (data.suggestions && data.suggestions.length > 0) {
      appendSuggestionChips(data.suggestions);
    }

    scrollToBottom();

    // Auto speak ONLY if permitted, popup is currently open, and TTS enabled
    if (autoSpeak && State.isOpen && State.ttsEnabled && data.audio_text) {
      speakText(data.audio_text);
    }
  }

  function appendSuggestionChips(suggestions) {
    const existing = UI.chatBody.querySelector('.kv-quick-prompts-dynamic');
    if (existing) existing.remove();

    const container = document.createElement('div');
    container.className = 'kv-quick-prompts kv-quick-prompts-dynamic';
    container.innerHTML = `
      <div class="kv-prompts-title">सुझाए गए प्रश्न (Suggested Queries):</div>
      <div class="kv-prompts-grid">
        ${suggestions.map(s => `<button type="button" class="kv-prompt-chip">${s}</button>`).join('')}
      </div>
    `;

    container.querySelectorAll('.kv-prompt-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        submitQuery(chip.textContent.trim());
      });
    });

    UI.chatBody.appendChild(container);
    scrollToBottom();
  }

  function showWelcomeMessage() {
    let farmerName = "किसान भाई";
    if (window.KisanAuth && window.KisanAuth.getCurrentUser()) {
      farmerName = window.KisanAuth.getCurrentUser().name || farmerName;
    }

    const welcomeData = {
      response: `**नमस्ते ${farmerName}! 🙏 मैं 'किसान वाणी' (Kisan Vani) आपकी डिजिटल कृषि सहायिका हूँ।**\n\n` +
        `मैं आपकी निम्न विषयों में मदद कर सकती हूँ:\n` +
        `• 🌾 **फसलों के एमएसपी भाव व मंडी दरें**\n` +
        `• 📅 **सरकारी खरीद शुरू होने की तारीखें (Procurement Schedule)**\n` +
        `• 📍 **नजदीकी खरीद केंद्र व वर्तमान भीड़ की स्थिति**\n` +
        `• ⚡ **डिजिटल टोकन व समय स्लॉट बुकिंग**\n` +
        `• 💳 **भुगतान (DBT) प्रक्रिया व शिकायत निवारण**\n\n` +
        `*आप सीधे माइक दबाकर बोल सकते हैं या नीचे दिए गए विकल्पों में से चुनें।*`,
      audio_text: `नमस्ते ${farmerName}! मैं किसान वाणी हूँ। आप मुझसे फसलों के भाव, खरीद की तारीखें, नजदीकी मंडी और स्लॉट बुकिंग के बारे में पूछ सकते हैं।`,
      quick_actions: [
        { label: "🌾 फसलों के भाव (MSP)", url: "farmer/centers.html" },
        { label: "📍 नजदीकी खरीद केंद्र", url: "farmer/centers.html" },
        { label: "⚡ स्लॉट बुक करें", url: "farmer/booking.html" }
      ],
      suggestions: [
        "गेहूं का एमएसपी भाव क्या है?",
        "सरसों की खरीद कब शुरू होगी?",
        "करनाल मंडी में कितनी भीड़ है?",
        "टोकन कैसे बुक करें?",
        "पेमेंट कितने दिन में आएगा?"
      ]
    };

    State.welcomeAudioText = welcomeData.audio_text;
    // Render the initial welcome message without auto-playing audio
    appendBotMessage(welcomeData, false);
  }

  function scrollToBottom() {
    setTimeout(() => {
      UI.chatBody.scrollTop = UI.chatBody.scrollHeight;
    }, 50);
  }

  // -------------------------------------------------------------
  // 6. QUERY EXECUTION (API + LOCAL ENGINE FALLBACK)
  // -------------------------------------------------------------
  async function submitQuery(queryText) {
    if (!queryText || !queryText.trim()) return;

    const cleanQuery = queryText.trim();
    appendUserMessage(cleanQuery);
    UI.textInput.value = '';

    // Show loading indicator
    const loadingEl = document.createElement('div');
    loadingEl.className = 'kv-msg kv-msg-bot kv-loading-indicator';
    loadingEl.innerHTML = `
      <div class="kv-bubble" style="color: #64748b; font-style: italic;">
        <span>🌾 उत्तर तैयार किया जा रहा है...</span>
      </div>
    `;
    UI.chatBody.appendChild(loadingEl);
    scrollToBottom();

    try {
      // 1. Attempt FastAPI backend call
      const res = await fetch('/api/v1/assistant/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: cleanQuery,
          language: State.currentLanguage.startsWith('hi') ? 'hi' : 'en',
          user_id: window.KisanAuth?.getCurrentUser()?.id || null,
          current_page: window.location.pathname
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      loadingEl.remove();
      appendBotMessage(data, State.isOpen);

    } catch (err) {
      console.warn("KisanVoiceAssistant: Backend query fallback triggered:", err.message);
      loadingEl.remove();

      // 2. Intelligent local fallback engine
      const localResp = processLocalQuery(cleanQuery);
      appendBotMessage(localResp, State.isOpen);
    }
  }

  function processLocalQuery(q) {
    const qLower = q.toLowerCase();

    // Check crop
    let matchedCropKey = null;
    if (qLower.includes('गेहूं') || qLower.includes('wheat') || qLower.includes('gehu')) matchedCropKey = 'wheat';
    else if (qLower.includes('सरसों') || qLower.includes('mustard') || qLower.includes('sarson')) matchedCropKey = 'mustard';
    else if (qLower.includes('चना') || qLower.includes('gram') || qLower.includes('chana')) matchedCropKey = 'gram';
    else if (qLower.includes('जौ') || qLower.includes('barley')) matchedCropKey = 'barley';
    else if (qLower.includes('धान') || qLower.includes('चावल') || qLower.includes('paddy') || qLower.includes('rice')) matchedCropKey = 'paddy';
    else if (qLower.includes('बाजरा') || qLower.includes('bajra')) matchedCropKey = 'bajra';
    else if (qLower.includes('कपास') || qLower.includes('cotton')) matchedCropKey = 'cotton';

    // 1. Dates query
    if (qLower.includes('तारीख') || qLower.includes('date') || qLower.includes('कब') || qLower.includes('shuru') || qLower.includes('schedule')) {
      if (matchedCropKey && LOCAL_KNOWLEDGE[matchedCropKey]) {
        const k = LOCAL_KNOWLEDGE[matchedCropKey];
        return {
          response: `📅 **${k.crop} की खरीद समय-सारणी (${k.season})**:\n\n` +
            `• **खरीद शुरू होने की तारीख:** **${k.start}**\n` +
            `• **खरीद समाप्त होने की तारीख:** **${k.end}**\n` +
            `• **न्यूनतम समर्थन मूल्य (MSP):** **${k.msp}**\n` +
            `• **मान्य नमी सीमा:** ${k.moisture}\n\n` +
            `💡 *मंडी जाने से पहले किसान सेतु पर अपना समय स्लॉट अवश्य बुक करें।*`,
          audio_text: `${k.crop} की सरकारी खरीद ${k.start} से ${k.end} तक चलेगी। इसका समर्थन मूल्य ${k.msp} है।`,
          quick_actions: [
            { label: "⚡ स्लॉट बुक करें", url: `farmer/booking.html?crop=${matchedCropKey}` },
            { label: "📍 खरीद केंद्र देखें", url: "farmer/centers.html" }
          ],
          suggestions: ["गेहूं का भाव क्या है?", "सरसों की खरीद कब शुरू होगी?", "टोकन कैसे मिलेगा?"]
        };
      } else {
        return {
          response: `📅 **सरकारी खरीद 2026 समय-सारणी**:\n\n` +
            `🌾 **रबी फसलें:**\n` +
            `• सरसों: 15 मार्च 2026 से 30 अप्रैल 2026 (MSP: ₹5,650)\n` +
            `• गेहूं: 1 अप्रैल 2026 से 15 मई 2026 (MSP: ₹2,275)\n` +
            `• चना: 1 अप्रैल 2026 से 15 मई 2026 (MSP: ₹5,440)\n\n` +
            `🌾 **खरीफ फसलें:**\n` +
            `• धान: 1 अक्टूबर 2026 से 15 नवंबर 2026 (MSP: ₹2,183)\n` +
            `• बाजरा: 1 अक्टूबर 2026 से 15 नवंबर 2026 (MSP: ₹2,500)\n\n` +
            `🕒 मंडी समय: 09:00 AM से 05:00 PM (सोमवार - शनिवार)`,
          audio_text: "रबी में सरसों की खरीद 15 मार्च से और गेहूं व चना की खरीद 1 अप्रैल 2026 से शुरू होगी। धान की खरीद 1 अक्टूबर से होगी।",
          quick_actions: [
            { label: "⚡ टोकन बुक करें", url: "farmer/booking.html" },
            { label: "📍 केंद्र देखें", url: "farmer/centers.html" }
          ],
          suggestions: ["गेहूं का भाव क्या है?", "टोकन कैसे बुक करें?"]
        };
      }
    }

    // 2. Price query
    if (qLower.includes('भाव') || qLower.includes('रेट') || qLower.includes('price') || qLower.includes('msp') || qLower.includes('dam') || matchedCropKey) {
      if (matchedCropKey && LOCAL_KNOWLEDGE[matchedCropKey]) {
        const k = LOCAL_KNOWLEDGE[matchedCropKey];
        return {
          response: `🌾 **${k.crop} का आधिकारिक मूल्य**:\n\n` +
            `• **सरकारी एमएसपी:** **${k.msp}**\n` +
            `• **डेमो मंडी दर:** ${k.demo}\n` +
            `• **स्वीकार्य नमी:** ${k.moisture}\n` +
            `• **भुगतान:** डीबीटी (DBT) द्वारा 48-72 घंटे में सीधे बैंक खाते में।`,
          audio_text: `${k.crop} का सरकारी एमएसपी भाव ${k.msp} है।`,
          quick_actions: [
            { label: "⚡ स्लॉट बुक करें", url: `farmer/booking.html?crop=${matchedCropKey}` }
          ],
          suggestions: ["खरीद कब शुरू होगी?", "पेमेंट कितने दिन में आएगा?"]
        };
      }
    }

    // 3. Booking query
    if (qLower.includes('booking') || qLower.includes('बुकिंग') || qLower.includes('token') || qLower.includes('टोकन') || qLower.includes('slot')) {
      return {
        response: `⚡ **टोकन बुक करने के आसान चरण**:\n\n` +
          `1. 'खरीद केंद्र खोजें' पर जाकर अपनी मंडी चुनें।\n` +
          `2. फसल का चयन करें और अनुमानित मात्रा भरें।\n` +
          `3. तारीख और समय स्लॉट (जैसे 09:00 AM) चुनें।\n` +
          `4. वाहन नंबर दर्ज करके पुष्टि करें और डिजिटल टोकन प्राप्त करें!`,
        audio_text: "टोकन बुक करने के लिए खरीद केंद्र चुनें, फसल और समय चुनें, और तुरंत डिजिटल टोकन प्राप्त करें।",
        quick_actions: [
          { label: "⚡ अभी स्लॉट बुक करें", url: "farmer/booking.html" },
          { label: "🎫 मेरा डिजिटल टोकन", url: "farmer/token.html" }
        ],
        suggestions: ["गेहूं का भाव क्या है?", "मंडी में कतार कैसे देखें?"]
      };
    }

    // 4. Fertilizer / Urea / DAP Dosage Queries (Ported from Kisan-Setu)
    if (qLower.includes('urea') || qLower.includes('यूरिया') || qLower.includes('खाद') || qLower.includes('fertilizer') || qLower.includes('dap') || qLower.includes('डीएपी') || qLower.includes('पोषण')) {
      return {
        response: `🌿 **वैज्ञानिक उर्वरक एवं पोषण प्रबंधन (Scientific Fertilizer Advisory)**:\n\n` +
          `• **डीएपी (DAP):** 50 से 55 किलोग्राम प्रति एकड़ बुवाई के समय बेसल डोज के रूप में डालें।\n` +
          `• **यूरिया (Urea) तीन चरणों में:** कुल 45 किग्रा/एकड़ (50% बुवाई पर, 25% प्रथम सिंचाई 21 दिन पर, 25% कल्ले फूटते समय)।\n` +
          `• **जिंक सल्फेट:** 10 किग्रा प्रति एकड़ (21% जिंक)। डीएपी के साथ कभी न मिलाएं।\n` +
          `• **मृदा रिपोर्ट आधारित लाभ:** सिफारिश अनुसार खाद का प्रयोग करने पर **Grade A खरीद बोनस** की पात्रता मिलती है।`,
        audio_text: "गेहूं और रबी फसलों के लिए 50 किलो डीएपी बुवाई के समय तथा 45 किलो यूरिया तीन चरणों में पहली और दूसरी सिंचाई पर डालें।",
        quick_actions: [
          { label: "🧪 मृदा परीक्षण कार्ड", url: "farmer/soil-testing.html" }
        ],
        suggestions: ["यूरिया कब डालना चाहिए?", "मृदा परीक्षण के क्या नियम हैं?", "गेहूं का भाव क्या है?"]
      };
    }

    // 5. Soil Testing & 48-Hour SLA Guarantee Queries
    if (qLower.includes('मृदा') || qLower.includes('soil') || qLower.includes('मिट्टी') || qLower.includes('sla') || qLower.includes('testing') || qLower.includes('स्वास्थ्य कार्ड')) {
      return {
        response: `🧪 **मृदा परीक्षण एवं 48-घंटे सेवा गारंटी (48-Hour Working SLA)**:\n\n` +
          `• **48-घंटे सेवा गारंटी:** आवेदन के 48 कार्य घंटों के भीतर प्रयोगशाला टीम नमूना संकलित कर डिजिटल हेल्थ कार्ड जारी करती है।\n` +
          `• **जांच घटक:** नाइट्रोजन (N), फास्फोरस (P), पोटाश (K), पीएच (pH), जैविक कार्बन (OC%), एवं ईसी (EC)।\n` +
          `• **अनुपालन प्रमाणीकरण:** वैज्ञानिक सलाह का पालन करने पर किसान को 'प्रमाणित अनुपालन बैच' और बोनस मिलता है।`,
        audio_text: "सरकारी सेवा गारंटी अनुसार 48 कार्य घंटों के भीतर प्रयोगशाला टीम मृदा स्वास्थ्य कार्ड और वैज्ञानिक खाद की सिफारिश जारी करती है।",
        quick_actions: [
          { label: "🧪 मृदा जांच आवेदन", url: "farmer/soil-testing.html" }
        ],
        suggestions: ["डीएपी की कितनी मात्रा डालें?", "टोकन कैसे बुक करें?"]
      };
    }

    // 6. Real-time Weather Queries
    if (qLower.includes('मौसम') || qLower.includes('weather') || qLower.includes('बारिश') || qLower.includes('rain') || qLower.includes('तापमान')) {
      const w = window.KisanAgriService?.weatherCache;
      if (w) {
        return {
          response: `🌤️ **लाइव मौसम स्थिति (${w.location}, ${w.region})**:\n\n` +
            `• **तापमान:** ${w.tempC}°C (अनुभूत: ${w.feelsLikeC}°C)\n` +
            `• **आर्द्रता:** ${w.humidity}% • **हवा:** ${w.windKph} km/h (${w.windDir})\n` +
            `• **स्थिति:** ${w.conditionText}\n` +
            `• **कृषि सलाह:** ${w.agroAdvice?.desc || 'मौसम कृषि कार्यों के लिए अनुकूल है।'}`,
          audio_text: `वर्तमान में तापमान ${w.tempC} डिग्री और मौसम ${w.conditionText} है। ${w.agroAdvice?.desc || ''}`,
          quick_actions: [
            { label: "🌾 डैशबोर्ड देखें", url: "farmer/dashboard.html" }
          ],
          suggestions: ["आज बारिश होगी क्या?", "फसलों के भाव क्या हैं?"]
        };
      }
    }

    // Default Fallback
    return {
      response: `🌾 **किसान वाणी सहायता**:\n\n` +
        `• **फसलों के भाव:** गेहूं ₹2,275/Q, सरसों ₹5,650/Q, चना ₹5,440/Q, धान ₹2,183/Q।\n` +
        `• **खरीद शुरू:** सरसों 15 मार्च से, गेहूं 1 अप्रैल 2026 से।\n` +
        `• **स्लॉट बुकिंग:** टोकन बुक करके मंडी में कतार से बचें।`,
      audio_text: "किसान भाई, आप फसलों के भाव, खरीद की तारीखें और टोकन बुकिंग के बारे में पूछ सकते हैं।",
      quick_actions: [
        { label: "🌾 फसलों के भाव", url: "farmer/centers.html" },
        { label: "⚡ टोकन बुक करें", url: "farmer/booking.html" }
      ],
      suggestions: ["गेहूं का भाव क्या है?", "सरसों की खरीद कब शुरू होगी?", "टोकन कैसे बुक करें?"]
    };
  }

  // -------------------------------------------------------------
  // 7. EVENT BINDINGS & CONTROLS
  // -------------------------------------------------------------
  function openPopup() {
    if (State.isOpen) return;
    State.isOpen = true;
    State.isMinimized = false;
    UI.popup.classList.add('kv-open');
    UI.popup.classList.remove('kv-minimized');
    if (UI.minimizeBtn) {
      UI.minimizeBtn.textContent = '➖';
      UI.minimizeBtn.title = 'छोटा करें (Minimize)';
    }
    setTimeout(() => {
      if (UI.textInput) UI.textInput.focus();
    }, 250);
  }

  function closePopup() {
    if (!State.isOpen) return;
    State.isOpen = false;
    State.isMinimized = false;
    UI.popup.classList.remove('kv-open');
    UI.popup.classList.remove('kv-minimized');
    stopSpeaking();
    stopListening();
  }

  function togglePopup() {
    if (State.isOpen) {
      closePopup();
    } else {
      openPopup();
    }
  }

  function toggleMinimize() {
    State.isMinimized = !State.isMinimized;
    if (State.isMinimized) {
      UI.popup.classList.add('kv-minimized');
      UI.minimizeBtn.textContent = '🗖';
      UI.minimizeBtn.title = 'बड़ा करें (Expand)';
    } else {
      UI.popup.classList.remove('kv-minimized');
      UI.minimizeBtn.textContent = '➖';
      UI.minimizeBtn.title = 'छोटा करें (Minimize)';
      scrollToBottom();
    }
  }

  function bindEvents() {
    // Launcher button toggle (opens if closed, closes if open)
    UI.launcher.addEventListener('click', togglePopup);

    // Close button (always closes and immediately stops speech & mic)
    UI.closeBtn.addEventListener('click', closePopup);

    // Minimize button
    UI.minimizeBtn.addEventListener('click', toggleMinimize);

    // Close on Escape key
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && State.isOpen) {
        closePopup();
      }
    });

    // Close when tapping/clicking anywhere outside the assistant popup
    document.addEventListener('pointerdown', (e) => {
      if (!State.isOpen) return;
      const isInsidePopup = UI.popup && UI.popup.contains(e.target);
      const isInsideLauncher = UI.launcher && UI.launcher.contains(e.target);
      const isHeaderOpenBtn = e.target.closest && e.target.closest('button[onclick*="KisanVoiceAssistant"]');
      if (!isInsidePopup && !isInsideLauncher && !isHeaderOpenBtn) {
        closePopup();
      }
    });

    // TTS Mute toggle
    UI.ttsToggleBtn.addEventListener('click', () => {
      State.ttsEnabled = !State.ttsEnabled;
      if (State.ttsEnabled) {
        UI.ttsToggleBtn.textContent = '🔊';
        UI.ttsToggleBtn.classList.remove('kv-active');
        UI.ttsToggleBtn.title = 'आवाज ऑन है (Voice Audio ON)';
      } else {
        stopSpeaking();
        UI.ttsToggleBtn.textContent = '🔇';
        UI.ttsToggleBtn.classList.add('kv-active');
        UI.ttsToggleBtn.title = 'आवाज म्यूट है (Voice Audio Muted)';
      }
    });

    // Reset button
    UI.resetBtn.addEventListener('click', () => {
      stopListening();
      stopSpeaking();
      UI.chatBody.innerHTML = '';
      State.hasSpokenWelcome = false;
      showWelcomeMessage();
    });

    // Mic button
    UI.micBtn.addEventListener('click', () => {
      if (State.isListening) {
        stopListening();
      } else {
        startListening();
      }
    });

    // Status cancel button
    UI.statusCancelBtn.addEventListener('click', () => {
      stopListening();
      stopSpeaking();
    });

    // Send button
    UI.sendBtn.addEventListener('click', () => {
      submitQuery(UI.textInput.value);
    });

    // Input Enter key
    UI.textInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        submitQuery(UI.textInput.value);
      }
    });

    // Header click in minimized state restores window
    UI.popup.querySelector('#kv-header').addEventListener('click', (e) => {
      if (State.isMinimized && !e.target.closest('.kv-icon-btn')) {
        toggleMinimize();
      }
    });
  }

  // -------------------------------------------------------------
  // 8. AUDIO CHIME & GATE PA ANNOUNCER
  // -------------------------------------------------------------
  function playAudioChime() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.85);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.85);
    } catch (e) {
      console.warn("Chime audio error:", e);
    }
  }

  function announceTokenPA(tokenNumber, gateNumber = 2, farmerName = '') {
    playAudioChime();
    setTimeout(() => {
      const hiText = `कृपया ध्यान दें। टोकन नंबर ${tokenNumber}। कृपया प्रवेश गेट नंबर ${gateNumber} पर आगे बढ़ें।`;
      const enText = `Attention please. Token number ${tokenNumber}. Please proceed to Gate number ${gateNumber}.`;
      speakText(`${hiText} ${enText}`);
    }, 450);

    if (window.KisanEventBus && typeof window.KisanEventBus.publish === 'function') {
      window.KisanEventBus.publish('GATE_CALLOUT', {
        tokenNumber,
        gateNumber,
        farmerName,
        timestamp: new Date().toISOString()
      });
    }
  }

  // -------------------------------------------------------------
  // 9. PUBLIC API & DOMCONTENTLOADED INITIALIZATION
  // -------------------------------------------------------------
  const KisanVoiceAssistant = {
    open: () => openPopup(),
    close: () => closePopup(),
    toggle: () => togglePopup(),
    ask: (question) => {
      openPopup();
      submitQuery(question);
    },
    speak: (text) => speakText(text),
    stop: () => {
      stopListening();
      stopSpeaking();
    },
    playChime: () => playAudioChime(),
    announceToken: (tokenNumber, gateNumber, farmerName) => announceTokenPA(tokenNumber, gateNumber, farmerName),
    callNextToken: (tokenNumber, gateNumber, farmerName) => announceTokenPA(tokenNumber, gateNumber, farmerName)
  };

  window.KisanVoiceAssistant = KisanVoiceAssistant;

  // Auto-mount on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createWidgetDOM);
  } else {
    createWidgetDOM();
  }

})();
