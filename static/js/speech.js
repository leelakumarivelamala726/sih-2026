/**
 * Ministry of Ayush – Smart MediKiosk
 * Speech Recognition & Synthesis Service (Web Speech API)
 * Supports Indian Languages: te-IN, hi-IN, ta-IN, kn-IN, en-IN, etc.
 */

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
    if (!('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel(); // Stop ongoing speech
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 0.95;

      // Select matching voice if available
      const voices = window.speechSynthesis.getVoices();
      if (voices && voices.length > 0) {
        const matchingVoice = voices.find(v => v.lang === lang || v.lang.startsWith(lang.split('-')[0]));
        if (matchingVoice) {
          utterance.voice = matchingVoice;
        }
      }

      if (onStart) utterance.onstart = onStart;
      if (onEnd) utterance.onend = onEnd;
      if (onError) utterance.onerror = onError;

      // Keep a reference to prevent garbage collection on some browsers
      window._activePrakritiUtterance = utterance;

      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('[TTS Error]', e);
      if (onError) onError(e);
    }
  }
}

window.PrakritiSpeechEngine = PrakritiSpeechEngine;

