/**
 * Test suite for TTS voice conversation feature
 */
const assert = require('assert');

// Mock browser SpeechSynthesis API
class MockSpeechSynthesisUtterance {
  constructor(text) {
    this.text = text;
    this.lang = 'en-US';
    this.rate = 1.0;
    this.pitch = 1.0;
    this.voice = null;
    this.onstart = null;
    this.onend = null;
    this.onerror = null;
  }
}

let speakCount = 0;
let cancelCount = 0;

const mockSpeechSynthesis = {
  speak: (utterance) => {
    speakCount++;
    if (utterance.onstart) utterance.onstart();
    setTimeout(() => {
      if (utterance.onend) utterance.onend();
    }, 10);
  },
  cancel: () => {
    cancelCount++;
  },
  getVoices: () => [
    { name: 'Microsoft Jenny (Natural) - English', lang: 'en-US' },
    { name: 'Google UK English Female', lang: 'en-GB' },
    { name: 'Microsoft Ravi - Telugu', lang: 'te-IN' }
  ]
};

global.window = {
  speechSynthesis: mockSpeechSynthesis,
  SpeechSynthesisUtterance: MockSpeechSynthesisUtterance
};
global.SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;

// Load speech.js
require('../static/js/speech.js');

console.log('Testing speakAIResponse definition...');
assert.strictEqual(typeof global.window.speakAIResponse, 'function');
assert.strictEqual(typeof global.window.stopAISpeech, 'function');

console.log('Testing voice selection and speech execution...');
let started = false;
let ended = false;

const res = global.window.speakAIResponse('Hello, how can I help you today?', {
  onStart: () => {
    started = true;
    assert.strictEqual(global.window.isAISpeaking, true, 'isAISpeaking must be true during speech');
    assert.strictEqual(cancelCount >= 1, true, 'Previous speech must be canceled');
  },
  onEnd: () => {
    ended = true;
    assert.strictEqual(global.window.isAISpeaking, false, 'isAISpeaking must be false after speech ends');
  }
});

assert.strictEqual(res, true);
assert.strictEqual(started, true);

setTimeout(() => {
  assert.strictEqual(ended, true);
  console.log('[OK] TTS Speech Synthesis & State Tracking verified successfully!');

  // Test stopAISpeech
  global.window.speakAIResponse('Second sentence');
  global.window.stopAISpeech();
  assert.strictEqual(global.window.isAISpeaking, false);
  console.log('[OK] stopAISpeech cancellation verified successfully!');
  console.log('ALL TTS VOICE UNIT TESTS PASSED!');
}, 50);
