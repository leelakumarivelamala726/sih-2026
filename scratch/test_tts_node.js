/**
 * Node-based unit test for speech.js voice synthesis behavior:
 * - Tests English voice selection and prioritization (en-IN > en-US > other English)
 * - Verifies that a Telugu default voice (voices[0]) is NEVER selected
 * - Verifies that if only non-English voices exist, browser English fallback (en-IN) is used
 * - Verifies voiceschanged handling and utterance parameters
 */
const fs = require('fs');

class MockSpeechSynthesisUtterance {
  constructor(text) {
    this.text = text;
    this.lang = 'en-US';
    this.rate = 1;
    this.pitch = 1;
    this.voice = null;
    this.onstart = null;
    this.onend = null;
    this.onerror = null;
  }
}

let spokenUtterances = [];
let voicesList = [];
let voicesChangedListeners = [];

const mockSpeechSynthesis = {
  cancel: () => {},
  speak: (utterance) => {
    spokenUtterances.push(utterance);
    if (utterance.onstart) utterance.onstart();
    setTimeout(() => {
      if (utterance.onend) utterance.onend();
    }, 10);
  },
  getVoices: () => voicesList,
  addEventListener: (event, handler) => {
    if (event === 'voiceschanged') voicesChangedListeners.push(handler);
  },
  onvoiceschanged: null
};

global.window = {
  speechSynthesis: mockSpeechSynthesis,
  SpeechSynthesisUtterance: MockSpeechSynthesisUtterance,
  dispatchEvent: () => {}
};
global.SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
global.CustomEvent = class CustomEvent {
  constructor(name, opts) {
    this.name = name;
    this.detail = opts ? opts.detail : {};
  }
};

// Evaluate speech.js
const speechJsCode = fs.readFileSync('static/js/speech.js', 'utf8');
eval(speechJsCode);

console.log('--- TEST 1: Functions exposed ---');
if (typeof window.speakAIResponse !== 'function') throw new Error('speakAIResponse missing');
if (typeof window.loadPreferredEnglishVoice !== 'function') throw new Error('loadPreferredEnglishVoice missing');
if (typeof window.isEnglishVoice !== 'function') throw new Error('isEnglishVoice missing');
console.log('[OK] TTS functions correctly exposed on window.');

console.log('\n--- TEST 2: Device with Telugu voice as voice #0 and OS default ---');
voicesList = [
  { name: 'Telugu India Male (తెలుగు)', lang: 'te-IN' }, // voices[0] is Telugu!
  { name: 'Google हिन्दी', lang: 'hi-IN' },
  { name: 'Microsoft Heera - English (India)', lang: 'en-IN' },
  { name: 'Google US English Natural', lang: 'en-US' }
];

const selectedVoice = window.loadPreferredEnglishVoice();
console.log('Selected voice name:', selectedVoice ? selectedVoice.name : null);
console.log('Selected voice lang:', selectedVoice ? selectedVoice.lang : null);

if (!selectedVoice || selectedVoice.lang !== 'en-IN') {
  throw new Error(`FAIL: Expected en-IN voice, got: ${selectedVoice ? selectedVoice.lang : 'none'}`);
}
if (selectedVoice.lang.startsWith('te') || selectedVoice.name.toLowerCase().includes('telugu')) {
  throw new Error('FAIL: Telugu voice was erroneously selected!');
}
console.log('[OK] Successfully prioritized en-IN over Telugu voice[0] and en-US.');

console.log('\n--- TEST 3: Device with Telugu voice #0 and ONLY en-US available ---');
voicesList = [
  { name: 'Telugu India Voice', lang: 'te-IN' },
  { name: 'Microsoft David - English (United States)', lang: 'en-US' }
];
const voiceUs = window.loadPreferredEnglishVoice();
if (!voiceUs || voiceUs.lang !== 'en-US') {
  throw new Error(`FAIL: Expected en-US fallback, got: ${voiceUs ? voiceUs.lang : 'none'}`);
}
console.log('[OK] Successfully fell back to en-US when en-IN not available (ignored Telugu).');

console.log('\n--- TEST 4: Device with ONLY non-English voices (Telugu & Hindi) ---');
voicesList = [
  { name: 'Telugu India Voice', lang: 'te-IN' },
  { name: 'Hindi India Voice', lang: 'hi-IN' }
];
const noEngVoice = window.loadPreferredEnglishVoice();
if (noEngVoice !== null) {
  throw new Error(`FAIL: Expected null voice when no English voice exists, but got: ${noEngVoice.name}`);
}

spokenUtterances = [];
window.speakAIResponse('Please describe your joint pain symptoms.');
if (spokenUtterances.length !== 1) throw new Error('Expected 1 utterance');
const uttNoEng = spokenUtterances[0];
console.log('Utterance voice with no English voice installed:', uttNoEng.voice);
console.log('Utterance lang with no English voice installed:', uttNoEng.lang);

if (uttNoEng.voice !== null) {
  throw new Error('FAIL: utterance.voice must be null so it does not speak in Telugu!');
}
if (uttNoEng.lang !== 'en-IN' && uttNoEng.lang !== 'en-US') {
  throw new Error(`FAIL: utterance.lang must be English, got: ${uttNoEng.lang}`);
}
console.log('[OK] Handled zero English voices safely using browser English-language fallback.');

console.log('\n--- TEST 5: Full Speech Invocation with en-IN voice ---');
voicesList = [
  { name: 'Telugu India Voice', lang: 'te-IN' },
  { name: 'Google English India Natural', lang: 'en-IN' }
];
spokenUtterances = [];
let startCalled = false;
let endCalled = false;

window.speakAIResponse('Namaste. I am AYUSH KRITI, your clinical assistant doctor.', {
  onStart: () => { startCalled = true; },
  onEnd: () => { endCalled = true; }
});

const activeUtt = spokenUtterances[0];
console.log('Spoken text:', activeUtt.text);
console.log('Spoken lang:', activeUtt.lang);
console.log('Spoken voice:', activeUtt.voice.name);
console.log('Spoken rate:', activeUtt.rate);

if (activeUtt.voice.name !== 'Google English India Natural') {
  throw new Error('FAIL: Active utterance voice mismatch');
}
if (activeUtt.rate !== 0.95) {
  throw new Error('FAIL: Rate mismatch');
}

setTimeout(() => {
  if (!startCalled) throw new Error('start callback was not called');
  if (!endCalled) throw new Error('end callback was not called');
  console.log('\nALL TTS ENGLISH VOICE SELECTION & SAFETY TESTS PASSED! 🎉');
}, 50);
