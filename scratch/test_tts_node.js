/**
 * Node-based unit test for speech.js and chat.js voice synthesis behavior
 */
const fs = require('fs');

// Create mock browser window environment
let canceledCount = 0;
let spokenUtterances = [];

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

const mockSpeechSynthesis = {
  cancel: () => {
    canceledCount++;
  },
  speak: (utterance) => {
    spokenUtterances.push(utterance);
    if (utterance.onstart) utterance.onstart();
    // Simulate speech completing
    setTimeout(() => {
      if (utterance.onend) utterance.onend();
    }, 10);
  },
  getVoices: () => [
    { name: 'Microsoft David', lang: 'en-US' },
    { name: 'Google US English Natural', lang: 'en-US' },
    { name: 'Google UK English Female', lang: 'en-GB' }
  ]
};

global.window = {
  speechSynthesis: mockSpeechSynthesis,
  SpeechSynthesisUtterance: MockSpeechSynthesisUtterance,
  dispatchEvent: (event) => {}
};
global.SpeechSynthesisUtterance = MockSpeechSynthesisUtterance;
global.CustomEvent = class CustomEvent {
  constructor(name, opts) {
    this.name = name;
    this.detail = opts.detail;
  }
};

// Evaluate speech.js
const speechJsCode = fs.readFileSync('static/js/speech.js', 'utf8');
eval(speechJsCode);

// Assertions
console.log('Testing speakAIResponse definition...');
if (typeof window.speakAIResponse !== 'function') {
  throw new Error('speakAIResponse is not exposed on window!');
}
if (typeof window.stopAISpeech !== 'function') {
  throw new Error('stopAISpeech is not exposed on window!');
}

console.log('Testing speech invocation...');
let startCalled = false;
let endCalled = false;

window.speakAIResponse('Namaste. I am AYUSH KRITI, your clinical assistant doctor.', {
  onStart: () => {
    startCalled = true;
    console.log('onStart callback fired successfully.');
  },
  onEnd: () => {
    endCalled = true;
    console.log('onEnd callback fired successfully.');
  }
});

if (spokenUtterances.length !== 1) {
  throw new Error('Expected 1 spoken utterance, got ' + spokenUtterances.length);
}

const utt = spokenUtterances[0];
console.log('Utterance text:', utt.text);
console.log('Utterance lang:', utt.lang);
console.log('Utterance rate:', utt.rate);
console.log('Utterance pitch:', utt.pitch);
console.log('Utterance voice:', utt.voice ? utt.voice.name : 'null');

if (utt.rate !== 0.95) {
  throw new Error('Expected rate 0.95, got ' + utt.rate);
}
if (!utt.voice || !utt.voice.name.includes('Natural')) {
  throw new Error('Expected Natural English voice selection!');
}

console.log('Testing stopAISpeech...');
window.stopAISpeech();
if (window.isAISpeaking !== false) {
  throw new Error('Expected window.isAISpeaking to be false after stopAISpeech!');
}

setTimeout(() => {
  if (!startCalled) throw new Error('start callback was not called');
  if (!endCalled) throw new Error('end callback was not called');
  console.log('ALL TTS SPEECH SYNTHESIS UNIT TESTS PASSED SUCCESSFULLY! 🎉');
}, 50);
