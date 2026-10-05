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

  // la conversación se cierra tras estos minutos sin escribir (igual que en el bot) y al volver empieza otra
  var MINUTOS_INACTIVO = 15, CLAVE_ULTIMO = "flopia_ultimo";
  function nuevaId() { return "web-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10); }
  var sesion = leer("localStorage", CLAVE_SESION, null);
  if (!sesion) {
    sesion = nuevaId();
    guardar("localStorage", CLAVE_SESION, sesion);
  }
  function tocar() { guardar("localStorage", CLAVE_ULTIMO, Date.now()); }
  function inactivo() { return Date.now() - leer("localStorage", CLAVE_ULTIMO, 0) > MINUTOS_INACTIVO * 60000; }

  var CSS = [
    ":host{all:initial;font-family:'Outfit',system-ui,-apple-system,'Segoe UI',sans-serif;color:#eaeaea;",
    "--verde:#3ee07f;--verde2:#2bc46a;--fondo:#0b0c0f;--panel:#121317;--burbuja:#17191e;--borde:#23262d;--suave:#8b9099}",
    "*{box-sizing:border-box}",
    "button{font-family:inherit}",
    /* lanzador */
    ".lanzador{position:fixed;right:20px;bottom:calc(20px + var(--alzar,0px));z-index:2147483000;width:62px;height:62px;border-radius:50%;border:0;cursor:pointer;",
    "background:radial-gradient(circle at 30% 25%,#6ff2a4,var(--verde) 45%,#1fa65a);box-shadow:0 10px 28px rgba(62,224,127,.35),0 2px 6px rgba(0,0,0,.5);",
    "display:grid;place-items:center;transition:transform .2s ease}",
    ".lanzador:hover{transform:translateY(-2px) scale(1.04)}",
    ".lanzador:focus-visible{outline:3px solid #fff;outline-offset:3px}",
    ".lanzador svg{width:30px;height:30px;color:#06130b}",
    ".lanzador::before{content:'';position:absolute;inset:-6px;border-radius:50%;border:2px solid var(--verde);opacity:.6;animation:pulso 2.4s ease-out infinite}",
    ".lanzador.abierto::before{display:none}",
    "@keyframes pulso{0%{transform:scale(.9);opacity:.7}80%,100%{transform:scale(1.25);opacity:0}}",
    ".punto{position:absolute;top:4px;right:4px;width:13px;height:13px;border-radius:50%;background:#ff4d6d;border:2px solid #0b0c0f}",
    ".saludo{position:fixed;right:92px;bottom:calc(30px + var(--alzar,0px));z-index:2147483000;max-width:240px;background:var(--panel);border:1px solid var(--borde);",
    "border-radius:14px 14px 4px 14px;padding:11px 34px 11px 14px;font-size:14px;line-height:1.35;box-shadow:0 10px 30px rgba(0,0,0,.45);",
    "animation:aparecer .35s ease both;cursor:pointer}",
    ".saludo b{color:var(--verde)}",
    ".saludo .x{position:absolute;top:6px;right:8px;background:none;border:0;color:var(--suave);font-size:16px;cursor:pointer;padding:2px 4px}",
    /* panel */
    ".panel{position:fixed;right:20px;bottom:calc(94px + var(--alzar,0px));z-index:2147483001;width:380px;height:min(620px,calc(100vh - 120px));",
    "background:var(--fondo);border:1px solid var(--borde);border-radius:20px;overflow:hidden;display:flex;flex-direction:column;",
    "box-shadow:0 24px 60px rgba(0,0,0,.6),0 0 0 1px rgba(62,224,127,.06);animation:aparecer .25s ease both}",
    ".panel[hidden],.saludo[hidden]{display:none}",
    "@keyframes aparecer{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:none}}",
    ".cabecera{display:flex;align-items:center;gap:12px;padding:14px 14px 14px 16px;background:linear-gradient(180deg,#14161b,#0f1014);border-bottom:1px solid var(--borde)}",
    ".avatar{width:42px;height:42px;border-radius:13px;flex:none;display:grid;place-items:center;font-weight:800;font-size:19px;color:#06130b;",
    "background:radial-gradient(circle at 30% 25%,#6ff2a4,var(--verde) 50%,#1fa65a);position:relative}",
    ".avatar::after{content:'';position:absolute;right:-2px;bottom:-2px;width:12px;height:12px;border-radius:50%;background:var(--verde);border:2px solid #101115}",
    ".titulo{flex:1;min-width:0}",
    ".titulo strong{display:block;font-size:16px;letter-spacing:.02em}",
    ".titulo span{display:block;font-size:12.5px;color:var(--suave)}",
    ".cerrar{background:none;border:0;color:var(--suave);width:36px;height:36px;border-radius:10px;cursor:pointer;display:grid;place-items:center}",
    ".cerrar:hover{background:#1a1c21;color:#fff}",
    ".mensajes{flex:1;overflow-y:auto;padding:16px 14px;display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth}",
    ".mensajes::-webkit-scrollbar{width:6px}.mensajes::-webkit-scrollbar-thumb{background:#262930;border-radius:6px}",
    ".msg{max-width:85%;font-size:14.5px;line-height:1.42;padding:10px 13px;border-radius:16px;white-space:pre-wrap;overflow-wrap:anywhere;animation:aparecer .2s ease both}",
    ".msg.bot{align-self:flex-start;background:var(--burbuja);border:1px solid var(--borde);border-top-left-radius:5px}",
    ".msg.yo{align-self:flex-end;background:var(--verde);color:#06130b;font-weight:500;border-top-right-radius:5px}",
    ".msg b{color:var(--verde)}.msg.yo b{color:inherit}",
    ".msg a{color:var(--verde)}",
    ".msg img{display:block;max-width:200px;max-height:240px;border-radius:10px}",
    ".msg.yo.foto{padding:5px;background:#1c3a29}",
    ".escribiendo{display:flex;align-items:center;gap:8px;color:var(--suave);font-size:13.5px}",
    ".puntos{display:inline-flex;gap:3px}.puntos i{width:6px;height:6px;border-radius:50%;background:var(--verde);animation:salto 1.2s infinite ease-in-out}",
    ".puntos i:nth-child(2){animation-delay:.15s}.puntos i:nth-child(3){animation-delay:.3s}",
    "@keyframes salto{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-4px);opacity:1}}",
    ".acciones{align-self:flex-start;display:flex;flex-wrap:wrap;gap:6px;max-width:92%;margin-top:-4px}",
    ".accion{background:#121417;border:1px solid var(--verde);color:var(--verde);border-radius:10px;padding:8px 12px;",
    "font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:.15s}",
    ".accion:hover{background:var(--verde);color:#06130b}",
    ".accion.chico{border-color:#2a2e35;color:#d9dce1;font-weight:500;padding:6px 10px;font-size:12.5px}",
    ".accion.chico:hover{border-color:var(--verde);background:#121417;color:var(--verde)}",
    ".accion.binance{border-color:#f0b90b;color:#f0b90b}.accion.binance:hover{background:#f0b90b;color:#1e2026}",
    ".accion.hecho{border-color:var(--verde);color:var(--verde)}",
    ".chips{display:flex;flex-wrap:wrap;gap:7px;padding:0 14px 10px}",
    ".chip{background:#121417;border:1px solid #2a2e35;color:#d9dce1;border-radius:999px;padding:7px 12px;font-size:13px;cursor:pointer;transition:.15s}",
    ".chip:hover{border-color:var(--verde);color:var(--verde)}",
    /* tarjeta de seguimiento */
    ".tarjeta{align-self:flex-start;width:88%;background:var(--panel);border:1px solid var(--borde);border-radius:16px;padding:13px 14px;animation:aparecer .2s ease both}",
    ".tarjeta.listo{border-color:var(--verde)}.tarjeta.error{border-color:#ff5c7a}",
    ".tarjeta h4{margin:0 0 9px;font-size:14px;display:flex;justify-content:space-between;gap:10px}",
    ".tarjeta h4 span{font-weight:400;color:var(--suave);font-variant-numeric:tabular-nums}",
    ".paso{display:flex;align-items:center;gap:9px;padding:4px 0;font-size:13.5px;color:var(--suave)}",
    ".paso.hecho{color:#eaeaea}",
    ".paso i{width:18px;height:18px;border-radius:50%;flex:none;border:2px solid #343841;display:grid;place-items:center;font-style:normal;font-size:11px}",
    ".paso.hecho i{background:var(--verde);border-color:var(--verde);color:#06130b}",
    ".paso.actual i{border-color:var(--verde);border-top-color:transparent;animation:girar .9s linear infinite}",
    "@keyframes girar{to{transform:rotate(360deg)}}",
    ".tarjeta p{margin:9px 0 0;font-size:13px;color:var(--suave);line-height:1.4}",
    /* barra de escribir */
    ".barra{display:flex;align-items:flex-end;gap:8px;padding:10px 12px 12px;border-top:1px solid var(--borde);background:#0d0e11}",
    ".barra textarea{flex:1;resize:none;max-height:110px;min-height:42px;background:#15171b;border:1px solid #262930;color:#eaeaea;border-radius:14px;",
    "padding:11px 13px;font:inherit;font-size:14.5px;outline:none;line-height:1.35}",
    ".barra textarea:focus{border-color:var(--verde)}",
    ".barra textarea::placeholder{color:#6d727b}",
    ".icono{width:42px;height:42px;flex:none;border-radius:13px;border:1px solid #262930;background:#15171b;color:#c9cdd3;cursor:pointer;display:grid;place-items:center}",
    ".icono:hover{color:var(--verde);border-color:var(--verde)}",
    ".enviar{background:var(--verde);border-color:var(--verde);color:#06130b}",
    ".enviar:hover{background:#5cf094;color:#06130b}",
    ".icono:disabled{opacity:.45;cursor:default}",
    ".icono svg{width:20px;height:20px}",
    ".pie{text-align:center;font-size:11px;color:#5d626b;padding:0 0 8px;background:#0d0e11}",
    "@media (max-width:520px){.panel{right:0;bottom:0;width:100vw;height:100dvh;border-radius:0;border:0}",
    ".lanzador{right:16px;bottom:calc(16px + var(--alzar,0px))}.saludo{right:84px;bottom:calc(24px + var(--alzar,0px))}.lanzador.abierto{display:none}}",
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
    '  <form class="barra">' +
    '    <button class="icono adjuntar" type="button" aria-label="Enviar comprobante de pago" title="Enviar comprobante de pago">' + ICONO_CLIP + '</button>' +
    '    <input class="archivo" type="file" accept="image/*" hidden>' +
    '    <textarea rows="1" maxlength="2000" placeholder="Escribe tu mensaje…" aria-label="Mensaje"></textarea>' +
    '    <button class="icono enviar" type="submit" aria-label="Enviar">' + ICONO_ENVIAR + '</button>' +
    '  </form>' +
    '  <div class="pie">Flop IA puede equivocarse. Pagos y recargas los confirma Inefablestore.</div>' +
    '</section>';

  var $ = function (sel) { return raiz.querySelector(sel); };
  var lanzador = $(".lanzador"), panel = $(".panel"), saludo = $(".saludo"), lista = $(".mensajes"),
      chips = $(".chips"), form = $(".barra"), entrada = $("textarea"), archivo = $(".archivo"),
      btnEnviar = $(".enviar"), btnAdjuntar = $(".adjuntar");

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
  function recordar(quien, texto, botones) {
    historial.push(botones && botones.length ? [quien, texto, botones] : [quien, texto]);
    historial = historial.slice(-40);
    guardar("sessionStorage", CLAVE_HISTORIAL, historial);
  }

  function burbuja(quien, texto, sinGuardar, botones) {
    var div = document.createElement("div");
    div.className = "msg " + quien;
    div.innerHTML = formatear(texto);
    lista.appendChild(div);
    if (botones && botones.length) pintarBotones(botones);
    if (!sinGuardar) recordar(quien, texto, botones);
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
      recordar("yo", "📎 Comprobante enviado");
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

    var respuesta = null, enVivo = null, seguir = null, botones = null;
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
        if (l.fin) { respuesta = l.fin.texto; seguir = l.fin.seguir || null; botones = l.fin.botones || null; }
      });
    } catch (e) {
      respuesta = "Uy, no pude conectarme ahora mismo 😕. Intenta de nuevo en unos segundos.";
    }
    relojes.forEach(clearTimeout);
    espera.remove();
    if (enVivo) enVivo.remove();
    if (respuesta) burbuja("bot", respuesta, false, botones);
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
      burbuja("bot", final.resumen || final.mensaje || final.texto || "");  // comprobante de cierre
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
    if (texto) enviar(texto);
    else setTimeout(function () { entrada.focus(); }, 50);
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
      historial.forEach(function (h) { burbuja(h[0], h[1], true, h[2]); });
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
