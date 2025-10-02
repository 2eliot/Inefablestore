// Home page carousels
document.addEventListener('DOMContentLoaded', () => {
  // Hero
  const hero = document.getElementById('hero');
  const track = hero ? hero.querySelector('.hero-track') : null;
  const prev = hero ? hero.querySelector('.hero-nav.prev') : null;
  const next = hero ? hero.querySelector('.hero-nav.next') : null;
  const dots = hero ? hero.querySelector('.hero-dots') : null;
  let heroIndex = 0;
  let heroImages = [];
  let heroTimer;

  function renderHero() {
    if (!track) return;
    track.innerHTML = '';
    const valid = heroImages.filter(Boolean);
    valid.forEach((src, i) => {
      const slide = document.createElement('div');
      slide.className = 'hero-slide' + (i === heroIndex ? ' active' : '');
      slide.style.backgroundImage = `url(${src})`;
      track.appendChild(slide);
    });
    if (dots) {
      dots.innerHTML = '';
      valid.forEach((_, i) => {
        const b = document.createElement('button');
        b.className = 'dot' + (i === heroIndex ? ' active' : '');
        b.addEventListener('click', () => { heroIndex = i; renderHero(); restartHeroTimer(); });
        dots.appendChild(b);
      });
    }
  }
  function moveHero(dir) {
    const validLen = heroImages.filter(Boolean).length;
    if (validLen === 0) return;
    heroIndex = (heroIndex + dir + validLen) % validLen;
    renderHero();
  }
  function restartHeroTimer() {
    clearInterval(heroTimer);
    heroTimer = setInterval(() => moveHero(1), 5000);
  }

  fetch('/store/hero').then(r => r.json()).then(data => {
    heroImages = (data && Array.isArray(data.images)) ? data.images : [];
    heroIndex = 0;
    renderHero();
    restartHeroTimer();
  }).catch(() => {});

  if (prev) prev.addEventListener('click', () => { moveHero(-1); restartHeroTimer(); });
  if (next) next.addEventListener('click', () => { moveHero(1); restartHeroTimer(); });

  // Packages: split by category into two rails
  function renderInto(railSelector, pkgs) {
    const r = document.querySelector(railSelector);
    if (!r) return;
    r.innerHTML = '';
    pkgs.forEach(p => {
      const card = document.createElement('article');
      card.className = 'pkg-card';
      const imgUrl = p.image_path || '';
      const isGif = /\.gif(\?.*)?$/i.test(imgUrl);
      const thumb = isGif
        ? `<div class="pkg-thumb"><img class="pkg-thumb-img" src="${imgUrl}" alt="${(p.name||'').replace(/"/g,'&quot;')}"/></div>`
        : `<div class="pkg-thumb" style="background-image:url('${imgUrl}')"></div>`;
      card.innerHTML = `${thumb}
        <h3 class="pkg-name">${p.name || ''}</h3>`;
      card.style.cursor = 'pointer';
      card.addEventListener('click', () => {
        if (p && typeof p.id !== 'undefined') {
          window.location.href = `/store/package/${p.id}`;
        }
      });
      r.appendChild(card);
    });
    // Align rail depending on whether it is scrollable
    adjustRailAlignment(r);
  }

  function adjustRailAlignment(rail) {
    if (!rail) return;
    // If content overflows horizontally, align to start to enable continuous scrolling
    const scrollable = rail.scrollWidth > rail.clientWidth + 2; // small tolerance
    rail.style.justifyContent = scrollable ? 'flex-start' : 'center';
  }

  Promise.all([
    fetch('/store/best_sellers').then(r => r.json()).catch(() => ({})),
    fetch('/store/packages?category=mobile').then(r => r.json()).catch(() => ({})),
    fetch('/store/packages?category=gift').then(r => r.json()).catch(() => ({})),
  ]).then(([best, mobile, gift]) => {
    renderInto('#rail-best', (best && best.packages) || []);
    renderInto('#rail-mobile', (mobile && mobile.packages) || []);
    renderInto('#rail-gift', (gift && gift.packages) || []);
  });

  // Re-check alignment on resize
  window.addEventListener('resize', () => {
    ['#rail-best', '#rail-mobile', '#rail-gift'].forEach(sel => {
      const el = document.querySelector(sel);
      if (el) adjustRailAlignment(el);
    });
  });

  // Compute step based on card spacing
  function railStep(r) {
    const items = r ? r.querySelectorAll('.pkg-card') : [];
    if (!items || items.length === 0) return Math.max(0, r.clientWidth - 40);
    if (items.length === 1) return items[0].offsetWidth + 20;
    const a = items[0];
    const b = items[1];
    const delta = Math.abs(b.offsetLeft - a.offsetLeft) || (a.offsetWidth + 14);
    // Advance approximately one full viewport of items
    const perView = Math.max(1, Math.round(r.clientWidth / delta));
    return perView * delta;
  }

  // Wire nav buttons via data-target
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.pkg-prev, .pkg-next');
    if (!btn) return;
    const target = btn.getAttribute('data-target');
    const r = target && document.querySelector(target);
    if (!r) return;
    // Ensure alignment is start when scrollable
    adjustRailAlignment(r);
    const dir = btn.classList.contains('pkg-prev') ? -1 : 1;
    const step = railStep(r);
    const maxLeft = r.scrollWidth - r.clientWidth;
    const nextLeft = Math.min(maxLeft, Math.max(0, r.scrollLeft + dir * step));
    r.scrollTo({ left: nextLeft, behavior: 'smooth' });
  });
});
