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

  function renderExtractedData(data) {
    ocrResultsPanel.style.display = 'block';
    extractedContent.innerHTML = '';

    const docTypeBadge = document.createElement('div');
    docTypeBadge.className = 'kiosk-badge';
    docTypeBadge.textContent = `Document Type: ${data.document_type.toUpperCase()} | Confidence: ${data.ocr_confidence.toUpperCase()}`;
    extractedContent.appendChild(docTypeBadge);

    if (data.extracted_data.lab_tests && data.extracted_data.lab_tests.length > 0) {
      const table = document.createElement('table');
      table.className = 'clinical-table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>Test Name</th>
            <th>Value</th>
            <th>Reference Range</th>
            <th>Doctor Flag</th>
          </tr>
        </thead>
        <tbody>
          ${data.extracted_data.lab_tests.map(t => `
            <tr class="${t.abnormal_flag === 1 ? 'abnormal-row' : ''}">
              <td><strong>${t.test_name}</strong></td>
              <td>${t.value} ${t.unit}</td>
              <td>${t.reference_range}</td>
              <td>${t.abnormal_flag === 1 ? '<span class="badge-urgent">⚠️ ABNORMAL</span>' : '<span class="badge-normal">Normal</span>'}</td>
            </tr>
          `).join('')}
        </tbody>
      `;
      extractedContent.appendChild(table);
    } else if (data.extracted_data.prescriptions && data.extracted_data.prescriptions.length > 0) {
      const table = document.createElement('table');
      table.className = 'clinical-table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>Medicine Name</th>
            <th>Strength</th>
            <th>Dosage / Frequency</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          ${data.extracted_data.prescriptions.map(p => `
            <tr>
              <td><strong>${p.medicine_name}</strong></td>
              <td>${p.strength}</td>
              <td>${p.dosage}</td>
              <td>${p.duration}</td>
            </tr>
          `).join('')}
        </tbody>
      `;
      extractedContent.appendChild(table);
    } else {
      extractedContent.innerHTML += `<p style="margin-top: 1rem; color: var(--ayush-text-muted);">Extracted raw text: <pre style="white-space: pre-wrap; background: #f8fafc; padding: 1rem; border-radius: 8px;">${data.raw_ocr_text || 'No readable text extracted. Marked for doctor review.'}</pre></p>`;
    }
  }
});
