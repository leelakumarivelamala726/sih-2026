/**
 * Ministry of Ayush – Smart MediKiosk
 * Prakriti-AI Interactive Case-Taking Dialogue
 */

document.addEventListener('DOMContentLoaded', () => {
  const welcomeCard = document.getElementById('welcomeCard');
  const chatInterface = document.getElementById('chatInterface');
  const startBtn = document.getElementById('startKioskBtn');
  const chatMessages = document.getElementById('chatMessages');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const micBtn = document.getElementById('micBtn');
  const aiStatusIndicator = document.getElementById('aiStatusIndicator');
  const emergencyBanner = document.getElementById('emergencyBanner');
  const scanLinkBtn = document.getElementById('scanLinkBtn');

  if (!chatInterface) return;

  const sessionId = chatInterface.dataset.sessionId;
  const language = chatInterface.dataset.language || 'en';
  const bcp47 = chatInterface.dataset.bcp47 || 'en-IN';

  const speechEngine = new window.PrakritiSpeechEngine(bcp47);

  // START Button Handler
  if (startBtn) {
    startBtn.addEventListener('click', () => {
      welcomeCard.style.display = 'none';
      chatInterface.style.display = 'grid';

      // Set 🟢 AI Active
      setStatus('active', '🟢 Prakriti-AI Active');

      // Fetch initial question if messages empty
      if (chatMessages.children.length === 0) {
        sendToAI("START_SESSION", true);
      }
    });
  }

  function setStatus(state) {
    if (!aiStatusIndicator) return;
    aiStatusIndicator.className = 'ai-status-pill';

    if (state === 'active') {
      aiStatusIndicator.classList.add('ai-status-active');
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> 🟢 Prakriti-AI Active`;
    } else if (state === 'listening') {
      aiStatusIndicator.classList.add('ai-status-listening');
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> 🎤 Listening...`;
    } else if (state === 'understanding') {
      aiStatusIndicator.classList.add('ai-status-understanding');
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> 🧠 Understanding...`;
    } else if (state === 'processing') {
      aiStatusIndicator.classList.add('ai-status-processing');
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> ⏳ Processing...`;
    } else if (state === 'speaking') {
      aiStatusIndicator.classList.add('ai-status-speaking');
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> 🔊 Prakriti-AI speaking...`;
    } else if (state === 'urgent') {
      aiStatusIndicator.classList.add('ai-status-urgent');
      aiStatusIndicator.innerHTML = `🔴 Emergency Triage Alert`;
    }
  }

  function appendMessage(sender, text) {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${sender === 'patient' ? 'message-patient' : 'message-ai'}`;

    const textEl = document.createElement('div');
    textEl.className = 'message-text';
    textEl.textContent = text;
    bubble.appendChild(textEl);

    const meta = document.createElement('div');
    meta.className = 'message-meta';
    meta.textContent = `${sender === 'patient' ? 'Patient' : 'Prakriti-AI'} • ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    bubble.appendChild(meta);

    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Trigger voice narration for AI messages
    if (sender === 'ai' && window.enableVoiceNarration) {
      speechEngine.speakText(
        text,
        bcp47,
        () => setStatus('speaking'),
        () => setStatus('active'),
        () => setStatus('active')
      );
    } else if (sender === 'ai') {
      setStatus('active');
    }
  }

  async function sendToAI(messageText, isInitial = false) {
    if (!messageText.trim()) return;

    if (!isInitial) {
      appendMessage('patient', messageText);
      chatInput.value = '';
    }

    setStatus('processing');

    try {
      const resp = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: isInitial ? 'START_SESSION' : messageText,
          language: language
        })
      });

      const data = await resp.json();

      if (data.is_urgent) {
        setStatus('urgent');
        if (emergencyBanner) {
          emergencyBanner.style.display = 'flex';
        }
      }

      appendMessage('ai', data.ai_response);

      if (data.is_completed && scanLinkBtn) {
        scanLinkBtn.style.display = 'inline-flex';
      }
    } catch (err) {
      console.error('[Chat Error]', err);
      setStatus('urgent');
      appendMessage('ai', 'Error communicating with Prakriti-AI service. Please try again.');
    }
  }

  // Send Click & Enter Key
  if (sendBtn) {
    sendBtn.addEventListener('click', () => {
      setStatus('understanding');
      sendToAI(chatInput.value);
    });
  }
  if (chatInput) {
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        setStatus('understanding');
        sendToAI(chatInput.value);
      }
    });
  }

  // Microphone Voice Input
  if (micBtn) {
    micBtn.addEventListener('click', () => {
      if (speechEngine.isListening) {
        speechEngine.stopListening();
        setStatus('active');
      } else {
        setStatus('listening');
        speechEngine.startListening(
          (transcript, isFinal) => {
            chatInput.value = transcript;
            if (isFinal) {
              setStatus('understanding');
              sendToAI(transcript);
            }
          },
          (isListening, error) => {
            if (isListening) {
              micBtn.classList.add('listening');
              micBtn.title = 'Listening... Click to stop';
              setStatus('listening');
            } else {
              micBtn.classList.remove('listening');
              micBtn.title = 'Click to speak';
              if (!isListening && !speechEngine.isListening) {
                // If not processing or speaking, return to active
                if (!aiStatusIndicator.classList.contains('ai-status-processing') &&
                    !aiStatusIndicator.classList.contains('ai-status-speaking') &&
                    !aiStatusIndicator.classList.contains('ai-status-understanding')) {
                  setStatus('active');
                }
              }
            }
          }
        );
      }
    });
  }
});

