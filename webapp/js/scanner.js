/**
 * scanner.js — Image upload, PDF, and live camera scanning logic.
 *
 * Depends on: app.js (window.App)
 * Uses:       /api/scan  (multipart POST)
 * Optional:   jsQR CDN for client-side preview scanning
 */

'use strict';

(function () {
  const { apiFetch, showToast, haptic, saveHistory, downloadBlob, copyText, tg } = window.App;

  // ── DOM refs ──────────────────────────────────────────────────────────
  const uploadZone    = document.getElementById('upload-zone');
  const fileInput     = document.getElementById('file-input');
  const scanSpinner   = document.getElementById('scan-spinner');
  const scanResult    = document.getElementById('scan-result');
  const cameraSection = document.getElementById('camera-section');
  const uploadSection = document.getElementById('upload-section');
  const cameraVideo   = document.getElementById('camera-video');

  const resultBadge   = document.getElementById('result-badge');
  const safetyBadge   = document.getElementById('safety-badge');
  const resultType    = document.getElementById('result-type');
  const resultData    = document.getElementById('result-data');
  const resultSummary = document.getElementById('result-summary');

  const btnOpenCamera   = document.getElementById('btn-open-camera');
  const btnUploadFile   = document.getElementById('btn-upload-file');
  const btnStopCamera   = document.getElementById('btn-stop-camera');
  const btnCopyData     = document.getElementById('btn-copy-data');
  const btnOpenLink     = document.getElementById('btn-open-link');
  const btnRegen        = document.getElementById('btn-regen');
  const btnSendToBot    = document.getElementById('btn-send-to-bot');

  let cameraStream = null;
  let scanLoopId   = null;
  let lastResult   = null;

  // ── Upload zone click & drag ──────────────────────────────────────────
  uploadZone.addEventListener('click', () => fileInput.click());
  btnUploadFile.addEventListener('click', () => fileInput.click());

  uploadZone.addEventListener('dragover', e => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
  uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer?.files[0];
    if (file) processFile(file);
  });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) processFile(file);
    fileInput.value = '';
  });

  // ── File processing ───────────────────────────────────────────────────
  async function processFile(file) {
    showSpinner(true);
    hideResult();

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await apiFetch('/api/scan', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Scan failed.' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const results = await res.json();

      if (!results || results.length === 0) {
        showToast('No codes detected in this file.');
        haptic('warning');
      } else {
        haptic('success');
        displayResult(results[0]);

        // Save to local history
        results.forEach(r => {
          saveHistory('scan', {
            ...r,
            date: new Date().toLocaleDateString(),
          });
        });

        if (results.length > 1) {
          showToast(`Found ${results.length} codes — showing first.`);
        }
      }
    } catch (err) {
      showToast(`Error: ${err.message}`);
      haptic('error');
    } finally {
      showSpinner(false);
    }
  }

  // ── Camera ────────────────────────────────────────────────────────────
  btnOpenCamera.addEventListener('click', startCamera);
  btnStopCamera.addEventListener('click', stopCamera);

  async function startCamera() {
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      cameraVideo.srcObject = cameraStream;
      cameraSection.style.display = 'block';
      uploadSection.style.display = 'none';
      hideResult();
      startScanLoop();
    } catch (err) {
      showToast('Camera access denied or unavailable.');
      haptic('error');
    }
  }

  function stopCamera() {
    if (scanLoopId) { cancelAnimationFrame(scanLoopId); scanLoopId = null; }
    if (cameraStream) {
      cameraStream.getTracks().forEach(t => t.stop());
      cameraStream = null;
    }
    cameraSection.style.display = 'none';
    uploadSection.style.display = 'block';
  }

  function startScanLoop() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    async function loop() {
      if (!cameraStream) return;
      if (cameraVideo.readyState === cameraVideo.HAVE_ENOUGH_DATA) {
        canvas.width  = cameraVideo.videoWidth;
        canvas.height = cameraVideo.videoHeight;
        ctx.drawImage(cameraVideo, 0, 0);

        // Send frame to API every 1.5 seconds
        canvas.toBlob(async blob => {
          if (!blob) return;
          const formData = new FormData();
          formData.append('file', blob, 'frame.jpg');

          try {
            const res = await apiFetch('/api/scan', { method: 'POST', body: formData });
            if (res.ok) {
              const results = await res.json();
              if (results?.length > 0) {
                stopCamera();
                haptic('success');
                displayResult(results[0]);
                saveHistory('scan', { ...results[0], date: new Date().toLocaleDateString() });
              }
            }
          } catch { /* ignore transient errors */ }
        }, 'image/jpeg', 0.85);
      }

      // Re-schedule after 1.5s
      setTimeout(() => { scanLoopId = requestAnimationFrame(loop); }, 1500);
    }

    scanLoopId = requestAnimationFrame(loop);
  }

  // ── Result display ────────────────────────────────────────────────────
  function displayResult(result) {
    lastResult = result;

    resultBadge.textContent = result.code_type || 'Code';
    resultType.textContent  = (result.content_type || 'unknown').toUpperCase();
    resultData.textContent  = result.raw_data || '';

    // Clean summary (strip markdown bold **)
    const summary = (result.summary || '').replace(/\*/g, '');
    resultSummary.textContent = summary;

    // Safety badge
    const isSafe = result.is_safe !== false;
    safetyBadge.textContent = isSafe ? '✅ Safe' : '🚨 Unsafe';
    safetyBadge.className = 'safety-badge ' + (isSafe ? 'safety-safe' : 'safety-dangerous');

    // Show "Open Link" button if URL
    if (result.content_type === 'url') {
      btnOpenLink.style.display = 'inline-flex';
      btnOpenLink.onclick = () => {
        if (isSafe) {
          tg?.openLink ? tg.openLink(result.raw_data) : window.open(result.raw_data, '_blank');
        } else {
          showToast('⚠️ This URL was flagged as unsafe!');
        }
      };
    } else {
      btnOpenLink.style.display = 'none';
    }

    scanResult.style.display = 'block';
    scanResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideResult() { scanResult.style.display = 'none'; lastResult = null; }

  function showSpinner(show) { scanSpinner.style.display = show ? 'flex' : 'none'; }

  // ── Result action buttons ─────────────────────────────────────────────
  btnCopyData.addEventListener('click', async () => {
    if (!lastResult) return;
    await copyText(lastResult.raw_data || '');
    showToast('Copied!');
    haptic('light');
  });

  btnRegen.addEventListener('click', () => {
    if (!lastResult) return;
    // Switch to generate tab and pre-fill data
    document.querySelector('[data-tab="generate"]').click();
    const dataField = document.getElementById('qr-data');
    if (dataField) dataField.value = lastResult.raw_data || '';
    showToast('Data copied to generator!');
  });

  btnSendToBot.addEventListener('click', () => {
    if (!lastResult || !tg) return;
    tg.sendData(JSON.stringify({
      action: 'scan_result',
      code_type: lastResult.code_type,
      raw_data: lastResult.raw_data,
      content_type: lastResult.content_type,
      is_safe: lastResult.is_safe,
    }));
  });

})();
