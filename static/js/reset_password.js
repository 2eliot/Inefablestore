document.addEventListener('DOMContentLoaded', () => {
  const email = document.getElementById('rp-email');
  const code = document.getElementById('rp-code');
  const pass = document.getElementById('rp-pass');
  const btnSend = document.getElementById('rp-send');
  const btnConfirm = document.getElementById('rp-confirm');
  const alertEl = document.getElementById('rp-alert');

  function show(type, msg) {
    if (!alertEl) return;
    alertEl.textContent = msg || '';
    alertEl.className = 'alert ' + (type || '');
    alertEl.removeAttribute('hidden');
  }
  function clear() {
    if (!alertEl) return;
    alertEl.setAttribute('hidden', '');
    alertEl.textContent = '';
  }

  async function sendCode() {
    clear();
    const e = (email && email.value || '').trim();
    if (!e) {
      show('error', 'Ingresa tu correo');
      email && email.focus();
      return;
    }
    try {
      btnSend && (btnSend.disabled = true);
      show('', 'Enviando código...');
      const res = await fetch('/auth/password_reset/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: e })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        show('error', data.error || 'No se pudo enviar el código');
        return;
      }
      show('success', 'Si el correo existe, enviamos un código. Revisa tu bandeja y spam.');
      code && code.focus();
    } catch (_) {
      show('error', 'No se pudo enviar el código');
    } finally {
      btnSend && (btnSend.disabled = false);
    }
  }

  async function confirmReset() {
    clear();
    const e = (email && email.value || '').trim();
    const c = (code && code.value || '').trim();
    const p = (pass && pass.value || '');
    if (!e) {
      show('error', 'Ingresa tu correo');
      email && email.focus();
      return;
    }
    if (!c || c.length < 6) {
      show('error', 'Ingresa el código de 6 dígitos');
      code && code.focus();
      return;
    }
    if (!p || p.length < 6) {
      show('error', 'La contraseña debe tener al menos 6 caracteres');
      pass && pass.focus();
      return;
    }
    try {
      btnConfirm && (btnConfirm.disabled = true);
      show('', 'Cambiando contraseña...');
      const res = await fetch('/auth/password_reset/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: e, code: c, new_password: p })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        show('error', data.error || 'No se pudo cambiar la contraseña');
        return;
      }
      show('success', 'Contraseña cambiada. Ya puedes iniciar sesión.');
      setTimeout(() => { window.location.href = '/'; }, 900);
    } catch (_) {
      show('error', 'No se pudo cambiar la contraseña');
    } finally {
      btnConfirm && (btnConfirm.disabled = false);
    }
  }

  if (btnSend) btnSend.addEventListener('click', sendCode);
  if (btnConfirm) btnConfirm.addEventListener('click', confirmReset);

  // Convenience: Enter triggers confirm when in code/password
  if (code) code.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirmReset(); });
  if (pass) pass.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirmReset(); });
});
