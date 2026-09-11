/**
 * Ministry of Ayush – Smart MediKiosk
 * Speech Recognition & Synthesis Service (Web Speech API)
 * Fully dynamic multilingual support: te-IN, hi-IN, ta-IN, kn-IN, ml-IN, mr-IN, bn-IN, gu-IN, pa-IN, or-IN, en-IN, etc.
 * Provides dynamic speakAIResponse(text, options) for automated AI voice conversation.
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
 * Dynamic voice selection for any supported language:
 * Fallback Hierarchy:
 * 1. Exact selected locale match (e.g. te-IN) + High Quality
 * 2. Exact selected locale match (e.g. te-IN)
 * 3. Language family match (e.g. te) + High Quality
 * 4. Language family match (e.g. te)
 * 5. Compatible voice by name (e.g. contains "Telugu" or "తెలుగు")
 * 6. English safeguard: If target is English, strictly prioritize en-IN then en-US, never non-English.
 * 7. Non-English safeguard: If target is Telugu/Hindi/etc. and no specific voice is installed,
 *    returns null so the browser platform uses its native synthesis engine for that BCP-47 tag
 *    (NEVER forcing English on a Telugu/regional user).
 */
function findBestVoiceForLanguage(targetLang, voicesList = null) {
  if (!('speechSynthesis' in window)) return null;

  const voices = voicesList || window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  const targetBcp47 = resolveBcp47(targetLang);
  const targetNorm = targetBcp47.replace(/_/g, '-').toLowerCase();
  const langPrefix = targetNorm.split('-')[0];

  // Return from cache if already resolved (only when querying browser getVoices)
  const useCache = !voicesList;
  const cacheKey = `${targetNorm}_${voices.length}`;
  if (useCache && voiceCache[cacheKey]) {
    return voiceCache[cacheKey];
  }

  const getNormLang = v => (v.lang || '').replace(/_/g, '-').toLowerCase();

  // Special Handling for English
  if (langPrefix === 'en') {
    const englishVoices = voices.filter(isEnglishVoice);
    if (englishVoices.length === 0) {
      if (useCache) voiceCache[cacheKey] = null;
      return null;
    }

    // 1. en-IN High Quality
    const enInHq = englishVoices.find(v => getNormLang(v) === 'en-in' && isHighQualityVoice(v));
    if (enInHq) { if (useCache) voiceCache[cacheKey] = enInHq; return enInHq; }

    // 2. en-IN Any
    const enInAny = englishVoices.find(v => getNormLang(v) === 'en-in');
    if (enInAny) { if (useCache) voiceCache[cacheKey] = enInAny; return enInAny; }

    // 3. en-US High Quality
    const enUsHq = englishVoices.find(v => getNormLang(v) === 'en-us' && isHighQualityVoice(v));
    if (enUsHq) { if (useCache) voiceCache[cacheKey] = enUsHq; return enUsHq; }

    // 4. en-US Any
    const enUsAny = englishVoices.find(v => getNormLang(v) === 'en-us');
    if (enUsAny) { if (useCache) voiceCache[cacheKey] = enUsAny; return enUsAny; }

    // 5. Any other English
    const anyEnHq = englishVoices.find(isHighQualityVoice);
    const selectedEn = anyEnHq || englishVoices[0];
    if (useCache) voiceCache[cacheKey] = selectedEn;
    return selectedEn;
  }

  // Handling for Regional Indian Languages (te, hi, ta, kn, ml, mr, bn, gu, pa, or)
  // Step 1: Exact locale match with high quality
  const exactHq = voices.find(v => getNormLang(v) === targetNorm && isHighQualityVoice(v));
  if (exactHq) { if (useCache) voiceCache[cacheKey] = exactHq; return exactHq; }

  // Step 2: Exact locale match any
  const exactAny = voices.find(v => getNormLang(v) === targetNorm);
  if (exactAny) { if (useCache) voiceCache[cacheKey] = exactAny; return exactAny; }

  // Step 3: Language family match with high quality (e.g. te or te-*)
  const familyHq = voices.find(v => {
    const vl = getNormLang(v);
    return (vl.startsWith(`${langPrefix}-`) || vl === langPrefix) && isHighQualityVoice(v);
  });
  if (familyHq) { if (useCache) voiceCache[cacheKey] = familyHq; return familyHq; }

  // Step 4: Language family match any
  const familyAny = voices.find(v => {
    const vl = getNormLang(v);
    return vl.startsWith(`${langPrefix}-`) || vl === langPrefix;
  });
  if (familyAny) { if (useCache) voiceCache[cacheKey] = familyAny; return familyAny; }

  // Step 5: Match by language name keywords
  const keywords = REGIONAL_VOICE_KEYWORDS[langPrefix] || [langPrefix];
  const nameMatch = voices.find(v => {
    const nameLower = (v.name || '').toLowerCase();
    return keywords.some(k => nameLower.includes(k.toLowerCase()));
  });
  if (nameMatch) { if (useCache) voiceCache[cacheKey] = nameMatch; return nameMatch; }

  // Step 6: Non-English requested but no specific voice object found in getVoices().
  // Return null so the browser platform routes utterance.lang = targetBcp47 to native synthesizer.
  // We NEVER set an English voice for Telugu/regional text!
  if (useCache) voiceCache[cacheKey] = null;
  return null;
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

  // Stop active speech immediately
  stopAISpeech();

  // Clear cache for fresh voice resolution
  voiceCache = {};

  // Update speech recognition engine language
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

  // 1. Cancel previous speech immediately
  window.speechSynthesis.cancel();
  setAISpeakingState(false);

  if (!text || !text.trim()) return false;

  const cb = typeof optionsOrCallbacks === 'function' ? { onEnd: optionsOrCallbacks } : (optionsOrCallbacks || {});

  // Determine target language (options.lang -> window.currentBcp47 -> default en-IN)
  const rawLang = cb.lang || window.currentBcp47 || window.currentAppLanguage || 'en-IN';
  const targetBcp47 = resolveBcp47(rawLang);

  // 2. Clean formatted text for natural pronunciation while PRESERVING Telugu & Indian Unicode
  const cleanText = text
    .replace(/[#*`_~]/g, '')
    .replace(/⚠️/g, ' ')
    .replace(/🚨/g, ' ')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  if (!cleanText) return false;

  try {
    // 3. Create SpeechSynthesisUtterance with target language
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = targetBcp47;
    utterance.rate = 0.95; // Calm, empathetic clinical cadence
    utterance.pitch = 1.0;

    // 4. Select the best available voice for this specific language
    const voice = findBestVoiceForLanguage(targetBcp47);
    if (voice) {
      utterance.voice = voice;
      if (voice.lang) {
        utterance.lang = voice.lang;
      }
    } else {
      // Safe fallback: No voice object in getVoices(), but set utterance.lang so
      // browser platform synthesizer synthesizes in the requested regional language.
      utterance.voice = null;
      utterance.lang = targetBcp47;
    }

    // 5. Expose speaking state
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
      // Normal cancellations / interruptions are not treated as true errors
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

    // 6. Speak the AI response
    window.speechSynthesis.speak(utterance);
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
    // If AI is currently speaking, stop speech before listening
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
