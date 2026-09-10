/**
 * Ministry of Ayush – Smart MediKiosk
 * Webcam Document Scanner & OCR Client Service
 */

document.addEventListener('DOMContentLoaded', () => {
  const video = document.getElementById('webcamVideo');
  const canvas = document.getElementById('captureCanvas');
  const startCameraBtn = document.getElementById('startCameraBtn');
  const captureBtn = document.getElementById('captureBtn');
  const retakeBtn = document.getElementById('retakeBtn');
  const uploadInput = document.getElementById('fileUploadInput');
  const ocrStatusEl = document.getElementById('ocrStatus');
  const ocrResultsPanel = document.getElementById('ocrResultsPanel');
  const extractedContent = document.getElementById('extractedContent');

  let stream = null;
  let capturedBase64 = null;
  const sessionId = document.getElementById('scannerContainer')?.dataset.sessionId;

  // Start Camera
  if (startCameraBtn) {
    startCameraBtn.addEventListener('click', async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false
        });
        video.srcObject = stream;
        video.style.display = 'block';
        startCameraBtn.style.display = 'none';
        captureBtn.style.display = 'inline-flex';
      } catch (err) {
        console.error('[Webcam Error]', err);
        alert('Could not access camera. Please allow camera permissions or upload an image file.');
      }
    });
  }

  // Capture Snapshot
  if (captureBtn) {
    captureBtn.addEventListener('click', () => {
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      capturedBase64 = canvas.toDataURL('image/jpeg', 0.92);
      canvas.style.display = 'block';
      video.style.display = 'none';

      captureBtn.style.display = 'none';
      retakeBtn.style.display = 'inline-flex';

      // Process OCR
      processDocumentOCR(capturedBase64);
    });
  }

  // Retake
  if (retakeBtn) {
    retakeBtn.addEventListener('click', () => {
      canvas.style.display = 'none';
      video.style.display = 'block';
      retakeBtn.style.display = 'none';
      captureBtn.style.display = 'inline-flex';
      capturedBase64 = null;
    });
  }

  // File Upload Fallback
  if (uploadInput) {
    uploadInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (event) => {
        capturedBase64 = event.target.result;
        processDocumentOCR(capturedBase64);
      };
      reader.readAsDataURL(file);
    });
  }

  async function processDocumentOCR(base64Data) {
    ocrStatusEl.style.display = 'block';
    ocrStatusEl.textContent = '🟡 Extracting document information using OCR...';

    let clientOcrText = "";
    // If Tesseract.js is loaded via CDN, run client-side OCR for high accuracy
    if (window.Tesseract) {
      try {
        const ocrResult = await Tesseract.recognize(base64Data, 'eng');
        clientOcrText = ocrResult.data.text;
      } catch (e) {
        console.warn('[Tesseract.js fallback]', e);
      }
    }

    try {
      const resp = await fetch('/api/documents/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          image_base64: base64Data,
          ocr_text: clientOcrText
        })
      });

      const data = await resp.json();
      ocrStatusEl.style.display = 'none';
      renderExtractedData(data);
    } catch (err) {
      console.error('[Upload Error]', err);
      ocrStatusEl.className = 'alert-banner alert-danger';
      ocrStatusEl.textContent = 'Failed to process document. Please try again.';
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderExtractedData(data) {
    ocrResultsPanel.style.display = 'block';
    extractedContent.innerHTML = '';

    const isLowConfidence = data.ocr_confidence === 'LOW' || data.review_required;
    const hasLabTests = data.extracted_data && data.extracted_data.lab_tests && data.extracted_data.lab_tests.length > 0;
    const hasPrescriptions = data.extracted_data && data.extracted_data.prescriptions && data.extracted_data.prescriptions.length > 0;
    const isUnreadable = !hasLabTests && !hasPrescriptions && (!data.raw_ocr_text || data.raw_ocr_text.trim().length < 15);

    // Warning / Insufficient Image Banner
    if (isUnreadable) {
      extractedContent.innerHTML += `
        <div class="alert-banner alert-danger" style="margin-bottom: 1.2rem; font-weight: 700;">
          ⚠️ Image quality is insufficient for reliable extraction. Please upload a clearer image.
        </div>
      `;
    } else if (isLowConfidence) {
      extractedContent.innerHTML += `
        <div class="alert-banner alert-warning" style="margin-bottom: 1.2rem; font-weight: 600;">
          ⚠️ Some information could not be reliably extracted. Please verify with the original document.
        </div>
      `;
    }

    // Top Status Header: Document Type & Confidence
    const headerRow = document.createElement('div');
    headerRow.style.display = 'flex';
    headerRow.style.justifyContent = 'space-between';
    headerRow.style.alignItems = 'center';
    headerRow.style.flexWrap = 'wrap';
    headerRow.style.gap = '0.8rem';
    headerRow.style.marginBottom = '1.2rem';
    headerRow.style.padding = '0.85rem 1.2rem';
    headerRow.style.background = '#ffffff';
    headerRow.style.border = '1px solid var(--ayush-border)';
    headerRow.style.borderRadius = '8px';

    const confClass = data.ocr_confidence === 'HIGH' ? 'ocr-badge-high' : (data.ocr_confidence === 'MEDIUM' ? 'ocr-badge-med' : 'ocr-badge-low');
    const confText = data.ocr_confidence === 'LOW' ? 'LOW / REVIEW REQUIRED' : data.ocr_confidence;

    headerRow.innerHTML = `
      <div>
        <strong style="color: var(--ayush-primary); font-size: 1.05rem;">Document Type:</strong>
        <span style="font-weight: 800; text-transform: uppercase; margin-left: 0.35rem; color: #0f172a;">${escapeHtml(data.document_type || 'MEDICAL DOCUMENT')}</span>
      </div>
      <div>
        <strong style="color: #475569; font-size: 0.95rem; margin-right: 0.4rem;">Confidence:</strong>
        <span class="ocr-badge-confidence ${confClass}">
          ${confText === 'HIGH' ? '✓ HIGH' : confText}
        </span>
      </div>
    `;
    extractedContent.appendChild(headerRow);

    // Patient Information Block if detected
    const patientInfo = data.extracted_data && data.extracted_data.patient_info;
    if (patientInfo && (patientInfo.name || patientInfo.age || patientInfo.gender || patientInfo.patient_id)) {
      const pBlock = document.createElement('div');
      pBlock.style.background = '#ffffff';
      pBlock.style.border = '1px solid var(--ayush-border)';
      pBlock.style.borderRadius = '8px';
      pBlock.style.padding = '1rem 1.2rem';
      pBlock.style.marginBottom = '1.2rem';
      pBlock.innerHTML = `
        <h4 style="font-size: 0.95rem; color: var(--ayush-primary); margin-bottom: 0.6rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 800;">Patient Information</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.8rem; font-size: 0.92rem;">
          <div><span style="color: #64748b;">Name:</span> <strong>${escapeHtml(patientInfo.name || 'Not detected')}</strong></div>
          <div><span style="color: #64748b;">Age:</span> <strong>${escapeHtml(patientInfo.age || 'Not detected')}</strong></div>
          <div><span style="color: #64748b;">Gender:</span> <strong>${escapeHtml(patientInfo.gender || 'Not detected')}</strong></div>
          <div><span style="color: #64748b;">Patient ID:</span> <strong>${escapeHtml(patientInfo.patient_id || 'Not detected')}</strong></div>
        </div>
      `;
      extractedContent.appendChild(pBlock);
    }

    // Side-by-side or comparison grid
    const compareGrid = document.createElement('div');
    compareGrid.className = 'ocr-compare-container';

    // Left Column: Original Scanned Image
    const previewBox = document.createElement('div');
    previewBox.className = 'ocr-image-preview-box';
    const previewImgSrc = data.image_url || capturedBase64 || '';
    previewBox.innerHTML = `
      <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.4rem; font-weight: 700;">ORIGINAL SCANNED DOCUMENT</div>
      ${previewImgSrc ? `<a href="${previewImgSrc}" target="_blank" title="Click to view full image in new tab"><img src="${previewImgSrc}" alt="Scanned Document" /></a>` : '<div style="color: #94a3b8; padding: 2rem;">No preview image</div>'}
      <div style="font-size: 0.72rem; color: #94a3b8; margin-top: 0.4rem;">🔍 Click to enlarge image</div>
    `;
    compareGrid.appendChild(previewBox);

    // Right Column: Structured Results Table
    const tableBox = document.createElement('div');
    tableBox.style.overflowX = 'auto';

    if (hasLabTests) {
      tableBox.innerHTML = `
        <h4 style="font-size: 1.05rem; color: var(--ayush-primary); margin-bottom: 0.6rem; font-weight: 800;">Laboratory Results</h4>
        <table class="clinical-table">
          <thead>
            <tr>
              <th>Test Name</th>
              <th>Result</th>
              <th>Unit</th>
              <th>Reference Range</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            ${data.extracted_data.lab_tests.map(t => {
              const conf = String(t.confidence || '');
              const isUncertain = conf.includes('LOW') || conf.includes('REVIEW');
              const badgeClass = isUncertain ? 'ocr-badge-low' : (t.abnormal_flag === 1 ? 'badge-urgent' : 'ocr-badge-high');
              const badgeText = isUncertain ? '⚠️ REVIEW REQUIRED' : (t.abnormal_flag === 1 ? '⚠️ ABNORMAL' : '✓ Normal');
              return `
                <tr class="${t.abnormal_flag === 1 ? 'abnormal-row' : ''}">
                  <td><strong>${escapeHtml(t.test_name)}</strong></td>
                  <td><strong>${escapeHtml(String(t.value))}</strong></td>
                  <td>${escapeHtml(t.unit || '')}</td>
                  <td>${escapeHtml(t.reference_range || 'N/A')}</td>
                  <td><span class="${badgeClass}">${badgeText}</span></td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `;
    } else if (hasPrescriptions) {
      tableBox.innerHTML = `
        <h4 style="font-size: 1.05rem; color: var(--ayush-primary); margin-bottom: 0.6rem; font-weight: 800;">Historical Prescriptions</h4>
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
            ${data.extracted_data.prescriptions.map(p => {
              const conf = String(p.confidence || '');
              const isUncertain = conf.includes('LOW') || conf.includes('REVIEW');
              const badgeClass = isUncertain ? 'ocr-badge-low' : 'ocr-badge-high';
              const badgeText = isUncertain ? '⚠️ REVIEW REQUIRED' : '✓ Recorded';
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
      tableBox.innerHTML = `
        <div style="padding: 1.5rem; background: #ffffff; border-radius: 8px; border: 1px solid var(--ayush-border); text-align: center; color: #64748b;">
          ${isUnreadable ? 'No structured entities could be recognized from this scan.' : 'Medical document text captured. Verbatim text available below.'}
        </div>
      `;
    }

    compareGrid.appendChild(tableBox);
    extractedContent.appendChild(compareGrid);

    // Expandable Raw OCR Text Section
    const rawDetails = document.createElement('details');
    rawDetails.style.marginTop = '1rem';
    rawDetails.style.background = '#ffffff';
    rawDetails.style.border = '1px solid var(--ayush-border)';
    rawDetails.style.borderRadius = '8px';
    rawDetails.style.padding = '0.8rem 1.2rem';
    rawDetails.innerHTML = `
      <summary style="cursor: pointer; font-weight: 700; color: #475569; font-size: 0.92rem;">
        📄 View Raw OCR Text
      </summary>
      <pre style="white-space: pre-wrap; font-family: monospace; font-size: 0.85rem; color: #334155; margin-top: 0.8rem; background: #f8fafc; padding: 1rem; border-radius: 6px; border: 1px solid #cbd5e1; max-height: 250px; overflow-y: auto;">${escapeHtml(data.raw_ocr_text || 'No raw text extracted.')}</pre>
    `;
    extractedContent.appendChild(rawDetails);
  }
});
