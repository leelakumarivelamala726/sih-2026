/**
 * Ministry of Ayush – Smart MediKiosk
 * Speech Recognition & Synthesis Service (Web Speech API)
 * Supports Indian Languages: te-IN, hi-IN, ta-IN, kn-IN, en-IN, etc.
 * Provides speakAIResponse(text) for automated AI voice conversation.
 */

let isSpeaking = false;
let currentUtterance = null;
let preferredEnglishVoice = null;

function loadPreferredEnglishVoice() {
  if (!('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return null;

  // Search hierarchy for natural English voice suitable for clinical conversation
  const voicePredicates = [
    v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Online')),
    v => v.name.includes('Google') && (v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN'),
    v => v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN',
    v => v.lang.startsWith('en')
  ];

  for (const pred of voicePredicates) {
    const found = voices.find(pred);
    if (found) {
      preferredEnglishVoice = found;
      return found;
    }
  }
  preferredEnglishVoice = voices[0];
  return preferredEnglishVoice;
}

if ('speechSynthesis' in window) {
  loadPreferredEnglishVoice();
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = loadPreferredEnglishVoice;
  }
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
 * - Sets language to English
 * - Selects best available English voice
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

    // 3. Set language to English (clinical patient-case conversation)
    utterance.lang = 'en-US';
    utterance.rate = 0.95; // Calm, clear, empathetic clinical cadence
    utterance.pitch = 1.0;

    // 4. Select the best available English voice
    const voice = preferredEnglishVoice || loadPreferredEnglishVoice();
    if (voice) {
      utterance.voice = voice;
      if (voice.lang) utterance.lang = voice.lang;
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
