/**
 * Ministry of Ayush – Smart MediKiosk
 * Speech Recognition & Synthesis Service (Web Speech API)
 * Supports Indian Languages: te-IN, hi-IN, ta-IN, kn-IN, en-IN, etc.
 * Provides speakAIResponse(text) for automated AI voice conversation.
 */

let isSpeaking = false;
let currentUtterance = null;
let preferredEnglishVoice = null;

/**
 * Strictly verify if a voice is an English voice.
 * Ensures language starts with 'en-' or equals 'en',
 * and explicitly rejects non-English / Telugu indicators.
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
 * Load and select the best available English voice:
 * - Loads voices using speechSynthesis.getVoices()
 * - Strictly filters voices whose lang starts with "en-"
 * - Prioritizes en-IN if available, otherwise en-US
 * - NEVER falls back to voices[0] or OS default (e.g. Telugu)
 * - Returns null if no English voice is found so the browser uses its English fallback
 */
function loadPreferredEnglishVoice() {
  if (!('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  // Filter strictly English voices
  const englishVoices = voices.filter(isEnglishVoice);
  if (englishVoices.length === 0) {
    // Under NO circumstances fall back to voices[0] or OS default!
    preferredEnglishVoice = null;
    return null;
  }

  const getNormLang = v => (v.lang || '').replace(/_/g, '-').toLowerCase();
  const isHighQuality = v => {
    const n = (v.name || '').toLowerCase();
    return n.includes('natural') || n.includes('neural') || n.includes('google') || n.includes('online');
  };

  // 1. Prioritize en-IN (Indian English)
  const enInHighQuality = englishVoices.find(v => getNormLang(v) === 'en-in' && isHighQuality(v));
  if (enInHighQuality) {
    preferredEnglishVoice = enInHighQuality;
    return enInHighQuality;
  }
  const enInAny = englishVoices.find(v => getNormLang(v) === 'en-in');
  if (enInAny) {
    preferredEnglishVoice = enInAny;
    return enInAny;
  }

  // 2. Otherwise prioritize en-US (US English)
  const enUsHighQuality = englishVoices.find(v => getNormLang(v) === 'en-us' && isHighQuality(v));
  if (enUsHighQuality) {
    preferredEnglishVoice = enUsHighQuality;
    return enUsHighQuality;
  }
  const enUsAny = englishVoices.find(v => getNormLang(v) === 'en-us');
  if (enUsAny) {
    preferredEnglishVoice = enUsAny;
    return enUsAny;
  }

  // 3. Fallback to any other English voice (e.g. en-GB, en-AU)
  const otherHighQuality = englishVoices.find(isHighQuality);
  if (otherHighQuality) {
    preferredEnglishVoice = otherHighQuality;
    return otherHighQuality;
  }

  preferredEnglishVoice = englishVoices[0];
  return preferredEnglishVoice;
}

// Register voiceschanged listeners
if ('speechSynthesis' in window) {
  loadPreferredEnglishVoice();
  if (typeof window.speechSynthesis.addEventListener === 'function') {
    window.speechSynthesis.addEventListener('voiceschanged', () => {
      loadPreferredEnglishVoice();
    });
  }
  window.speechSynthesis.onvoiceschanged = () => {
    loadPreferredEnglishVoice();
  };
}

function setAISpeakingState(state) {
  isSpeaking = state;
  window.isAISpeaking = state;
  try {
    window.dispatchEvent(new CustomEvent('ai-speaking-state-change', { detail: { isSpeaking: state } }));
  } catch (e) {}
}

/**
 * Reusable function to speak AI response using Web Speech Synthesis API.
 * - Cancels previous speech
 * - Creates SpeechSynthesisUtterance
 * - Explicitly forces language to English (en-IN or en-US)
 * - Selects best available English voice (en-IN prioritized, then en-US)
 * - Uses browser English fallback if no voice object installed (never Telugu)
 * - Speaks the AI response
 * - Exposes speaking state so the UI can show "Speaking..."
 */
function speakAIResponse(text, callbacks = {}) {
  if (!('speechSynthesis' in window)) {
    console.warn('[TTS] Web SpeechSynthesis not supported in this browser.');
    if (typeof callbacks === 'function') callbacks(new Error('SpeechSynthesis not supported'));
    else if (callbacks && callbacks.onError) callbacks.onError(new Error('SpeechSynthesis not supported'));
    return false;
  }

  // 1. Cancel previous speech immediately
  window.speechSynthesis.cancel();
  setAISpeakingState(false);

  if (!text || !text.trim()) return false;

  const cb = typeof callbacks === 'function' ? { onEnd: callbacks } : (callbacks || {});

  // Clean formatted text for natural speech pronunciation
  const cleanText = text
    .replace(/[#*`_~]/g, '')
    .replace(/⚠️/g, 'Note: ')
    .replace(/🚨/g, 'Alert: ')
    .replace(/https?:\/\/\S+/g, '')
    .trim();

  try {
    // 2. Create SpeechSynthesisUtterance
    const utterance = new SpeechSynthesisUtterance(cleanText);

    // 3. Explicitly force intended AI voice language to English
    // Do NOT depend on browser default voice or system language
    utterance.lang = 'en-IN';
    utterance.rate = 0.95; // Calm, clear, empathetic clinical cadence
    utterance.pitch = 1.0;

    // 4. Select the best available English voice
    const voice = loadPreferredEnglishVoice() || preferredEnglishVoice;
    if (voice && isEnglishVoice(voice)) {
      utterance.voice = voice;
      if (voice.lang && isEnglishVoice(voice)) {
        utterance.lang = voice.lang;
      }
    } else {
      // If no English voice is available in getVoices(), use browser's
      // English-language speechSynthesis fallback instead of selecting a Telugu voice.
      utterance.voice = null;
      utterance.lang = 'en-IN';
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
      // Canceled utterances are not true errors
      if (e.error !== 'canceled' && e.error !== 'interrupted') {
        console.warn('[TTS Speech Error]', e.error || e);
      }
      setAISpeakingState(false);
      currentUtterance = null;
      if (cb.onError) cb.onError(e);
    };

    currentUtterance = utterance;
    // Retain global reference to avoid garbage collection bug in Chromium
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

window.speakAIResponse = speakAIResponse;
window.stopAISpeech = stopAISpeech;
window.loadPreferredEnglishVoice = loadPreferredEnglishVoice;
window.isEnglishVoice = isEnglishVoice;
window.isAISpeaking = false;

class PrakritiSpeechEngine {
  constructor(lang = 'en-IN') {
    this.lang = lang;
    this.recognition = null;
    this.isListening = false;
    this.onTranscriptCallback = null;
    this.onStatusChangeCallback = null;
    this.initRecognition();
  }

  setLanguage(langCode) {
    this.lang = langCode;
    if (this.recognition) {
      this.recognition.lang = langCode;
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
    return speakAIResponse(text, { onStart, onEnd, onError });
  }
}

window.PrakritiSpeechEngine = PrakritiSpeechEngine;
