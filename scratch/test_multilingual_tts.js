/**
 * Unit tests for Multilingual TTS Voice Selection & Fallback Hierarchy
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Mock browser SpeechSynthesis environment
class MockUtterance {
  constructor(text) {
    this.text = text;
    this.lang = '';
    this.voice = null;
    this.rate = 1.0;
    this.pitch = 1.0;
    this.onstart = null;
    this.onend = null;
    this.onerror = null;
  }
}

let mockVoices = [];
let spokenUtterances = [];

const mockSpeechSynthesis = {
  getVoices: () => mockVoices,
  speak: (utt) => {
    spokenUtterances.push(utt);
    if (utt.onstart) utt.onstart();
    setTimeout(() => {
      if (utt.onend) utt.onend();
    }, 10);
  },
  cancel: () => {},
  addEventListener: () => {},
  onvoiceschanged: null
};

global.window = {
  speechSynthesis: mockSpeechSynthesis,
  dispatchEvent: () => {},
  SpeechSynthesisUtterance: MockUtterance
};
global.SpeechSynthesisUtterance = MockUtterance;
global.document = {
  addEventListener: () => {}
};
global.CustomEvent = class CustomEvent {
  constructor(name, opts) {
    this.name = name;
    this.detail = opts ? opts.detail : null;
  }
};

// Evaluate speech.js in mock environment
const speechJsPath = path.join(__dirname, '..', 'static', 'js', 'speech.js');
const code = fs.readFileSync(speechJsPath, 'utf8');
eval(code);

console.log('--- 1. Testing BCP-47 Resolution for All 11 Languages ---');
assert.strictEqual(window.resolveBcp47('te'), 'te-IN');
assert.strictEqual(window.resolveBcp47('hi'), 'hi-IN');
assert.strictEqual(window.resolveBcp47('en'), 'en-IN');
assert.strictEqual(window.resolveBcp47('ta'), 'ta-IN');
assert.strictEqual(window.resolveBcp47('kn'), 'kn-IN');
assert.strictEqual(window.resolveBcp47('ml'), 'ml-IN');
assert.strictEqual(window.resolveBcp47('mr'), 'mr-IN');
assert.strictEqual(window.resolveBcp47('bn'), 'bn-IN');
assert.strictEqual(window.resolveBcp47('gu'), 'gu-IN');
assert.strictEqual(window.resolveBcp47('pa'), 'pa-IN');
assert.strictEqual(window.resolveBcp47('or'), 'or-IN');
assert.strictEqual(window.resolveBcp47('te-IN'), 'te-IN');
assert.strictEqual(window.resolveBcp47('en-US'), 'en-US');
console.log('[OK] All 11 languages mapped to valid BCP-47 tags.');

console.log('\n--- 2. Testing Telugu Voice Selection (Exact & Family) ---');
mockVoices = [
  { name: 'Microsoft Ravi - Telugu (India)', lang: 'te-IN' },
  { name: 'Microsoft Mohan - Telugu (India) Natural', lang: 'te-IN' },
  { name: 'Microsoft Heera - English (India)', lang: 'en-IN' },
  { name: 'Google US English', lang: 'en-US' }
];

const selectedTelugu = window.findBestVoiceForLanguage('te-IN', mockVoices);
assert.ok(selectedTelugu, 'Telugu voice must be found');
assert.strictEqual(selectedTelugu.lang, 'te-IN');
assert.ok(selectedTelugu.name.includes('Natural'), 'Should prioritize high quality Natural Telugu voice');
console.log(`[OK] Selected Telugu Voice: ${selectedTelugu.name} (${selectedTelugu.lang})`);

console.log('\n--- 3. Testing Telugu Voice Selection by Keyword / Family ---');
mockVoices = [
  { name: 'Telugu Regional Voice', lang: 'te' },
  { name: 'Microsoft Heera - English (India)', lang: 'en-IN' }
];
const familyTelugu = window.findBestVoiceForLanguage('te', mockVoices);
assert.ok(familyTelugu, 'Should match language family or keyword');
assert.strictEqual(familyTelugu.name, 'Telugu Regional Voice');
console.log(`[OK] Selected Telugu Voice by Family/Keyword: ${familyTelugu.name}`);

console.log('\n--- 4. Testing Hindi Voice Selection ---');
mockVoices = [
  { name: 'Microsoft Swara - Hindi (India) Natural', lang: 'hi-IN' },
  { name: 'Microsoft Madhur - Hindi (India)', lang: 'hi-IN' },
  { name: 'Microsoft Ravi - Telugu (India)', lang: 'te-IN' },
  { name: 'Microsoft Heera - English (India)', lang: 'en-IN' }
];
const selectedHindi = window.findBestVoiceForLanguage('hi-IN', mockVoices);
assert.ok(selectedHindi, 'Hindi voice must be found');
assert.strictEqual(selectedHindi.lang, 'hi-IN');
assert.ok(selectedHindi.name.includes('Natural'), 'Should prioritize Natural Hindi voice');
console.log(`[OK] Selected Hindi Voice: ${selectedHindi.name} (${selectedHindi.lang})`);

console.log('\n--- 5. Testing English Voice Safeguard ---');
// Environment where Telugu is voice[0]
mockVoices = [
  { name: 'Microsoft Ravi - Telugu (India)', lang: 'te-IN' },
  { name: 'Microsoft Heera - English (India) Natural', lang: 'en-IN' },
  { name: 'Google US English', lang: 'en-US' }
];
const selectedEnglish = window.findBestVoiceForLanguage('en-IN', mockVoices);
assert.ok(selectedEnglish, 'English voice must be found');
assert.strictEqual(selectedEnglish.lang, 'en-IN');
assert.strictEqual(selectedEnglish.name, 'Microsoft Heera - English (India) Natural');
console.log(`[OK] English strictly selected: ${selectedEnglish.name} (Telugu voice[0] properly rejected)`);

console.log('\n--- 6. Testing Telugu Fallback When No Telugu Voice Object in getVoices() ---');
// Only English voices installed in browser
mockVoices = [
  { name: 'Microsoft David - English (United States)', lang: 'en-US' },
  { name: 'Microsoft Zira - English (United States)', lang: 'en-US' }
];
const noTeVoice = window.findBestVoiceForLanguage('te-IN', mockVoices);
assert.strictEqual(noTeVoice, null, 'Must return null so platform synthesizer uses utterance.lang, NEVER forcing English');
console.log('[OK] Returned null when no Telugu voice object in getVoices() (Safe fallback for platform synthesis)');

console.log('\n--- 7. Testing speakAIResponse with Telugu Text ---');
spokenUtterances = [];
const teluguText = 'నమస్కారం, ఈ రోజు మీకు ఎలాంటి ఆరోగ్య సమస్య లేదా ఇబ్బంది ఉంది? దయచేసి వివరంగా చెప్పండి.';

mockVoices = [
  { name: 'Microsoft Mohan - Telugu (India) Natural', lang: 'te-IN' },
  { name: 'Microsoft Heera - English (India)', lang: 'en-IN' }
];

window.setSessionLanguage('te', 'te-IN');
const speakRes = window.speakAIResponse(teluguText, { lang: 'te-IN' });
assert.strictEqual(speakRes, true);
assert.strictEqual(spokenUtterances.length, 1);
const utt = spokenUtterances[0];
assert.strictEqual(utt.lang, 'te-IN', 'Utterance lang must be te-IN');
assert.strictEqual(utt.voice.name, 'Microsoft Mohan - Telugu (India) Natural');
assert.ok(utt.text.includes('నమస్కారం'), 'Telugu Unicode must be preserved');
console.log(`[OK] Spoken Telugu utterance verified: lang=${utt.lang}, voice=${utt.voice.name}, rate=${utt.rate}`);

console.log('\n--- 8. Testing speakAIResponse with Telugu Text when No Voice Installed ---');
spokenUtterances = [];
mockVoices = []; // Empty getVoices() or only English
window.speakAIResponse(teluguText, { lang: 'te-IN' });
assert.strictEqual(spokenUtterances.length, 1);
const uttFallback = spokenUtterances[0];
assert.strictEqual(uttFallback.lang, 'te-IN', 'Must preserve te-IN for platform synthesis');
assert.strictEqual(uttFallback.voice, null, 'Voice object is null for native routing');
console.log(`[OK] Platform fallback verified: utterance.lang=${uttFallback.lang}, voice=${uttFallback.voice}`);

console.log('\n--- 9. Dynamic Language Switching ---');
window.setSessionLanguage('hi', 'hi-IN');
assert.strictEqual(window.currentAppLanguage, 'hi');
assert.strictEqual(window.currentBcp47, 'hi-IN');

window.setSessionLanguage('te', 'te-IN');
assert.strictEqual(window.currentAppLanguage, 'te');
assert.strictEqual(window.currentBcp47, 'te-IN');
console.log('[OK] Session language switching verified seamlessly.');

console.log('\nALL 9 MULTILINGUAL TTS TESTS PASSED WITH 100% SUCCESS! 🎉');
