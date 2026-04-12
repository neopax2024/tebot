/**
 * generator.js — Code generation, live preview, and export.
 *
 * Depends on: app.js (window.App)
 * Uses: /api/generate/qr, /api/generate/barcode, /api/generate/datamatrix
 */

'use strict';

(function () {
  const { apiFetch, showToast, haptic, saveHistory, downloadBlob, tg } = window.App;

  // ── State ─────────────────────────────────────────────────────────────
  let activeType   = 'qr';
  let activeFmt    = 'png';
  let activeStyle  = 'square';
  let previewTimer = null;
  let logoFile     = null;

  // ── DOM refs ──────────────────────────────────────────────────────────
  const genSpinner        = document.getElementById('gen-spinner');
  const previewImg        = document.getElementById('preview-img');
  const previewPlaceholder = document.querySelector('.preview-placeholder');
  const btnGenerate       = document.getElementById('btn-generate');
  const btnGenerateSend   = document.getElementById('btn-generate-send');
  const btnRefreshPreview = document.getElementById('btn-refresh-preview');

  // QR
  const qrDataType   = document.getElementById('qr-data-type');
  const qrData       = document.getElementById('qr-data');
  const wifiFields   = document.getElementById('wifi-fields');
  const wifiSsid     = document.getElementById('wifi-ssid');
  const wifiPassword = document.getElementById('wifi-password');
  const wifiSecurity = document.getElementById('wifi-security');
  const qrFgColor    = document.getElementById('qr-fg-color');
  const qrBgColor    = document.getElementById('qr-bg-color');
  const qrFgLabel    = document.getElementById('qr-fg-label');
  const qrBgLabel    = document.getElementById('qr-bg-label');
  const qrEcSelect   = document.getElementById('qr-ec');
  const logoInput    = document.getElementById('logo-input');
  const btnUploadLogo= document.getElementById('btn-upload-logo');
  const btnRemoveLogo= document.getElementById('btn-remove-logo');
  const logoPreview  = document.getElementById('logo-preview');
  const logoImg      = document.getElementById('logo-img');

  // Barcode
  const bcFormat  = document.getElementById('bc-format');
  const bcData    = document.getElementById('bc-data');
  const bcFgColor = document.getElementById('bc-fg-color');
  const bcBgColor = document.getElementById('bc-bg-color');

  // Data Matrix
  const dmData    = document.getElementById('dm-data');
  const dmFgColor = document.getElementById('dm-fg-color');
  const dmBgColor = document.getElementById('dm-bg-color');

  // ── Code type selector ────────────────────────────────────────────────
  document.querySelectorAll('.type-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.type-btn').forEach(b => b.classList.toggle('active', b === btn));
      activeType = btn.dataset.type;
      document.querySelectorAll('.gen-options').forEach(el => {
        el.style.display = el.id === `opts-${activeType}` ? 'block' : 'none';
      });
      schedulePreview();
    });
  });

  // ── Style selector ────────────────────────────────────────────────────
  document.querySelectorAll('.style-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.style-btn').forEach(b => b.classList.toggle('active', b === btn));
      activeStyle = btn.dataset.style;
      schedulePreview();
    });
  });

  // ── Format selector ───────────────────────────────────────────────────
  document.querySelectorAll('.format-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const parent = btn.closest('.format-selector');
      parent.querySelectorAll('.format-btn').forEach(b => b.classList.toggle('active', b === btn));
      activeFmt = btn.dataset.fmt;
    });
  });

  // ── WiFi fields toggle ────────────────────────────────────────────────
  qrDataType.addEventListener('change', () => {
    wifiFields.style.display = qrDataType.value === 'wifi' ? 'block' : 'none';
    schedulePreview();
  });

  // ── Color pickers ─────────────────────────────────────────────────────
  qrFgColor.addEventListener('input', () => { qrFgLabel.textContent = qrFgColor.value; schedulePreview(); });
  qrBgColor.addEventListener('input', () => { qrBgLabel.textContent = qrBgColor.value; schedulePreview(); });

  // ── Logo upload ───────────────────────────────────────────────────────
  btnUploadLogo.addEventListener('click', () => logoInput.click());
  logoInput.addEventListener('change', () => {
    const file = logoInput.files[0];
    if (!file) return;
    logoFile = file;
    const url = URL.createObjectURL(file);
    logoImg.src = url;
    logoPreview.style.display = 'flex';
    btnUploadLogo.style.display = 'none';
    schedulePreview();
  });
  btnRemoveLogo.addEventListener('click', () => {
    logoFile = null;
    logoPreview.style.display = 'none';
    btnUploadLogo.style.display = 'block';
    schedulePreview();
  });

  // ── Data input triggers ───────────────────────────────────────────────
  [qrData, qrEcSelect, bcData, bcFormat, dmData].forEach(el => {
    el?.addEventListener('input', schedulePreview);
    el?.addEventListener('change', schedulePreview);
  });
  [wifiSsid, wifiPassword].forEach(el => el?.addEventListener('input', schedulePreview));

  // ── Refresh button ────────────────────────────────────────────────────
  btnRefreshPreview.addEventListener('click', generatePreview);

  // ── Scheduled preview (debounced 800ms) ──────────────────────────────
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(generatePreview, 800);
  }

  async function generatePreview() {
    const body = buildRequestBody();
    if (!body || !body.data) return;

    try {
      const endpoint = endpointFor(activeType);
      const previewBody = { ...body, export_format: 'png' };
      const res = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(previewBody),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      previewImg.src = url;
      previewImg.style.display = 'block';
      if (previewPlaceholder) previewPlaceholder.style.display = 'none';
    } catch { /* silent */ }
  }

  // ── Generate & download ───────────────────────────────────────────────
  btnGenerate.addEventListener('click', async () => {
    const body = buildRequestBody();
    if (!body?.data?.trim()) {
      showToast('Please enter some data to encode.');
      haptic('warning');
      return;
    }

    showGenSpinner(true);
    try {
      const endpoint = endpointFor(activeType);
      const res = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, export_format: activeFmt }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const ext  = activeFmt;
      downloadBlob(blob, `code.${ext}`);
      haptic('success');
      showToast('Downloaded!');

      saveHistory('gen', {
        type: activeType,
        data: body.data,
        format: ext,
        date: new Date().toLocaleDateString(),
      });

    } catch (err) {
      showToast(`Error: ${err.message}`);
      haptic('error');
    } finally {
      showGenSpinner(false);
    }
  });

  // ── Send to Bot ───────────────────────────────────────────────────────
  btnGenerateSend.addEventListener('click', () => {
    const body = buildRequestBody();
    if (!body?.data?.trim()) {
      showToast('Enter data first.');
      return;
    }
    tg?.sendData(JSON.stringify({
      action: 'generate',
      code_type: activeType,
      data: body.data,
      export_format: activeFmt,
      options: body,
    }));
  });

  // ── Helpers ───────────────────────────────────────────────────────────
  function buildRequestBody() {
    if (activeType === 'qr') {
      let data = qrData.value.trim();
      const dtype = qrDataType.value;
      if (dtype === 'wifi') {
        const ssid = wifiSsid.value.trim();
        const pw   = wifiPassword.value.trim();
        const sec  = wifiSecurity.value || 'WPA';
        data = `WIFI:T:${sec};S:${ssid};P:${pw};;`;
      } else if (dtype === 'email' && data && !data.startsWith('mailto:')) {
        data = `mailto:${data}`;
      } else if (dtype === 'phone' && data && !data.startsWith('tel:')) {
        data = `tel:${data}`;
      }
      return {
        data,
        error_correction: qrEcSelect.value,
        fg_color: qrFgColor.value,
        bg_color: qrBgColor.value,
        style: activeStyle,
        size_px: 400,
      };
    }

    if (activeType === 'barcode') {
      return {
        data: bcData.value.trim(),
        barcode_format: bcFormat.value,
        fg_color: bcFgColor.value,
        bg_color: bcBgColor.value,
      };
    }

    if (activeType === 'datamatrix') {
      return {
        data: dmData.value.trim(),
        fg_color: dmFgColor.value,
        bg_color: dmBgColor.value,
        size_px: 300,
      };
    }

    return null;
  }

  function endpointFor(type) {
    const map = { qr: '/api/generate/qr', barcode: '/api/generate/barcode', datamatrix: '/api/generate/datamatrix' };
    return map[type] || '/api/generate/qr';
  }

  function showGenSpinner(show) {
    genSpinner.style.display = show ? 'flex' : 'none';
    btnGenerate.disabled = show;
    btnGenerateSend.disabled = show;
  }

})();
