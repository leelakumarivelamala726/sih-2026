/**
 * Ministry of Ayush – Smart MediKiosk
 * AYUSH KRITI Interactive Case-Taking Dialogue
 * Integrates automated multilingual Text-to-Speech (TTS) and Speech-to-Text (STT) voice conversation.
 */

function initKioskChat() {
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
  const globalVoiceToggle = document.getElementById('globalVoiceToggle');
  const voiceNarrationToggle = document.getElementById('voiceNarrationToggle');
  const sessionLanguageSelect = document.getElementById('sessionLanguageSelect');

  if (!chatInterface) return;

  const sessionId = chatInterface.dataset.sessionId;
  let language = chatInterface.dataset.language || 'en';
  let bcp47 = chatInterface.dataset.bcp47 || (window.resolveBcp47 ? window.resolveBcp47(language) : 'en-IN');

  // Synchronize global language state across TTS and STT
  if (window.setSessionLanguage) {
    window.setSessionLanguage(language, bcp47);
  }

  const speechEngine = new window.PrakritiSpeechEngine(bcp47);

  // Track duplicate speech prevention
  let lastAutoSpokenText = '';

  // Initialize global voice narration state
  if (typeof window.enableVoiceNarration === 'undefined') {
    window.enableVoiceNarration = true;
  }

  // Synchronize Global Voice Toggle UI controls
  function updateVoiceToggleUI(enabled) {
    window.enableVoiceNarration = enabled;
    if (voiceNarrationToggle) {
      voiceNarrationToggle.checked = enabled;
    }
    if (globalVoiceToggle) {
      if (enabled) {
        globalVoiceToggle.classList.remove('voice-off');
        globalVoiceToggle.classList.add('voice-on');
        globalVoiceToggle.innerHTML = '🔊 Voice: ON';
        globalVoiceToggle.title = 'AI Voice is ON (Click to Mute)';
      } else {
        globalVoiceToggle.classList.remove('voice-on');
        globalVoiceToggle.classList.add('voice-off');
        globalVoiceToggle.innerHTML = '🔇 Voice: OFF';
        globalVoiceToggle.title = 'AI Voice is OFF (Click to Turn ON)';
      }
    }
  }

  // Initialize toggle buttons state
  updateVoiceToggleUI(window.enableVoiceNarration);

  if (globalVoiceToggle) {
    globalVoiceToggle.addEventListener('click', () => {
      const newState = !window.enableVoiceNarration;
      updateVoiceToggleUI(newState);
      if (!newState) {
        window.stopAISpeech();
        resetAllSpeakerButtons();
        setStatus('active');
      }
    });
  }

  if (voiceNarrationToggle) {
    voiceNarrationToggle.addEventListener('change', (e) => {
      const newState = e.target.checked;
      updateVoiceToggleUI(newState);
      if (!newState) {
        window.stopAISpeech();
        resetAllSpeakerButtons();
        setStatus('active');
      }
    });
  }

  function resetAllSpeakerButtons() {
    document.querySelectorAll('.msg-speaker-btn').forEach(btn => {
      btn.classList.remove('is-speaking');
      btn.innerHTML = '🔊 <span>Listen</span>';
      btn.title = 'Listen / Replay response';
    });
  }

  // Handle Dynamic Language Switching during Consultation
  if (sessionLanguageSelect) {
    sessionLanguageSelect.addEventListener('change', async (e) => {
      const selectedOption = sessionLanguageSelect.options[sessionLanguageSelect.selectedIndex];
      const newLang = selectedOption.value;
      const newBcp47 = selectedOption.getAttribute('data-bcp47') || (window.resolveBcp47 ? window.resolveBcp47(newLang) : `${newLang}-IN`);

      language = newLang;
      bcp47 = newBcp47;
      chatInterface.dataset.language = newLang;
      chatInterface.dataset.bcp47 = newBcp47;

      // Immediately cancel playing speech and update engines
      window.stopAISpeech();
      resetAllSpeakerButtons();
      setStatus('active');

      if (window.setSessionLanguage) {
        window.setSessionLanguage(newLang, newBcp47);
      }
      speechEngine.setLanguage(newBcp47);

      // Reset auto-spoken cache so new questions in the new language speak cleanly
      lastAutoSpokenText = '';

      // Update session language in backend database asynchronously
      try {
        await fetch(`/api/patient/change-language/${sessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: newLang })
        });
      } catch (err) {
        console.warn('[Language Switch Sync Error]', err);
      }
    });
  }

  // START Button Handler
  if (startBtn) {
    startBtn.addEventListener('click', () => {
      welcomeCard.style.display = 'none';
      chatInterface.style.display = 'grid';

      // Show AI Active indicator
      setStatus('active');

      // Fetch initial question if messages empty
      if (chatMessages.children.length === 0) {
        sendToAI("START_SESSION", true);
      }
    });
  }

  function setStatus(state) {
    if (!aiStatusIndicator) return;
    aiStatusIndicator.style.display = 'inline-flex';
    aiStatusIndicator.className = 'ai-status-pill';

    if (state === 'active') {
      aiStatusIndicator.classList.add('ai-status-active');
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> 🟢 AYUSH KRITI Active`;
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
      aiStatusIndicator.innerHTML = `<span class="pulse-dot"></span> 🔊 AYUSH KRITI speaking...`;
    } else if (state === 'urgent') {
      aiStatusIndicator.classList.add('ai-status-urgent');
      aiStatusIndicator.innerHTML = `🔴 Emergency Triage Alert`;
    }
  }

  // Listen to custom speaking state change events
  window.addEventListener('ai-speaking-state-change', (e) => {
    if (e.detail && e.detail.isSpeaking) {
      setStatus('speaking');
    } else {
      if (aiStatusIndicator && aiStatusIndicator.classList.contains('ai-status-speaking')) {
        setStatus('active');
      }
    }
  });

  function appendMessage(sender, text) {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${sender === 'patient' ? 'message-patient' : 'message-ai'}`;

    const textEl = document.createElement('div');
    textEl.className = 'message-text';
    textEl.textContent = text;
    bubble.appendChild(textEl);

    const meta = document.createElement('div');
    meta.className = 'message-meta';

    const labelSpan = document.createElement('span');
    labelSpan.textContent = `${sender === 'patient' ? 'Patient' : 'AYUSH KRITI'} • ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    meta.appendChild(labelSpan);

    let speakerBtn = null;
    if (sender === 'ai') {
      speakerBtn = document.createElement('button');
      speakerBtn.type = 'button';
      speakerBtn.className = 'msg-speaker-btn';
      speakerBtn.title = 'Listen / Replay response';
      speakerBtn.innerHTML = '🔊 <span>Listen</span>';

      speakerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (window.isAISpeaking && speakerBtn.classList.contains('is-speaking')) {
          // Stop / mute speech if currently speaking
          window.stopAISpeech();
          resetAllSpeakerButtons();
          setStatus('active');
        } else {
          // Play or replay this specific message in current language
          window.stopAISpeech();
          resetAllSpeakerButtons();
          speakerBtn.classList.add('is-speaking');
          speakerBtn.innerHTML = '⏹️ <span>Stop</span>';
          speakerBtn.title = 'Stop reading aloud';

          window.speakAIResponse(text, {
            lang: bcp47,
            onStart: () => {
              setStatus('speaking');
            },
            onEnd: () => {
              speakerBtn.classList.remove('is-speaking');
              speakerBtn.innerHTML = '🔊 <span>Listen</span>';
              speakerBtn.title = 'Listen / Replay response';
              setStatus('active');
            },
            onError: (err) => {
              speakerBtn.classList.remove('is-speaking');
              speakerBtn.innerHTML = '🔊 <span>Listen</span>';
              speakerBtn.title = 'Listen / Replay response';
              setStatus('active');
            }
          });
        }
      });
      meta.appendChild(speakerBtn);
    }

    bubble.appendChild(meta);
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Trigger automated voice narration for new AI messages if Voice is ON
    if (sender === 'ai') {
      if (window.enableVoiceNarration && text && text !== lastAutoSpokenText) {
        lastAutoSpokenText = text;
        // Stop any previously playing speech
        window.stopAISpeech();
        resetAllSpeakerButtons();

        if (speakerBtn) {
          speakerBtn.classList.add('is-speaking');
          speakerBtn.innerHTML = '⏹️ <span>Stop</span>';
          speakerBtn.title = 'Stop reading aloud';
        }

        window.speakAIResponse(text, {
          lang: bcp47,
          onStart: () => {
            setStatus('speaking');
          },
          onEnd: () => {
            if (speakerBtn) {
              speakerBtn.classList.remove('is-speaking');
              speakerBtn.innerHTML = '🔊 <span>Listen</span>';
              speakerBtn.title = 'Listen / Replay response';
            }
            setStatus('active');
          },
          onError: (err) => {
            if (speakerBtn) {
              speakerBtn.classList.remove('is-speaking');
              speakerBtn.innerHTML = '🔊 <span>Listen</span>';
              speakerBtn.title = 'Listen / Replay response';
            }
            setStatus('active');
          }
        });
      } else {
        setStatus('active');
      }
    }
  }

  async function sendToAI(messageText, isInitial = false) {
    if (!messageText.trim()) return;

    // Cancel ongoing speech when sending an answer or new question
    window.stopAISpeech();
    resetAllSpeakerButtons();

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
      appendMessage('ai', 'Error communicating with AYUSH KRITI service. Please try again.');
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
      // If AI is currently speaking, stop it immediately when user clicks mic
      if (window.isAISpeaking) {
        window.stopAISpeech();
        resetAllSpeakerButtons();
        setStatus('active');
      }

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
}

// Ensure execution whether DOM is loading or already ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initKioskChat);
} else {
  initKioskChat();
}
