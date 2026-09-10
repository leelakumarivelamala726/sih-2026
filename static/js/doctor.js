/**
 * Ministry of Ayush – Smart MediKiosk
 * Doctor Dashboard Interactive Console
 */

document.addEventListener('DOMContentLoaded', () => {
  const patientSelect = document.getElementById('doctorPatientSelect');
  const tabButtons = document.querySelectorAll('.console-tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const verifyBtn = document.getElementById('verifyClinicalBtn');

  let activeSessionId = null;

  // Tab switching
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(btn.dataset.tab);
      if (targetPane) targetPane.classList.add('active');
    });
  });

  function switchTab(tabId) {
    tabButtons.forEach(b => {
      if (b.dataset.tab === tabId) b.classList.add('active');
      else b.classList.remove('active');
    });
    tabPanes.forEach(p => {
      if (p.id === tabId) p.classList.add('active');
      else p.classList.remove('active');
    });
  }

  // Quick Patient Switcher Event
  if (patientSelect) {
    patientSelect.addEventListener('change', (e) => {
      const sid = e.target.value;
      if (sid) {
        activeSessionId = sid;
        loadPatientBundle(sid);
      }
    });
  }

  // Doctor Quick Action Buttons
  document.getElementById('actionViewSummaryBtn')?.addEventListener('click', () => {
    switchTab('tabAiSummary');
  });
  document.getElementById('actionViewCaseBtn')?.addEventListener('click', () => {
    switchTab('tabEditHistory');
  });
  document.getElementById('actionViewLabsBtn')?.addEventListener('click', () => {
    switchTab('tabReports');
  });
  document.getElementById('actionPrintSummaryBtn')?.addEventListener('click', () => {
    window.print();
  });

  // Print Case Summary (Header button)
  const printBtn = document.getElementById('printCaseSummaryBtn');
  if (printBtn) {
    printBtn.addEventListener('click', () => {
      window.print();
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function loadPatientBundle(sessionId, forceRefresh = false) {
    const consoleContainer = document.getElementById('clinicalConsole');
    if (!consoleContainer || !sessionId) return;

    const summaryEl = document.getElementById('aiSummaryContent');
    if (summaryEl) {
      summaryEl.innerHTML = `
        <div style="padding: 2.5rem 1rem; text-align: center; color: var(--ayush-text-muted);">
          <span class="pulse-dot"></span>
          <span style="font-weight: 700; color: var(--ayush-primary); margin-left: 0.6rem; font-size: 1.05rem;">Generating clinical summary with AYUSH KRITI...</span>
          <p style="margin-top: 0.5rem; font-size: 0.85rem; color: #64748b;">Synthesizing chief complaint, clinical history, transcripts, and scanned reports...</p>
        </div>
      `;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 15000);

      const url = forceRefresh ? `/api/doctor/patient/${sessionId}?force_refresh=1` : `/api/doctor/patient/${sessionId}`;
      const resp = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}: ${resp.statusText}`);
      }

      const bundle = await resp.json();
      if (!bundle || bundle.error) {
        throw new Error(bundle ? bundle.error : 'Invalid response from clinical bundle API');
      }

      const sessionObj = bundle.session || {};
      const historyObj = bundle.history || {};

      // Populate Header
      const nameEl = document.getElementById('patientHeaderName');
      if (nameEl) nameEl.textContent = `${sessionObj.patient_name || 'Patient'} (${sessionObj.age || 'N/A'}Y / ${sessionObj.gender || 'N/A'})`;
      
      const tokenEl = document.getElementById('patientHeaderToken');
      if (tokenEl) tokenEl.textContent = `Token: ${sessionObj.token_number || '-'}`;
      
      const abhaEl = document.getElementById('patientHeaderAbha');
      if (abhaEl) abhaEl.textContent = `ABHA: ${sessionObj.abha_id || '-'}`;

      const complaintEl = document.getElementById('patientHeaderComplaint');
      if (complaintEl) {
        complaintEl.textContent = `Chief Complaint: ${historyObj.chief_complaint || sessionObj.chief_complaint || 'Case-taking in progress'}`;
      }

      // Red-flag notification badge
      const redFlagBadge = document.getElementById('patientRedFlagBadge');
      if (redFlagBadge) {
        const isUrgent = sessionObj.priority_level === 'urgent' || (historyObj.red_flags && historyObj.red_flags !== '[]');
        redFlagBadge.style.display = isUrgent ? 'inline-block' : 'none';
      }

      // Sync dropdown value
      if (patientSelect && patientSelect.value != sessionId) {
        patientSelect.value = sessionId;
      }

      // Tab 1: Prominent Clinical Summary (Medical Card Layout)
      renderClinicalSummary(bundle, summaryEl);

      // Tab 2: Original Verbatim Transcripts
      const transcriptsContainer = document.getElementById('transcriptContent');
      if (transcriptsContainer) {
        transcriptsContainer.innerHTML = '';
        const transcripts = bundle.transcripts || [];
        if (transcripts.length > 0) {
          transcripts.forEach(t => {
            const tRow = document.createElement('div');
            tRow.style.padding = '0.75rem 1rem';
            tRow.style.borderBottom = '1px solid #e2e8f0';
            tRow.innerHTML = `
              <div style="font-size: 0.8rem; font-weight: 700; color: ${t.speaker === 'ai' ? '#0a4d2e' : '#0284c7'};">
                ${(t.speaker || 'AI').toUpperCase()} (${t.language || 'en'}) • ${t.created_at || ''}
              </div>
              <div style="font-size: 1rem; margin-top: 0.25rem;">${escapeHtml(t.original_transcript)}</div>
            `;
            transcriptsContainer.appendChild(tRow);
          });
        } else {
          transcriptsContainer.innerHTML = '<p style="color: #64748b;">No conversation transcripts recorded.</p>';
        }
      }

      // Tab 3: Scanned Reports & Labs
      renderReportsTab(bundle);

      // Tab 4: Editable History & AYUSH Parameters
      const safeVal = (v) => v || '';
      const setInput = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = safeVal(val);
      };

      setInput('editChiefComplaint', historyObj.chief_complaint);
      setInput('editDuration', historyObj.duration);
      setInput('editOnset', historyObj.onset);
      setInput('editSeverity', historyObj.severity);
      setInput('editLocation', historyObj.location);
      setInput('editAssociatedSymptoms', historyObj.associated_symptoms);
      setInput('editHpi', historyObj.history_of_present_illness);
      setInput('editPastHistory', historyObj.past_medical_history);
      setInput('editPastSurgical', historyObj.past_surgical_history);
      setInput('editMedications', historyObj.medication_history);
      setInput('editAllergies', historyObj.allergy_history);
      setInput('editFamilyHistory', historyObj.family_history);

      // AYUSH fields
      setInput('editPrakriti', historyObj.prakriti);
      setInput('editVikriti', historyObj.vikriti);
      setInput('editDosha', historyObj.dosha);
      setInput('editAgni', historyObj.agni);
      setInput('editAma', historyObj.ama);
      setInput('editKoshta', historyObj.koshta || historyObj.bowel_habits);
      setInput('editNidra', historyObj.nidra || historyObj.sleep);
      setInput('editAhara', historyObj.ahara || historyObj.diet);
      setInput('editVihara', historyObj.vihara || historyObj.lifestyle);
      setInput('editManasika', historyObj.manasika);
      setInput('editAyushHistory', historyObj.ayush_specific_history);

      // Tab 5: Medical Coding
      renderMedicalCodingTab(bundle.coding_suggestions || []);

      // Tab 6: Previous Visits Timeline
      renderTimelineTab(bundle.timeline || []);

    } catch (err) {
      console.error('[Load Patient Error]', err);
      if (summaryEl) {
        const isTimeout = err.name === 'AbortError';
        summaryEl.innerHTML = `
          <div class="alert-banner alert-warning" style="margin: 1.5rem 0; padding: 1.2rem 1.4rem; border-radius: 8px; border: 1.5px solid #f59e0b; background: #fffbeb;">
            <div style="font-weight: 700; color: #92400e; font-size: 1.05rem; display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.4rem;">
              <span>⚠️ Clinical Summary Notice</span>
            </div>
            <p style="margin: 0 0 0.85rem 0; color: #78350f; font-size: 0.95rem; line-height: 1.5;">
              ${isTimeout 
                ? 'The AI summarization request timed out while generating the live draft. You can retry generating the summary, or inspect the transcripts and clinical records in the tabs above.' 
                : (escapeHtml(err.message) || 'The clinical summary could not be retrieved at this moment. Please retry or inspect the transcripts.')}
            </p>
            <div style="display: flex; gap: 0.75rem; align-items: center;">
              <button type="button" class="btn btn-secondary btn-sm" id="retrySummaryBtn" style="padding: 0.4rem 0.9rem; font-size: 0.88rem; font-weight: 700; cursor: pointer;">
                🔄 Retry Summary Generation
              </button>
            </div>
          </div>
        `;
        document.getElementById('retrySummaryBtn')?.addEventListener('click', () => {
          loadPatientBundle(sessionId, true);
        });
      }
    }
  }

  async function loadDedicatedAISummary(sessionId, forceRefresh = false) {
    const summaryEl = document.getElementById('aiSummaryContent');
    if (!summaryEl) return;

    try {
      const resp = await fetch(`/api/ai/summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, force_refresh: forceRefresh })
      });
      const data = await resp.json();
      if (data.status === 'success' && data.summary_text) {
        summaryEl.innerHTML = renderMarkdown(data.summary_text);
      } else {
        throw new Error(data.message || 'AI summary synthesis pending');
      }
    } catch (e) {
      console.warn('[Dedicated AI Summary Warning]', e);
      summaryEl.innerHTML = `
        <div class="alert-banner alert-warning" style="margin: 1.5rem 0; padding: 1.2rem; border-radius: 8px;">
          <strong style="color: #92400e;">⚠️ Clinical Summary Generation Notice</strong>
          <p style="margin-top: 0.4rem; color: #78350f;">Unable to generate AI summary at this moment. Please review the transcripts and clinical history tabs.</p>
          <button type="button" class="btn btn-secondary btn-sm" id="retrySummaryBtn2" style="margin-top: 0.5rem; cursor: pointer;">🔄 Retry</button>
        </div>
      `;
      document.getElementById('retrySummaryBtn2')?.addEventListener('click', () => {
        loadDedicatedAISummary(sessionId, true);
      });
    }
  }

  function renderClinicalSummary(bundle, container) {
    if (!container) return;
    const cs = bundle.clinical_summary || {};
    const sessionObj = bundle.session || {};
    const historyObj = bundle.history || {};
    const details = cs.structured_details || {};
    const keyFindings = cs.key_findings || {};
    const labs = bundle.lab_reports || bundle.labs || [];
    const abnormalLabs = cs.abnormal_findings || labs.filter(l => l.abnormal_flag === 1);
    const rxs = bundle.prescriptions || [];
    const timeline = cs.timeline || bundle.timeline || [];
    const actions = cs.recommended_actions || [
      'Conduct focused physical examination and review vital parameters.',
      'Correlate clinical findings with laboratory investigations.',
      'Finalize prescription and verify case in Doctor Portal.'
    ];

    function getCleanVal(key, defaultVal = 'Not provided') {
      const v = details[key] !== undefined ? details[key] : historyObj[key];
      if (v === undefined || v === null) return defaultVal;
      const s = String(v).trim();
      if (!s || s.toLowerCase() === 'none' || s.toLowerCase() === 'null' || s.toLowerCase() === 'undefined' || s.toLowerCase() === 'n/a' || s.toLowerCase() === 'nil' || s === '[]') {
        return defaultVal;
      }
      return s;
    }

    function renderVal(v) {
      const isMissing = !v || v === 'Not provided';
      return `<span class="cs-field-val ${isMissing ? 'not-provided' : ''}">${escapeHtml(v)}</span>`;
    }

    // Patient Demographics
    const pName = sessionObj.patient_name || details.patient_name || 'Patient';
    const pAge = sessionObj.age || details.age || 'Not provided';
    const pGender = sessionObj.gender || details.gender || 'Not provided';
    const pAbha = sessionObj.abha_id || details.abha_id || 'Not provided';
    const pPhone = sessionObj.phone_number || details.phone_number || 'Not provided';
    const pToken = sessionObj.token_number || '-';
    const pDate = sessionObj.session_date || 'Today';
    const isUrgent = sessionObj.priority_level === 'urgent' || (keyFindings.risk_indicators && keyFindings.risk_indicators.includes('🔴'));

    // Narrative paragraph (exact requested format)
    const narrativeText = cs.clinical_summary_text || `Patient presents with ${getCleanVal('chief_complaints')} for ${getCleanVal('duration_of_symptoms')}. Relevant symptoms include ${getCleanVal('symptoms')}. Past history includes ${getCleanVal('past_medical_history')}. Current medications/allergies: Medications: ${getCleanVal('current_medications')}; Allergies: ${getCleanVal('allergies')}. Lifestyle and wellness indicators show Diet/Appetite: ${getCleanVal('diet_appetite')}; Sleep: ${getCleanVal('sleep_pattern')}; Bowel: ${getCleanVal('bowel_habits')}; Lifestyle: ${getCleanVal('lifestyle_information')}; Mental/Stress: ${getCleanVal('stress_mental_wellness')}. Laboratory/OCR findings indicate ${abnormalLabs.length > 0 ? `${abnormalLabs.length} abnormal lab parameter(s) identified.` : 'Not provided'}.`;

    // Markdown summary text if available
    let rawSummaryText = '';
    if (bundle.summary && bundle.summary.summary_text) rawSummaryText = bundle.summary.summary_text;
    else if (typeof bundle.summary === 'string') rawSummaryText = bundle.summary;

    let html = `
      <div class="cs-card-container">

        <!-- Print Only Official Header -->
        <div class="cs-print-header">
          <h2 style="color: #0a4d2e; margin: 0; font-size: 1.6rem; font-weight: 800;">MINISTRY OF AYUSH • GOVERNMENT OF BHARAT</h2>
          <p style="margin: 0.3rem 0 0 0; font-size: 0.95rem; font-weight: 700; color: #475569;">Smart MediKiosk Clinical History Platform • Clinical Case Summary Report</p>
        </div>

        <!-- 1. Patient Demographics & Identification -->
        <div class="cs-demographics-card">
          <div class="cs-demo-item">
            <span class="cs-demo-label">Patient Name</span>
            <span class="cs-demo-val">${escapeHtml(pName)}</span>
          </div>
          <div class="cs-demo-item">
            <span class="cs-demo-label">Age / Gender</span>
            <span class="cs-demo-val">${escapeHtml(String(pAge))}Y / ${escapeHtml(pGender)}</span>
          </div>
          <div class="cs-demo-item">
            <span class="cs-demo-label">ABHA ID</span>
            <span class="cs-demo-val"><code>${escapeHtml(pAbha)}</code></span>
          </div>
          <div class="cs-demo-item">
            <span class="cs-demo-label">Phone Number</span>
            <span class="cs-demo-val">${escapeHtml(pPhone)}</span>
          </div>
          <div class="cs-demo-item">
            <span class="cs-demo-label">Token / Date</span>
            <span class="cs-demo-val">${escapeHtml(pToken)} • <small style="font-size: 0.82rem; font-weight: 600;">${escapeHtml(pDate)}</small></span>
          </div>
          <div class="cs-demo-item">
            <span class="cs-demo-label">Triage Priority</span>
            <span class="cs-demo-val">${isUrgent ? '<span class="badge-urgent">🔴 URGENT</span>' : '<span class="badge-normal">🟢 Normal</span>'}</span>
          </div>
        </div>

        <!-- 2. AI-Assisted Clinical Summary Narrative -->
        <div class="cs-narrative-card">
          <div class="cs-narrative-header">
            <div class="cs-narrative-title">
              <span>📋 CLINICAL SUMMARY</span>
              <span style="font-size: 0.78rem; font-weight: 800; background: #dcfce7; color: #166534; padding: 0.2rem 0.65rem; border-radius: 12px;">AI-Assisted Draft</span>
            </div>
            <div style="font-size: 0.82rem; color: #166534; font-weight: 600;">
              ℹ️ Synthesized from patient intake • Physician verification required
            </div>
          </div>
          <div class="cs-narrative-text">
            ${escapeHtml(narrativeText)}
          </div>
        </div>

        <!-- 3. Key Clinical Findings Subsection -->
        <div class="cs-key-findings-section">
          <div class="cs-section-heading">
            <span>🔍 Key Clinical Findings</span>
          </div>
          <div class="cs-findings-grid">
            <div class="cs-finding-box">
              <span class="cs-finding-label">Chief Complaint</span>
              <span class="cs-finding-val" style="color: var(--ayush-primary); font-weight: 700;">${escapeHtml(keyFindings.chief_complaint || getCleanVal('chief_complaints'))}</span>
            </div>
            <div class="cs-finding-box">
              <span class="cs-finding-label">Important Symptoms</span>
              <span class="cs-finding-val">${escapeHtml(keyFindings.important_symptoms || getCleanVal('symptoms'))}</span>
            </div>
            <div class="cs-finding-box ${abnormalLabs.length > 0 ? 'urgent' : ''}">
              <span class="cs-finding-label">Abnormal Lab Values</span>
              <span class="cs-finding-val">
                ${abnormalLabs.length > 0 
                  ? abnormalLabs.map(l => `<span class="badge-abnormal-pill" style="margin: 0.15rem 0.25rem 0.15rem 0;">⚠️ ${escapeHtml(l.test_name)}: ${escapeHtml(String(l.value || l.test_value))} ${escapeHtml(l.unit || '')}</span>`).join('') 
                  : '<span style="color: #166534; font-weight: 600;">✓ No abnormal parameters flagged</span>'}
              </span>
            </div>
            <div class="cs-finding-box ${isUrgent ? 'urgent' : ''}">
              <span class="cs-finding-label">Risk Indicators</span>
              <span class="cs-finding-val" style="${isUrgent ? 'color: #991b1b; font-weight: 700;' : 'color: #15803d;'}">
                ${escapeHtml(keyFindings.risk_indicators || (isUrgent ? '🔴 High Priority / Red-Flag Alert' : '🟢 Normal Clinical Priority'))}
              </span>
            </div>
            <div class="cs-finding-box">
              <span class="cs-finding-label">Relevant Medical History</span>
              <span class="cs-finding-val">${escapeHtml(keyFindings.relevant_medical_history || getCleanVal('past_medical_history'))}</span>
            </div>
            <div class="cs-finding-box ${isUrgent ? 'urgent' : ''}">
              <span class="cs-finding-label">AI-Detected Concerns</span>
              <span class="cs-finding-val">
                ${(keyFindings.ai_detected_concerns && keyFindings.ai_detected_concerns.length > 0)
                  ? keyFindings.ai_detected_concerns.map(c => `<div>${escapeHtml(c)}</div>`).join('')
                  : 'No urgent safety concerns detected.'}
              </span>
            </div>
          </div>
        </div>

        <!-- 4. Detailed Structured Clinical Profile -->
        <div class="cs-profile-grid">

          <!-- Subsection: Complaints & Present Illness -->
          <div class="cs-profile-card">
            <h4 style="color: var(--ayush-primary); font-size: 1.02rem; font-weight: 800; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
              🩺 Complaints & Present Illness
            </h4>
            <div class="cs-field-row">
              <span class="cs-field-label">Chief Complaint:</span>
              ${renderVal(getCleanVal('chief_complaints'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Symptoms:</span>
              ${renderVal(getCleanVal('symptoms'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Duration:</span>
              ${renderVal(getCleanVal('duration_of_symptoms'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Present Illness / HPI:</span>
              ${renderVal(getCleanVal('present_illness_hpi'))}
            </div>
          </div>

          <!-- Subsection: Medical, Family & Personal History -->
          <div class="cs-profile-card">
            <h4 style="color: var(--ayush-primary); font-size: 1.02rem; font-weight: 800; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
              📜 Medical & Family History
            </h4>
            <div class="cs-field-row">
              <span class="cs-field-label">Past Medical History:</span>
              ${renderVal(getCleanVal('past_medical_history'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Past Surgical History:</span>
              ${renderVal(getCleanVal('past_surgical_history'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Family History:</span>
              ${renderVal(getCleanVal('family_history'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Personal History:</span>
              ${renderVal(getCleanVal('personal_history'))}
            </div>
          </div>

          <!-- Subsection: Medications, Allergies & Treatments -->
          <div class="cs-profile-card">
            <h4 style="color: var(--ayush-primary); font-size: 1.02rem; font-weight: 800; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
              💊 Medications & Allergies
            </h4>
            <div class="cs-field-row">
              <span class="cs-field-label">Current Medications:</span>
              ${renderVal(getCleanVal('current_medications'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Known Allergies:</span>
              ${renderVal(getCleanVal('allergies'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Previous Treatments:</span>
              ${renderVal(getCleanVal('previous_treatments'))}
            </div>
          </div>

          <!-- Subsection: Lifestyle & Wellness Indicators -->
          <div class="cs-profile-card">
            <h4 style="color: #166534; font-size: 1.02rem; font-weight: 800; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
              🌿 Lifestyle & Wellness Profile
            </h4>
            <div class="cs-field-row">
              <span class="cs-field-label">Lifestyle / Activity:</span>
              ${renderVal(getCleanVal('lifestyle_information'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Sleep Pattern:</span>
              ${renderVal(getCleanVal('sleep_pattern'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Diet & Appetite:</span>
              ${renderVal(getCleanVal('diet_appetite'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Bowel Habits:</span>
              ${renderVal(getCleanVal('bowel_habits'))}
            </div>
            <div class="cs-field-row">
              <span class="cs-field-label">Stress / Mental Wellness:</span>
              ${renderVal(getCleanVal('stress_mental_wellness'))}
            </div>
          </div>

        </div>

        <!-- 5. Uploaded Lab Reports / OCR Results & Abnormal Findings -->
        <div class="cs-profile-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
            <h4 style="color: var(--ayush-primary); font-size: 1.05rem; font-weight: 800; margin: 0;">
              🧪 Uploaded Lab Reports / OCR Results & Abnormal Findings
            </h4>
            <button type="button" class="btn btn-secondary btn-sm" id="btnSummaryToLabs" style="padding: 0.25rem 0.75rem; font-size: 0.8rem; cursor: pointer;">
              View Scanned Images ➔
            </button>
          </div>
          ${labs.length > 0 ? `
            <table class="cs-lab-summary-table">
              <thead>
                <tr>
                  <th>Test Name</th>
                  <th>Result Value</th>
                  <th>Reference Range</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${labs.map(l => {
                  const valStr = l.value !== undefined ? l.value : (l.test_value || 'Not provided');
                  const isAb = l.abnormal_flag === 1;
                  return `
                    <tr style="${isAb ? 'background: #fff5f5;' : ''}">
                      <td><strong>${escapeHtml(l.test_name || 'Lab Investigation')}</strong></td>
                      <td><strong>${escapeHtml(String(valStr))} ${escapeHtml(l.unit || '')}</strong></td>
                      <td>${escapeHtml(l.reference_range || 'Not provided')}</td>
                      <td>${isAb ? '<span class="badge-abnormal-pill">⚠️ ABNORMAL</span>' : '<span class="badge-normal-pill">Normal</span>'}</td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          ` : '<p style="color: #94a3b8; font-style: italic; margin: 0.5rem 0;">No laboratory tests or documents uploaded for this case.</p>'}
        </div>

        <!-- 6. AI-Generated Case Insights & Recommended Follow-up / Next Clinical Action -->
        <div class="cs-profile-card" style="background: #f8fafc; border-left: 4px solid var(--ayush-accent);">
          <h4 style="color: var(--ayush-primary); font-size: 1.05rem; font-weight: 800; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
            💡 AI-Generated Case Insights & Recommended Follow-up
          </h4>
          <ul class="cs-action-list">
            ${actions.map(act => `<li>${escapeHtml(act)}</li>`).join('')}
          </ul>
        </div>

        <!-- 7. Clinical History / Timeline (Previous Visits - Latest First) -->
        <div class="cs-profile-card">
          <h4 style="color: var(--ayush-primary); font-size: 1.05rem; font-weight: 800; margin-bottom: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem;">
            📅 Clinical History / Timeline (Chronological Previous Cases)
          </h4>
          ${timeline.length > 0 ? `
            <table class="cs-lab-summary-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Complaint</th>
                  <th>Assessment</th>
                  <th>Treatment / Recommendation</th>
                  <th>Follow-up</th>
                </tr>
              </thead>
              <tbody>
                ${timeline.map(t => `
                  <tr>
                    <td><strong>${escapeHtml(t.date || '-')}</strong><br><small style="color: #64748b;">Token: ${escapeHtml(t.token_number || '')}</small></td>
                    <td>${escapeHtml(t.complaint || 'Not provided')}</td>
                    <td>${escapeHtml(t.assessment || 'Completed')}</td>
                    <td>${escapeHtml(t.treatment || 'Evaluated')}</td>
                    <td><span class="badge-normal-pill">${escapeHtml(t.status || 'Verified')}</span></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p style="color: #94a3b8; font-style: italic; margin: 0.5rem 0;">Initial consultation at Smart MediKiosk. No previous visits recorded on file.</p>'}
        </div>

        ${rawSummaryText ? `
          <!-- Collapsible Raw AI Markdown Summary -->
          <details style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.75rem 1.2rem;">
            <summary style="font-weight: 700; color: var(--ayush-primary); cursor: pointer; font-size: 0.92rem;">
              📄 View Comprehensive AI Markdown Draft
            </summary>
            <div style="margin-top: 1rem; line-height: 1.7; font-size: 0.98rem;">
              ${renderMarkdown(rawSummaryText)}
            </div>
          </details>
        ` : ''}

        <!-- Print Only Physician Signature Block -->
        <div class="cs-print-signature-block">
          <div>
            <strong>Consulting Physician:</strong> Dr. Rohan Patel, MD (Ayush)<br>
            <span style="font-size: 0.85rem; color: #64748b;">Doctor ID: DOC-AYUSH-01</span>
          </div>
          <div style="text-align: right;">
            <strong>Physician Signature:</strong> ___________________________<br>
            <span style="font-size: 0.85rem; color: #64748b;">Date: ${escapeHtml(pDate)}</span>
          </div>
        </div>

      </div>
    `;

    container.innerHTML = html;

    // Attach in-card jump button
    document.getElementById('btnSummaryToLabs')?.addEventListener('click', () => {
      switchTab('tabReports');
    });
  }

  function renderReportsTab(bundle) {
    const container = document.getElementById('reportsContent');
    container.innerHTML = '';

    const docs = bundle.documents || [];
    const labs = bundle.lab_reports || [];
    const rxs = bundle.prescriptions || [];

    if (docs.length === 0 && labs.length === 0 && rxs.length === 0) {
      container.innerHTML = '<div style="padding: 2.5rem; text-align: center; color: #64748b; background: #ffffff; border: 1px solid var(--ayush-border); border-radius: 8px;">No scanned documents, lab investigations, or historical prescriptions on file for this session.</div>';
      return;
    }

    // Render each Scanned Medical Document with Structured Comparison View
    if (docs.length > 0) {
      docs.forEach((doc, idx) => {
        let extracted = {};
        try {
          extracted = typeof doc.extracted_information === 'string' ? JSON.parse(doc.extracted_information) : (doc.extracted_information || {});
        } catch(e) {
          extracted = {};
        }

        const isLowConf = doc.ocr_confidence === 'low' || extracted.review_required;
        const confBadgeClass = doc.ocr_confidence === 'high' ? 'ocr-badge-high' : (doc.ocr_confidence === 'medium' ? 'ocr-badge-med' : 'ocr-badge-low');
        const confBadgeText = doc.ocr_confidence === 'low' ? '⚠️ LOW / REVIEW REQUIRED' : (doc.ocr_confidence === 'high' ? '✓ HIGH' : 'MEDIUM');

        const docCard = document.createElement('div');
        docCard.style.background = '#ffffff';
        docCard.style.border = '1.5px solid var(--ayush-border)';
        docCard.style.borderRadius = 'var(--radius-md)';
        docCard.style.padding = '1.4rem';
        docCard.style.marginBottom = '2rem';

        let innerHtml = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.75rem;">
            <div>
              <span style="font-weight: 800; color: var(--ayush-primary); font-size: 1.1rem; text-transform: uppercase;">
                📄 Scanned Document #${idx + 1}: ${(doc.document_type || 'MEDICAL REPORT').toUpperCase()}
              </span>
              <span style="color: #64748b; font-size: 0.85rem; margin-left: 0.8rem;">Uploaded: ${doc.created_at || ''}</span>
            </div>
            <div>
              <span class="ocr-badge-confidence ${confBadgeClass}">
                Confidence: ${confBadgeText}
              </span>
            </div>
          </div>
        `;

        if (isLowConf) {
          innerHtml += `
            <div class="alert-banner alert-warning" style="margin-bottom: 1.2rem; font-weight: 600;">
              ⚠️ Some information could not be reliably extracted. Please verify with the original document.
            </div>
          `;
        }

        // Comparison Container
        innerHtml += `
          <div class="ocr-compare-container" style="margin-bottom: 1rem;">
            <!-- Left: Original Scanned Image -->
            <div class="ocr-image-preview-box">
              <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.4rem; font-weight: 700;">ORIGINAL SCANNED DOCUMENT</div>
              <a href="${doc.file_path}" target="_blank" title="Click to view full image in new tab">
                <img src="${doc.file_path}" alt="Document Image" />
              </a>
              <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.4rem;">🔍 Click to enlarge image</div>
            </div>

            <!-- Right: Structured Data -->
            <div style="overflow-x: auto;">
        `;

        // Table for labs or prescriptions belonging to this doc or in extracted
        const docLabs = (extracted.lab_tests && extracted.lab_tests.length > 0) ? extracted.lab_tests : labs.filter(l => l.document_id === doc.id);
        const docRxs = (extracted.prescriptions && extracted.prescriptions.length > 0) ? extracted.prescriptions : rxs.filter(r => r.document_id === doc.id);

        if (docLabs.length > 0) {
          innerHtml += `
            <h4 style="color: var(--ayush-primary); font-size: 1.05rem; margin-bottom: 0.6rem; font-weight: 800;">Extracted Laboratory Results</h4>
            <table class="clinical-table">
              <thead>
                <tr>
                  <th>Test Name</th>
                  <th>Result</th>
                  <th>Unit</th>
                  <th>Reference Range</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${docLabs.map(l => {
                  const val = l.value !== undefined ? l.value : (l.test_value || '');
                  const isAbnormal = l.abnormal_flag === 1;
                  const isUncertain = (l.confidence && String(l.confidence).includes('LOW')) || String(val).toUpperCase().includes('REVIEW');
                  const badgeClass = isUncertain ? 'ocr-badge-low' : (isAbnormal ? 'badge-urgent' : 'badge-normal');
                  const badgeText = isUncertain ? '⚠️ REVIEW REQUIRED' : (isAbnormal ? '⚠️ ABNORMAL' : 'Normal');
                  return `
                    <tr class="${isAbnormal ? 'abnormal-row' : ''}">
                      <td><strong>${escapeHtml(l.test_name)}</strong></td>
                      <td><strong>${escapeHtml(String(val))}</strong></td>
                      <td>${escapeHtml(l.unit || '')}</td>
                      <td>${escapeHtml(l.reference_range || 'N/A')}</td>
                      <td><span class="${badgeClass}">${badgeText}</span></td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          `;
        } else if (docRxs.length > 0) {
          innerHtml += `
            <h4 style="color: var(--ayush-primary); font-size: 1.05rem; margin-bottom: 0.6rem; font-weight: 800;">Extracted Historical Prescriptions</h4>
            <table class="clinical-table">
              <thead>
                <tr>
                  <th>Medicine Name</th>
                  <th>Strength</th>
                  <th>Dosage / Frequency</th>
                  <th>Duration</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                ${docRxs.map(p => {
                  const isUncertain = p.confidence && String(p.confidence).includes('LOW');
                  const badgeClass = isUncertain ? 'ocr-badge-low' : 'ocr-badge-high';
                  const badgeText = isUncertain ? '⚠️ REVIEW REQUIRED' : '✓ Historical';
                  return `
                    <tr>
                      <td><strong>${escapeHtml(p.medicine_name)}</strong></td>
                      <td>${escapeHtml(p.strength || 'N/A')}</td>
                      <td>${escapeHtml(p.dosage || 'As directed')}</td>
                      <td>${escapeHtml(p.duration || 'N/A')}</td>
                      <td><span class="${badgeClass}">${badgeText}</span></td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          `;
        } else {
          innerHtml += `
            <div style="padding: 1.5rem; background: #f8fafc; border-radius: 8px; border: 1px solid var(--ayush-border); text-align: center; color: #64748b;">
              Document saved. Raw verbatim text available below.
            </div>
          `;
        }

        innerHtml += `
            </div>
          </div>

          <!-- Expandable Raw OCR Text Section -->
          <details style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.75rem 1rem;">
            <summary style="cursor: pointer; font-weight: 700; color: #475569; font-size: 0.88rem;">
              📄 View Raw OCR Text
            </summary>
            <pre style="white-space: pre-wrap; font-family: monospace; font-size: 0.82rem; color: #334155; margin-top: 0.75rem; max-height: 220px; overflow-y: auto; background: #ffffff; padding: 0.8rem; border-radius: 4px; border: 1px solid #e2e8f0;">${escapeHtml(doc.ocr_text || 'No raw text extracted.')}</pre>
          </details>
        `;

        docCard.innerHTML = innerHtml;
        container.appendChild(docCard);
      });
    }

    // Also display global lab tests if not tied to specific document
    const orphanLabs = labs.filter(l => !l.document_id);
    if (orphanLabs.length > 0) {
      container.innerHTML += `
        <h4 style="margin-bottom: 0.5rem; color: var(--ayush-primary);">Additional Laboratory Investigations</h4>
        <table class="clinical-table" style="margin-bottom: 2rem;">
          <thead>
            <tr><th>Test Name</th><th>Value</th><th>Reference Range</th><th>Status</th></tr>
          </thead>
          <tbody>
            ${orphanLabs.map(l => `
              <tr class="${l.abnormal_flag === 1 ? 'abnormal-row' : ''}">
                <td>${escapeHtml(l.test_name)}</td>
                <td><strong>${escapeHtml(String(l.value))} ${escapeHtml(l.unit || '')}</strong></td>
                <td>${escapeHtml(l.reference_range || 'N/A')}</td>
                <td>${l.abnormal_flag === 1 ? '<span class="badge-urgent">⚠️ ABNORMAL</span>' : '<span class="badge-normal">Normal</span>'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }
  }

  function renderMedicalCodingTab(suggestions) {
    const container = document.getElementById('codingContent');
    container.innerHTML = '';
    if (!suggestions || suggestions.length === 0) {
      container.innerHTML = '<p style="color: #64748b;">No automated code suggestions. You may add ICD-10 or NAMASTE codes manually below.</p>';
      return;
    }

    container.innerHTML = `
      <h4 style="margin-bottom: 1rem; color: var(--ayush-primary);">AI Coding Suggestions (Select to assign)</h4>
      <div style="display: flex; flex-direction: column; gap: 0.85rem;">
        ${suggestions.map((s, idx) => `
          <div style="padding: 1rem; border: 1.5px solid #e2e8f0; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: 700; font-size: 1.05rem;">${s.condition}</div>
              <div style="font-size: 0.9rem; color: #0284c7; margin-top: 0.2rem;">ICD-10: <code>${s.icd10}</code></div>
              <div style="font-size: 0.9rem; color: #0a4d2e; margin-top: 0.2rem;">Ayush NAMASTE: <code>${s.namaste_ayush_code}</code></div>
            </div>
            <input type="checkbox" checked class="code-select-checkbox" data-icd="${s.icd10}" data-namaste="${s.namaste_ayush_code}" style="width: 22px; height: 22px;" />
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderTimelineTab(timeline) {
    const container = document.getElementById('timelineContent');
    container.innerHTML = '';
    if (!timeline || timeline.length === 0) {
      container.innerHTML = '<p style="color: #64748b;">No previous hospital visits recorded for this patient.</p>';
      return;
    }

    timeline.forEach(v => {
      container.innerHTML += `
        <div style="padding: 1.2rem; border-left: 4px solid var(--ayush-primary); background: #f8fafc; border-radius: 8px; margin-bottom: 1rem;">
          <div style="display: flex; justify-content: space-between;">
            <strong style="color: var(--ayush-primary);">${v.token_number} • Visit Date: ${v.session_date}</strong>
            <span class="badge-verified">${v.status.toUpperCase()}</span>
          </div>
          <div style="margin-top: 0.5rem;"><strong>Chief Complaint:</strong> ${v.chief_complaint || 'N/A'}</div>
          ${v.doctor_notes ? `<div style="margin-top: 0.25rem; color: #475569;"><strong>Doctor Notes:</strong> ${v.doctor_notes} (by ${v.doctor_name || 'Dr. Rohan Patel'})</div>` : ''}
        </div>
      `;
    });
  }

  function getDoctorFormData() {
    return {
      chief_complaint: document.getElementById('editChiefComplaint')?.value.trim() || '',
      duration: document.getElementById('editDuration')?.value.trim() || '',
      onset: document.getElementById('editOnset')?.value.trim() || '',
      severity: document.getElementById('editSeverity')?.value.trim() || '',
      location: document.getElementById('editLocation')?.value.trim() || '',
      associated_symptoms: document.getElementById('editAssociatedSymptoms')?.value.trim() || '',
      history_of_present_illness: document.getElementById('editHpi')?.value.trim() || '',
      past_medical_history: document.getElementById('editPastHistory')?.value.trim() || '',
      past_surgical_history: document.getElementById('editPastSurgical')?.value.trim() || '',
      medication_history: document.getElementById('editMedications')?.value.trim() || '',
      allergy_history: document.getElementById('editAllergies')?.value.trim() || '',
      family_history: document.getElementById('editFamilyHistory')?.value.trim() || '',
      prakriti: document.getElementById('editPrakriti')?.value.trim() || '',
      vikriti: document.getElementById('editVikriti')?.value.trim() || '',
      dosha: document.getElementById('editDosha')?.value.trim() || '',
      agni: document.getElementById('editAgni')?.value.trim() || '',
      ama: document.getElementById('editAma')?.value.trim() || '',
      koshta: document.getElementById('editKoshta')?.value.trim() || '',
      nidra: document.getElementById('editNidra')?.value.trim() || '',
      ahara: document.getElementById('editAhara')?.value.trim() || '',
      vihara: document.getElementById('editVihara')?.value.trim() || '',
      manasika: document.getElementById('editManasika')?.value.trim() || '',
      ayush_specific_history: document.getElementById('editAyushHistory')?.value.trim() || ''
    };
  }

  // Save Doctor History Edits Button
  const saveDoctorHistoryBtn = document.getElementById('saveDoctorHistoryBtn');
  if (saveDoctorHistoryBtn) {
    saveDoctorHistoryBtn.addEventListener('click', async () => {
      if (!activeSessionId) return;
      saveDoctorHistoryBtn.disabled = true;
      saveDoctorHistoryBtn.textContent = 'Saving...';

      try {
        const payload = getDoctorFormData();
        const resp = await fetch(`/api/patient/edit-history/${activeSessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (res.status === 'success') {
          alert('✓ Clinical history & AYUSH parameters updated successfully.');
          if (res.summary && res.summary.summary_text) {
            document.getElementById('aiSummaryContent').innerHTML = renderMarkdown(res.summary.summary_text);
          }
        }
      } catch (err) {
        console.error('[Save History Error]', err);
        alert('Failed to save history edits.');
      } finally {
        saveDoctorHistoryBtn.disabled = false;
        saveDoctorHistoryBtn.textContent = '💾 Save Clinical History Edits';
      }
    });
  }

  // Print / Export Case Summary Button
  const printCaseSummaryBtn = document.getElementById('printCaseSummaryBtn');
  if (printCaseSummaryBtn) {
    printCaseSummaryBtn.addEventListener('click', () => {
      window.print();
    });
  }

  // Final Verification
  if (verifyBtn) {
    verifyBtn.addEventListener('click', async () => {
      if (!activeSessionId) return;

      const formData = getDoctorFormData();

      // First persist updated clinical history to database
      try {
        await fetch(`/api/patient/edit-history/${activeSessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData)
        });
      } catch (e) {
        console.warn('[History Pre-save Warning]', e);
      }

      const doctorNotes = document.getElementById('doctorNotesInput')?.value || 'Verified after clinical consultation.';
      const selectedCodes = [];
      document.querySelectorAll('.code-select-checkbox:checked').forEach(cb => {
        selectedCodes.push({ icd10: cb.dataset.icd, namaste: cb.dataset.namaste });
      });

      try {
        const resp = await fetch(`/api/doctor/verify/${activeSessionId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            edited_history: JSON.stringify(formData),
            doctor_notes: doctorNotes,
            medical_codes: selectedCodes
          })
        });

        const res = await resp.json();
        alert(res.message);
        if (activeSessionId) {
          loadPatientBundle(activeSessionId);
        }
      } catch (err) {
        console.error('[Verification Error]', err);
        alert('Failed to verify clinical record.');
      }
    });
  }

  function renderMarkdown(md) {
    if (!md) return '';

    // Convert markdown alerts: > [!NOTE] or > [!CAUTION]
    let html = md
      .replace(/>\s*\[!CAUTION\][\r\n]+((?:>.*[\r\n]*)+)/gi, (match, p1) => {
        const content = p1.replace(/^>\s?/gm, '');
        return `<div class="alert-banner alert-danger" style="margin: 1rem 0; border: 1.5px solid #ef4444; background: #fef2f2; color: #991b1b; padding: 0.9rem 1.2rem; border-radius: 6px;">${content}</div>`;
      })
      .replace(/>\s*\[!NOTE\][\r\n]+((?:>.*[\r\n]*)+)/gi, (match, p1) => {
        const content = p1.replace(/^>\s?/gm, '');
        return `<div class="alert-banner alert-info" style="margin: 1rem 0; background: #e0f2fe; border: 1.5px solid #0284c7; color: #0369a1; padding: 0.9rem 1.2rem; border-radius: 6px;">${content}</div>`;
      });

    // Parse Markdown tables
    const tableRegex = /((?:\|[^\n\r]+\|(?:\r?\n|$))+)/g;
    html = html.replace(tableRegex, (tableBlock) => {
      const rows = tableBlock.trim().split(/\r?\n/).map(r => r.trim()).filter(Boolean);
      if (rows.length < 2) return tableBlock;
      let headerHtml = '';
      let bodyHtml = '';
      let isHeader = true;

      rows.forEach((row) => {
        if (/^\|(?:\s*:?-+:?\s*\|)+$/.test(row)) {
          isHeader = false;
          return;
        }
        const cells = row.split('|').slice(1, -1).map(c => c.trim());
        if (isHeader) {
          headerHtml += '<tr>' + cells.map(c => `<th style="padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; text-align: left; font-size: 0.88rem; font-weight: 700;">${c}</th>`).join('') + '</tr>';
        } else {
          bodyHtml += '<tr>' + cells.map(c => `<td style="padding: 8px 12px; border: 1px solid #e2e8f0; font-size: 0.9rem;">${c}</td>`).join('') + '</tr>';
        }
      });

      return `<div style="overflow-x: auto; margin: 1rem 0;"><table class="clinical-table" style="width: 100%; border-collapse: collapse; margin: 0.5rem 0;"><thead>${headerHtml}</thead><tbody>${bodyHtml}</tbody></table></div>`;
    });

    // Headers & inline formatting
    html = html
      .replace(/^### (.*$)/gim, '<h3 style="color: var(--ayush-primary); margin-top: 1.2rem; font-size: 1.25rem; font-weight: 800;">$1</h3>')
      .replace(/^#### (.*$)/gim, '<h4 style="color: #1b794f; margin-top: 1rem; font-size: 1.05rem; font-weight: 700; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">$1</h4>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.88rem; color: #0369a1;">$1</code>')
      .replace(/\n\n+/g, '<br><br>')
      .replace(/\n/g, '<br>');

    return html;
  }

  // Initial load
  if (window.initialSessionId) {
    activeSessionId = window.initialSessionId;
  } else if (patientSelect && patientSelect.value) {
    activeSessionId = patientSelect.value;
  }
  
  if (activeSessionId) {
    loadPatientBundle(activeSessionId);
  }
});
