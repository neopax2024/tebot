/**
 * app.js — Core Mini App initialisation, tab routing, and utilities.
 */

'use strict';

// ── Telegram WebApp init ──────────────────────────────────────────────────
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.enableClosingConfirmation();
}

// Backend base URL — same origin in production; override for local dev
const API_BASE = window.TG_API_BASE || window.location.origin;

// ── Tab routing ───────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tabId = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.querySelectorAll('.tab-content').forEach(c => {
      c.classList.toggle('active', c.id === `tab-${tabId}`);
    });
  });
});

// Support ?mode=scan|generate deep-link from bot button
(function () {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get('mode');
  if (mode === 'scan') {
    document.querySelector('[data-tab="scan"]')?.click();
  } else if (mode === 'generate') {
    document.querySelector('[data-tab="generate"]')?.click();
  }
})();

// ── Toast notification ────────────────────────────────────────────────────
function showToast(msg, duration = 2500) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), duration);
}

// ── Haptic feedback ───────────────────────────────────────────────────────
function haptic(type = 'light') {
  tg?.HapticFeedback?.impactOccurred(type);
}

// ── Utility: fetch with timeout ───────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30_000);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return res;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

// ── Utility: download a blob ──────────────────────────────────────────────
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
}

// ── Utility: copy text ────────────────────────────────────────────────────
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback
    const el = document.createElement('textarea');
    el.value = text;
    el.style.position = 'fixed';
    el.style.opacity = '0';
    document.body.appendChild(el);
    el.focus();
    el.select();
    document.execCommand('copy');
    el.remove();
    return true;
  }
}

// ── History tab: toggle ───────────────────────────────────────────────────
document.querySelectorAll('.toggle-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.toggle-btn').forEach(b => b.classList.toggle('active', b === btn));
    renderHistory(btn.dataset.hist);
  });
});

// Simple in-memory history store (populated by scanner.js / generator.js)
const historyStore = {
  scan: JSON.parse(localStorage.getItem('scan_history') || '[]'),
  gen: JSON.parse(localStorage.getItem('gen_history') || '[]'),
};

function saveHistory(type, item) {
  historyStore[type].unshift(item);
  if (historyStore[type].length > 50) historyStore[type].length = 50;
  try {
    localStorage.setItem(`${type}_history`, JSON.stringify(historyStore[type]));
  } catch { /* quota */ }
}

function renderHistory(type = 'scan') {
  const list = document.getElementById('history-list');
  const items = historyStore[type] || [];

  if (!items.length) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <p>No ${type === 'scan' ? 'scans' : 'generated codes'} yet.</p>
      </div>`;
    return;
  }

  list.innerHTML = items.map((item, idx) => `
    <div class="history-item" data-idx="${idx}" data-type="${type}">
      <div class="hi-header">
        <span class="hi-type">${item.code_type || item.type || 'Code'}</span>
        <span class="hi-date">${item.date || ''}</span>
      </div>
      <div class="hi-data">${item.data || item.raw_data || ''}</div>
      <div class="hi-meta">
        <span>${item.content_type || item.format || ''}</span>
        ${item.is_safe === false ? '<span style="color:#ef4444">⚠️ Suspicious</span>' : ''}
      </div>
    </div>
  `).join('');

  // Click to copy
  list.querySelectorAll('.history-item').forEach(el => {
    el.addEventListener('click', async () => {
      const idx = +el.dataset.idx;
      const item = historyStore[type][idx];
      await copyText(item.data || item.raw_data || '');
      showToast('Copied to clipboard!');
      haptic('light');
    });
  });
}

// Initial render
renderHistory('scan');

// ── Expose globals ────────────────────────────────────────────────────────
window.App = {
  tg,
  API_BASE,
  apiFetch,
  downloadBlob,
  copyText,
  showToast,
  haptic,
  saveHistory,
  renderHistory,
};
