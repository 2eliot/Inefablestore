// Standalone checkout page (pasarela de pago)
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('checkout');
  if (!root) return;
  const gid = root.getAttribute('data-gid');
  // Resumen de la compra (tarjeta colapsable)
  const sumCard = document.getElementById('co-sum-card');
  const sumToggle = document.getElementById('co-sum-toggle');
  const sumThumb = document.getElementById('co-sum-thumb');
  const sumGame = document.getElementById('co-sum-game');
  const sumPack = document.getElementById('co-sum-pack');
  const sumMeta = document.getElementById('co-sum-meta');
  const sumTotal = document.getElementById('co-sum-total');
  const sumOld = document.getElementById('co-sum-old');
  const sumQty = document.getElementById('co-sum-qty');
  // Información de pago
  const methodNameEl = document.getElementById('co-method-name');
  const payTotalEl = document.getElementById('co-pay-total');
  const payFieldsEl = document.getElementById('co-pay-fields');
  const copyAllBtn = document.getElementById('co-copy-all');
  const coTimer = document.getElementById('co-timer');
  const coRef = document.getElementById('co-ref');
  const btnConfirm = document.getElementById('btn-co-confirm');
  const coDiscNote = document.getElementById('co-disc-note');
  const finalCard = document.getElementById('co-final-card');
  const coQrModal = document.getElementById('coQrModal');
  const coQrModalClose = document.getElementById('coQrModalClose');
  const coQrModalTitle = document.getElementById('coQrModalTitle');
  const coQrModalImage = document.getElementById('coQrModalImage');
  const refError = document.getElementById('ref-error');
  const refCounter = document.getElementById('ref-counter');
  const blockedOverlay = document.getElementById('blocked-overlay');
  const blockedClose = document.getElementById('blocked-close');
  const blockedWhats = document.getElementById('blocked-whatsapp');
  const waLink = (root.getAttribute('data-whatsapp') || '').trim();
  const gname = (root.getAttribute('data-gname') || '').trim();
  const gimg = (root.getAttribute('data-gimg') || '').trim();
  const directToPin = (root.getAttribute('data-direct-pin') || 'false').trim().toLowerCase() === 'true';
  // Proof / comprobante elements
  const proofInput = document.getElementById('payment_capture');
  const proofDropzone = document.getElementById('proofDropzone');
  const proofInner = document.getElementById('proofDropzoneInner');
  const proofFileName = document.getElementById('proofFileName');
  const proofPreview = document.getElementById('proofPreview');
  const proofTitle = document.getElementById('proofTitle');
  const proofHint = document.getElementById('proofHint');
  const captureRefBox = document.getElementById('captureRefBox');
  const captureRefLabel = document.getElementById('captureRefLabel');
  const captureRefValue = document.getElementById('captureRefValue');
  const captureRefHint = document.getElementById('captureRefHint');
  const checkoutEmail = document.getElementById('checkout-email');
  const checkoutPhone = document.getElementById('checkout-phone');
  const checkoutPhoneLocal = document.getElementById('checkout-phone-local');
  const checkoutPhoneCc = document.getElementById('checkout-phone-cc');
  const checkoutPhoneCcBtn = document.getElementById('checkout-phone-cc-btn');
  const checkoutPhoneCcMenu = document.getElementById('checkout-phone-cc-menu');
  const checkoutPhoneCcLabel = document.getElementById('checkout-phone-cc-label');
  const checkoutSaveContact = document.getElementById('checkout-save-contact');
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
  let referralCodeError = '';

  // Toggle del resumen (colapsado por defecto, como en el diseño)
  if (sumToggle && sumCard) {
    sumToggle.addEventListener('click', () => sumCard.classList.toggle('open'));
  }

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

  function getValidatedSpecialCode() {
    const validRefCode = window.__validRef && String(window.__validRef.code || '').trim();
    if (!qRefCode || !validRefCode) return '';
    return validRefCode.toLowerCase() === qRefCode.toLowerCase() ? qRefCode : '';
  }

  function renderReferralStatusNote() {
    if (!coDiscNote) return;
    if (qRefCode && referralCodeError) {
      coDiscNote.removeAttribute('hidden');
      coDiscNote.textContent = referralCodeError;
      return;
    }
    coDiscNote.setAttribute('hidden', '');
    coDiscNote.textContent = '';
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

  function getStoredVerifiedPlayerContext(uid) {
    const safeUid = String(uid || '').trim();
    if (!safeUid) return null;
    try {
      const raw = localStorage.getItem(`checkout_verified_player:${String(gid || '').trim()}:${safeUid}`) || '';
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || String(parsed.uid || '').trim() !== safeUid) return null;
      if (String(parsed.gid || '').trim() !== String(gid || '').trim()) return null;
      return {
        uid: safeUid,
        zid: String(parsed.zid || '').trim(),
        nick: String(parsed.nick || '').trim(),
      };
    } catch (_) {
      return null;
    }
  }

  function inferStoredZoneId(uid) {
    const safeUid = String(uid || '').trim();
    if (!safeUid) return '';
    try {
      const soPrefix = `sonick:${String(gid || '').trim()}:${safeUid}:`;
      const mlPrefix = `mlnick:${safeUid}:`;
      for (let idx = 0; idx < localStorage.length; idx += 1) {
        const key = String(localStorage.key(idx) || '');
        let zone = '';
        if (key.startsWith(soPrefix)) {
          zone = key.slice(soPrefix.length).trim();
        } else if (key.startsWith(mlPrefix)) {
          zone = key.slice(mlPrefix.length).trim();
        }
        if (!zone || !/^\d+$/.test(zone)) continue;
        const value = String(localStorage.getItem(key) || '').trim();
        if (isValidVerifiedNick(value)) return zone;
      }
    } catch (_) {}
    return '';
  }

  function getEffectivePlayerContext(overrides) {
    const uid = String((overrides && overrides.uid != null ? overrides.uid : qCid) || '').trim();
    const explicitZid = String((overrides && overrides.zid != null ? overrides.zid : qZid) || '').trim();
    const explicitNick = String((overrides && overrides.nick != null ? overrides.nick : qNick) || '').trim();
    const stored = getStoredVerifiedPlayerContext(uid);
    const inferredZid = inferStoredZoneId(uid);
    const zid = explicitZid || (stored ? stored.zid : '') || inferredZid;
    const nick = explicitNick || getStoredVerifiedNick(uid, zid) || (stored ? stored.nick : '');
    return { uid, zid, nick };
  }

  // Pintar juego + jugador de inmediato para no esperar los fetches
  (function initialHeader(){
    if (sumThumb && gimg) {
      sumThumb.innerHTML = `<img src="${gimg}" alt="${gname || 'Juego'}">`;
    }
    if (sumGame) sumGame.textContent = gname || '';
    const qs0 = new URLSearchParams(window.location.search);
    const qCid0 = (qs0.get('cid') || '').trim();
    if (sumMeta && !directToPin && qCid0) {
      const initialCtx = getEffectivePlayerContext({
        uid: qCid0,
        zid: (qs0.get('zid') || '').trim(),
        nick: (qs0.get('nn') || '').trim(),
      });
      const idValue0 = initialCtx.zid ? `${qCid0}/${initialCtx.zid}` : qCid0;
      sumMeta.textContent = 'ID ' + idValue0 + (initialCtx.nick ? ' · ' + initialCtx.nick : '');
    }
  })();

  let allItems = [];
  let rate = 0;
  let paymentsCfg = null;
  let countdownId = null;

  function openQrModal(src, title) {
    if (!coQrModal || !coQrModalImage) return;
    coQrModalImage.src = src || '';
    coQrModalImage.alt = title || 'QR de pago';
    if (coQrModalTitle) coQrModalTitle.textContent = title || 'QR de pago';
    coQrModal.removeAttribute('hidden');
    coQrModal.classList.add('is-open');
  }

  function closeQrModal() {
    if (!coQrModal) return;
    coQrModal.classList.remove('is-open');
    coQrModal.setAttribute('hidden', '');
  }

  if (coQrModalClose) {
    coQrModalClose.addEventListener('click', closeQrModal);
  }
  if (coQrModal) {
    // Toca fuera (o en cualquier parte del overlay) para cerrar
    coQrModal.addEventListener('click', (event) => {
      if (event.target === coQrModal) closeQrModal();
    });
  }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && coQrModal && !coQrModal.hasAttribute('hidden')) {
      closeQrModal();
    }
  });

  // Restore selection and currency from URL first, then localStorage
  const qs = new URLSearchParams(window.location.search);
  const qSel = qs.get('sel');
  const qItemId = qs.get('item'); // alternativa a 'sel': id del item (usado por "Reintentar pago")
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
  const CONTACT_LS_KEY = 'inefablestore_checkout_contact';
  let contactState = null;
  try { contactState = JSON.parse(localStorage.getItem(CONTACT_LS_KEY) || 'null'); } catch (_) { contactState = null; }
  // If method is explicitly provided, it wins
  let currency = (qMethod === 'pm') ? 'BSD' : (qMethod === 'binance') ? 'USD' : ((qCur === 'BSD' || qCur === 'USD') ? qCur : 'USD');
  let selectedIndex = (qSel !== null && !isNaN(parseInt(qSel, 10))) ? parseInt(qSel, 10) : -1;

  function splitPhoneParts(rawPhone) {
    const raw = String(rawPhone || '').trim();
    if (!raw) return { cc: '+58', local: '' };
    const match = raw.match(/^(\+\d+)\s*(.*)$/);
    if (match) {
      return {
        cc: match[1] || '+58',
        local: (match[2] || '').trim(),
      };
    }
    return { cc: '+58', local: raw };
  }

  function updateCombinedPhone() {
    if (!checkoutPhone) return '';
    const cc = checkoutPhoneCc ? String(checkoutPhoneCc.value || '').trim().replace(/\s+/g, '') : '';
    const local = checkoutPhoneLocal ? String(checkoutPhoneLocal.value || '').trim() : '';
    const fullPhone = [cc, local].filter(Boolean).join(' ').trim();
    checkoutPhone.value = fullPhone;
    return fullPhone;
  }

  function getCheckoutEmailValue() {
    return checkoutEmail ? String(checkoutEmail.value || '').trim() : '';
  }

  function getCheckoutPhoneValue() {
    return updateCombinedPhone();
  }

  function clearSavedCheckoutContact() {
    try { localStorage.removeItem(CONTACT_LS_KEY); } catch (_) {}
  }

  function persistCheckoutContact() {
    if (!checkoutSaveContact || !checkoutSaveContact.checked) return;
    try {
      const next = {
        email: getCheckoutEmailValue(),
        phone: getCheckoutPhoneValue(),
        save: true,
      };
      localStorage.setItem(CONTACT_LS_KEY, JSON.stringify(next));
    } catch (_) {}
  }

  (function initCheckoutContactFields() {
    const savedEmail = contactState && contactState.save ? String(contactState.email || '').trim() : '';
    const savedPhone = contactState && contactState.save ? String(contactState.phone || '').trim() : '';
    const phoneParts = splitPhoneParts(qPhone || savedPhone || '');
    if (checkoutSaveContact) {
      checkoutSaveContact.checked = !!(contactState && contactState.save);
      checkoutSaveContact.addEventListener('change', () => {
        if (checkoutSaveContact.checked) {
          persistCheckoutContact();
          return;
        }
        clearSavedCheckoutContact();
      });
    }
    if (checkoutEmail) {
      checkoutEmail.value = qEmail || savedEmail || '';
      checkoutEmail.addEventListener('input', () => {
        if (checkoutSaveContact && checkoutSaveContact.checked) persistCheckoutContact();
      });
    }
    if (checkoutPhoneCc) checkoutPhoneCc.value = phoneParts.cc;
    if (checkoutPhoneCcLabel) checkoutPhoneCcLabel.textContent = phoneParts.cc;
    if (checkoutPhoneLocal) {
      checkoutPhoneLocal.value = phoneParts.local;
      checkoutPhoneLocal.addEventListener('input', () => {
        updateCombinedPhone();
        if (checkoutSaveContact && checkoutSaveContact.checked) persistCheckoutContact();
      });
    }
    updateCombinedPhone();
    if (checkoutPhoneCcBtn && checkoutPhoneCcMenu) {
      checkoutPhoneCcBtn.addEventListener('click', () => {
        const nextHidden = !checkoutPhoneCcMenu.hidden;
        checkoutPhoneCcMenu.hidden = nextHidden;
        checkoutPhoneCcBtn.classList.toggle('open', !nextHidden);
        checkoutPhoneCcBtn.setAttribute('aria-expanded', String(!nextHidden));
      });
      checkoutPhoneCcMenu.addEventListener('click', (event) => {
        const option = event.target.closest('[data-cc]');
        if (!option) return;
        const cc = String(option.getAttribute('data-cc') || '+58').trim();
        if (checkoutPhoneCc) checkoutPhoneCc.value = cc;
        if (checkoutPhoneCcLabel) checkoutPhoneCcLabel.textContent = cc;
        updateCombinedPhone();
        if (checkoutSaveContact && checkoutSaveContact.checked) persistCheckoutContact();
        checkoutPhoneCcMenu.hidden = true;
        checkoutPhoneCcBtn.classList.remove('open');
        checkoutPhoneCcBtn.setAttribute('aria-expanded', 'false');
      });
      document.addEventListener('click', (event) => {
        if (!checkoutPhoneCcMenu.hidden && !event.target.closest('.phone-prefix')) {
          checkoutPhoneCcMenu.hidden = true;
          checkoutPhoneCcBtn.classList.remove('open');
          checkoutPhoneCcBtn.setAttribute('aria-expanded', 'false');
        }
      });
    }
  })();

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
  // Global delegated copy handler with fallback (botones .copy-btn con data-copy)
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

  async function copyTextRaw(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      try {
        const tmp = document.createElement('textarea');
        tmp.value = text;
        tmp.style.cssText = 'position:fixed;opacity:0;';
        document.body.appendChild(tmp);
        tmp.select();
        document.execCommand('copy');
        document.body.removeChild(tmp);
        return true;
      } catch (err) {
        return false;
      }
    }
  }

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
        // Items with no_discount flag are excluded from all discount codes
        if (it && it.no_discount) frac = 0;
        if (it && frac > 0 && Array.isArray(window.__validRef.item_discounts)) {
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
    const t = computeTotals();
    const qty = Math.max(1, quantity || 1);
    const originalAmount = Number(t.baseBeforeDiscount || 0);
    const totalAmount = Number(t.amount || 0);
    const discountAmount = Math.max(0, originalAmount - totalAmount);

    let selectedTitle = '';
    try {
      if (allItems && selectedIndex >= 0 && selectedIndex < allItems.length) {
        const item = allItems[selectedIndex];
        const baseTitle = String(item.title || '').trim();
        const subtitle = String(item.subtitle || '').trim();
        const titleWithSubtitle = subtitle ? `${baseTitle} ${subtitle}` : baseTitle;
        selectedTitle = qty > 1 ? `${titleWithSubtitle} x${qty}` : titleWithSubtitle;
      }
    } catch (_) {}

    if (sumPack) sumPack.textContent = selectedTitle || (gname || '...');

    // ID + Nick solo si hay CID (se omite para gift cards)
    if (sumMeta) {
      const playerCtx = getEffectivePlayerContext();
      const uid = playerCtx.uid;
      if (!directToPin && uid) {
        const zid = playerCtx.zid || '';
        const idValue = zid ? `${uid}/${zid}` : uid;
        sumMeta.textContent = 'ID ' + idValue + (playerCtx.nick ? ' · ' + playerCtx.nick : '');
      } else {
        sumMeta.textContent = '';
      }
    }

    const totalTxt = formatPriceFor(t.displayCurrency, totalAmount);
    if (sumTotal) sumTotal.textContent = totalTxt;
    if (payTotalEl) payTotalEl.textContent = totalTxt;

    // Precio anterior tachado cuando hay descuento aplicado
    const hasDiscount = discountAmount > 0 && originalAmount > totalAmount;
    if (sumOld) {
      if (hasDiscount) {
        sumOld.hidden = false;
        sumOld.textContent = formatPriceFor(t.displayCurrency, originalAmount);
      } else {
        sumOld.hidden = true;
        sumOld.textContent = '';
      }
    }
    if (sumQty) sumQty.textContent = 'Cantidad ' + qty;

    renderReferralStatusNote();
  }

  function renderInfo() {
    if (!payFieldsEl) return;
    payFieldsEl.innerHTML = '';

    const addField = (label, value) => {
      const safeValue = String(value || '').trim();
      const tile = document.createElement('div');
      tile.className = 'co-field';
      tile.innerHTML = `
        <div class="co-field-copy">
          <div class="co-field-label"></div>
          <div class="co-field-value"></div>
        </div>
        <div class="co-field-ico">⧉</div>`;
      tile.querySelector('.co-field-label').textContent = label;
      tile.querySelector('.co-field-value').textContent = safeValue || '-';
      tile.addEventListener('click', async () => {
        if (!safeValue) return;
        const ok = await copyTextRaw(safeValue);
        if (!ok) { alert('No se pudo copiar'); return; }
        tile.classList.add('copied');
        tile.querySelector('.co-field-ico').textContent = '✓';
        setTimeout(() => {
          tile.classList.remove('copied');
          tile.querySelector('.co-field-ico').textContent = '⧉';
        }, 1200);
      });
      payFieldsEl.appendChild(tile);
      return tile;
    };

    const addQrTile = (src, title) => {
      const safeSrc = String(src || '').trim();
      if (!safeSrc) return;
      const tile = document.createElement('div');
      tile.className = 'co-qr-tile';
      tile.innerHTML = `
        <svg width="13" height="15" viewBox="0 0 24 24" fill="none" stroke="#3ee07f" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect><path d="M14 14h3v3h-3zM18 18h3v3h-3z"></path></svg>
        <div class="co-qr-tile-label">VER QR</div>`;
      tile.addEventListener('click', () => openQrModal(safeSrc, title || 'QR de pago'));
      payFieldsEl.appendChild(tile);
    };

    let copyValues = () => [];

    if (currency === 'BSD') {
      if (methodNameEl) methodNameEl.textContent = 'PAGO MÓVIL';
      const bank = (paymentsCfg && paymentsCfg.pm_bank) || '';
      const cedula = (paymentsCfg && paymentsCfg.pm_id) || '';
      const phone = (paymentsCfg && paymentsCfg.pm_phone) || '';
      const qr = (paymentsCfg && paymentsCfg.pm_qr_path) || '';
      addField('BANCO', bank);
      addField('CÉDULA', cedula);
      addField('TELÉFONO', phone);
      addQrTile(qr, 'QR de Pago Móvil');
      copyValues = () => {
        const t = computeTotals();
        const monto = String(Math.round(Number(t.amount || 0)));
        return [bank, cedula, phone, monto];
      };
    } else {
      if (methodNameEl) methodNameEl.textContent = 'BINANCE';
      const email = (paymentsCfg && paymentsCfg.binance_email) || '';
      const phone = (paymentsCfg && paymentsCfg.binance_phone) || '';
      const qr = (paymentsCfg && paymentsCfg.binance_qr_path) || '';
      addField('PLATAFORMA', 'Binance');
      addField('CORREO', email);
      addField('USUARIO', phone);
      addQrTile(qr, 'QR de Binance');
      copyValues = () => {
        const t = computeTotals();
        return ['Binance', email, phone, String(Number(t.amount || 0).toFixed(2))];
      };
      // Si la verificación automática está activa para ESTE item, avisar sobre la nota del beneficiario
      if (isBinanceAuto) {
        const note = document.createElement('div');
        note.className = 'co-binance-note';
        note.innerHTML = '<div style="font-weight:700; color:#f0a52a; margin-bottom:6px;">⚠️ IMPORTANTE — Verificación automática</div>'
          + '<div>Al realizar el pago en Binance, <b>escribe tu número de referencia</b> en el campo <b>"Nota del beneficiario"</b> (memo/note).</div>'
          + '<div style="color:#8a8a8a; margin-top:6px;">Sin este código en la nota, tu pago <b>NO</b> podrá ser verificado automáticamente y deberá ser aprobado manualmente.</div>';
        payFieldsEl.parentNode.insertBefore(note, payFieldsEl.nextSibling);
      }
    }

    if (copyAllBtn) {
      copyAllBtn.onclick = async () => {
        const text = copyValues().filter(v => v).join('\n');
        const ok = await copyTextRaw(text);
        if (!ok) return;
        copyAllBtn.textContent = 'COPIADO ✓';
        setTimeout(() => { copyAllBtn.textContent = 'COPIAR TODO'; }, 1400);
      };
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
    // Permite llegar con ?item=<id> (ej. desde "Reintentar pago" en la página de gracias)
    if (selectedIndex < 0 && qItemId) {
      const byId = allItems.findIndex(it => String(it.id) === String(qItemId));
      if (byId >= 0) selectedIndex = byId;
    }
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
    // Hide proof card (columna del comprobante)
    const proofCard = proofDropzone ? proofDropzone.closest('.proof-card') : null;
    if (proofCard) proofCard.style.display = 'none';
    // Hide reference section (label, input, counter, error)
    const refGroup = coRef ? coRef.closest('.ref-group') : null;
    if (refGroup) refGroup.style.display = 'none';
    // Refrescar la tarjeta de pago para que muestre la nota de verificación automática
    renderInfo();
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
    // Insert a card with the code and instructions BEFORE the final card
    if (!finalCard || !finalCard.parentNode) return;
    const card = document.createElement('div');
    card.className = 'co-card co-pay-card';
    card.id = 'binance-auto-card';
    card.innerHTML = `
      <div class="co-method-row">
        <div class="co-method-line l"></div>
        <div style="font-family:'Outfit';font-size:15px;letter-spacing:.1em;white-space:nowrap">VERIFICACIÓN AUTOMÁTICA</div>
        <div class="co-method-line r"></div>
      </div>
      <div style="text-align:center;">
        <div style="color:#f0a52a; font-weight:700; font-size:13px; margin-bottom:8px;">⚠️ IMPORTANTE</div>
        <div style="color:#c4c4c4; font-size:13px; line-height:1.5;">Al realizar el pago en Binance, escribe este código en el campo <b style="color:#eaeaea">"Nota del beneficiario"</b> (memo/note)</div>
        <div class="co-auto-code">
          <div class="co-auto-code-box">${binanceAutoCode}</div>
          <button type="button" class="copy-btn" data-copy="${binanceAutoCode}" style="padding:10px 14px; font-size:12px; border:1px solid #2b2b2b; border-radius:8px; background:#0d0d0d; color:#eaeaea; cursor:pointer;">Copiar</button>
        </div>
        <div style="color:#8a8a8a; font-size:12px; margin-top:8px;">Sin este código en la nota, tu pago <b>NO</b> podrá ser verificado automáticamente.</div>
        <div style="color:#8a8a8a; font-size:12px; margin-top:6px;">Una vez realizado el pago, presiona <b style="color:#3ee07f">"YA REALICÉ EL PAGO"</b> y tu recarga será procesada automáticamente al verificar el pago.</div>
      </div>
    `;
    finalCard.parentNode.insertBefore(card, finalCard);
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
    if (proofDropzone) {
      proofDropzone.classList.add('uploaded');
      proofDropzone.classList.remove('proof-dropzone--error');
    }
    if (proofTitle) proofTitle.textContent = 'Captura cargada';
    if (proofHint) proofHint.textContent = 'Toca para reemplazar';
    if (proofInner) {
      proofInner.classList.add('proof-dropzone-inner--selected');
    }
    renderCaptureReferenceState('idle');
    updateSubmitState();
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
      // Oculto mientras no haya dígitos (evita el "0" suelto entre campos)
      refCounter.style.display = cnt > 0 ? 'block' : 'none';
      // Green when within valid range (1..21)
      refCounter.style.color = (cnt >= 1 && cnt <= 21) ? '#3ee07f' : '#6e6e6e';
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
            refCounter.style.color = '#ff5d5d';
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
            refCounter.style.color = '#3ee07f';
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
        referralCodeError = '';
        renderHeader();
        return;
      }
      window.__validRef = null;
      referralCodeError = (data && data.error) ? data.error : 'El código de descuento no aplica para esta compra.';
      renderReferralStatusNote();
    } catch (_) {
      window.__validRef = null;
      referralCodeError = 'No se pudo validar el código de descuento.';
      renderReferralStatusNote();
    }
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
        const name = qName || '';
        const email = getCheckoutEmailValue() || qEmail || '';
        const phone = getCheckoutPhoneValue() || qPhone || '';
        if (!email) {
          alert('Ingresa tu correo');
          if (checkoutEmail) checkoutEmail.focus();
          releaseCheckoutRequest();
          return;
        }
        if (!phone) {
          alert('Ingresa tu número de teléfono');
          releaseCheckoutRequest();
          return;
        }
        const playerCtx = getEffectivePlayerContext();
        const customer_id = playerCtx.uid || '';
        const customer_zone = playerCtx.zid || '';
        const nn = (function() {
          if (playerCtx.nick) return playerCtx.nick;
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
          special_code: getValidatedSpecialCode(),
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
      const name = qName || '';
      const email = getCheckoutEmailValue() || qEmail || '';
      const phone = getCheckoutPhoneValue() || qPhone || '';
      if (!email) {
        alert('Ingresa tu correo');
        if (checkoutEmail) checkoutEmail.focus();
        releaseCheckoutRequest();
        return;
      }
      if (!phone) {
        alert('Ingresa tu número de teléfono');
        releaseCheckoutRequest();
        return;
      }
      const playerCtx = getEffectivePlayerContext();
      const customer_id = playerCtx.uid || '';
      const customer_zone = playerCtx.zid || '';
      const nn = (function() {
        if (playerCtx.nick) return playerCtx.nick;
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
      fd.append('special_code', getValidatedSpecialCode());
      fd.append('nn', nn);
      fd.append('idempotency_key', idempotencyKey);
      const selectedCaptureFile = proofInput.files[0];
      const originalText = btnConfirm.textContent;
      btnConfirm.textContent = 'Procesando...';
      btnConfirm.disabled = true;
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
