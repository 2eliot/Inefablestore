/* Flop IA: burbuja de chat de Inefablestore.
 * Habla con el servicio del bot (chatbot-hibrido) en la ruta de data-api (por defecto /flop-ia).
 * Todo vive dentro de un Shadow DOM para que los estilos de la tienda y los del chat no se mezclen.
 * Uso desde la página: window.FlopIA.abrir() o window.FlopIA.abrir("precios de free fire").
 */
(function () {
  "use strict";
  if (window.FlopIA) return;

  var script = document.currentScript;
  var API = ((script && script.getAttribute("data-api")) || "/flop-ia").replace(/\/$/, "");
  var CLAVE_SESION = "flopia_sesion", CLAVE_HISTORIAL = "flopia_historial", CLAVE_ABIERTO = "flopia_abierto",
      CLAVE_SEGUIR = "flopia_seguir", CLAVE_SALUDO = "flopia_saludo";

  function leer(almacen, clave, defecto) {
    try { var v = window[almacen].getItem(clave); return v === null ? defecto : JSON.parse(v); } catch (e) { return defecto; }
  }
  function guardar(almacen, clave, valor) {
    try { window[almacen].setItem(clave, JSON.stringify(valor)); } catch (e) { /* modo privado */ }
  }

  // la conversación se cierra tras estos minutos sin escribir (igual que en el bot) y al volver empieza otra;
  // mientras el bot espera el pago (ya dio los datos de pago móvil) aguanta mucho más: pagar tarda
  var MINUTOS_INACTIVO = 15, MINUTOS_PAGO = 120, CLAVE_ULTIMO = "flopia_ultimo", CLAVE_PAGO = "flopia_pago";
  function nuevaId() { return "web-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10); }
  var sesion = leer("localStorage", CLAVE_SESION, null);
  if (!sesion) {
    sesion = nuevaId();
    guardar("localStorage", CLAVE_SESION, sesion);
  }
  function tocar() { guardar("localStorage", CLAVE_ULTIMO, Date.now()); }
  function inactivo() {
    var minutos = leer("localStorage", CLAVE_PAGO, false) ? MINUTOS_PAGO : MINUTOS_INACTIVO;
    return Date.now() - leer("localStorage", CLAVE_ULTIMO, 0) > minutos * 60000;
  }

  var CSS = [
    /* colores: estilo WhatsApp oscuro con el verde de la tienda solo en acentos */
    ":host{all:initial;font-family:'Outfit',system-ui,-apple-system,'Segoe UI',sans-serif;color:#e9edef;font-size:14px;",
    "-webkit-text-size-adjust:100%;text-size-adjust:100%;",
    "--verde:#3ee07f;--verde2:#2bc46a;--fondo:#0b141a;--panel:#111b21;--cabecera:#1a242b;--entrante:#1f2c34;",
    "--saliente:#0f5e49;--campo:#2a3942;--borde:#222d34;--suave:#8696a0;--texto:#e9edef}",
    "*{box-sizing:border-box}",
    "button{font-family:inherit}",
    /* lanzador */
    ".lanzador{position:fixed;right:20px;bottom:calc(20px + var(--alzar,0px));z-index:2147483000;width:58px;height:58px;border-radius:50%;border:0;cursor:pointer;",
    "background:radial-gradient(circle at 30% 25%,#6ff2a4,var(--verde) 45%,#1fa65a);box-shadow:0 10px 28px rgba(62,224,127,.3),0 2px 6px rgba(0,0,0,.5);",
    "display:grid;place-items:center;transition:transform .2s ease}",
    ".lanzador:hover{transform:translateY(-2px) scale(1.04)}",
    ".lanzador:focus-visible{outline:3px solid #fff;outline-offset:3px}",
    ".lanzador svg{width:28px;height:28px;color:#06130b}",
    ".lanzador::before{content:'';position:absolute;inset:-6px;border-radius:50%;border:2px solid var(--verde);opacity:.6;animation:pulso 2.4s ease-out infinite}",
    ".lanzador.abierto::before{display:none}",
    "@keyframes pulso{0%{transform:scale(.9);opacity:.7}80%,100%{transform:scale(1.25);opacity:0}}",
    ".punto{position:absolute;top:4px;right:4px;width:13px;height:13px;border-radius:50%;background:#ff4d6d;border:2px solid #0b141a}",
    ".saludo{position:fixed;right:88px;bottom:calc(28px + var(--alzar,0px));z-index:2147483000;max-width:230px;background:var(--entrante);",
    "border-radius:12px 12px 4px 12px;padding:10px 30px 10px 12px;font-size:13px;line-height:1.35;box-shadow:0 10px 30px rgba(0,0,0,.45);",
    "animation:aparecer .35s ease both;cursor:pointer}",
    ".saludo b{color:var(--verde)}",
    ".saludo .x{position:absolute;top:5px;right:7px;background:none;border:0;color:var(--suave);font-size:16px;cursor:pointer;padding:2px 4px}",
    /* panel */
    ".panel{position:fixed;right:20px;bottom:calc(90px + var(--alzar,0px));z-index:2147483001;width:380px;height:min(640px,calc(100vh - 120px));",
    "background:var(--fondo);border:1px solid var(--borde);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;",
    "box-shadow:0 24px 60px rgba(0,0,0,.6);animation:aparecer .25s ease both}",
    ".panel[hidden],.saludo[hidden]{display:none}",
    "@keyframes aparecer{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:none}}",
    /* cabecera, como la de un chat de WhatsApp */
    ".cabecera{display:flex;align-items:center;gap:10px;padding:9px 10px 9px 14px;background:var(--cabecera);border-bottom:1px solid var(--borde)}",
    ".avatar{width:38px;height:38px;border-radius:50%;flex:none;display:grid;place-items:center;font-weight:700;font-size:17px;color:#06130b;",
    "background:radial-gradient(circle at 30% 25%,#6ff2a4,var(--verde) 50%,#1fa65a);position:relative}",
    ".avatar::after{content:'';position:absolute;right:-1px;bottom:-1px;width:11px;height:11px;border-radius:50%;background:var(--verde);border:2px solid var(--cabecera)}",
    ".titulo{flex:1;min-width:0}",
    ".titulo strong{display:block;font-size:15px;font-weight:600;letter-spacing:.01em}",
    ".titulo span{display:block;font-size:12px;color:var(--suave);margin-top:1px}",
    ".cerrar{background:none;border:0;color:var(--suave);width:36px;height:36px;border-radius:50%;cursor:pointer;display:grid;place-items:center}",
    ".cerrar:hover{background:#2a3942;color:#fff}",
    /* mensajes: fondo con textura suave, burbujas planas con cola, mensajes seguidos pegados y la hora dentro */
    ".mensajes{flex:1;overflow-y:auto;padding:10px 12px 14px;display:flex;flex-direction:column;scroll-behavior:smooth;",
    "background:var(--fondo) radial-gradient(rgba(255,255,255,.04) 1px,transparent 1.2px) 0 0/22px 22px}",
    ".mensajes::-webkit-scrollbar{width:5px}.mensajes::-webkit-scrollbar-thumb{background:#2a3942;border-radius:6px}",
    ".msg{position:relative;max-width:80%;font-size:14px;line-height:1.4;padding:6px 9px 7px 10px;border-radius:9px;white-space:pre-wrap;overflow-wrap:anywhere;",
    "margin-top:10px;box-shadow:0 1px 1px rgba(0,0,0,.3);animation:aparecer .2s ease both}",
    ".msg.seguido{margin-top:3px}",
    ".msg.bot{align-self:flex-start;background:var(--entrante)}",
    ".msg.bot.cola{border-top-left-radius:0}",
    ".msg.bot.cola::before{content:'';position:absolute;top:0;left:-7px;border-top:9px solid var(--entrante);border-left:7px solid transparent}",
    ".msg.yo{align-self:flex-end;background:var(--saliente);color:#e9fdf3}",
    ".msg.yo.cola{border-top-right-radius:0}",
    ".msg.yo.cola::before{content:'';position:absolute;top:0;right:-7px;border-top:9px solid var(--saliente);border-right:7px solid transparent}",
    ".msg .hora{float:right;margin:7px -3px -4px 10px;font-size:10.5px;line-height:1;color:var(--suave);user-select:none}",
    ".msg.yo .hora{color:#9fd9c3}",
    ".msg b{color:var(--verde);font-weight:600}.msg.yo b{color:inherit}",
    ".msg a{color:#53bdeb}",
    ".msg img{display:block;max-width:200px;max-height:240px;border-radius:8px}",
    ".msg.yo.foto{padding:4px;background:var(--saliente)}",
    ".escribiendo{display:flex;align-items:center;gap:8px;color:var(--suave);font-size:12.5px}",
    ".puntos{display:inline-flex;gap:3px}.puntos i{width:6px;height:6px;border-radius:50%;background:var(--verde);animation:salto 1.2s infinite ease-in-out}",
    ".puntos i:nth-child(2){animation-delay:.15s}.puntos i:nth-child(3){animation-delay:.3s}",
    "@keyframes salto{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-4px);opacity:1}}",
    /* botones que manda el bot (copiar datos, Binance, WhatsApp) */
    ".acciones{align-self:flex-start;display:flex;flex-wrap:wrap;gap:6px;max-width:88%;margin-top:5px}",
    ".accion{background:var(--entrante);border:1px solid rgba(62,224,127,.55);color:var(--verde);border-radius:8px;padding:7px 11px;",
    "font-size:12.5px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:.15s}",
    ".accion:hover{background:var(--verde);color:#06130b}",
    ".accion.chico{border-color:#2a3942;color:#cfd8dc;font-weight:500;padding:5px 9px;font-size:12px}",
    ".accion.chico:hover{border-color:var(--verde);background:var(--entrante);color:var(--verde)}",
    ".accion.binance{border-color:#f0b90b;color:#f0b90b}.accion.binance:hover{background:#f0b90b;color:#1e2026}",
    ".accion.hecho{border-color:var(--verde);color:var(--verde)}",
    ".chips{display:flex;flex-wrap:wrap;gap:6px;padding:4px 12px 8px;background:var(--fondo)}",
    ".chip{background:var(--entrante);border:1px solid #2a3942;color:#cfd8dc;border-radius:999px;padding:6px 11px;font-size:12.5px;cursor:pointer;transition:.15s}",
    ".chip:hover{border-color:var(--verde);color:var(--verde)}",
    /* tarjeta de seguimiento */
    ".tarjeta{align-self:flex-start;width:86%;background:var(--entrante);border-radius:9px;padding:10px 12px;margin-top:10px;",
    "border-left:3px solid #2a3942;animation:aparecer .2s ease both}",
    ".tarjeta.listo{border-left-color:var(--verde)}.tarjeta.error{border-left-color:#ff5c7a}",
    ".tarjeta h4{margin:0 0 8px;font-size:13.5px;display:flex;justify-content:space-between;gap:10px}",
    ".tarjeta h4 span{font-weight:400;color:var(--suave);font-variant-numeric:tabular-nums}",
    ".paso{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:13px;color:var(--suave)}",
    ".paso.hecho{color:var(--texto)}",
    ".paso i{width:17px;height:17px;border-radius:50%;flex:none;border:2px solid #3b4a54;display:grid;place-items:center;font-style:normal;font-size:10px}",
    ".paso.hecho i{background:var(--verde);border-color:var(--verde);color:#06130b}",
    ".paso.actual i{border-color:var(--verde);border-top-color:transparent;animation:girar .9s linear infinite}",
    "@keyframes girar{to{transform:rotate(360deg)}}",
    ".tarjeta p{margin:8px 0 0;font-size:12.5px;color:var(--suave);line-height:1.4}",
    /* barra de escribir: campo redondeado con el clip dentro y el botón verde aparte, como WhatsApp */
    ".barra{display:flex;align-items:flex-end;gap:6px;padding:7px 8px calc(7px + env(safe-area-inset-bottom,0px));background:var(--cabecera)}",
    ".campo{flex:1;display:flex;align-items:flex-end;min-width:0;background:var(--campo);border-radius:22px;padding:2px 8px 2px 2px}",
    ".campo:focus-within{box-shadow:0 0 0 1px rgba(62,224,127,.5)}",
    ".barra textarea{flex:1;min-width:0;resize:none;max-height:110px;min-height:36px;background:transparent;border:0;color:var(--texto);",
    "padding:9px 6px 9px 2px;font:inherit;font-size:14px;outline:none;line-height:1.3}",
    ".barra textarea::placeholder{color:var(--suave)}",
    ".icono{width:36px;height:36px;flex:none;border-radius:50%;border:0;background:transparent;color:var(--suave);cursor:pointer;display:grid;place-items:center}",
    ".icono:hover{color:var(--verde)}",
    ".adjuntar{margin:1px 0}",
    ".enviar{width:42px;height:42px;background:var(--verde);color:#06130b}",
    ".enviar:hover{background:#5cf094;color:#06130b}",
    ".icono:disabled{opacity:.45;cursor:default}",
    ".icono svg{width:20px;height:20px}",
    ".pie{text-align:center;font-size:10.5px;color:#667781;padding:0 10px calc(6px + env(safe-area-inset-bottom,0px));background:var(--cabecera)}",
    /* teléfono: pantalla completa, letra un punto más pequeña y más aire entre mensajes */
    "@media (max-width:520px){.panel{right:0;bottom:0;width:100vw;height:100dvh;border-radius:0;border:0}",
    ".lanzador{right:16px;bottom:calc(16px + var(--alzar,0px))}.saludo{right:84px;bottom:calc(24px + var(--alzar,0px))}.lanzador.abierto{display:none}",
    ".msg{font-size:13.5px;max-width:82%;margin-top:11px}.msg.seguido{margin-top:3px}.mensajes{padding:8px 10px 12px}",
    ".titulo strong{font-size:14.5px}.titulo span{font-size:11.5px}.chip{font-size:12px;padding:6px 10px}.accion{font-size:12px}",
    /* 16px en el campo: así iOS no hace zoom al tocar para escribir */
    ".barra textarea{font-size:16px;padding:7px 6px 7px 2px;min-height:34px}}",
    /* puerta de acceso: sesión y teléfono antes de escribir */
    ".puerta{padding:14px 14px calc(12px + env(safe-area-inset-bottom,0px));background:var(--cabecera);display:flex;flex-direction:column;gap:9px}",
    ".puerta[hidden]{display:none}",
    ".puerta p{margin:0;font-size:13px;line-height:1.4;color:var(--texto)}",
    ".puerta p.error{color:#ff8fa3;font-size:12px}",
    ".puerta a{display:flex;align-items:center;justify-content:center;gap:8px;padding:10px;border-radius:10px;font-weight:600;font-size:13.5px;text-decoration:none}",
    ".puerta a.google{background:#fff;color:#1f1f1f}",
    ".puerta a.otro{border:1px solid #2a3942;color:#cfd8dc}",
    ".puerta .fila{display:flex;gap:6px}",
    ".puerta input{flex:1;min-width:0;background:var(--campo);border:0;border-radius:10px;color:var(--texto);padding:10px 12px;font:inherit;font-size:16px;outline:none}",
    ".puerta button{background:var(--verde);color:#06130b;border:0;border-radius:10px;padding:0 14px;font-weight:700;cursor:pointer}",
    ".puerta button:disabled{opacity:.5}",
    "@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}"
  ].join("");

  var ICONO_CHAT = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3C6.5 3 2 6.8 2 11.5c0 2.4 1.2 4.6 3.1 6.1L4.3 21l3.9-1.8c1.2.4 2.5.6 3.8.6 5.5 0 10-3.8 10-8.4S17.5 3 12 3zm-4 9.6a1.3 1.3 0 1 1 0-2.6 1.3 1.3 0 0 1 0 2.6zm4 0a1.3 1.3 0 1 1 0-2.6 1.3 1.3 0 0 1 0 2.6zm4 0a1.3 1.3 0 1 1 0-2.6 1.3 1.3 0 0 1 0 2.6z"/></svg>';
  var ICONO_X = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  var ICONO_CLIP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5l-8.6 8.6a5 5 0 0 1-7.1-7.1l8.6-8.6a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.9-7.9"/></svg>';
  var ICONO_ENVIAR = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3.4 20.4l17.5-7.5a1 1 0 0 0 0-1.8L3.4 3.6a1 1 0 0 0-1.4 1.1L3.9 11l9.1 1-9.1 1-1.9 6.3a1 1 0 0 0 1.4 1.1z"/></svg>';

  var CHIPS = [["💎 Ver precios", "precios"], ["⚡ Comprar recarga", "quiero comprar una recarga"],
               ["🔎 Estado de mi recarga", "estado de mi recarga"], ["💳 Métodos de pago", "métodos de pago"]];
  var ESPERAS = [[0, "Flop está escribiendo"], [2500, "Un momento, estoy revisando"], [7000, "Ya casi lo tengo"],
                 [14000, "Gracias por esperar 🙏"]];
  var ESPERAS_FOTO = [[0, "Leyendo tu comprobante 🔎"], [4000, "Registrando tu pago"], [10000, "Ya casi, gracias por esperar 🙏"]];

  // ---------- construir ----------
  var host = document.createElement("div");
  host.id = "flop-ia";
  var raiz = host.attachShadow({ mode: "open" });
  raiz.innerHTML = "<style>" + CSS + "</style>" +
    '<button class="lanzador" type="button" aria-label="Abrir chat con Flop IA">' + ICONO_CHAT + '</button>' +
    '<div class="saludo" hidden role="status"><button class="x" type="button" aria-label="Cerrar">×</button>' +
    '¿Dudas o quieres recargar? <b>Pregúntale a Flop IA</b> ⚡</div>' +
    '<section class="panel" hidden role="dialog" aria-label="Chat con Flop IA">' +
    '  <header class="cabecera"><div class="avatar" aria-hidden="true">F</div>' +
    '    <div class="titulo"><strong>Flop IA</strong><span>Asistente de Inefablestore · en línea</span></div>' +
    '    <button class="cerrar" type="button" aria-label="Cerrar chat">' + ICONO_X + '</button></header>' +
    '  <div class="mensajes" aria-live="polite"></div>' +
    '  <div class="chips"></div>' +
    '  <div class="puerta" hidden></div>' +
    '  <form class="barra">' +
    '    <div class="campo">' +
    '      <button class="icono adjuntar" type="button" aria-label="Enviar comprobante de pago" title="Enviar comprobante de pago">' + ICONO_CLIP + '</button>' +
    '      <input class="archivo" type="file" accept="image/*" hidden>' +
    '      <textarea rows="1" maxlength="2000" placeholder="Mensaje" aria-label="Mensaje"></textarea>' +
    '    </div>' +
    '    <button class="icono enviar" type="submit" aria-label="Enviar">' + ICONO_ENVIAR + '</button>' +
    '  </form>' +
    '  <div class="pie">Flop IA puede equivocarse. Pagos y recargas los confirma Inefablestore.</div>' +
    '</section>';

  var $ = function (sel) { return raiz.querySelector(sel); };
  var lanzador = $(".lanzador"), panel = $(".panel"), saludo = $(".saludo"), lista = $(".mensajes"),
      chips = $(".chips"), form = $(".barra"), entrada = $("textarea"), archivo = $(".archivo"),
      btnEnviar = $(".enviar"), btnAdjuntar = $(".adjuntar"), puerta = $(".puerta");

  // ---------- cuenta: para hablar con Flop hay que iniciar sesión y tener teléfono ----------
  var cuenta = null;
  async function cargarCuenta() {
    try {
      var r = await fetch("/auth/me/contact", { credentials: "same-origin", cache: "no-store" });
      cuenta = await r.json();
    } catch (e) { cuenta = null; }
    return cuenta;
  }
  function cuentaLista() { return !!(cuenta && cuenta.logged_in && cuenta.has_phone); }
  function pintarPuerta() {
    var lista_ = cuentaLista();
    puerta.hidden = lista_;
    form.style.display = lista_ ? "" : "none";
    if (!lista_) chips.style.display = "none"; else chips.style.display = "";
    if (lista_) { puerta.innerHTML = ""; return; }
    var aqui = location.pathname + location.search;
    aqui += (aqui.indexOf("?") >= 0 ? "&" : "?") + "chat";
    if (!cuenta || !cuenta.logged_in) {
      puerta.innerHTML = "<p>Para hablar con Flop inicia sesión. Es solo la primera vez 🙌</p>" +
        (cuenta && cuenta.google ? '<a class="google" href="#">Continuar con Google</a>' : "") +
        '<a class="otro" href="/?login=1&next=' + encodeURIComponent(aqui) + '">Entrar con correo</a>';
      var g = puerta.querySelector(".google");
      if (g) g.addEventListener("click", function (e) {
        e.preventDefault();
        if (window.InefableLogin) window.InefableLogin.google(aqui);
        else location.href = "/?login=1&next=" + encodeURIComponent(aqui);
      });
      return;
    }
    puerta.innerHTML = "<p>Antes de empezar, escribe tu teléfono de Pago Móvil. Con él verificamos tus pagos.</p>" +
      '<div class="fila"><input type="tel" inputmode="tel" placeholder="04XX XXX XXXX" aria-label="Teléfono de Pago Móvil">' +
      '<button type="button">Guardar</button></div><p class="error" hidden></p>';
    var inp = puerta.querySelector("input"), btn = puerta.querySelector("button"), err = puerta.querySelector(".error");
    async function guardarTelefono() {
      btn.disabled = true; err.hidden = true;
      try {
        var r = await fetch("/auth/me/phone", { method: "POST", credentials: "same-origin",
          headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phone: inp.value }) });
        var d = await r.json();
        if (d && d.ok) { cuenta.has_phone = true; pintarPuerta(); setTimeout(function () { entrada.focus(); }, 50); return; }
        err.textContent = (d && d.error) || "No se pudo guardar el teléfono"; err.hidden = false;
      } catch (e) { err.textContent = "Sin conexión. Intenta de nuevo."; err.hidden = false; }
      btn.disabled = false;
    }
    btn.addEventListener("click", guardarTelefono);
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); guardarTelefono(); } });
    setTimeout(function () { inp.focus(); }, 50);
  }

  // ---------- utilidades ----------
  function escapar(t) {
    return String(t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function formatear(t) {  // *negrita* y enlaces, sin permitir HTML del servidor
    return escapar(t)
      .replace(/\*([^*\n]{1,80})\*/g, "<b>$1</b>")
      .replace(/~([^~\n]{1,40})~/g, '<s style="opacity:.6">$1</s>')  // precio antes del descuento
      .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  }
  function bajar() { lista.scrollTop = lista.scrollHeight; }

  var historial = leer("sessionStorage", CLAVE_HISTORIAL, []);
  function recordar(quien, texto, botones, hora) {
    historial.push([quien, texto, botones && botones.length ? botones : null, hora || ""]);
    historial = historial.slice(-40);
    guardar("sessionStorage", CLAVE_HISTORIAL, historial);
  }
  function ahoraHM() {
    try { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; }
  }

  // como en WhatsApp: los mensajes seguidos del mismo lado van pegados y solo el primero lleva la "cola";
  // cada burbuja muestra su hora abajo a la derecha. hora: undefined = ahora, "" = sin hora (historial viejo)
  function burbuja(quien, texto, sinGuardar, botones, hora) {
    var div = document.createElement("div");
    var anterior = lista.lastElementChild;
    var seguido = anterior && anterior.classList.contains("msg") && anterior.classList.contains(quien)
                  && !anterior.classList.contains("escribiendo");
    div.className = "msg " + quien + (seguido ? " seguido" : " cola");
    if (hora === undefined) hora = ahoraHM();
    div.innerHTML = formatear(texto) + (hora ? '<span class="hora">' + escapar(hora) + "</span>" : "");
    lista.appendChild(div);
    if (botones && botones.length) pintarBotones(botones);
    if (!sinGuardar) recordar(quien, texto, botones, hora);
    bajar();
    return div;
  }

  // botones que manda el bot: copiar datos, abrir un enlace (Binance Pay) o enviar un mensaje
  async function copiar(texto) {
    try { await navigator.clipboard.writeText(texto); return true; } catch (e) { /* sin permiso: método viejo */ }
    var area = document.createElement("textarea");
    area.value = texto; area.style.position = "fixed"; area.style.opacity = "0";
    document.body.appendChild(area); area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    area.remove();
    return ok;
  }
  function pintarBotones(botones) {
    var fila = document.createElement("div");
    fila.className = "acciones";
    botones.forEach(function (b) {
      var el;
      if (b.tipo === "enlace") {
        el = document.createElement("a");
        el.href = b.url; el.target = "_blank"; el.rel = "noopener";
      } else {
        el = document.createElement("button");
        el.type = "button";
      }
      el.className = "accion" + (b.chico ? " chico" : "") + (/binance/i.test(b.etiqueta || "") ? " binance" : "");
      el.textContent = b.etiqueta;
      if (b.tipo === "copiar") {
        el.addEventListener("click", async function () {
          var ok = await copiar(b.texto);
          el.textContent = ok ? "✓ Copiado" : "No se pudo copiar";
          el.classList.add("hecho");
          setTimeout(function () { el.textContent = b.etiqueta; el.classList.remove("hecho"); }, 1600);
        });
      } else if (b.tipo === "enviar") {
        el.addEventListener("click", function () { enviar(b.mensaje, null, b.etiqueta); });
      }
      fila.appendChild(el);
    });
    lista.appendChild(fila);
  }

  function pintarChips(mostrar) {
    chips.innerHTML = "";
    if (!mostrar) return;
    CHIPS.forEach(function (c) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.textContent = c[0];
      b.addEventListener("click", function () { enviar(c[1], null, c[0]); });
      chips.appendChild(b);
    });
  }

  async function leerLineas(resp, alLeer) {
    if (!resp.ok) {
      var err = {};
      try { err = await resp.json(); } catch (e) { /* sin cuerpo */ }
      throw new Error(err.error || ("HTTP " + resp.status));
    }
    var lector = resp.body.getReader(), dec = new TextDecoder(), pendiente = "";
    for (;;) {
      var r = await lector.read();
      if (r.done) break;
      pendiente += dec.decode(r.value, { stream: true });
      var corte;
      while ((corte = pendiente.indexOf("\n")) >= 0) {
        var linea = pendiente.slice(0, corte);
        pendiente = pendiente.slice(corte + 1);
        if (linea.trim()) alLeer(JSON.parse(linea));
      }
    }
  }

  // ---------- conversar ----------
  var ocupado = false;
  function bloquear(si) {
    ocupado = si;
    btnEnviar.disabled = btnAdjuntar.disabled = si;
  }

  async function enviar(texto, imagen, etiqueta) {
    if (ocupado) return;
    if (!cuentaLista()) { pintarPuerta(); return; }
    texto = (texto || "").trim();
    if (!texto && !imagen) return;
    // escribió después de que el chat se cerró por inactividad: empieza una conversación nueva
    if (historial.length && inactivo() && !Object.keys(siguiendo).length) nuevaConversacion();
    pintarChips(false);
    if (imagen) {
      var foto = document.createElement("div");
      foto.className = "msg yo foto";
      var img = document.createElement("img");
      img.src = imagen; img.alt = "Comprobante enviado";
      foto.appendChild(img);
      lista.appendChild(foto);
      recordar("yo", "📎 Comprobante enviado", null, ahoraHM());
    } else {
      burbuja("yo", etiqueta || texto);
    }
    bloquear(true);
    tocar();

    var espera = document.createElement("div");
    espera.className = "msg bot escribiendo";
    espera.innerHTML = '<span class="puntos"><i></i><i></i><i></i></span><span class="frase"></span>';
    lista.appendChild(espera);
    bajar();
    var frase = espera.querySelector(".frase");
    var relojes = (imagen ? ESPERAS_FOTO : ESPERAS).map(function (e) {
      return setTimeout(function () { frase.textContent = e[1] + "…"; }, e[0]);
    });

    var respuesta = null, enVivo = null, seguir = null, botones = null, esperandoPago = null;
    try {
      var resp = await fetch(API + (imagen ? "/api/comprobante" : "/api/chat"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(imagen ? { imagen: imagen, sesion: sesion } : { mensaje: texto, sesion: sesion })
      });
      await leerLineas(resp, function (l) {
        if (l.trozo) {
          if (!enVivo) { espera.remove(); enVivo = burbuja("bot", "", true); enVivo.textContent = ""; }
          enVivo.textContent += l.trozo;
          bajar();
        }
        if (l.fin) {
          respuesta = l.fin.texto; seguir = l.fin.seguir || null; botones = l.fin.botones || null;
          if ("esperando_pago" in l.fin) esperandoPago = !!l.fin.esperando_pago;
        }
      });
    } catch (e) {
      respuesta = "Uy, no pude conectarme ahora mismo 😕. Intenta de nuevo en unos segundos.";
    }
    relojes.forEach(clearTimeout);
    espera.remove();
    if (enVivo) enVivo.remove();
    if (respuesta) burbuja("bot", respuesta, false, botones);
    if (esperandoPago !== null) guardar("localStorage", CLAVE_PAGO, esperandoPago);
    bloquear(false);
    entrada.focus();
    tocar();
    if (seguir) seguirOrden(seguir.orden);
  }

  // ---------- seguimiento de la recarga ----------
  var siguiendo = {};
  window.addEventListener("beforeunload", function (ev) {
    if (Object.keys(siguiendo).length) { ev.preventDefault(); ev.returnValue = ""; }
  });

  function pintarPasos(caja, p, terminada) {
    var pasos = p.pasos || [];
    var actual = -1;
    for (var i = 0; i < pasos.length; i++) { if (!pasos[i].hecho) { actual = i; break; } }
    var cont = caja.querySelector(".pasos");
    cont.innerHTML = "";
    pasos.forEach(function (s, i) {
      var fila = document.createElement("div");
      fila.className = "paso" + (s.hecho ? " hecho" : (i === actual && !terminada ? " actual" : ""));
      fila.innerHTML = "<i>" + (s.hecho ? "✓" : "") + "</i>";
      fila.appendChild(document.createTextNode(s.label || ""));
      cont.appendChild(fila);
    });
    if (p.mensaje) caja.querySelector("p").textContent = p.mensaje;
  }

  async function seguirOrden(orden) {
    if (siguiendo[orden]) return;
    siguiendo[orden] = true;
    guardar("sessionStorage", CLAVE_SEGUIR, orden);
    var caja = document.createElement("div");
    caja.className = "tarjeta";
    caja.innerHTML = '<h4><b class="t"></b><span class="reloj">0:00</span></h4><div class="pasos"></div>' +
      "<p>Estamos verificando tu pago. No salgas del chat, te aviso aquí mismo ⏳</p>";
    caja.querySelector(".t").textContent = "⏳ Procesando tu recarga · #" + orden;
    lista.appendChild(caja);
    bajar();
    var inicio = Date.now(), reloj = caja.querySelector(".reloj");
    var tic = setInterval(function () {
      var s = Math.floor((Date.now() - inicio) / 1000);
      reloj.textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }, 1000);
    var final = null;
    // si la conexión se corta antes de terminar (red móvil, proxy), se vuelve a conectar sola
    for (var intento = 0; intento < 6 && !final; intento++) {
      if (intento) await new Promise(function (ok) { setTimeout(ok, 3000); });
      try {
        var resp = await fetch(API + "/api/seguir", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sesion: sesion, orden: orden })
        });
        if (resp.status === 403) break;  // la orden no es de esta conversación
        await leerLineas(resp, function (l) {
          if (l.progreso) { pintarPasos(caja, l.progreso, false); bajar(); }
          if (l.listo) final = l.listo;
        });
      } catch (e) { /* se reintenta */ }
    }
    if (!final) final = { texto: "Perdí la conexión con el seguimiento. Escribe «estado» y te digo cómo va tu recarga." };
    clearInterval(tic);
    delete siguiendo[orden];
    try { sessionStorage.removeItem(CLAVE_SEGUIR); } catch (e) { /* nada */ }
    if (final) {
      var ok = final.estado === "approved" || final.estado === "delivered", mal = final.estado === "rejected";
      caja.classList.add(ok ? "listo" : (mal ? "error" : "x"));
      caja.querySelector(".t").textContent = (ok ? "✅ Recarga lista" : (mal ? "❌ Recarga rechazada" : "⏳ Recarga en proceso"))
        + " · #" + orden;
      if (final.pasos) pintarPasos(caja, final, true);
      // comprobante de cierre; si la tienda rechazó la orden trae el botón de WhatsApp
      burbuja("bot", final.resumen || final.mensaje || final.texto || "", false, final.botones);
      if (!panel.hidden) return;
      lanzador.insertAdjacentHTML("beforeend", '<span class="punto" aria-hidden="true"></span>');
    }
  }

  // ---------- abrir y cerrar ----------
  function abrir(texto) {
    panel.hidden = false;
    saludo.hidden = true;
    lanzador.classList.add("abierto");
    lanzador.setAttribute("aria-label", "Cerrar chat con Flop IA");
    var punto = lanzador.querySelector(".punto");
    if (punto) punto.remove();
    guardar("sessionStorage", CLAVE_ABIERTO, true);
    guardar("localStorage", CLAVE_SALUDO, true);
    if (lista.children.length && inactivo() && !Object.keys(siguiendo).length) nuevaConversacion();
    tocar();
    // avisa al bot que alguien abrió el chat: carga la IA mientras el cliente escribe
    fetch(API + "/api/abrir", { method: "POST", headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ sesion: sesion }) }).catch(function () {});
    if (!lista.children.length) {
      burbuja("bot", "¡Hola! Soy *Flop IA* 👋\nTe ayudo con precios, recargas, pagos y cualquier duda de Inefablestore. ¿Qué necesitas?", true);
      pintarChips(true);
    }
    bajar();
    cargarCuenta().then(function () {
      pintarPuerta();
      if (!cuentaLista()) return;
      if (texto) enviar(texto);
      else setTimeout(function () { entrada.focus(); }, 50);
    });
  }
  function cerrar() {
    panel.hidden = true;
    lanzador.classList.remove("abierto");
    lanzador.setAttribute("aria-label", "Abrir chat con Flop IA");
    guardar("sessionStorage", CLAVE_ABIERTO, false);
    lanzador.focus();
  }

  lanzador.addEventListener("click", function () { panel.hidden ? abrir() : cerrar(); });
  $(".cerrar").addEventListener("click", cerrar);
  saludo.addEventListener("click", function (e) {
    if (e.target.classList.contains("x")) { saludo.hidden = true; guardar("localStorage", CLAVE_SALUDO, true); return; }
    abrir();
  });
  raiz.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) cerrar(); });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var t = entrada.value;
    entrada.value = "";
    entrada.style.height = "";
    enviar(t);
  });
  entrada.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  entrada.addEventListener("input", function () {
    entrada.style.height = "auto";
    entrada.style.height = Math.min(entrada.scrollHeight, 110) + "px";
  });
  btnAdjuntar.addEventListener("click", function () { archivo.click(); });
  archivo.addEventListener("change", function () {
    var f = archivo.files[0];
    archivo.value = "";
    if (!f) return;
    if (f.size > 8 * 1024 * 1024) { burbuja("bot", "Esa imagen pesa más de 8 MB. Envíame una captura más liviana 🙏"); return; }
    var lector = new FileReader();
    lector.onload = function () { enviar("", lector.result); };
    lector.readAsDataURL(f);
  });

  // barras fijas de la tienda pegadas abajo (checkout móvil, paquete elegido): la burbuja sube para no taparlas
  var BARRAS = "#mobile-checkout-bar, #mfs, [data-flop-ia-evitar]";
  function acomodar() {
    var alto = 0;
    document.querySelectorAll(BARRAS).forEach(function (el) {
      if (el.hidden || getComputedStyle(el).display === "none") return;
      var r = el.getBoundingClientRect();
      if (r.height && r.bottom >= window.innerHeight - 2) alto = Math.max(alto, r.height);
    });
    host.style.setProperty("--alzar", alto ? Math.round(alto + 8) + "px" : "0px");
  }

  // ---------- arranque ----------
  function iniciar() {
    document.body.appendChild(host);
    acomodar();
    setInterval(acomodar, 700);
    window.addEventListener("resize", acomodar);
    if (historial.length) {
      historial.forEach(function (h) { burbuja(h[0], h[1], true, h[2], h[3] || ""); });
    }
    // enlace directo al chat (para WhatsApp, redes, etc.):
    //   inefablestor.com/?chat                          abre Flop IA
    //   inefablestor.com/?chat=quiero recargar free fire  abre Flop IA y envía ese mensaje
    var params = new URLSearchParams(location.search);
    var directo = params.has("chat") ? (params.get("chat") || "") : (location.hash === "#chat" ? "" : null);
    if (directo !== null) {
      params.delete("chat");  // se quita de la dirección para que al recargar no se repita
      var resto = params.toString();
      history.replaceState(null, "", location.pathname + (resto ? "?" + resto : "")
                           + (location.hash === "#chat" ? "" : location.hash));
      saludo.hidden = true;
      abrir(directo.trim().slice(0, 300));
    } else if (leer("sessionStorage", CLAVE_ABIERTO, false)) {
      abrir();
    }
    var pendiente = leer("sessionStorage", CLAVE_SEGUIR, null);
    if (pendiente) seguirOrden(pendiente);  // venía siguiendo una recarga en otra página
    if (!leer("localStorage", CLAVE_SALUDO, false) && panel.hidden) {
      setTimeout(function () { if (panel.hidden) saludo.hidden = false; }, 4000);
    }
    // cualquier elemento con data-flop-ia abre el chat (los botones del pie de página)
    document.addEventListener("click", function (e) {
      var el = e.target.closest && e.target.closest("[data-flop-ia]");
      if (!el) return;
      e.preventDefault();
      abrir(el.getAttribute("data-flop-ia") || "");
    });
  }

  // ---------- cierre por inactividad ----------
  function nuevaConversacion() {
    sesion = nuevaId();
    guardar("localStorage", CLAVE_SESION, sesion);
    guardar("localStorage", CLAVE_PAGO, false);
    historial = [];
    guardar("sessionStorage", CLAVE_HISTORIAL, historial);
    lista.innerHTML = "";
    pintarChips(false);
  }
  setInterval(function () {
    if (!historial.length || Object.keys(siguiendo).length || !inactivo() || ocupado) return;
    nuevaConversacion();
    if (!panel.hidden) {
      burbuja("bot", "💤 Cerré el chat anterior por inactividad. Cuando quieras, escríbeme y empezamos de nuevo 🙌", true);
      pintarChips(true);
    }
  }, 30000);

  window.FlopIA = { abrir: abrir, cerrar: cerrar };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
