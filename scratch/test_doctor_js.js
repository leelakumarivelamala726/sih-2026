const fs = require('fs');
const http = require('http');

// Mock a browser DOM
const elements = {};
function getEl(id) {
  if (!elements[id]) {
    elements[id] = {
      id: id,
      innerHTML: 'Loading clinical summary...',
      textContent: '',
      style: {},
      value: '',
      children: [],
      appendChild: function(c) { this.children.push(c); },
      classList: {
        add: () => {},
        remove: () => {},
        contains: () => false
      }
    };
  }
  return elements[id];
}

global.document = {
  getElementById: getEl,
  querySelectorAll: () => [],
  createElement: (tag) => ({
    tagName: tag,
    style: {},
    innerHTML: '',
    appendChild: () => {}
  }),
  addEventListener: () => {}
};
global.window = {
  print: () => {}
};

// Now fetch bundle from server
async function test() {
  const req = await fetch('http://127.0.0.1:5000/api/doctor/patient/41', {
    headers: {
      'Cookie': 'session=...' // Need real cookie or test without auth
    }
  });
  console.log('Status:', req.status);
}
