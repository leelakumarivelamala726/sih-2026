/**
 * Ministry of Ayush – Smart MediKiosk
 * Speech Recognition & Synthesis Service (Web Speech API)
 * Fully dynamic multilingual support with prioritized Telugu voice matching and safe platform synthesis.
 */

let isSpeaking = false;
let currentUtterance = null;
let preferredEnglishVoice = null;
let voiceCache = {};

// Application supported languages to BCP-47 locale map
const SUPPORTED_LANG_BCP47 = {
  'en': 'en-IN',
  'te': 'te-IN',
  'hi': 'hi-IN',
  'ta': 'ta-IN',
  'kn': 'kn-IN',
  'ml': 'ml-IN',
  'mr': 'mr-IN',
  'bn': 'bn-IN',
  'gu': 'gu-IN',
  'pa': 'pa-IN',
  'or': 'or-IN'
};

// Language keywords for name-based voice matching
const REGIONAL_VOICE_KEYWORDS = {
  'te': ['telugu', 'తెలుగు'],
  'hi': ['hindi', 'हिंदी'],
  'ta': ['tamil', 'தமிழ்'],
  'kn': ['kannada', 'ಕನ್ನಡ'],
  'ml': ['malayalam', 'മലയാളം'],
  'mr': ['marathi', 'मराठी'],
  'bn': ['bengali', 'বাংলা', 'bangla'],
  'gu': ['gujarati', 'ગુજરાતી'],
  'pa': ['punjabi', 'ਪੰਜਾਬੀ'],
  'or': ['odia', 'oriya', 'ଓଡ଼ିଆ']
};

/**
 * Resolve language code (e.g. 'te' or 'te-IN') to standard BCP-47 tag.
 */
function resolveBcp47(lang) {
  if (!lang) return 'en-IN';
  const clean = String(lang).trim();
  if (clean.includes('-')) return clean;
  const lower = clean.toLowerCase();
  return SUPPORTED_LANG_BCP47[lower] || `${lower}-IN`;
}

/**
 * Check if a voice is high quality / neural / natural.
 */
function isHighQualityVoice(v) {
  if (!v || !v.name) return false;
  const n = v.name.toLowerCase();
  return n.includes('natural') || n.includes('neural') || n.includes('google') || n.includes('online') || n.includes('premium');
}

/**
 * Strictly verify if a voice is an English voice.
 * Rejects non-English / Telugu voices when English is specifically targeted.
 */
function isEnglishVoice(v) {
  if (!v) return false;
  const lang = (v.lang || '').replace(/_/g, '-').toLowerCase();
  const name = (v.name || '').toLowerCase();
  if (lang.startsWith('te') || name.includes('telugu') || name.includes('తెలుగు')) {
    return false;
  }
  return lang.startsWith('en-') || lang === 'en';
}

/**
 * Find Telugu voice using required priority:
 * 1. Exact te-IN
 * 2. Any te-*
 * 3. te
 * 4. Voice name containing Telugu
 * 5. If no Telugu voice object is available, return null
 * (NEVER assign an English voice to a Telugu utterance)
 */
function findTeluguVoice(voicesList = null) {
  const voices = voicesList || (typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
  if (!voices || voices.length === 0) return null;

  const getNormLang = v => (v.lang || '').replace(/_/g, '-').toLowerCase();

  // 1. Exact te-IN (prefer High Quality)
  const exactHq = voices.find(v => getNormLang(v) === 'te-in' && isHighQualityVoice(v));
  if (exactHq) return exactHq;
  const exact = voices.find(v => getNormLang(v) === 'te-in');
  if (exact) return exact;

  // 2. Any te-* (e.g. te-AP, te-TS)
  const prefixHq = voices.find(v => getNormLang(v).startsWith('te-') && isHighQualityVoice(v));
  if (prefixHq) return prefixHq;
  const prefix = voices.find(v => getNormLang(v).startsWith('te-'));
  if (prefix) return prefix;

  // 3. te
  const langTe = voices.find(v => getNormLang(v) === 'te');
  if (langTe) return langTe;

  // 4. Voice name containing Telugu
  const nameTelugu = voices.find(v => {
    const n = (v.name || '').toLowerCase();
    return n.includes('telugu') || n.includes('తెలుగు');
  });
  if (nameTelugu) return nameTelugu;

  // 5. No Telugu voice object available
  return null;
}

/**
 * Find English voice prioritizing en-IN then en-US, rejecting non-English.
 */
function findEnglishVoice(voicesList = null) {
  const voices = voicesList || (typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
  if (!voices || voices.length === 0) return null;

  const englishVoices = voices.filter(isEnglishVoice);
  if (englishVoices.length === 0) return null;

  const getNormLang = v => (v.lang || '').replace(/_/g, '-').toLowerCase();

  // 1. en-IN High Quality
  const enInHq = englishVoices.find(v => getNormLang(v) === 'en-in' && isHighQualityVoice(v));
  if (enInHq) return enInHq;
  const enInAny = englishVoices.find(v => getNormLang(v) === 'en-in');
  if (enInAny) return enInAny;

  // 2. en-US High Quality
  const enUsHq = englishVoices.find(v => getNormLang(v) === 'en-us' && isHighQualityVoice(v));
  if (enUsHq) return enUsHq;
  const enUsAny = englishVoices.find(v => getNormLang(v) === 'en-us');
  if (enUsAny) return enUsAny;

  // 3. Any other English
  const anyEnHq = englishVoices.find(isHighQualityVoice);
  return anyEnHq || englishVoices[0];
}

/**
 * Find regional Indian voice (Hindi, Tamil, etc.).
 */
function findRegionalVoice(langPrefix, targetNorm, voicesList = null) {
  const voices = voicesList || (typeof window !== 'undefined' && window.speechSynthesis ? window.speechSynthesis.getVoices() : []);
  if (!voices || voices.length === 0) return null;

  const getNormLang = v => (v.lang || '').replace(/_/g, '-').toLowerCase();

  const exactHq = voices.find(v => getNormLang(v) === targetNorm && isHighQualityVoice(v));
  if (exactHq) return exactHq;
  const exactAny = voices.find(v => getNormLang(v) === targetNorm);
  if (exactAny) return exactAny;

  const familyHq = voices.find(v => (getNormLang(v).startsWith(`${langPrefix}-`) || getNormLang(v) === langPrefix) && isHighQualityVoice(v));
  if (familyHq) return familyHq;
  const familyAny = voices.find(v => getNormLang(v).startsWith(`${langPrefix}-`) || getNormLang(v) === langPrefix);
  if (familyAny) return familyAny;

  const keywords = REGIONAL_VOICE_KEYWORDS[langPrefix] || [langPrefix];
  const nameMatch = voices.find(v => {
    const nameLower = (v.name || '').toLowerCase();
    return keywords.some(k => nameLower.includes(k.toLowerCase()));
  });
  if (nameMatch) return nameMatch;

  return null;
}

/**
 * Dynamic voice selection for any supported language.
 */
function findBestVoiceForLanguage(targetLang, voicesList = null) {
  if (!('speechSynthesis' in window)) return null;

  const bcp47 = resolveBcp47(targetLang);
  const targetNorm = bcp47.replace(/_/g, '-').toLowerCase();
  const langPrefix = targetNorm.split('-')[0];

  const useCache = !voicesList;
  const voices = voicesList || window.speechSynthesis.getVoices();
  const cacheKey = `${targetNorm}_${voices.length}`;
  if (useCache && voiceCache[cacheKey] !== undefined) {
    return voiceCache[cacheKey];
  }

  let selected = null;
  if (langPrefix === 'te') {
    selected = findTeluguVoice(voices);
  } else if (langPrefix === 'en') {
    selected = findEnglishVoice(voices);
  } else {
    selected = findRegionalVoice(langPrefix, targetNorm, voices);
  }

  if (useCache) {
    voiceCache[cacheKey] = selected;
  }
  return selected;
}

/**
 * Asynchronously wait for voices to load if getVoices() is initially empty.
 */
function waitForVoices(timeoutMs = 600) {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) return resolve([]);
    const current = window.speechSynthesis.getVoices();
    if (current && current.length > 0) return resolve(current);

    let done = false;
    const finish = (v) => {
      if (!done) {
        done = true;
        resolve(v || window.speechSynthesis.getVoices() || []);
      }
    };

    const timer = setTimeout(() => finish([]), timeoutMs);

    const handler = () => {
      clearTimeout(timer);
      const v = window.speechSynthesis.getVoices();
      if (v && v.length > 0) finish(v);
    };

    if (typeof window.speechSynthesis.addEventListener === 'function') {
      window.speechSynthesis.addEventListener('voiceschanged', handler, { once: true });
    } else {
      window.speechSynthesis.onvoiceschanged = handler;
    }
  });
}

/**
 * Backward-compatible English voice loader.
 */
function loadPreferredEnglishVoice() {
  preferredEnglishVoice = findBestVoiceForLanguage('en-IN');
  return preferredEnglishVoice;
}

// Reset voice cache on voiceschanged
function onVoicesLoaded() {
  voiceCache = {};
  loadPreferredEnglishVoice();
}

if ('speechSynthesis' in window) {
  onVoicesLoaded();
  if (typeof window.speechSynthesis.addEventListener === 'function') {
    window.speechSynthesis.addEventListener('voiceschanged', onVoicesLoaded);
  }
  window.speechSynthesis.onvoiceschanged = onVoicesLoaded;
}

function setAISpeakingState(state) {
  isSpeaking = state;
  window.isAISpeaking = state;
  try {
    window.dispatchEvent(new CustomEvent('ai-speaking-state-change', { detail: { isSpeaking: state } }));
  } catch (e) {}
}

// Active session language state
window.currentAppLanguage = 'en';
window.currentBcp47 = 'en-IN';

/**
 * Update the consultation language dynamically.
 * Immediately cancels ongoing speech, updates STT, and refreshes voice selection.
 */
function setSessionLanguage(langCode, bcp47Code = null) {
  const normCode = (langCode || 'en').toLowerCase();
  const normBcp47 = bcp47Code || resolveBcp47(normCode);

  window.currentAppLanguage = normCode;
  window.currentBcp47 = normBcp47;

  stopAISpeech();
  voiceCache = {};

  if (window.prakritiSpeechEngineInstance) {
    window.prakritiSpeechEngineInstance.setLanguage(normBcp47);
  }

  try {
    window.dispatchEvent(new CustomEvent('session-language-changed', {
      detail: { language: normCode, bcp47: normBcp47 }
    }));
  } catch (e) {}
}

/**
 * Reusable function to speak AI response using Web Speech Synthesis API.
 * Dynamically adapts to the active consultation language (Telugu, Hindi, English, etc.).
 *
 * @param {string} text - Text to speak
 * @param {Object|Function} optionsOrCallbacks - { lang, onStart, onEnd, onError } or callback function
 */
function speakAIResponse(text, optionsOrCallbacks = {}) {
  if (!('speechSynthesis' in window)) {
    console.warn('[TTS] Web SpeechSynthesis not supported in this browser.');
    if (typeof optionsOrCallbacks === 'function') optionsOrCallbacks(new Error('SpeechSynthesis not supported'));
    else if (optionsOrCallbacks && optionsOrCallbacks.onError) optionsOrCallbacks.onError(new Error('SpeechSynthesis not supported'));
    return false;
  }

  if (!text || !text.trim()) return false;

  const cb = typeof optionsOrCallbacks === 'function' ? { onEnd: optionsOrCallbacks } : (optionsOrCallbacks || {});

  // Determine target language (options.lang -> window.currentBcp47 -> default en-IN)
  const rawLang = cb.lang || window.currentBcp47 || window.currentAppLanguage || 'en-IN';
  const targetBcp47 = resolveBcp47(rawLang);

  // Clean formatted text while STRICTLY preserving Telugu & Indian Unicode characters
  const cleanText = text
    .replace(/[#*`_~]/g, '')
    .replace(/⚠️/g, ' ')
    .replace(/🚨/g, ' ')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  if (!cleanText) return false;

  // Handle getVoices() loading asynchronously if initially empty
  const voicesNow = window.speechSynthesis.getVoices();
  if (!voicesNow || voicesNow.length === 0) {
    waitForVoices(500).then(() => {
      executeSpeechUtterance(cleanText, targetBcp47, cb);
    });
    return true;
  }

  return executeSpeechUtterance(cleanText, targetBcp47, cb);
}

/**
 * Internal execution of speech utterance with Chromium cancellation safety and status updates.
 */
function executeSpeechUtterance(cleanText, targetBcp47, cb) {
  let wasCanceling = false;
  try {
    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
      window.speechSynthesis.cancel();
      wasCanceling = true;
    }
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }
  } catch (e) {}

  setAISpeakingState(false);

  try {
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = targetBcp47;
    utterance.rate = 0.95; // Calm, empathetic clinical cadence
    utterance.pitch = 1.0;

    const langPrefix = targetBcp47.split('-')[0].toLowerCase();
    const voice = findBestVoiceForLanguage(targetBcp47);

    if (langPrefix === 'te') {
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang || 'te-IN';
        console.log(`[TTS] Speaking Telugu using voice: "${voice.name}" (${voice.lang})`);
        window._teluguVoiceStatus = { installed: true, voiceName: voice.name, lang: voice.lang };
      } else {
        // No Telugu voice object in getVoices() -> use platform synthesis with te-IN
        utterance.voice = null;
        utterance.lang = 'te-IN';
        console.info('[TTS] No dedicated Telugu voice in browser getVoices(). Using platform synthesis (utterance.lang = "te-IN", voice = null).');
        window._teluguVoiceStatus = { installed: false, voiceName: null, lang: 'te-IN' };
      }
    } else if (langPrefix === 'en') {
      if (voice && isEnglishVoice(voice)) {
        utterance.voice = voice;
        utterance.lang = voice.lang || 'en-IN';
      } else {
        utterance.voice = null;
        utterance.lang = 'en-IN';
      }
    } else {
      if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang || targetBcp47;
      } else {
        utterance.voice = null;
        utterance.lang = targetBcp47;
      }
    }

    utterance.onstart = () => {
      setAISpeakingState(true);
      if (cb.onStart) cb.onStart();
    };

    utterance.onend = () => {
      setAISpeakingState(false);
      currentUtterance = null;
      if (cb.onEnd) cb.onEnd();
    };

    utterance.onerror = (e) => {
      if (e.error !== 'canceled' && e.error !== 'interrupted') {
        console.warn(`[TTS Speech Error for ${targetBcp47}]`, e.error || e);
      }
      setAISpeakingState(false);
      currentUtterance = null;
      if (cb.onError) cb.onError(e);
    };

    currentUtterance = utterance;
    // Retain global reference against Chromium garbage collection bug
    window._activePrakritiUtterance = utterance;

    const doSpeak = () => {
      try {
        if (window.speechSynthesis.paused) {
          window.speechSynthesis.resume();
        }
        window.speechSynthesis.speak(utterance);
      } catch (err) {
        console.warn('[TTS Speak Error]', err);
        setAISpeakingState(false);
        if (cb.onError) cb.onError(err);
      }
    };

    if (wasCanceling) {
      setTimeout(doSpeak, 20);
    } else {
      doSpeak();
    }
    return true;
  } catch (err) {
    console.warn('[TTS Execution Error]', err);
    setAISpeakingState(false);
    if (cb.onError) cb.onError(err);
    return false;
  }
}

function stopAISpeech() {
  if ('speechSynthesis' in window) {
    try {
      window.speechSynthesis.cancel();
    } catch (e) {}
  }
  setAISpeakingState(false);
  currentUtterance = null;
  window._activePrakritiUtterance = null;
}

// Global API Exposure
window.speakAIResponse = speakAIResponse;
window.stopAISpeech = stopAISpeech;
window.findBestVoiceForLanguage = findBestVoiceForLanguage;
window.findTeluguVoice = findTeluguVoice;
window.loadPreferredEnglishVoice = loadPreferredEnglishVoice;
window.isEnglishVoice = isEnglishVoice;
window.resolveBcp47 = resolveBcp47;
window.setSessionLanguage = setSessionLanguage;
window.isAISpeaking = false;

/**
 * Speech Recognition Engine for Voice Input (STT)
 */
class PrakritiSpeechEngine {
  constructor(lang = 'en-IN') {
    this.lang = resolveBcp47(lang);
    this.recognition = null;
    this.isListening = false;
    this.onTranscriptCallback = null;
    this.onStatusChangeCallback = null;
    window.prakritiSpeechEngineInstance = this;
    this.initRecognition();
  }

  setLanguage(langCode) {
    this.lang = resolveBcp47(langCode);
    if (this.recognition) {
      this.recognition.lang = this.lang;
    }
  }

  initRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn('[Speech] Web Speech Recognition API not supported in this browser.');
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = false;
    this.recognition.interimResults = true;
    this.recognition.lang = this.lang;

    this.recognition.onstart = () => {
      this.isListening = true;
      if (this.onStatusChangeCallback) this.onStatusChangeCallback(true);
    };

    this.recognition.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      if (this.onTranscriptCallback) {
        this.onTranscriptCallback(final || interim, Boolean(final));
      }
    };

    this.recognition.onerror = (event) => {
      console.error('[Speech Error]', event.error);
      this.isListening = false;
      if (this.onStatusChangeCallback) this.onStatusChangeCallback(false, event.error);
    };

    this.recognition.onend = () => {
      this.isListening = false;
      if (this.onStatusChangeCallback) this.onStatusChangeCallback(false);
    };
  }

  startListening(onTranscript, onStatusChange) {
    if (window.isAISpeaking) {
      stopAISpeech();
    }

    if (!this.recognition) {
      alert('Speech Recognition is not supported by your browser. Please type your answers.');
      return;
    }
    this.onTranscriptCallback = onTranscript;
    this.onStatusChangeCallback = onStatusChange;
    try {
      this.recognition.start();
    } catch (e) {
      console.warn('[Speech Start Warning]', e);
    }
  }

  stopListening() {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
      this.isListening = false;
    }
  }

  speakText(text, lang = this.lang, onStart = null, onEnd = null, onError = null) {
    return speakAIResponse(text, { lang, onStart, onEnd, onError });
  }
}

window.PrakritiSpeechEngine = PrakritiSpeechEngine;
