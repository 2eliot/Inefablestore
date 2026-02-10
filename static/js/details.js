// Details page logic
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('game-details');
  if (!root) return;
  const gid = root.getAttribute('data-game-id');
  const category = (root.getAttribute('data-category') || '').toLowerCase();
  const requiresZone = (root.getAttribute('data-requires-zone') === '1');
  const isGift = category === 'gift';
  const grid = document.getElementById('items-grid');
  const selBox = document.getElementById('selected-box');
  const selTitle = document.getElementById('selected-title');
  const selPrice = document.getElementById('selected-price');
  const sumPrice = document.getElementById('summary-price');
  const btnMore = document.getElementById('btn-more');
  const btnPayBSD = document.getElementById('pay-bsd');
  const btnPayUSD = document.getElementById('pay-usd');
  // Package info (Leer) modal
  const btnLeer = document.getElementById('btn-leer');
  const pkgInfoModal = document.getElementById('pkg-info-modal');
  const pkgInfoContent = document.getElementById('pkg-info-content');
  const btnClosePkgInfo = document.querySelector('[data-close-pkg-info]');
  // Package-level special description source (admin set per package)
  const gameSpecDescEl = document.getElementById('game-special-desc');
  // Mobile footer selection
  const mfs = document.getElementById('mfs');
  const mfsTitle = document.getElementById('mfs-title');
  const mfsPrice = document.getElementById('mfs-price');
  const mfsClose = document.getElementById('mfs-close');
  const mfsPlus = document.getElementById('mfs-plus');
  const mfsMinus = document.getElementById('mfs-minus');
  const mfsQtyVal = document.getElementById('mfs-qty-val');
  // Step 4 inputs
  const inputCustomerId = document.getElementById('customer-id');
  const inputCustomerZone = document.getElementById('customer-zone');
  const btnVerifyPlayer = document.getElementById('btn-verify-player');
  const playerNickname = document.getElementById('player-nickname');
  const btnRightLogin = document.getElementById('btn-right-login');
  const activeLogin = (root.getAttribute('data-active-login') === '1');
  // Hide Step 1 (player ID) for gift category and renumber badges/texts
  if (isGift && inputCustomerId) {
    const stepCard = inputCustomerId.closest('.step-card');
    if (stepCard) stepCard.hidden = true;
    const stepCards = root.querySelectorAll('.details-right .step-card');
    const step2Title = stepCards[1] && stepCards[1].querySelector('.step-title');
    const step3Title = stepCards[2] && stepCards[2].querySelector('.step-title');
    const step4Title = stepCards[3] && stepCards[3].querySelector('.step-title');
    if (step2Title) {
      step2Title.dataset.step = '1';
      step2Title.textContent = 'Selecciona tu producto';
    }
    if (step3Title) {
      step3Title.dataset.step = '2';
      step3Title.textContent = 'Seleccione un método de pago';
    }
    if (step4Title) {
      step4Title.dataset.step = '3';
      step4Title.textContent = 'Ingresa tus datos';
    }
  }

  function ensureDesktopQty() {
    if (!selBox) return;
    const isPhone = window.matchMedia('(max-width: 699px)').matches;
    if (isPhone) return;
    if (!dqWrap) {
      dqWrap = document.createElement('div');
      dqWrap.style.display = 'flex';
      dqWrap.style.alignItems = 'center';
      dqWrap.style.justifyContent = 'center';
      dqWrap.style.gap = '10px';
      dqWrap.style.marginTop = '8px';
      dqMinus = document.createElement('button');
      dqMinus.type = 'button';
      dqMinus.className = 'btn';
      dqMinus.textContent = '−';
      dqVal = document.createElement('span');
      dqVal.style.minWidth = '28px';
      dqVal.style.textAlign = 'center';
      dqVal.style.fontWeight = '900';
      dqVal.textContent = String(Math.max(1, quantity || 1));
      dqPlus = document.createElement('button');
      dqPlus.type = 'button';
      dqPlus.className = 'btn';
      dqPlus.textContent = '+';
      dqWrap.appendChild(dqMinus);
      dqWrap.appendChild(dqVal);
      dqWrap.appendChild(dqPlus);
      selBox.parentNode && selBox.parentNode.insertBefore(dqWrap, selBox.nextSibling);
      dqPlus.addEventListener('click', () => setQuantity((quantity || 1) + 1));
      dqMinus.addEventListener('click', () => setQuantity((quantity || 1) - 1));
    }
    if (dqVal) dqVal.textContent = String(Math.max(1, quantity || 1));
  }

  // Right small login button opens auth modal (only when active)
  if (activeLogin && btnRightLogin) {
    btnRightLogin.addEventListener('click', () => {
      const modal = document.getElementById('auth-modal');
      if (modal) modal.removeAttribute('hidden');
    });
  }

  // Open/close package info modal via "Leer" button
  if (btnLeer && pkgInfoModal) {
    btnLeer.addEventListener('click', () => {
      pkgInfoModal.removeAttribute('hidden');
    });
  }
  if (btnClosePkgInfo && pkgInfoModal) {
    btnClosePkgInfo.addEventListener('click', () => {
      pkgInfoModal.setAttribute('hidden', '');
    });
  }
  if (pkgInfoModal) {
    pkgInfoModal.addEventListener('click', (e) => {
      if (e.target && e.target.classList && e.target.classList.contains('modal-backdrop')) {
        pkgInfoModal.setAttribute('hidden', '');
      }
    });
  }

  // Quantity controls in mobile footer
  function setQuantity(q) {
    const old = quantity;
    quantity = Math.max(1, Math.min(99, Math.floor(q || 1)));
    if (quantity !== old) {
      if (mfsQtyVal) mfsQtyVal.textContent = String(quantity);
      // Update shown prices when quantity changes
      if (selectedItemIndex >= 0) {
        const it = allItems[selectedItemIndex];
        const unit = currentUnitValue(it);
        const total = unit * quantity;
        if (selPrice) selPrice.textContent = formatPrice(total);
        if (sumPrice) sumPrice.textContent = formatPrice(total);
      }
      updateMobileFooter();
      persistState();
    }
  }
  if (mfsPlus) mfsPlus.addEventListener('click', () => setQuantity((quantity || 1) + 1));
  if (mfsMinus) mfsMinus.addEventListener('click', () => setQuantity((quantity || 1) - 1));

  
  const inputEmail = document.getElementById('email');
  const inputPhone = document.getElementById('phone');
  const inputPhoneLocal = document.getElementById('phone-local');
  const inputPhoneCc = document.getElementById('phone-cc');
  const phoneCcBtn = document.querySelector('.phone-prefix .phone-cc-btn');
  const phoneCcMenu = document.getElementById('phone-cc-menu');
  const phoneCcLabel = document.getElementById('phone-cc-label');
  const chkSave = document.getElementById('save-data');
  const btnBuy = document.getElementById('btn-buy');
  const inputRefCode = document.getElementById('ref-code');
  const refStatus = document.getElementById('ref-status');
  let validRef = null; // { code, discount, item_discounts?: [{item_id, discount}] }
  // Pay modal
  const payModal = document.getElementById('pay-modal');
  const payInfo = document.getElementById('pay-info');
  const payTotalTitle = document.getElementById('pay-total-title');
  const payTimer = document.getElementById('pay-timer');
  const payRef = document.getElementById('pay-ref');
  const btnConfirmPay = document.getElementById('btn-confirm-pay');
  let paymentsCfg = null;
  let countdownId = null;
  let allItems = [];
  let showingAll = false; // only used on mobile
  let isMobile = window.matchMedia('(max-width: 699px)').matches;
  let rate = 0; // BsD per 1 USD
  // Default: show BsD first on mobile footer; USD on desktop until user chooses
  let currency = isMobile ? 'BSD' : 'USD'; // 'USD' or 'BSD'
  let selectedItemIndex = -1;
  let methodChosen = false; // show prices only after choosing a payment method
  let quantity = 1; // selected quantity
  let dqWrap = null; let dqVal = null; let dqPlus = null; let dqMinus = null;

  // Hide "Ver más" button by default until we know there are more than 6 items
  if (btnMore) {
    btnMore.hidden = true;
    btnMore.style.display = 'none';
  }

  function updateCombinedPhone() {
    if (!inputPhone) return;
    const cc = (inputPhoneCc ? inputPhoneCc.value.trim() : '').replace(/\s+/g, '');
    const local = (inputPhoneLocal ? inputPhoneLocal.value.trim() : '');
    const val = [cc, local].filter(Boolean).join(' ');
    inputPhone.value = val;
  }

  // Country code dropdown with dynamic population and search
  async function populateCountries() {
    if (!phoneCcMenu) return;
    // Build container: search + list
    phoneCcMenu.innerHTML = '';
    const search = document.createElement('input');
    search.type = 'text';
    search.placeholder = 'Buscar país o código';
    search.className = 'phone-cc-search';
    const list = document.createElement('div');
    list.className = 'phone-cc-list';
    phoneCcMenu.appendChild(search);
    phoneCcMenu.appendChild(list);
    // Loading state
    const loading = document.createElement('div');
    loading.style.color = '#94a3b8';
    loading.style.padding = '6px 8px';
    loading.textContent = 'Cargando...';
    list.appendChild(loading);
    let rows = [];
    try {
      const res = await fetch('https://restcountries.com/v3.1/all?fields=name,idd,cca2');
      const data = await res.json();
      rows = (data || []).map(r => {
        const root = (r.idd && r.idd.root) || '';
        const sufs = (r.idd && r.idd.suffixes) || [];
        const dial = (root && sufs && sufs.length) ? (root + sufs[0]) : (root || '');
        return {
          name: (r.name && (r.name.common || r.name.official)) || '',
          code: (r.cca2 || '').toLowerCase(),
          dial: dial || ''
        };
      }).filter(x => x.name && x.code && x.dial.startsWith('+'));
      rows.sort((a,b) => a.name.localeCompare(b.name, 'es')); 
    } catch(_) {
      rows = [ { name: 'Venezuela', code: 've', dial: '+58' } ];
    }
    function render(filter) {
      list.innerHTML = '';
      const f = (filter || '').toLowerCase();
      rows.filter(x => !f || x.name.toLowerCase().includes(f) || x.dial.includes(f))
        .forEach(x => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.setAttribute('data-cc', x.dial);
          btn.setAttribute('data-flag', x.code);
          btn.className = 'phone-cc-item';
          btn.innerHTML = `
            <span class="cc-left">
              <img src="https://flagcdn.com/w20/${x.code}.png" alt="" width="16" height="12">
              <span class="cc-name">${x.name}</span>
            </span>
            <span class="cc-dial">${x.dial}</span>
          `;
          btn.addEventListener('click', () => {
            if (inputPhoneCc) inputPhoneCc.value = x.dial;
            if (phoneCcLabel) phoneCcLabel.textContent = x.dial;
            const img = phoneCcBtn && phoneCcBtn.querySelector('img');
            if (img) img.src = `https://flagcdn.com/w20/${x.code}.png`;
            phoneCcMenu.setAttribute('hidden', '');
            updateCombinedPhone();
          });
          list.appendChild(btn);
        });
      if (!list.children.length) {
        const empty = document.createElement('div');
        empty.style.color = '#94a3b8';
        empty.style.padding = '6px 8px';
        empty.textContent = 'Sin resultados';
        list.appendChild(empty);
      }
    }
    search.addEventListener('input', () => render(search.value));
    render('');
  }

  function mobileFooterHeight() {
    try {
      const el = document.getElementById('mfs');
      if (!el) return 0;
      const visible = !el.hasAttribute('hidden') || el.classList.contains('show');
      if (!visible) return 0;
      const r = el.getBoundingClientRect();
      return Math.max(0, r.height || 0);
    } catch (_) { return 0; }
  }

  function positionPhoneMenu() {
    if (!phoneCcBtn || !phoneCcMenu) return;
    const menu = phoneCcMenu;
    const list = menu.querySelector('.phone-cc-list');
    const btnRect = phoneCcBtn.getBoundingClientRect();
    const vh = window.innerHeight || document.documentElement.clientHeight || 0;
    const footerH = mobileFooterHeight();
    const margin = 10;
    const desired = 192; // 4 items x 44px aprox + padding
    // Space below button considering footer
    const spaceBelow = Math.max(0, vh - btnRect.bottom - footerH - margin);
    const spaceAbove = Math.max(0, btnRect.top - margin);
    // Default open downward
    menu.style.top = 'calc(100% + 6px)';
    menu.style.bottom = 'auto';
    const maxHDown = Math.max(120, Math.min(desired, spaceBelow));
    const maxHUp = Math.max(120, Math.min(desired, spaceAbove));
    let useUp = false;
    if (maxHDown < 140 && maxHUp > maxHDown) useUp = true;
    if (useUp) {
      menu.style.top = 'auto';
      menu.style.bottom = 'calc(100% + 6px)';
      if (list) list.style.maxHeight = `${maxHUp}px`;
      else menu.style.maxHeight = `${maxHUp}px`;
    } else {
      if (list) list.style.maxHeight = `${maxHDown}px`;
      else menu.style.maxHeight = `${maxHDown}px`;
    }
  }

  if (phoneCcBtn && phoneCcMenu) {
    phoneCcBtn.addEventListener('click', async () => {
      const isHidden = phoneCcMenu.hasAttribute('hidden');
      if (isHidden) {
        phoneCcMenu.removeAttribute('hidden');
        phoneCcBtn.classList.add('open');
        phoneCcBtn.setAttribute('aria-expanded', 'true');
        await populateCountries();
        positionPhoneMenu();
      } else {
        phoneCcMenu.setAttribute('hidden', '');
        phoneCcBtn.classList.remove('open');
        phoneCcBtn.setAttribute('aria-expanded', 'false');
      }
    });
    // Keyboard support
    phoneCcBtn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        phoneCcBtn.click();
      }
    });
    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!phoneCcMenu) return;
      if (phoneCcMenu.hasAttribute('hidden')) return;
      if (e.target === phoneCcBtn || phoneCcBtn.contains(e.target)) return;
      if (phoneCcMenu.contains(e.target)) return;
      phoneCcMenu.setAttribute('hidden', '');
      phoneCcBtn.classList.remove('open');
      phoneCcBtn.setAttribute('aria-expanded', 'false');
    });
    // Re-position on resize/scroll while open
    window.addEventListener('resize', () => { if (!phoneCcMenu.hasAttribute('hidden')) positionPhoneMenu(); });
    window.addEventListener('scroll', () => { if (!phoneCcMenu.hasAttribute('hidden')) positionPhoneMenu(); }, { passive: true });
  }

  if (inputPhoneLocal) inputPhoneLocal.addEventListener('input', updateCombinedPhone);

  function updateMobileFooter() {
    if (!mfs) return;
    const show = selectedItemIndex >= 0;
    if (!show) {
      mfs.classList.remove('show');
      mfs.setAttribute('hidden', '');
      return;
    }
    const it = (allItems && selectedItemIndex >= 0) ? allItems[selectedItemIndex] : null;
    if (it) {
      if (mfsTitle) mfsTitle.textContent = it.title || '';
      if (mfsPrice) {
        const unit = currency === 'BSD' ? (Number(it.price || 0) * (rate || 0)) : Number(it.price || 0);
        const val = unit * Math.max(1, quantity || 1);
        mfsPrice.textContent = formatPrice(val);
      }
    }
    mfs.classList.add('show');
    mfs.removeAttribute('hidden');
    if (mfsQtyVal) mfsQtyVal.textContent = String(Math.max(1, quantity || 1));
    if (dqVal) dqVal.textContent = String(Math.max(1, quantity || 1));
  }

  function formatPrice(n){
    const v = Number(n || 0);
    if (currency === 'BSD') {
      // Show in BsD
      return v.toLocaleString('es-VE', { style:'currency', currency:'VES', minimumFractionDigits: 0, maximumFractionDigits: 0 });
    } else {
      // Show in USD
      return v.toLocaleString('en-US', { style:'currency', currency:'USD', maximumFractionDigits: 2 });
    }
  }

  // Returns unit price in the currently selected currency
  function currentUnitValue(it) {
    if (!it) return 0;
    const base = Number(it.price || 0);
    return (currency === 'BSD') ? (base * (rate || 0)) : base;
  }

  function renderItems(items) {
    if (!grid) return;
    grid.innerHTML = '';
    if (!items || items.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.innerHTML = '<p>No hay paquetes configurados para este juego.</p>';
      grid.appendChild(empty);
      return;
    }
    // Group items: specials first
    const specials = (items || []).filter(it => (it.sticker || '').toLowerCase() === 'special');
    const normals = (items || []).filter(it => (it.sticker || '').toLowerCase() !== 'special');
    const ordered = specials.concat(normals);
    const visible = isMobile ? (showingAll ? ordered : ordered.slice(0, 6)) : ordered;

    const firstNormalInVisible = visible.find(x => normals.indexOf(x) !== -1);
    // Helper to trim transparent borders of a PNG icon using canvas
    async function trimPngTransparency(imgEl) {
      try {
        await new Promise((res, rej) => {
          if (imgEl.complete && imgEl.naturalWidth > 0) return res();
          imgEl.addEventListener('load', () => res(), { once: true });
          imgEl.addEventListener('error', () => rej(new Error('load error')), { once: true });
        });
        const w = imgEl.naturalWidth;
        const h = imgEl.naturalHeight;
        if (!w || !h) return;
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(imgEl, 0, 0);
        const { data } = ctx.getImageData(0, 0, w, h);
        let top = 0, left = 0, right = w - 1, bottom = h - 1;
        let found = false;
        // Top
        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            const a = data[(y * w + x) * 4 + 3];
            if (a !== 0) { top = y; found = true; break; }
          }
          if (found) break;
        }
        found = false;
        // Bottom
        for (let y = h - 1; y >= top; y--) {
          for (let x = 0; x < w; x++) {
            const a = data[(y * w + x) * 4 + 3];
            if (a !== 0) { bottom = y; found = true; break; }
          }
          if (found) break;
        }
        found = false;
        // Left
        for (let x = 0; x < w; x++) {
          for (let y = top; y <= bottom; y++) {
            const a = data[(y * w + x) * 4 + 3];
            if (a !== 0) { left = x; found = true; break; }
          }
          if (found) break;
        }
        found = false;
        // Right
        for (let x = w - 1; x >= left; x--) {
          for (let y = top; y <= bottom; y++) {
            const a = data[(y * w + x) * 4 + 3];
            if (a !== 0) { right = x; found = true; break; }
          }
          if (found) break;
        }
        const cw = Math.max(1, right - left + 1);
        const ch = Math.max(1, bottom - top + 1);
        if (cw === w && ch === h) return; // nothing to trim
        const out = document.createElement('canvas');
        out.width = cw;
        out.height = ch;
        const octx = out.getContext('2d');
        octx.drawImage(canvas, left, top, cw, ch, 0, 0, cw, ch);
        const dataUrl = out.toDataURL('image/png');
        imgEl.src = dataUrl;
      } catch (_) { /* ignore */ }
    }
    visible.forEach((it) => {
      // Insert a thin separator line before the first normal item when specials exist
      if (specials.length && firstNormalInVisible === it) {
        const sep = document.createElement('div');
        sep.style.borderTop = '1px solid rgba(148,163,184,0.35)';
        sep.style.margin = '8px 0';
        sep.style.gridColumn = '1 / -1';
        grid.appendChild(sep);
      }
      const b = document.createElement('button');
      b.className = 'item-pill';
      // Do NOT show price in the package selector; only title. Optionally show icon (forced size).
      const isPhone = window.matchMedia('(max-width: 700px)').matches;
      const iconSize = isPhone ? 30 : 50;
      const iconHtml = (it.icon_path && it.icon_path.trim())
        ? `<img class=\"item-icon\" src=\"${it.icon_path}\" alt=\"\" style=\"width:${iconSize}px;height:${iconSize}px;object-fit:contain;display:inline-block;\" />`
        : '';
      b.innerHTML = `
  <div class="item-pill-col item-pill-row" style="display:flex;align-items:center;gap:8px;">
    <div class="item-pill-title">${it.title || ''}</div>
    ${iconHtml}
  </div>
`;
      b.addEventListener('click', () => {
        selBox.hidden = false;
        selTitle.textContent = it.title;
        const unit = currentUnitValue(it);
        const total = unit * Math.max(1, quantity || 1);
        selPrice.textContent = formatPrice(total);
        sumPrice.textContent = formatPrice(total);
        grid.querySelectorAll('.item-pill').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        selectedItemIndex = items.indexOf(it);
        // Toggle 'Leer' button based on special flag and special package description
        if (btnLeer) {
          const isSpecial = ((it.sticker || '').toLowerCase() === 'special');
          const pkgDesc = gameSpecDescEl ? String(gameSpecDescEl.textContent || '').trim() : '';
          const hasDesc = !!pkgDesc;
          if (isSpecial && hasDesc) {
            btnLeer.style.display = 'inline';
            if (pkgInfoContent) pkgInfoContent.textContent = pkgDesc;
          } else {
            btnLeer.style.display = 'none';
          }
        }
        persistState();
        updateMobileFooter();
        ensureDesktopQty();
      });
      // Keep selection active on re-render (e.g., when switching payment method)
      if (items.indexOf(it) === selectedItemIndex) {
        b.classList.add('active');
        selBox.hidden = false;
        selTitle.textContent = it.title || '';
        const unit = currentUnitValue(it);
        const total = unit * Math.max(1, quantity || 1);
        selPrice.textContent = formatPrice(total);
        sumPrice.textContent = formatPrice(total);
        ensureDesktopQty();
        if (btnLeer) {
          const isSpecial = ((it.sticker || '').toLowerCase() === 'special');
          const pkgDesc = gameSpecDescEl ? String(gameSpecDescEl.textContent || '').trim() : '';
          const hasDesc = !!pkgDesc;
          if (isSpecial && hasDesc) {
            btnLeer.style.display = 'inline';
            if (pkgInfoContent) pkgInfoContent.textContent = pkgDesc;
          } else {
            btnLeer.style.display = 'none';
          }
        }
      }
      // Autoselect first visible if none selected yet
      grid.appendChild(b);
      // After mount, if PNG, trim transparent padding to visually ignore empty background
      try {
        const img = b.querySelector('.item-icon');
        if (img && (/(\.png)(\?|$)/i).test(String(img.src))) {
          // Use rAF to ensure element is in DOM, then trim
          requestAnimationFrame(() => trimPngTransparency(img));
        }
      } catch (_) { /* ignore */ }
    });
    
    // Control "Ver más" button visibility after rendering all items
    if (btnMore) {
      // Always hide on desktop
      if (!isMobile) {
        btnMore.hidden = true;
        btnMore.style.display = 'none';
      } else {
        // On mobile: Show ONLY if there are MORE than 6 packages
        const needMore = ordered.length > 6;
        if (needMore) {
          btnMore.hidden = false;
          btnMore.style.display = 'inline-block';
          btnMore.textContent = showingAll ? 'Ver menos' : 'Ver más';
        } else {
          btnMore.hidden = true;
          btnMore.style.display = 'none';
        }
      }
    }
  }

  // Toggle "Ver más" / "Ver menos" on mobile
  if (btnMore) {
    btnMore.addEventListener('click', () => {
      showingAll = !showingAll;
      renderItems(allItems);
      try { btnMore.blur(); } catch (_) {}
    });
  }

  fetch(`/store/package/${gid}/items`).then(r => r.json()).then(data => {
    allItems = (data && data.items) || [];
    showingAll = false;
    // Hide "Ver más" button immediately if there are 6 or fewer items
    if (btnMore && allItems.length <= 6) {
      btnMore.hidden = true;
      btnMore.style.display = 'none';
    }
    renderItems(allItems);
  }).catch(() => {});

  // Fetch exchange rate (BsD per 1 USD)
  fetch('/store/rate').then(r => r.json()).then(data => {
    rate = Number((data && data.rate_bsd_per_usd) || 0);
    renderItems(allItems);
  }).catch(() => { rate = 0; renderItems(allItems); });
  // Fetch payments configuration (Admin-configured)
  fetch('/store/payments').then(r => r.json()).then(data => {
    if (data && data.ok) paymentsCfg = data.payments || null;
    try {
      const cfg = paymentsCfg || {};
      // Pago Móvil
      if (btnPayBSD) {
        const url = (cfg.pm_image_path || '').trim();
        if (url) {
          btnPayBSD.innerHTML = `<img src="${url}" alt="Pago Móvil" style="max-height:42px; max-width:160px; object-fit:contain; display:block; margin:0 auto;" />`;
          if (/(\.png)(\?|$)/i.test(url)) {
            const img = btnPayBSD.querySelector('img');
            if (img) { requestAnimationFrame(() => { try {
              const canvas = document.createElement('canvas');
              const ctx = canvas.getContext('2d');
              img.addEventListener('load', () => {
                const w = img.naturalWidth, h = img.naturalHeight; if (!w||!h) return;
                canvas.width = w; canvas.height = h; ctx.drawImage(img, 0, 0);
                const { data } = ctx.getImageData(0, 0, w, h);
                let top=0,left=0,right=w-1,bottom=h-1,found=false;
                for(let y=0;y<h;y++){ for(let x=0;x<w;x++){ if(data[(y*w+x)*4+3]!==0){ top=y; found=true; break; } } if(found) break; }
                found=false; for(let y=h-1;y>=top;y--){ for(let x=0;x<w;x++){ if(data[(y*w+x)*4+3]!==0){ bottom=y; found=true; break; } } if(found) break; }
                found=false; for(let x=0;x<w;x++){ for(let y=top;y<=bottom;y++){ if(data[(y*w+x)*4+3]!==0){ left=x; found=true; break; } } if(found) break; }
                found=false; for(let x=w-1;x>=left;x--){ for(let y=top;y<=bottom;y++){ if(data[(y*w+x)*4+3]!==0){ right=x; found=true; break; } } if(found) break; }
                const cw = Math.max(1, right-left+1), ch = Math.max(1, bottom-top+1);
                if (cw===w && ch===h) return;
                const out = document.createElement('canvas'); out.width=cw; out.height=ch; out.getContext('2d').drawImage(canvas, left, top, cw, ch, 0, 0, cw, ch);
                img.src = out.toDataURL('image/png');
              }, { once:true });
            } catch(_){} }); }
          }
        } else {
          btnPayBSD.textContent = 'Pago Móvil';
        }
      }
      // Binance
      if (btnPayUSD) {
        const url2 = (cfg.binance_image_path || '').trim();
        if (url2) {
          btnPayUSD.innerHTML = `<img src="${url2}" alt="Binance" style="max-height:42px; max-width:160px; object-fit:contain; display:block; margin:0 auto;" />`;
          if (/(\.png)(\?|$)/i.test(url2)) {
            const img2 = btnPayUSD.querySelector('img');
            if (img2) { requestAnimationFrame(() => { try {
              const canvas = document.createElement('canvas');
              const ctx = canvas.getContext('2d');
              img2.addEventListener('load', () => {
                const w = img2.naturalWidth, h = img2.naturalHeight; if (!w||!h) return;
                canvas.width = w; canvas.height = h; ctx.drawImage(img2, 0, 0);
                const { data } = ctx.getImageData(0, 0, w, h);
                let top=0,left=0,right=w-1,bottom=h-1,found=false;
                for(let y=0;y<h;y++){ for(let x=0;x<w;x++){ if(data[(y*w+x)*4+3]!==0){ top=y; found=true; break; } } if(found) break; }
                found=false; for(let y=h-1;y>=top;y--){ for(let x=0;x<w;x++){ if(data[(y*w+x)*4+3]!==0){ bottom=y; found=true; break; } } if(found) break; }
                found=false; for(let x=0;x<w;x++){ for(let y=top;y<=bottom;y++){ if(data[(y*w+x)*4+3]!==0){ left=x; found=true; break; } } if(found) break; }
                found=false; for(let x=w-1;x>=left;x--){ for(let y=top;y<=bottom;y++){ if(data[(y*w+x)*4+3]!==0){ right=x; found=true; break; } } if(found) break; }
                const cw = Math.max(1, right-left+1), ch = Math.max(1, bottom-top+1);
                if (cw===w && ch===h) return;
                const out = document.createElement('canvas'); out.width=cw; out.height=ch; out.getContext('2d').drawImage(canvas, left, top, cw, ch, 0, 0, cw, ch);
                img2.src = out.toDataURL('image/png');
              }, { once:true });
            } catch(_){} }); }
          }
        } else {
          btnPayUSD.textContent = 'Binance';
        }
      }
    } catch (_) {}
  }).catch(() => { paymentsCfg = null; });

  if (mfsClose) {
    mfsClose.addEventListener('click', () => {
      if (!mfs) return;
      mfs.classList.remove('show');
      mfs.setAttribute('hidden', '');
    });
  }

  function setCurrency(newCurrency) {
    currency = newCurrency;
    methodChosen = true;
    // toggle active state on buttons
    if (btnPayBSD && btnPayUSD) {
      if (currency === 'BSD') {
        btnPayBSD.classList.add('primary');
        btnPayUSD.classList.remove('primary');
      } else {
        btnPayUSD.classList.add('primary');
        btnPayBSD.classList.remove('primary');
      }
    }
    // Recompute and show prices only now that a method is chosen
    if (selectedItemIndex >= 0) {
      const it = allItems[selectedItemIndex];
      if (it) {
        const unit = currentUnitValue(it);
        const total = unit * Math.max(1, quantity || 1);
        selPrice.textContent = formatPrice(total);
        sumPrice.textContent = formatPrice(total);
      }
    }
    renderItems(allItems);
    persistState();
    updateMobileFooter();
  }

  if (btnPayBSD) btnPayBSD.addEventListener('click', () => setCurrency('BSD'));
  if (btnPayUSD) btnPayUSD.addEventListener('click', () => setCurrency('USD'));

  // Do not pre-select a payment method to avoid showing prices prematurely

  // Re-render on resize to switch mobile/desktop behavior
  window.addEventListener('resize', () => {
    const nowMobile = window.matchMedia('(max-width: 699px)').matches;
    if (nowMobile !== isMobile) {
      isMobile = nowMobile;
      showingAll = false; // reset when switching
      // If user hasn't chosen a method yet, keep defaulting: BsD on mobile, USD on desktop
      if (!methodChosen) {
        currency = isMobile ? 'BSD' : 'USD';
      }
      renderItems(allItems);
    }
    updateMobileFooter();
  });

  // =====================
  // Local persistence + profile autofill
  // =====================
  const LS_KEY = 'inefablestore_checkout';

  function persistState() {
    if (!chkSave || !chkSave.checked) return; // only persist if user opted in
    const data = {
      customer_id: isGift ? '' : (inputCustomerId ? inputCustomerId.value.trim() : ''),
      customer_zone: (requiresZone && !isGift && inputCustomerZone) ? (inputCustomerZone.value.trim()) : '',
      email: inputEmail ? inputEmail.value.trim() : '',
      phone: inputPhone ? inputPhone.value.trim() : '',
      currency,
      selectedIndex: selectedItemIndex,
      quantity: Math.max(1, quantity || 1),
      save: true
    };
    try { localStorage.setItem(LS_KEY, JSON.stringify(data)); } catch (_) {}
  }

  function clearState() {
    try { localStorage.removeItem(LS_KEY); } catch (_) {}
  }

  function loadLocal() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) { return null; }
  }

  function applyState(state) {
    if (!state || !state.save) return; // only apply if user opted in previously
    if (chkSave) chkSave.checked = true;
    if (!isGift && inputCustomerId && state.customer_id && !inputCustomerId.value) inputCustomerId.value = state.customer_id;
    if (!isGift && requiresZone && inputCustomerZone && state.customer_zone && !inputCustomerZone.value) inputCustomerZone.value = state.customer_zone;
    if (inputEmail && state.email) inputEmail.value = state.email;
    if (inputPhone && state.phone) {
      // Try to split +CC local
      const s = String(state.phone || '').trim();
      const m = s.match(/^(\+\d{1,4})\s+(.*)$/);
      if (m) {
        if (inputPhoneCc) inputPhoneCc.value = m[1];
        if (phoneCcLabel) phoneCcLabel.textContent = m[1];
        if (inputPhoneLocal && !inputPhoneLocal.value) inputPhoneLocal.value = m[2];
        updateCombinedPhone();
      } else {
        if (inputPhoneLocal && !inputPhoneLocal.value) inputPhoneLocal.value = s;
        updateCombinedPhone();
      }
    }
    if (typeof state.selectedIndex === 'number') selectedItemIndex = state.selectedIndex;
    if (state.currency === 'BSD' || state.currency === 'USD') setCurrency(state.currency);
    if (typeof state.quantity === 'number' && state.quantity > 0) {
      quantity = Math.max(1, Math.floor(state.quantity));
      if (mfsQtyVal) mfsQtyVal.textContent = String(quantity);
    }
    updateMobileFooter();
  }

  async function loadProfileThenLocal() {
    // Try admin profile endpoint (logged-in admin).
    // If fails or not admin, fall back to localStorage only.
    let applied = false;
    try {
      const res = await fetch('/auth/profile');
      const data = await res.json();
      if (data && data.ok && data.profile) {
        if (inputEmail) inputEmail.value = data.profile.email || '';
        if (inputPhone) inputPhone.value = data.profile.phone || '';
        applied = true;
      }
    } catch (_) {}
    if (!applied) {
      const st = loadLocal();
      applyState(st);
    }
  }

  // Wire inputs to persist
  [inputEmail, inputPhone].forEach(el => {
    if (!el) return;
    el.addEventListener('input', () => { if (chkSave && chkSave.checked) persistState(); });
  });
  if (chkSave) chkSave.addEventListener('change', () => { if (chkSave.checked) { persistState(); } else { clearState(); } });
  if (btnBuy) btnBuy.addEventListener('click', () => { if (chkSave && chkSave.checked) persistState(); });

  // Initial load of profile/local state after items/rate are ready
  loadProfileThenLocal();

  // =====================
  // Pay modal logic
  // =====================
  function currentSelectedItem() {
    if (!allItems || selectedItemIndex < 0 || selectedItemIndex >= allItems.length) return null;
    return allItems[selectedItemIndex];
  }

  function computeCurrentTotal() {
    const it = currentSelectedItem();
    if (!it) return 0;
    const baseUsd = Number(it.price || 0);
    let totalUsd = baseUsd;
    if (validRef) {
      // Prefer item-specific discount if available
      let frac = Number(validRef.discount || 0);
      try {
        if (Array.isArray(validRef.item_discounts)) {
          const hit = validRef.item_discounts.find(x => Number(x.item_id) === Number(it.id));
          if (hit && typeof hit.discount === 'number') frac = Number(hit.discount || 0);
        }
      } catch(_){}
      if (frac > 0) totalUsd = totalUsd * (1 - frac);
    }
    return currency === 'BSD' ? totalUsd * (rate || 0) : totalUsd;
  }

  function openPay() {
    if (!payModal) return;
    // Title
    const total = computeCurrentTotal();
    const label = currency === 'BSD' ? 'BsD' : 'USD';
    payTotalTitle.textContent = `Total a pagar: ${formatPrice(total)} ${label === 'USD' ? '' : ''}`;
    // Info
    if (payInfo) {
      payInfo.innerHTML = '';
      if (currency === 'BSD') {
        const rows = [
          ['Banco', (paymentsCfg && paymentsCfg.pm_bank) || ''],
          ['Nombre', (paymentsCfg && paymentsCfg.pm_name) || ''],
          ['Teléfono', (paymentsCfg && paymentsCfg.pm_phone) || ''],
          ['Cédula/RIF', (paymentsCfg && paymentsCfg.pm_id) || ''],
        ];
        rows.forEach(([k, v]) => {
          const div = document.createElement('div');
          div.innerHTML = `<div style="display:flex; justify-content:space-between; gap:10px; border-top:1px solid rgba(148,163,184,0.2); padding-top:10px;"><strong>${k}</strong><span>${v || '-'}</span></div>`;
          payInfo.appendChild(div);
        });
      } else {
        const rows = [
          ['Binance', 'Transferencia interna'],
          ['Email', (paymentsCfg && paymentsCfg.binance_email) || ''],
          ['Teléfono', (paymentsCfg && paymentsCfg.binance_phone) || ''],
        ];
        rows.forEach(([k, v]) => {
          const div = document.createElement('div');
          div.innerHTML = `<div style="display:flex; justify-content:space-between; gap:10px; border-top:1px solid rgba(148,163,184,0.2); padding-top:10px;"><strong>${k}</strong><span>${v || '-'}</span></div>`;
          payInfo.appendChild(div);
        });
      }
    }
    // Timer 30:00
    startTimer(30 * 60);
    payRef && (payRef.value = '');
    payModal.removeAttribute('hidden');
  }

  function closePay() {
    if (!payModal) return;
    payModal.setAttribute('hidden', '');
    if (countdownId) { clearInterval(countdownId); countdownId = null; }
  }

  function startTimer(seconds) {
    if (!payTimer) return;
    let remaining = seconds;
    if (countdownId) clearInterval(countdownId);
    const render = () => {
      const m = Math.floor(remaining / 60).toString().padStart(2, '0');
      const s = Math.floor(remaining % 60).toString().padStart(2, '0');
      payTimer.textContent = `${m}:${s}`;
    };
    render();
    countdownId = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      render();
      if (remaining <= 0) {
        clearInterval(countdownId);
      }
    }, 1000);
  }

  if (btnBuy) {
    btnBuy.addEventListener('click', () => {
      if (selectedItemIndex < 0) return alert('Selecciona un paquete');
      if (!isGift) {
        if (!inputCustomerId || !inputCustomerId.value.trim()) {
          alert('Ingrese su ID de jugador');
          if (inputCustomerId) inputCustomerId.focus();
          return;
        }
        if (requiresZone && inputCustomerZone && !inputCustomerZone.value.trim()) {
          alert('Ingresa tu Zona ID');
          inputCustomerZone.focus();
          return;
        }
      }
      // Persist current selection if user opted
      if (chkSave && chkSave.checked) persistState();
      const gid = root.getAttribute('data-game-id');
      const method = (currency === 'BSD') ? 'pm' : 'binance';
      // Require phone before proceeding to checkout
      updateCombinedPhone();
      if (!inputPhone || !inputPhone.value.trim()) {
        alert('Ingresa tu número de teléfono');
        if (inputPhoneLocal) inputPhoneLocal.focus();
        return;
      }
      const paramsObj = {
        sel: String(selectedItemIndex),
        cur: currency,
        method,
        n: '',
        e: (inputEmail && inputEmail.value.trim()) || '',
        p: (inputPhone && inputPhone.value.trim()) || '',
        q: String(Math.max(1, quantity || 1))
      };
      if (!isGift && inputCustomerId) {
        paramsObj.cid = inputCustomerId.value.trim();
      }
      if (!isGift && requiresZone && inputCustomerZone) {
        paramsObj.zid = inputCustomerZone.value.trim();
      }
      const rcode = inputRefCode ? inputRefCode.value.trim() : '';
      if (rcode) paramsObj.rc = rcode;
      const params = new URLSearchParams(paramsObj);
      window.location.href = `/checkout/${gid}?${params.toString()}`;
    });
  }

  async function validateRefCode() {
    if (!inputRefCode) return;
    const code = inputRefCode.value.trim();
    const gid = (() => { const r = document.getElementById('game-details'); return r ? r.getAttribute('data-game-id') : ''; })();
    validRef = null;
    if (!code) { if (refStatus) refStatus.textContent = ''; renderItems(allItems); return; }
    try {
      if (refStatus) { refStatus.style.color = '#94a3b8'; refStatus.textContent = 'Validando...'; }
      const res = await fetch(`/store/special/validate?code=${encodeURIComponent(code)}&gid=${encodeURIComponent(gid||'')}`);
      const data = await res.json();
      if (!res.ok || !data.ok || !data.allowed) throw new Error(data.error || 'Código inválido');
      validRef = { code, discount: Number(data.discount || 0), item_discounts: Array.isArray(data.item_discounts) ? data.item_discounts : null };
      // Determine effective percent for current selection (if any)
      let shownPct = Math.round(Number(validRef.discount||0) * 100);
      try {
        const it = currentSelectedItem();
        if (it && Array.isArray(validRef.item_discounts)) {
          const hit = validRef.item_discounts.find(x => Number(x.item_id) === Number(it.id));
          if (hit && typeof hit.discount === 'number') shownPct = Math.round(Number(hit.discount||0)*100);
        }
      } catch(_){}
      if (refStatus) { refStatus.style.color = '#86efac'; refStatus.textContent = `Código válido: ${code} (${shownPct}% OFF)`; }
      renderItems(allItems);
    } catch (e) {
      validRef = null;
      if (refStatus) refStatus.textContent = '';
    }
  }
  // Attach validators
  if (inputRefCode) {
    inputRefCode.addEventListener('blur', validateRefCode);
    inputRefCode.addEventListener('input', () => {
      if (!inputRefCode.value.trim()) {
        validRef = null;
        if (refStatus) refStatus.textContent = '';
        renderItems(allItems);
      }
    });
  }
});



