// Standalone checkout page
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('checkout');
  if (!root) return;
  const gid = root.getAttribute('data-gid');
  const coTotal = document.getElementById('co-total');
  const coInfo = document.getElementById('co-info');
  const coTimer = document.getElementById('co-timer');
  const coRef = document.getElementById('co-ref');
  const btnConfirm = document.getElementById('btn-co-confirm');
  const coDiscNote = document.getElementById('co-disc-note');
  const refError = document.getElementById('ref-error');
  const refCounter = document.getElementById('ref-counter');
  const blockedOverlay = document.getElementById('blocked-overlay');
  const blockedClose = document.getElementById('blocked-close');
  const blockedWhats = document.getElementById('blocked-whatsapp');
  const waLink = (root.getAttribute('data-whatsapp') || '').trim();
  const gname = (root.getAttribute('data-gname') || '').trim();
  const gimg = (root.getAttribute('data-gimg') || '').trim();
  // Proof / comprobante elements
  const proofInput = document.getElementById('payment_capture');
  const proofDropzone = document.getElementById('proofDropzone');
  const proofInner = document.getElementById('proofDropzoneInner');
  const proofFileName = document.getElementById('proofFileName');
  const proofPreview = document.getElementById('proofPreview');
  const captureRefBox = document.getElementById('captureRefBox');
  const captureRefLabel = document.getElementById('captureRefLabel');
  const captureRefValue = document.getElementById('captureRefValue');
  const captureRefHint = document.getElementById('captureRefHint');
  let proofPreviewUrl = '';
  let captureReferenceLookupId = 0;
  let latestCaptureReferencePreview = '';
  let isReferenceValid = false;
  let hasCapture = false;
  let isBinanceAuto = false;
  let binanceAutoCode = '';
  let checkoutRequestInFlight = false;
  let checkoutAttemptKey = '';
  let captureAnalysisInFlight = false;
  let captureAnalysisPromise = null;

  function getCheckoutAttemptKey() {
    if (checkoutAttemptKey) return checkoutAttemptKey;
    try {
      if (window.crypto && typeof window.crypto.randomUUID === 'function') {
        checkoutAttemptKey = `checkout:${gid}:${window.crypto.randomUUID()}`;
        return checkoutAttemptKey;
      }
    } catch (_) {}
    checkoutAttemptKey = `checkout:${gid}:${Date.now().toString(36)}:${Math.random().toString(36).slice(2, 10)}`;
    return checkoutAttemptKey;
  }

  function releaseCheckoutRequest() {
    checkoutRequestInFlight = false;
    updateSubmitState();
  }

  function renderCaptureReferenceState(mode, value = '', hint = '') {
    if (!captureRefBox || !captureRefLabel || !captureRefValue || !captureRefHint) return;
    captureRefBox.hidden = false;
    captureRefBox.classList.remove('capture-ref-box--loading', 'capture-ref-box--error');

    if (mode === 'loading') {
      latestCaptureReferencePreview = '';
      captureRefBox.classList.add('capture-ref-box--loading');
      captureRefLabel.textContent = 'Analizando comprobante';
      captureRefValue.textContent = 'Buscando referencia...';
      captureRefHint.textContent = hint || 'Esto tarda unos segundos.';
      return;
    }
    if (mode === 'success') {
      latestCaptureReferencePreview = String(value || '').trim();
      captureRefLabel.textContent = 'Referencia extraída';
      captureRefValue.textContent = value || '-';
      captureRefHint.textContent = hint || 'Usa este número si quieres compararlo con la referencia que escribiste.';
      return;
    }
    captureRefBox.hidden = true;
    latestCaptureReferencePreview = '';
    captureRefLabel.textContent = 'Analizando comprobante';
    captureRefValue.textContent = '...';
    captureRefHint.textContent = '';
  }

  async function extractCaptureReference(file) {
    if (!file) {
      renderCaptureReferenceState('idle');
      return '';
    }
    const currentLookupId = ++captureReferenceLookupId;
    renderCaptureReferenceState('loading');
    const fd = new FormData();
    fd.append('payment_capture', file);
    try {
      const res = await fetch('/orders/extract-capture-reference', {
        method: 'POST',
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (currentLookupId !== captureReferenceLookupId) return '';
      if (!res.ok || !data.ok) {
        renderCaptureReferenceState('idle');
        return '';
      }
      if (data.found && data.reference) {
        renderCaptureReferenceState('success', data.reference);
        return String(data.reference || '').trim();
      }
      renderCaptureReferenceState('idle');
      return '';
    } catch (_) {
      if (currentLookupId !== captureReferenceLookupId) return '';
      renderCaptureReferenceState('idle');
      return '';
    }
  }

  async function analyzeSelectedCapture(options = {}) {
    const { force = false } = options;
    const selectedFile = proofInput && proofInput.files && proofInput.files[0];
    if (!selectedFile) {
      latestCaptureReferencePreview = '';
      renderCaptureReferenceState('idle');
      return '';
    }
    if (!force && latestCaptureReferencePreview) {
      return latestCaptureReferencePreview;
    }
    if (captureAnalysisPromise) {
      return captureAnalysisPromise;
    }

    captureAnalysisInFlight = true;
    const currentPromise = (async () => {
      try {
        const extractedReference = await extractCaptureReference(selectedFile);
        latestCaptureReferencePreview = String(extractedReference || '').trim();
        return latestCaptureReferencePreview;
      } finally {
        captureAnalysisInFlight = false;
        if (captureAnalysisPromise === currentPromise) {
          captureAnalysisPromise = null;
        }
        updateSubmitState();
      }
    })();
    captureAnalysisPromise = currentPromise;
    return currentPromise;
  }

  function isValidVerifiedNick(nick) {
    const text = String(nick || '').trim();
    if (!text) return false;
    const lower = text.toLowerCase();
    const invalidParts = [
      'id inválido',
      'id invalido',
      'não existe',
      'nao existe',
      'network',
      'conexión de la red',
      'conexao de rede',
      'inténtalo de nuevo',
      'tente novamente',
      'try again',
      'error'
    ];
    return !invalidParts.some(part => lower.includes(part));
  }

  function getStoredVerifiedNick(uid, zid) {
    const safeUid = String(uid || '').trim();
    const safeZid = String(zid || '').trim();
    if (!safeUid) return '';
    try {
      if (safeZid) {
        const soZoneVal = (localStorage.getItem(`sonick:${gid}:${safeUid}:${safeZid}`) || '').toString().trim();
        if (isValidVerifiedNick(soZoneVal)) return soZoneVal;
        const mlVal = (localStorage.getItem(`mlnick:${safeUid}:${safeZid}`) || '').toString().trim();
        if (isValidVerifiedNick(mlVal)) return mlVal;
      }
      const soVal = (localStorage.getItem(`sonick:${gid}:${safeUid}`) || '').toString().trim();
      if (isValidVerifiedNick(soVal)) return soVal;
      const ffVal = (localStorage.getItem(`ffnick:${safeUid}`) || '').toString().trim();
      return isValidVerifiedNick(ffVal) ? ffVal : '';
    } catch (_) {
      return '';
    }
  }

  // Render basic game block immediately to avoid waiting for fetches
  (function initialHeader(){
    if (!coTotal) return;
    const qs0 = new URLSearchParams(window.location.search);
    const qCid0 = (qs0.get('cid') || '').trim();
    const qNick0 = (qs0.get('nn') || '').trim();
    const qZid0 = (qs0.get('zid') || '').trim();
    if (!qCid0) {
      coTotal.setAttribute('hidden', '');
      return;
    }
    const leftImg = gimg ? `<img class="co-summary-art" src="${gimg}" alt="${gname || 'Juego'}">` : '';
    const titleLine = gname ? `<div class="co-summary-game">${gname}</div>` : '';
    let nn0 = qNick0;
    if (!nn0) {
      nn0 = getStoredVerifiedNick(qCid0, qZid0);
    }
    const idLabel0 = qZid0 ? 'ID/Zona ID' : 'ID';
    const idValue0 = qZid0 ? `${qCid0}/${qZid0}` : qCid0;
    const idLine = `<div class="co-summary-id">${idLabel0}: ${idValue0}</div>`;
    const nameLine = nn0 ? `<div class="co-summary-nick">Nick: ${nn0}</div>` : '';
    coTotal.innerHTML = `
      <div class="co-summary">
        <div class="co-summary-head">
          ${leftImg}
          <div class="co-summary-copy">
            ${titleLine}
            <div class="co-summary-meta">
              ${nameLine}
              ${idLine}
            </div>
          </div>
        </div>
        <div class="co-summary-divider"></div>
        <div class="co-summary-body">
          <div class="co-summary-row co-summary-row--total">
            <div class="co-summary-label">Total a pagar</div>
            <div class="co-summary-value co-summary-value--total">...</div>
          </div>
        </div>
      </div>
    `;
  })();

  let allItems = [];
  let rate = 0;
  let paymentsCfg = null;
  let countdownId = null;

  // Restore selection and currency from URL first, then localStorage
  const qs = new URLSearchParams(window.location.search);
  const qSel = qs.get('sel');
  const qCur = qs.get('cur');
  const qMethod = qs.get('method'); // 'pm' | 'binance'
  const qCid = qs.get('cid');
  const qNick = (qs.get('nn') || '').trim();
  const qZid = qs.get('zid');
  const qRefCode = (qs.get('rc') || '').trim();
  const qName = qs.get('n') || '';
  const qEmail = qs.get('e') || '';
  const qPhone = qs.get('p') || '';
  const qQtyRaw = qs.get('q');
  let quantity = 1;
  try {
    const qn = parseInt(qQtyRaw, 10);
    if (!isNaN(qn) && qn > 0) quantity = Math.min(99, qn);
  } catch(_) { quantity = 1; }
  const LS_KEY = 'inefablestore_checkout';
  let state = null;
  try { state = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (_) { state = null; }
  // If method is explicitly provided, it wins
  let currency = (qMethod === 'pm') ? 'BSD' : (qMethod === 'binance') ? 'USD' : ((qCur === 'BSD' || qCur === 'USD') ? qCur : ((state && state.currency === 'BSD') ? 'BSD' : 'USD'));
  let selectedIndex = (qSel !== null && !isNaN(parseInt(qSel, 10))) ? parseInt(qSel, 10) : ((state && typeof state.selectedIndex === 'number') ? state.selectedIndex : -1);

  function formatPriceFor(cur, n){
    const v = Number(n || 0);
    if (cur === 'BSD') {
      return v.toLocaleString('es-VE', { style:'currency', currency:'VES', minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }
    return v.toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 });
  }
  function formatPrice(n){
    // Backwards-compatible helper using current currency
    return formatPriceFor(currency, n);
  }
  // Global delegated copy handler with fallback
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.copy-btn');
    if (!btn) return;
    const text = btn.getAttribute('data-copy') || '';
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = 'Copiado';
      setTimeout(() => { btn.textContent = 'Copiar'; }, 1200);
    } catch (_) {
      // Fallback for environments without Clipboard API permissions
      try {
        const tmp = document.createElement('input');
        tmp.value = text;
        document.body.appendChild(tmp);
        tmp.select();
        document.execCommand('copy');
        document.body.removeChild(tmp);
        btn.textContent = 'Copiado';
        setTimeout(() => { btn.textContent = 'Copiar'; }, 1200);
      } catch (err) {
        alert('No se pudo copiar');
      }
    }
  });



  function computeTotals() {
    // Returns { amount, displayCurrency, usedCurrency, baseBeforeDiscount }
    if (!allItems || selectedIndex < 0 || selectedIndex >= allItems.length) return { amount: 0, displayCurrency: currency, usedCurrency: currency, baseBeforeDiscount: 0 };
    const unitUsd = Number(allItems[selectedIndex].price || 0);
    const qty = Math.max(1, quantity || 1);
    const baseUsd = unitUsd * qty;
    // Apply influencer discount ONLY to 1 unit, not to all quantity
    let totalUsd = baseUsd;
    if (window.__validRef) {
      // Prefer item-specific discount when available
      let frac = Number(window.__validRef.discount || 0);
      try {
        const it = (allItems && selectedIndex >= 0) ? allItems[selectedIndex] : null;
        if (it && Array.isArray(window.__validRef.item_discounts)) {
          const hit = window.__validRef.item_discounts.find(x => Number(x.item_id) === Number(it.id));
          if (hit && typeof hit.discount === 'number') frac = Number(hit.discount || 0);
        }
      } catch(_){}
      if (frac > 0) {
        totalUsd = (unitUsd * qty) - (unitUsd * frac);
      }
    }
    if (currency === 'BSD') {
      if (rate && rate > 0) {
        return {
          amount: Math.round(totalUsd * rate),
          displayCurrency: 'BSD',
          usedCurrency: 'BSD',
          baseBeforeDiscount: Math.round(baseUsd * rate)
        };
      }
      // Fallback to USD if rate is not available to avoid showing 0
      return { amount: totalUsd, displayCurrency: 'USD', usedCurrency: 'USD', baseBeforeDiscount: baseUsd };
    }
    return { amount: totalUsd, displayCurrency: 'USD', usedCurrency: 'USD', baseBeforeDiscount: baseUsd };
  }

  function currentCheckoutMethod() {
    if (qMethod === 'binance') return 'binance';
    return 'pm';
  }

  function renderHeader() {
    if (!coTotal) return;
    if (!(qCid || '').trim()) {
      coTotal.setAttribute('hidden', '');
      return;
    }
    try { coTotal.removeAttribute('hidden'); } catch (_) {}

    const t = computeTotals();
    const qty = Math.max(1, quantity || 1);
    const originalAmount = Number(t.baseBeforeDiscount || 0);
    const totalAmount = Number(t.amount || 0);
    const discountAmount = Math.max(0, originalAmount - totalAmount);

    let selectedTitle = '';
    try {
      if (allItems && selectedIndex >= 0 && selectedIndex < allItems.length) {
        const item = allItems[selectedIndex];
        selectedTitle = qty > 1 ? `${item.title} x${qty}` : `${item.title}`;
      }
    } catch (_) {}

    const leftImg = gimg ? `<img class="co-summary-art" src="${gimg}" alt="${gname || 'Juego'}">` : '';
    const titleLine = gname ? `<div class="co-summary-game">${gname}</div>` : '';

    const playerBlock = (() => {
      const uid = (qCid || '').trim();
      let nn = (qNick || '').trim();
      const zid = (qZid || '').trim();
      if (!nn && uid) {
        nn = getStoredVerifiedNick(uid, zid);
      }
      if (!uid) return '';
      const safeName = nn || '';
      const nameLine = safeName ? `<div class="co-summary-nick">Nick: ${safeName}</div>` : '';
      const idLabel = zid ? 'ID/Zona ID' : 'ID';
      const idValue = zid ? `${uid}/${zid}` : uid;
      return `
        <div class="co-summary-meta">
          ${nameLine}
          <div class="co-summary-id">${idLabel}: ${idValue}</div>
        </div>`;
    })();

    const rows = [];
    if (originalAmount > 0) {
      rows.push(`
        <div class="co-summary-row">
          <div class="co-summary-label">Precio original</div>
          <div class="co-summary-value ${discountAmount > 0 ? 'co-summary-value--muted' : ''}">${formatPriceFor(t.displayCurrency, originalAmount)}</div>
        </div>
      `);
    }
    if (discountAmount > 0) {
      rows.push(`
        <div class="co-summary-row">
          <div class="co-summary-label">Descuento aplicado</div>
          <div class="co-summary-value co-summary-value--discount">- ${formatPriceFor(t.displayCurrency, discountAmount)}</div>
        </div>
      `);
    }
    rows.push(`
      <div class="co-summary-row">
        <div class="co-summary-label">Cantidad</div>
        <div class="co-summary-value">${qty}</div>
      </div>
    `);
    rows.push(`
      <div class="co-summary-row co-summary-row--total">
        <div class="co-summary-label">Total a pagar</div>
        <div class="co-summary-value co-summary-value--total">${formatPriceFor(t.displayCurrency, totalAmount)}</div>
      </div>
    `);

    coTotal.innerHTML = `
      <div class="co-summary">
        <div class="co-summary-head">
          ${leftImg}
          <div class="co-summary-copy">
            ${titleLine}
            ${selectedTitle ? `<div class="co-summary-item">${selectedTitle}</div>` : ''}
            ${playerBlock}
          </div>
        </div>
        <div class="co-summary-divider"></div>
        <div class="co-summary-body">${rows.join('')}</div>
      </div>
    `;

    if (coDiscNote) {
      coDiscNote.setAttribute('hidden', '');
      coDiscNote.innerHTML = '';
    }
  }

  function renderInfo() {
    if (!coInfo) return;
    coInfo.innerHTML = '';
    const svg = (name) => {
      if (name === 'bank') return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M3 10h18v2H3v-2zm2 3h2v5H5v-5zm4 0h2v5H9v-5zm4 0h2v5h-2v-5zm4 0h2v5h-2v-5zM3 21h18v2H3v-2zM12 2l9 6H3l9-6z"/></svg>';
      if (name === 'email') return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 13L2 6.76V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6.76L12 13zm0-2.4L22 4H2l10 6.6z"/></svg>';
      if (name === 'user') return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5zm0 2c-4.33 0-8 2.17-8 5v1h16v-1c0-2.83-3.67-5-8-5z"/></svg>';
      if (name === 'id') return '<svg viewBox=\"0 0 24 24\" width=\"20\" height=\"20\" fill=\"currentColor\" aria-hidden=\"true\"><path d=\"M3 4h18v16H3z\" opacity=\".3\"/><path d=\"M21 2H3a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1zM4 6h16v12H4zm3 2h6v2H7zm0 4h10v2H7z\"/></svg>';
      return '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="10"/></svg>';
    };
    const addItem = (iconName, value) => {
      const row = document.createElement('div');
      row.className = 'co-item';
      row.style.gridTemplateColumns = '28px 1fr';
      const ico = document.createElement('div');
      ico.className = 'co-ico';
      ico.innerHTML = svg(iconName);
      const val = document.createElement('div');
      val.className = 'co-val';
      val.textContent = value || '-';
      row.appendChild(ico);
      row.appendChild(val);
      coInfo.appendChild(row);
    };
    const addCopyAllBtn = (getValues) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'copy-btn';
      btn.style.cssText = 'width:100%; margin-top:10px; padding:10px 14px; font-size:13px; font-weight:800;';
      btn.textContent = 'Copiar todo';
      btn.addEventListener('click', async () => {
        const values = typeof getValues === 'function' ? getValues() : getValues;
        const text = values.filter(v => v).join('\n');
        try {
          await navigator.clipboard.writeText(text);
          btn.textContent = '¡Copiado!';
          setTimeout(() => { btn.textContent = 'Copiar todo'; }, 1200);
        } catch (_) {
          try {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.cssText = 'position:fixed;opacity:0;';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            btn.textContent = '¡Copiado!';
            setTimeout(() => { btn.textContent = 'Copiar todo'; }, 1200);
          } catch (_) { /* ignore */ }
        }
      });
      coInfo.appendChild(btn);
    };
    // Optional player info lines (kept at top if present)
    // Player ID (qCid) intentionally hidden from checkout UI, but still used internally
    if (currency === 'BSD') {
      const bank = (paymentsCfg && paymentsCfg.pm_bank) || '';
      const cedula = (paymentsCfg && paymentsCfg.pm_id) || '';
      const phone = (paymentsCfg && paymentsCfg.pm_phone) || '';
      addItem('bank', bank);
      addItem('id', cedula);
      addItem('user', phone);
      addCopyAllBtn(() => {
        const t = computeTotals();
        const monto = String(Math.round(Number(t.amount || 0)));
        return [bank, cedula, phone, monto];
      });
    } else {
      // Binance: show provider name, email and Pay ID
      addItem('bank', 'Binance');
      addItem('email', (paymentsCfg && paymentsCfg.binance_email) || '');
      addItem('user', (paymentsCfg && paymentsCfg.binance_phone) || '');
      // If Binance auto-verification is enabled for THIS item, show instructions about the beneficiary note
      if (isBinanceAuto) {
        const note = document.createElement('div');
        note.style.cssText = 'margin-top:12px; padding:10px 14px; background:rgba(245,158,11,0.1); border:1.5px solid rgba(245,158,11,0.35); border-radius:10px; text-align:center;';
        const refVal = coRef ? coRef.value.trim() : '';
        note.innerHTML = '<div style="font-weight:900; color:#fbbf24; margin-bottom:6px;">⚠️ IMPORTANTE — Verificación automática</div>'
          + '<div style="color:#e2e8f0; font-size:13px; line-height:1.4;">Al realizar el pago en Binance, <b>escribe tu número de referencia</b> en el campo <b>"Nota del beneficiario"</b> (memo/note).</div>'
          + '<div style="color:#94a3b8; font-size:12px; margin-top:6px;">Sin este código en la nota, tu pago <b>NO</b> podrá ser verificado automáticamente y deberá ser aprobado manualmente.</div>';
        coInfo.appendChild(note);
      }
    }
  }

  function startTimer(seconds) {
    if (!coTimer) return;
    let remaining = seconds;
    const render = () => {
      const m = Math.floor(remaining / 60).toString().padStart(2, '0');
      const s = Math.floor(remaining % 60).toString().padStart(2, '0');
      coTimer.textContent = `${m}:${s}`;
    };
    render();
    if (countdownId) clearInterval(countdownId);
    countdownId = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      render();
      if (remaining <= 0) clearInterval(countdownId);
    }, 1000);
  }

  // Fetch data
  Promise.all([
    fetch(`/store/package/${gid}/items`).then(r => r.json()).catch(() => null),
    fetch('/store/rate').then(r => r.json()).catch(() => null),
    fetch('/store/payments').then(r => r.json()).catch(() => null)
  ]).then(([itemsRes, rateRes, payRes]) => {
    allItems = (itemsRes && itemsRes.items) || [];
    if (selectedIndex < 0 && allItems.length > 0) selectedIndex = 0;
    rate = Number((rateRes && rateRes.rate_bsd_per_usd) || 0);
    paymentsCfg = (payRes && payRes.ok && payRes.payments) ? payRes.payments : null;
    // Detect Binance auto-verification mode PER ITEM
    const globalBinanceAuto = (qMethod === 'binance' && paymentsCfg && paymentsCfg.binance_auto_enabled === '1');
    isBinanceAuto = false; // will be set after item auto-check
    renderHeader();
    renderInfo();
    startTimer(30*60);
    if (globalBinanceAuto && allItems.length > 0 && selectedIndex >= 0 && selectedIndex < allItems.length) {
      const selItem = allItems[selectedIndex];
      fetch(`/store/item/${selItem.id}/auto-check`).then(r => r.json()).then(data => {
        if (data && data.ok && data.auto) {
          isBinanceAuto = true;
          setupBinanceAutoMode();
        }
      }).catch(() => { /* item not auto — use normal flow */ });
    }
  });

  // Initialize button as disabled
  if (btnConfirm) {
    btnConfirm.disabled = true;
  }

  // Proof dropzone / file input handling
  function updateSubmitState() {
    if (btnConfirm) {
      if (checkoutRequestInFlight) {
        btnConfirm.disabled = true;
        return;
      }
      if (isBinanceAuto) {
        // In auto mode only need the generated code (always present once fetched)
        btnConfirm.disabled = !binanceAutoCode;
      } else {
        btnConfirm.disabled = !(hasCapture && isReferenceValid);
      }
    }
  }

  // ── Binance Auto Mode Setup ──
  function setupBinanceAutoMode() {
    // Hide proof card
    const proofCard = proofDropzone ? proofDropzone.closest('.proof-card') : null;
    if (proofCard) proofCard.style.display = 'none';
    // Hide reference section (label, input, digits, paste button, error, counter)
    const refGroup = coRef ? coRef.closest('.ref-group') : null;
    if (refGroup) refGroup.style.display = 'none';
    // Fetch unique code from server
    fetch('/orders/generate-binance-code').then(r => r.json()).then(data => {
      if (data && data.ok && data.code) {
        binanceAutoCode = data.code;
        renderBinanceAutoCard();
        updateSubmitState();
      } else {
        alert('No se pudo generar el código de verificación');
      }
    }).catch(() => alert('Error de red al generar código'));
  }

  function renderBinanceAutoCard() {
    // Insert a card with the code and instructions BEFORE the timer card
    const timerCard = coTimer ? coTimer.closest('.co-card') : null;
    if (!timerCard) return;
    const card = document.createElement('div');
    card.className = 'co-card';
    card.id = 'binance-auto-card';
    card.innerHTML = `
      <h3>Verificación Automática Binance</h3>
      <div style="text-align:center; padding:12px 0;">
        <div style="color:#fbbf24; font-weight:900; font-size:14px; margin-bottom:10px;">⚠️ IMPORTANTE</div>
        <div style="color:#e2e8f0; font-size:13px; line-height:1.5; margin-bottom:14px;">Al realizar el pago en Binance, escribe este código en el campo <b>"Nota del beneficiario"</b> (memo/note)</div>
        <div style="display:flex; align-items:center; justify-content:center; gap:10px; margin:16px 0;">
          <div style="background:rgba(16,185,129,0.12); border:2px solid #10b981; border-radius:12px; padding:16px 28px; font-size:28px; font-weight:900; letter-spacing:8px; color:#10b981; font-family:monospace;">${binanceAutoCode}</div>
          <button type="button" class="copy-btn" data-copy="${binanceAutoCode}" style="padding:10px 14px; font-size:13px;">Copiar</button>
        </div>
        <div style="color:#94a3b8; font-size:12px; margin-top:8px;">Sin este código en la nota, tu pago <b>NO</b> podrá ser verificado automáticamente.</div>
        <div style="color:#94a3b8; font-size:12px; margin-top:6px;">Una vez realizado el pago, presiona <b>"Confirmar Pago"</b> y tu recarga será procesada automáticamente al verificar el pago.</div>
      </div>
    `;
    timerCard.parentNode.insertBefore(card, timerCard);
    // Change confirm button text
    if (btnConfirm) {
      btnConfirm.textContent = 'Confirmar Pago';
    }
  }

  if (proofDropzone && proofInput) {
    proofDropzone.addEventListener('click', () => proofInput.click());
    proofDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      proofDropzone.classList.add('proof-dropzone--over');
    });
    proofDropzone.addEventListener('dragleave', () => proofDropzone.classList.remove('proof-dropzone--over'));
    proofDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      proofDropzone.classList.remove('proof-dropzone--over');
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) {
        // Assign to the hidden input via DataTransfer
        try {
          const dt = new DataTransfer();
          dt.items.add(file);
          proofInput.files = dt.files;
        } catch(_) {}
        onCaptureSelected(file);
      }
    });
    proofInput.addEventListener('change', () => {
      if (proofInput.files && proofInput.files.length > 0) {
        onCaptureSelected(proofInput.files[0]);
      }
    });
  }

  function onCaptureSelected(file) {
    hasCapture = !!file;
    captureReferenceLookupId += 1;
    captureAnalysisInFlight = false;
    captureAnalysisPromise = null;
    latestCaptureReferencePreview = '';
    if (proofPreviewUrl) {
      URL.revokeObjectURL(proofPreviewUrl);
      proofPreviewUrl = '';
    }
    if (proofFileName) {
      proofFileName.textContent = file.name;
      proofFileName.style.display = 'block';
    }
    if (proofPreview && file && String(file.type || '').startsWith('image/')) {
      proofPreviewUrl = URL.createObjectURL(file);
      proofPreview.src = proofPreviewUrl;
      proofPreview.style.display = 'block';
    }
    if (proofInner) {
      proofInner.classList.add('proof-dropzone-inner--selected');
    }
    renderCaptureReferenceState('idle');
    updateSubmitState();
    if (file) {
      analyzeSelectedCapture({ force: true }).catch(() => {});
    }
  }

  if (blockedClose && blockedOverlay) {
    blockedClose.addEventListener('click', () => { blockedOverlay.style.display = 'none'; blockedOverlay.setAttribute('aria-hidden', 'true'); });
    blockedOverlay.addEventListener('click', (e) => { if (e.target === blockedOverlay) { blockedOverlay.style.display = 'none'; blockedOverlay.setAttribute('aria-hidden', 'true'); } });
  }

  // Function to update visual digit indicators (dynamic up to 21)
  function updateDigitIndicators(length) {
    const maxLen = 21;
    const cnt = Math.max(0, Math.min(maxLen, Number(length || 0)));
    const wrap = document.getElementById('digit-counter');
    if (wrap) {
      // Rebuild dots according to current length
      const dots = new Array(cnt).fill(0).map(() => '<div class="digit-dot filled"></div>').join('');
      wrap.innerHTML = dots;
    }
    if (refCounter) {
      // Show only the count to avoid implying a fixed length
      refCounter.textContent = `${cnt}`;
      // Green when within valid range (1..21)
      refCounter.style.color = (cnt >= 1 && cnt <= 21) ? '#10b981' : '#94a3b8';
    }
  }

  // Reference input: allow only digits, enable when 1..21 (máximo 21)
  if (coRef) {
    coRef.addEventListener('input', (e) => {
      // Remove non-digit characters
      let value = e.target.value.replace(/\D/g, '');
      // Limit to 21 digits
      value = value.substring(0, 21);
      e.target.value = value;
      
      // Update visual indicators
      updateDigitIndicators(value.length);
      
      // Reset validation state
      isReferenceValid = false;
      if (refError) {
        refError.style.display = 'none';
        refError.textContent = '';
      }
      
      // Enable/disable button based on length
      if (btnConfirm) {
        isReferenceValid = (value.length >= 1 && value.length <= 21);
        updateSubmitState();
      }
      
      // Check for duplicate reference when at least 1 digit
      if (value.length >= 1) {
        checkReferenceAvailability(value);
      }
    });

    // On paste: keep digits up to 21 and enable when 1..21
    coRef.addEventListener('paste', (e) => {
      e.preventDefault();
      try {
        const clip = (e.clipboardData || window.clipboardData);
        const text = (clip && typeof clip.getData === 'function') ? (clip.getData('text') || '') : '';
        const digits = String(text || '').replace(/\D/g, '');
        const only = digits.substring(0, 21);
        coRef.value = only;
        // Update UI
        updateDigitIndicators(only.length);
        // Reset/hide previous error
        isReferenceValid = false;
        if (refError) { refError.style.display = 'none'; refError.textContent = ''; }
        // Enable/disable confirm and trigger availability check
        isReferenceValid = (only.length >= 1 && only.length <= 21);
        updateSubmitState();
        if (only.length >= 1) {
          checkReferenceAvailability(only);
        }
      } catch (_) {
        // Fallback: let the normal input handler sanitize afterwards
      }
    });
  }
  
  // Function to check if reference is already in use
  async function checkReferenceAvailability(reference) {
    try {
      const res = await fetch(`/orders/check-reference?reference=${encodeURIComponent(reference)}`);
      const data = await res.json();
      
      if (res.ok && data.ok) {
        if (data.exists) {
          // Reference already in use
          isReferenceValid = false;
          if (refError) {
            refError.textContent = data.message || 'Su referencia ya fue subida y su recarga está siendo procesada';
            refError.style.display = 'block';
          }
          updateSubmitState();
          // Make counter text red to indicate error
          if (refCounter) {
            refCounter.style.color = '#ef4444';
          }
        } else {
          // Reference available
          isReferenceValid = true;
          if (refError) {
            refError.style.display = 'none';
            refError.textContent = '';
          }
          updateSubmitState();
          // Make counter text green to indicate success
          if (refCounter) {
            refCounter.style.color = '#10b981';
          }
        }
      }
    } catch (err) {
      console.error('Error checking reference:', err);
      // On error, allow submission (backend will validate again)
      isReferenceValid = true;
      updateSubmitState();
    }
  }

  // Validate referral code from query if present
  (async function validateRefAtStart(){
    if (!qRefCode) return;
    try {
      const qCid = qs.get('cid') || '';
      const qp = new URLSearchParams({ code: qRefCode, gid: gid || '' });
      if (qCid) qp.set('cid', qCid);
      const res = await fetch(`/store/special/validate?${qp.toString()}`);
      const data = await res.json();
      if (res.ok && data && data.ok && data.allowed) {
        window.__validRef = { code: qRefCode, discount: Number(data.discount || 0), item_discounts: Array.isArray(data.item_discounts) ? data.item_discounts : null };
        renderHeader();
      }
    } catch (_) { /* ignore */ }
  })();

  if (btnConfirm) {
    btnConfirm.addEventListener('click', async () => {
      if (checkoutRequestInFlight) return;
      checkoutRequestInFlight = true;
      btnConfirm.disabled = true;
      const idempotencyKey = getCheckoutAttemptKey();

      // ── Binance Auto Mode: simplified flow ──
      if (isBinanceAuto) {
        if (!binanceAutoCode) {
          alert('Código de verificación no disponible');
          releaseCheckoutRequest();
          return;
        }
        const item = (allItems && selectedIndex >= 0 && selectedIndex < allItems.length) ? allItems[selectedIndex] : null;
        const totals = computeTotals();
        let st = null;
        try { st = JSON.parse(localStorage.getItem('inefablestore_checkout') || 'null'); } catch (_) { st = null; }
        const name = qName || (st && st.name) || '';
        const email = qEmail || (st && st.email) || '';
        const phone = qPhone || (st && st.phone) || '';
        if (!phone) {
          alert('Ingresa tu número de teléfono');
          releaseCheckoutRequest();
          return;
        }
        const customer_id = qs.get('cid') || '';
        const customer_zone = qs.get('zid') || '';
        const nn = (function() {
          if (qNick) return qNick;
          const uid = customer_id;
          if (!uid) return '';
          return getStoredVerifiedNick(uid, customer_zone || '');
        })();
        // JSON body (no file needed)
        const payload = {
          store_package_id: gid,
          item_id: item ? item.id : null,
          items: item ? [{ item_id: item.id, qty: Math.max(1, quantity || 1) }] : [],
          amount: totals.amount,
          currency: totals.usedCurrency,
          method: 'binance',
          reference: binanceAutoCode,
          name: name,
          email: email,
          phone: phone,
          customer_id: customer_id,
          customer_zone: customer_zone,
          special_code: qRefCode || '',
          nn: nn,
          idempotency_key: idempotencyKey
        };
        const originalText = btnConfirm.textContent;
        btnConfirm.textContent = 'Procesando...';
        btnConfirm.disabled = true;
        const controller = new AbortController();
        const tid = setTimeout(() => controller.abort(), 30000);
        try {
          const res = await fetch('/orders', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-Idempotency-Key': idempotencyKey
            },
            body: JSON.stringify(payload),
            signal: controller.signal
          });
          const data = await res.json().catch(() => ({}));
          if (res.status === 403) {
            if (blockedOverlay) {
              if (blockedWhats) blockedWhats.href = waLink || '#';
              blockedOverlay.style.display = 'flex';
              blockedOverlay.removeAttribute('aria-hidden');
            } else {
              throw new Error((data && data.error) || 'Este ID está bloqueado.');
            }
            return;
          }
          if (!res.ok || !data.ok) throw new Error((data && data.error) || 'No se pudo crear la orden');
          window.location.href = `/gracias/${encodeURIComponent(data.order_id)}`;
        } catch (err) {
          const msg = (err && err.name === 'AbortError') ? 'La solicitud tardó demasiado. Intenta de nuevo.' : (err.message || 'No se pudo crear la orden');
          alert(msg);
        } finally {
          clearTimeout(tid);
          btnConfirm.textContent = originalText;
          releaseCheckoutRequest();
        }
        return;
      }

      // ── Normal flow (Pago Móvil / Binance manual) ──
      const ref = coRef ? coRef.value.trim() : '';
      if (!ref) {
        alert('Ingrese la referencia');
        releaseCheckoutRequest();
        return;
      }
      // Validate numeric with máximo 21 (1..21)
      if (!(ref.length >= 1 && ref.length <= 21 && /^\d+$/.test(ref))) {
        alert('La referencia debe ser numérica y tener máximo 21 dígitos');
        releaseCheckoutRequest();
        return;
      }
      // Require capture file
      if (!proofInput || !proofInput.files || proofInput.files.length === 0) {
        alert('Por favor adjunta el comprobante de pago');
        if (proofDropzone) proofDropzone.classList.add('proof-dropzone--error');
        releaseCheckoutRequest();
        return;
      }
      // Prepare order payload
      const item = (allItems && selectedIndex >= 0 && selectedIndex < allItems.length) ? allItems[selectedIndex] : null;
      const totals = computeTotals();
      const amount = totals.amount;
      const method = (totals.usedCurrency === 'BSD') ? 'pm' : 'binance';
      // Buyer info: prefer URL params from details, fallback to localStorage
      let state = null;
      try { state = JSON.parse(localStorage.getItem('inefablestore_checkout') || 'null'); } catch (_) { state = null; }
      const name = qName || (state && state.name) || '';
      const email = qEmail || (state && state.email) || '';
      const phone = qPhone || (state && state.phone) || '';
      if (!phone) {
        alert('Ingresa tu número de teléfono');
        releaseCheckoutRequest();
        return;
      }
      const customer_id = qs.get('cid') || '';
      const customer_zone = qs.get('zid') || '';
      const nn = (function() {
        if (qNick) return qNick;
        const uid = customer_id;
        if (!uid) return '';
        return getStoredVerifiedNick(uid, customer_zone || '');
      })();
      // Build FormData to include the capture file
      const fd = new FormData();
      fd.append('store_package_id', gid);
      if (item) fd.append('item_id', item.id);
      fd.append('items', JSON.stringify(item ? [{ item_id: item.id, qty: Math.max(1, quantity || 1) }] : []));
      fd.append('amount', amount);
      fd.append('currency', totals.usedCurrency);
      fd.append('method', method);
      fd.append('reference', ref);
      fd.append('name', name);
      fd.append('email', email);
      fd.append('phone', phone);
      fd.append('customer_id', customer_id);
      fd.append('customer_zone', customer_zone);
      fd.append('special_code', qRefCode || '');
      fd.append('nn', nn);
      fd.append('idempotency_key', idempotencyKey);
      const selectedCaptureFile = proofInput.files[0];
      const originalText = btnConfirm.textContent;
      btnConfirm.textContent = 'Procesando...';
      btnConfirm.disabled = true;
      if (selectedCaptureFile) {
        try {
          btnConfirm.textContent = 'Analizando comprobante...';
          latestCaptureReferencePreview = await analyzeSelectedCapture();
        } catch (_) {
          latestCaptureReferencePreview = '';
        }
        btnConfirm.textContent = 'Procesando...';
      }
      if (latestCaptureReferencePreview) fd.append('capture_reference_preview', latestCaptureReferencePreview);
      fd.append('payment_capture', selectedCaptureFile);
      // UI loading state
      // Abort fetch if it takes too long
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 30000);
      try {
        const res = await fetch('/orders', {
          method: 'POST',
          headers: { 'X-Idempotency-Key': idempotencyKey },
          body: fd,
          signal: controller.signal
        });
        const data = await res.json().catch(() => ({}));
        if (res.status === 403) {
          if (blockedOverlay) {
            if (blockedWhats) blockedWhats.href = waLink || '#';
            blockedOverlay.style.display = 'flex';
            blockedOverlay.removeAttribute('aria-hidden');
          } else {
            throw new Error((data && data.error) || 'Este ID está bloqueado.');
          }
          return;
        }
        if (!res.ok || !data.ok) throw new Error((data && data.error) || 'No se pudo crear la orden');
        // Redirect to dedicated thank-you page
        window.location.href = `/gracias/${encodeURIComponent(data.order_id)}`;
      } catch (err) {
        const msg = (err && err.name === 'AbortError') ? 'La solicitud tardó demasiado. Intenta de nuevo.' : (err.message || 'No se pudo crear la orden');
        alert(msg);
      } finally {
        clearTimeout(tid);
        btnConfirm.textContent = originalText;
        releaseCheckoutRequest();
      }
    });
  }
});
