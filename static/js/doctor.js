/**
 * Ministry of Ayush – Smart MediKiosk
 * Doctor Dashboard Interactive Console
 */

document.addEventListener('DOMContentLoaded', () => {
  const queueListEl = document.getElementById('doctorQueueList');
  const patientSearchInput = document.getElementById('patientSearchInput');
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

  // Load patient bundle when clicking a queue item
  document.addEventListener('click', (e) => {
    const queueItem = e.target.closest('.queue-item');
    if (queueItem) {
      document.querySelectorAll('.queue-item').forEach(i => i.classList.remove('active'));
      queueItem.classList.add('active');
      activeSessionId = queueItem.dataset.sessionId;
      loadPatientBundle(activeSessionId);
    }
  });

  // Patient Search
  if (patientSearchInput) {
    patientSearchInput.addEventListener('input', async (e) => {
      const q = e.target.value.trim();
      if (!q) {
        loadQueue();
        return;
      }
      const resp = await fetch(`/api/doctor/search?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      renderSearchResults(data.results);
    });
  }

  async function loadQueue() {
    try {
      const resp = await fetch('/api/doctor/queue');
      const data = await resp.json();
      renderQueue(data.queue);
    } catch (err) {
      console.error('[Queue Fetch Error]', err);
    }
  }

  function renderQueue(queue) {
    if (!queueListEl) return;
    queueListEl.innerHTML = '';
    if (queue.length === 0) {
      queueListEl.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--ayush-text-muted);">No patients currently in queue.</div>';
      return;
    }

    queue.forEach((p, idx) => {
      const item = document.createElement('div');
      item.className = `queue-item ${p.priority_level === 'urgent' ? 'urgent' : ''} ${idx === 0 && !activeSessionId ? 'active' : ''}`;
      item.dataset.sessionId = p.session_id;

      item.innerHTML = `
        <div class="queue-item-header">
          <span class="queue-token">${p.token_number}</span>
          ${p.priority_level === 'urgent' ? '<span class="badge-urgent">🔴 URGENT</span>' : (p.status === 'verified' ? '<span class="badge-verified">✓ VERIFIED</span>' : '<span class="badge-normal">WAITING</span>')}
        </div>
        <div class="queue-patient-name">${p.patient_name}</div>
        <div class="queue-meta">${p.age}Y • ${p.gender} • ABHA: <code>${p.abha_id}</code></div>
        <div class="queue-meta" style="color: var(--ayush-primary); font-weight: 600;">${p.chief_complaint || 'Case-taking in progress'}</div>
      `;
      queueListEl.appendChild(item);
    });

    if (!activeSessionId && queue.length > 0) {
      activeSessionId = queue[0].session_id;
      loadPatientBundle(activeSessionId);
    }
  }

  function renderSearchResults(results) {
    if (!queueListEl) return;
    queueListEl.innerHTML = '<div style="padding: 0.5rem 0.8rem; font-size: 0.8rem; color: #92400e; background: #fffbeb; border-radius: 6px; margin-bottom: 0.5rem;">Note: Phone numbers may match multiple family members.</div>';
    results.forEach(p => {
      const item = document.createElement('div');
      item.className = 'queue-item';
      item.innerHTML = `
        <div class="queue-patient-name">${p.patient_name}</div>
        <div class="queue-meta">${p.age}Y • ${p.gender} • ABHA: <code>${p.abha_id}</code></div>
        <div class="queue-meta">Phone: ${p.phone_number} • Total Visits: ${p.visit_count}</div>
      `;
      queueListEl.appendChild(item);
    });
  }

  async function loadPatientBundle(sessionId) {
    const consoleContainer = document.getElementById('clinicalConsole');
    if (!consoleContainer) return;

    try {
      const resp = await fetch(`/api/doctor/patient/${sessionId}`);
      const bundle = await resp.json();

      // Populate Header
      document.getElementById('patientHeaderName').textContent = `${bundle.session.patient_name} (${bundle.session.age}Y / ${bundle.session.gender})`;
      document.getElementById('patientHeaderToken').textContent = `Token: ${bundle.session.token_number}`;
      document.getElementById('patientHeaderAbha').textContent = `ABHA: ${bundle.session.abha_id}`;

      // Tab 1: AI Summary
      document.getElementById('aiSummaryContent').innerHTML = renderMarkdown(bundle.summary.summary_text);

      // Tab 2: Original Verbatim Transcripts
      const transcriptsContainer = document.getElementById('transcriptContent');
      transcriptsContainer.innerHTML = '';
      if (bundle.transcripts && bundle.transcripts.length > 0) {
        bundle.transcripts.forEach(t => {
          const tRow = document.createElement('div');
          tRow.style.padding = '0.75rem 1rem';
          tRow.style.borderBottom = '1px solid #e2e8f0';
          tRow.innerHTML = `
            <div style="font-size: 0.8rem; font-weight: 700; color: ${t.speaker === 'ai' ? '#0a4d2e' : '#0284c7'};">
              ${t.speaker.toUpperCase()} (${t.language}) • ${t.created_at}
            </div>
            <div style="font-size: 1rem; margin-top: 0.25rem;">${t.original_transcript}</div>
          `;
          transcriptsContainer.appendChild(tRow);
        });
      } else {
        transcriptsContainer.innerHTML = '<p style="color: #64748b;">No conversation transcripts recorded.</p>';
      }

      // Tab 3: Scanned Reports & Labs
      renderReportsTab(bundle);

      // Tab 4: Editable History & AYUSH Parameters
      document.getElementById('editChiefComplaint').value = bundle.history.chief_complaint || '';
      document.getElementById('editDuration').value = bundle.history.duration || '';
      document.getElementById('editOnset').value = bundle.history.onset || '';
      document.getElementById('editSeverity').value = bundle.history.severity || '';
      document.getElementById('editLocation').value = bundle.history.location || '';
      document.getElementById('editAssociatedSymptoms').value = bundle.history.associated_symptoms || '';
      document.getElementById('editHpi').value = bundle.history.history_of_present_illness || '';
      document.getElementById('editPastHistory').value = bundle.history.past_medical_history || '';
      document.getElementById('editPastSurgical').value = bundle.history.past_surgical_history || '';
      document.getElementById('editMedications').value = bundle.history.medication_history || '';
      document.getElementById('editAllergies').value = bundle.history.allergy_history || '';
      document.getElementById('editFamilyHistory').value = bundle.history.family_history || '';

      // AYUSH fields
      document.getElementById('editPrakriti').value = bundle.history.prakriti || '';
      document.getElementById('editVikriti').value = bundle.history.vikriti || '';
      document.getElementById('editDosha').value = bundle.history.dosha || '';
      document.getElementById('editAgni').value = bundle.history.agni || '';
      document.getElementById('editAma').value = bundle.history.ama || '';
      document.getElementById('editKoshta').value = bundle.history.koshta || bundle.history.bowel_habits || '';
      document.getElementById('editNidra').value = bundle.history.nidra || bundle.history.sleep || '';
      document.getElementById('editAhara').value = bundle.history.ahara || bundle.history.diet || '';
      document.getElementById('editVihara').value = bundle.history.vihara || bundle.history.lifestyle || '';
      document.getElementById('editManasika').value = bundle.history.manasika || '';
      document.getElementById('editAyushHistory').value = bundle.history.ayush_specific_history || '';

      // Tab 5: Medical Coding
      renderMedicalCodingTab(bundle.coding_suggestions);

      // Tab 6: Previous Visits Timeline
      renderTimelineTab(bundle.timeline);

    } catch (err) {
      console.error('[Load Patient Error]', err);
    }
  }

  function renderReportsTab(bundle) {
    const container = document.getElementById('reportsContent');
    container.innerHTML = '';

    // Lab Tests Table
    if (bundle.lab_reports && bundle.lab_reports.length > 0) {
      container.innerHTML += `
        <h4 style="margin-bottom: 0.5rem; color: var(--ayush-primary);">Extracted Laboratory Investigations</h4>
        <table class="clinical-table" style="margin-bottom: 2rem;">
          <thead>
            <tr><th>Test Name</th><th>Value</th><th>Reference Range</th><th>Status</th></tr>
          </thead>
          <tbody>
            ${bundle.lab_reports.map(l => `
              <tr class="${l.abnormal_flag === 1 ? 'abnormal-row' : ''}">
                <td>${l.test_name}</td>
                <td><strong>${l.value} ${l.unit || ''}</strong></td>
                <td>${l.reference_range || 'N/A'}</td>
                <td>${l.abnormal_flag === 1 ? '<span class="badge-urgent">⚠️ ABNORMAL</span>' : '<span class="badge-normal">Normal</span>'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    // Historical Prescriptions Table
    if (bundle.prescriptions && bundle.prescriptions.length > 0) {
      container.innerHTML += `
        <h4 style="margin-bottom: 0.5rem; color: var(--ayush-primary);">Historical Prescriptions (Extracted Document)</h4>
        <table class="clinical-table" style="margin-bottom: 2rem;">
          <thead>
            <tr><th>Medicine</th><th>Strength</th><th>Dosage</th><th>Duration</th></tr>
          </thead>
          <tbody>
            ${bundle.prescriptions.map(p => `
              <tr>
                <td>${p.medicine_name}</td>
                <td>${p.strength || 'N/A'}</td>
                <td>${p.dosage || 'N/A'}</td>
                <td>${p.duration || 'N/A'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    if (bundle.documents && bundle.documents.length > 0) {
      container.innerHTML += `<h4 style="margin-bottom: 0.5rem;">Scanned Document Images</h4><div style="display: flex; gap: 1rem; flex-wrap: wrap;">`;
      bundle.documents.forEach(d => {
        container.innerHTML += `
          <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.5rem; text-align: center;">
            <a href="${d.file_path}" target="_blank">
              <img src="${d.file_path}" style="width: 160px; height: 120px; object-fit: cover; border-radius: 4px;" />
            </a>
            <div style="font-size: 0.75rem; margin-top: 0.3rem;">${d.document_type.toUpperCase()}</div>
          </div>
        `;
      });
      container.innerHTML += `</div>`;
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
        loadQueue();
      } catch (err) {
        console.error('[Verification Error]', err);
        alert('Failed to verify clinical record.');
      }
    });
  }

  function renderMarkdown(md) {
    if (!md) return '';
    return md
      .replace(/^### (.*$)/gim, '<h3 style="color: var(--ayush-primary); margin-top: 1rem;">$1</h3>')
      .replace(/^#### (.*$)/gim, '<h4 style="color: #1b794f; margin-top: 0.8rem;">$1</h4>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">$1</code>')
      .replace(/\n/g, '<br>');
  }

  // Initial load
  loadQueue();
});
