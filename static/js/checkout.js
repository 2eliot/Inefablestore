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
  let isReferenceValid = false;

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
        return { amount: totalUsd * rate, displayCurrency: 'BSD', usedCurrency: 'BSD', baseBeforeDiscount: baseUsd * rate };
      }
      // Fallback to USD if rate is not available to avoid showing 0
      return { amount: totalUsd, displayCurrency: 'USD', usedCurrency: 'USD', baseBeforeDiscount: baseUsd };
    }
    return { amount: totalUsd, displayCurrency: 'USD', usedCurrency: 'USD', baseBeforeDiscount: baseUsd };
  }

  function renderHeader() {
    const t = computeTotals();
    // Default header: simple total
    coTotal.textContent = `Total a pagar: ${formatPriceFor(t.displayCurrency, t.amount)}`;
    if (coDiscNote) { coDiscNote.setAttribute('hidden', ''); coDiscNote.innerHTML = ''; }

    // If discount via creator code is active, show detailed breakdown
    if (allItems && selectedIndex >= 0 && selectedIndex < allItems.length && window.__validRef && window.__validRef.discount) {
      const frac = Number(window.__validRef.discount || 0);
      const pct = (frac * 100).toFixed(1).replace(/\.?0$/, ''); // 10.0 -> 10, 10.5 stays
      // Unit price in current display currency
      const it = allItems[selectedIndex];
      const unitUsd = Number(it.price || 0);
      const displayUnit = (t.displayCurrency === 'BSD' && rate && rate > 0) ? unitUsd * rate : unitUsd;
      const qty = Math.max(1, quantity || 1);
      // Compose styled breakdown (keeps theme colors; green accent comes from CSS var)
      const thanks = (window.__validRef && window.__validRef.code) ? `Gracias por usar el código de ${window.__validRef.code}` : '';
      coTotal.textContent = `Total a pagar: ${formatPriceFor(t.displayCurrency, t.amount)}`;
      if (coDiscNote) {
        coDiscNote.innerHTML = `
          <div class="co-badge">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M20 7h-2.18A3 3 0 0 0 15 3a3 3 0 0 0-3 3 3 3 0 0 0-3-3 3 3 0 0 0-2.82 4H4a1 1 0 0 0-1 1v3h18V8a1 1 0 0 0-1-1zM9 5a1 1 0 1 1 0 2H7.82A1.82 1.82 0 0 1 9 5zm6 0a1.82 1.82 0 0 1 1.18 3H15a1 1 0 1 1 0-2zM3 13v6a1 1 0 0 0 1 1h7v-7H3zm10 0v7h7a1 1 0 0 0 1-1v-6h-8z"/></svg>
            <span>${pct}% de descuento aplicado</span>
          </div>
          <div class="co-total">Total a pagar: ${formatPriceFor(t.displayCurrency, t.amount)}</div>
          <div class="co-old">Precio original: ${formatPriceFor(t.displayCurrency, t.baseBeforeDiscount)}</div>
          <div class="co-qty">Cantidad: ${qty}</div>
        `;
        coDiscNote.removeAttribute('hidden');
      }
    }

    // When no discount: show simple block with total and quantity
    if ((!window.__validRef || !window.__validRef.discount) && coDiscNote) {
      coDiscNote.innerHTML = `
        <div class="co-total">Total a pagar: ${formatPriceFor(t.displayCurrency, t.amount)}</div>
        <div class="co-qty">Cantidad: ${Math.max(1, quantity || 1)}</div>
      `;
      coDiscNote.removeAttribute('hidden');
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
      const ico = document.createElement('div');
      ico.className = 'co-ico';
      ico.innerHTML = svg(iconName);
      const val = document.createElement('div');
      val.className = 'co-val';
      val.textContent = value || '-';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'copy-btn';
      btn.setAttribute('data-copy', value || '');
      btn.textContent = 'Copiar';
      row.appendChild(ico);
      row.appendChild(val);
      row.appendChild(btn);
      coInfo.appendChild(row);
    };
    // Optional player info lines (kept at top if present)
    // Player ID (qCid) intentionally hidden from checkout UI, but still used internally
    if (currency === 'BSD') {
      // Show PM bank/name/phone/id
      addItem('bank', (paymentsCfg && paymentsCfg.pm_bank) || '');
      addItem('user', (paymentsCfg && paymentsCfg.pm_name) || '');
      addItem('user', (paymentsCfg && paymentsCfg.pm_phone) || '');
      addItem('id', (paymentsCfg && paymentsCfg.pm_id) || '');
    } else {
      // Binance: show provider name, email and Pay ID
      addItem('bank', 'Binance');
      addItem('email', (paymentsCfg && paymentsCfg.binance_email) || '');
      addItem('user', (paymentsCfg && paymentsCfg.binance_phone) || '');
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
    renderHeader();
    renderInfo();
    startTimer(30*60);
  });

  // Initialize button as disabled
  if (btnConfirm) {
    btnConfirm.disabled = true;
  }

  if (blockedClose && blockedOverlay) {
    blockedClose.addEventListener('click', () => { blockedOverlay.style.display = 'none'; blockedOverlay.setAttribute('aria-hidden', 'true'); });
    blockedOverlay.addEventListener('click', (e) => { if (e.target === blockedOverlay) { blockedOverlay.style.display = 'none'; blockedOverlay.setAttribute('aria-hidden', 'true'); } });
  }

  // Function to update visual digit indicators
  function updateDigitIndicators(length) {
    // Update dots
    for (let i = 1; i <= 6; i++) {
      const dot = document.getElementById(`dot-${i}`);
      if (dot) {
        if (i <= length) {
          dot.classList.add('filled');
        } else {
          dot.classList.remove('filled');
        }
      }
    }
    // Update counter text
    if (refCounter) {
      refCounter.textContent = `${length}/6 dígitos`;
      if (length === 6) {
        refCounter.style.color = '#10b981';
      } else {
        refCounter.style.color = '#94a3b8';
      }
    }
  }

  // Reference validation: only allow digits and exactly 6 characters
  if (coRef) {
    coRef.addEventListener('input', (e) => {
      // Remove non-digit characters
      let value = e.target.value.replace(/\D/g, '');
      // Limit to 6 digits
      value = value.substring(0, 6);
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
        btnConfirm.disabled = value.length !== 6;
      }
      
      // Check for duplicate reference when 6 digits are entered
      if (value.length === 6) {
        checkReferenceAvailability(value);
      }
    });

    // On paste: extract only last 6 digits from any pasted text
    coRef.addEventListener('paste', (e) => {
      e.preventDefault();
      try {
        const clip = (e.clipboardData || window.clipboardData);
        const text = (clip && typeof clip.getData === 'function') ? (clip.getData('text') || '') : '';
        const digits = String(text || '').replace(/\D/g, '');
        const last6 = digits.slice(-6);
        coRef.value = last6;
        // Update UI
        updateDigitIndicators(last6.length);
        // Reset/hide previous error
        isReferenceValid = false;
        if (refError) { refError.style.display = 'none'; refError.textContent = ''; }
        // Enable/disable confirm and trigger availability check
        if (btnConfirm) btnConfirm.disabled = last6.length !== 6;
        if (last6.length === 6) {
          checkReferenceAvailability(last6);
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
          if (btnConfirm) {
            btnConfirm.disabled = true;
          }
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
          if (btnConfirm) {
            btnConfirm.disabled = false;
          }
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
      if (btnConfirm && coRef && coRef.value.length === 6) {
        btnConfirm.disabled = false;
      }
    }
  }

  // Validate referral code from query if present
  (async function validateRefAtStart(){
    if (!qRefCode) return;
    try {
      const res = await fetch(`/store/special/validate?code=${encodeURIComponent(qRefCode)}&gid=${encodeURIComponent(gid||'')}`);
      const data = await res.json();
      if (res.ok && data && data.ok && data.allowed) {
        window.__validRef = { code: qRefCode, discount: Number(data.discount || 0), item_discounts: Array.isArray(data.item_discounts) ? data.item_discounts : null };
        renderHeader();
      }
    } catch (_) { /* ignore */ }
  })();

  if (btnConfirm) {
    btnConfirm.addEventListener('click', async () => {
      const ref = coRef ? coRef.value.trim() : '';
      if (!ref) { alert('Ingrese la referencia'); return; }
      // Validate exactly 6 digits
      if (ref.length !== 6 || !/^\d{6}$/.test(ref)) {
        alert('La referencia debe tener exactamente 6 dígitos');
        return;
      }
      // Check if reference validation passed
      if (!isReferenceValid) {
        alert('Por favor, ingrese una referencia válida');
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
      if (!phone) { alert('Ingresa tu número de teléfono'); return; }
      const customer_id = qs.get('cid') || '';
      const customer_zone = qs.get('zid') || '';
      const payload = {
        store_package_id: gid,
        item_id: item ? item.id : null,
        // Multi-package support: send items with quantity of selected package
        items: (item ? [{ item_id: item.id, qty: Math.max(1, quantity || 1) }] : []),
        amount,
        currency: totals.usedCurrency,
        method,
        reference: ref,
        name,
        email,
        phone,
        customer_id,
        customer_zone,
        special_code: qRefCode || ''
      };
      // UI loading state
      const originalText = btnConfirm.textContent;
      btnConfirm.textContent = 'Procesando...';
      btnConfirm.disabled = true;
      // Abort fetch if it takes too long
      const controller = new AbortController();
      const tid = setTimeout(() => controller.abort(), 15000);
      try {
        const res = await fetch('/orders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
        // Redirect to dedicated thank-you page
        window.location.href = `/gracias/${encodeURIComponent(data.order_id)}`;
      } catch (err) {
        const msg = (err && err.name === 'AbortError') ? 'La solicitud tardó demasiado. Intenta de nuevo.' : (err.message || 'No se pudo crear la orden');
        alert(msg);
      } finally {
        clearTimeout(tid);
        btnConfirm.textContent = originalText;
        btnConfirm.disabled = false;
      }
    });
  }
});
