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
  const LS_KEY = 'inefablestore_checkout';
  let state = null;
  try { state = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (_) { state = null; }
  // If method is explicitly provided, it wins
  let currency = (qMethod === 'pm') ? 'BSD' : (qMethod === 'binance') ? 'USD' : ((qCur === 'BSD' || qCur === 'USD') ? qCur : ((state && state.currency === 'BSD') ? 'BSD' : 'USD'));
  let selectedIndex = (qSel !== null && !isNaN(parseInt(qSel, 10))) ? parseInt(qSel, 10) : ((state && typeof state.selectedIndex === 'number') ? state.selectedIndex : -1);

  function formatPrice(n){
    const v = Number(n || 0);
    if (currency === 'BSD') {
      return v.toLocaleString('es-VE', { style:'currency', currency:'VES', minimumFractionDigits: 0, maximumFractionDigits: 0 });
    } else {
      return v.toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 });
    }
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



  function computeTotal() {
    if (!allItems || selectedIndex < 0 || selectedIndex >= allItems.length) return 0;
    const baseUsd = Number(allItems[selectedIndex].price || 0);
    let totalUsd = baseUsd;
    if (window.__validRef && window.__validRef.discount) {
      totalUsd = totalUsd * (1 - window.__validRef.discount);
    }
    return currency === 'BSD' ? totalUsd * (rate || 0) : totalUsd;
  }

  function renderHeader() {
    const total = computeTotal();
    // If discount active, show new price then old price struck-through
    if (allItems && selectedIndex >= 0 && selectedIndex < allItems.length && window.__validRef && window.__validRef.discount) {
      const baseUsd = Number(allItems[selectedIndex].price || 0);
      const base = (currency === 'BSD') ? baseUsd * (rate || 0) : baseUsd;
      if (base > total) {
        coTotal.innerHTML = `Total a pagar: <span class="price-new">${formatPrice(total)}</span> <span class="price-old">${formatPrice(base)}</span>`;
        // Show discount note below
        const pct = Math.round(Number(window.__validRef.discount || 0) * 100);
        if (coDiscNote) { coDiscNote.textContent = `${pct}% de descuento activo`; coDiscNote.removeAttribute('hidden'); }
        return;
      }
    } else {
      coTotal.textContent = `Total a pagar: ${formatPrice(total)}`;
    }
    // Hide note if not discounted
    if (coDiscNote) coDiscNote.setAttribute('hidden', '');
  }

  function renderInfo() {
    if (!coInfo) return;
    coInfo.innerHTML = '';
    const addRow = (label, value) => {
      const row = document.createElement('div');
      row.className = 'co-row';
      const left = document.createElement('strong');
      left.textContent = label;
      const right = document.createElement('div');
      right.style.display = 'flex';
      right.style.gap = '8px';
      const val = document.createElement('span');
      val.textContent = value || '-';
      val.className = 'co-val';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'copy-btn';
      btn.setAttribute('data-copy', value || '');
      btn.textContent = 'Copiar';
      right.appendChild(val);
      right.appendChild(btn);
      row.appendChild(left);
      row.appendChild(right);
      coInfo.appendChild(row);
    };
    if (qCid) addRow('ID de jugador', qCid);
    if (qZid) addRow('Zona ID', qZid);
    if (currency === 'BSD') {
      addRow('Banco', (paymentsCfg && paymentsCfg.pm_bank) || '');
      addRow('Nombre', (paymentsCfg && paymentsCfg.pm_name) || '');
      addRow('Teléfono', (paymentsCfg && paymentsCfg.pm_phone) || '');
      addRow('Cédula/RIF', (paymentsCfg && paymentsCfg.pm_id) || '');
    } else {
      // For Binance, show Email and Pay ID only
      addRow('Email', (paymentsCfg && paymentsCfg.binance_email) || '');
      addRow('Pay ID', (paymentsCfg && paymentsCfg.binance_phone) || '');
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

  // Validate referral code from query if present
  (async function validateRefAtStart(){
    if (!qRefCode) return;
    try {
      const res = await fetch(`/store/special/validate?code=${encodeURIComponent(qRefCode)}&gid=${encodeURIComponent(gid||'')}`);
      const data = await res.json();
      if (res.ok && data && data.ok && data.allowed) {
        window.__validRef = { code: qRefCode, discount: Number(data.discount || 0) };
        renderHeader();
      }
    } catch (_) { /* ignore */ }
  })();

  if (btnConfirm) {
    btnConfirm.addEventListener('click', async () => {
      const ref = coRef ? coRef.value.trim() : '';
      if (!ref) { alert('Ingrese la referencia'); return; }
      // Prepare order payload
      const item = (allItems && selectedIndex >= 0 && selectedIndex < allItems.length) ? allItems[selectedIndex] : null;
      const baseUsd = item ? Number(item.price || 0) : 0;
      const amount = (currency === 'BSD') ? baseUsd * (rate || 0) : baseUsd;
      const method = (currency === 'BSD') ? 'pm' : 'binance';
      // Buyer info: prefer URL params from details, fallback to localStorage
      let state = null;
      try { state = JSON.parse(localStorage.getItem('inefablestore_checkout') || 'null'); } catch (_) { state = null; }
      const name = qName || (state && state.name) || '';
      const email = qEmail || (state && state.email) || '';
      const phone = qPhone || (state && state.phone) || '';
      const customer_id = qs.get('cid') || '';
      const customer_zone = qs.get('zid') || '';
      const payload = {
        store_package_id: gid,
        item_id: item ? item.id : null,
        amount,
        currency,
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
        if (!res.ok || !data.ok) throw new Error((data && data.error) || 'No se pudo crear la orden');
        const wrap = document.getElementById('checkout');
        if (wrap) {
          wrap.innerHTML = `
            <div style="max-width:720px;margin:40px auto;text-align:center;color:#e5e7eb;">
              <div style="background:#10b981;color:#062a1d;font-weight:900;padding:14px;border-radius:12px;">¡Gracias por tu compra!</div>
              <p style="margin-top:12px;">Tu orden #${data.order_id} ha sido registrada y será procesada por nuestro equipo.</p>
              <p>Te redirigiremos al inicio en unos segundos...</p>
            </div>`;
        }
        setTimeout(() => { window.location.href = '/'; }, 3000);
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
