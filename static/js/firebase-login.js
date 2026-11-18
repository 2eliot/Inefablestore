// Login con Google mediante Firebase Authentication.
// La sesión real es la de la tienda: Firebase solo prueba quién es el usuario
// (ID token) y el servidor lo valida en /auth/firebase.
// Uso: window.InefableLogin.google("/ruta-a-la-que-volver")
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, getRedirectResult, signOut,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const cfg = window.INEFABLE_FIREBASE || {};
const app = initializeApp(cfg);
const auth = getAuth(app);
auth.languageCode = "es";
const CLAVE_VOLVER = "inefable_login_volver";

function rutaSegura(ruta) {
  const r = String(ruta || "");
  return r.startsWith("/") && !r.startsWith("//") ? r : location.pathname + location.search;
}

async function entrarEnLaTienda(user, volver) {
  const idToken = await user.getIdToken();
  const resp = await fetch("/auth/firebase", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }),
  });
  const data = await resp.json().catch(() => ({}));
  // La sesión queda en la tienda; la de Firebase no hace falta mantenerla.
  signOut(auth).catch(() => {});
  if (!resp.ok || !data.ok) throw new Error(data.error || "No se pudo iniciar sesión");
  if (data.redirect === "/contador") { location.href = "/contador"; return; }
  location.href = rutaSegura(volver);
}

async function google(volver) {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  try {
    const res = await signInWithPopup(auth, provider);
    await entrarEnLaTienda(res.user, volver);
  } catch (e) {
    const code = (e && e.code) || "";
    if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") return;
    if (code === "auth/popup-blocked" || code === "auth/operation-not-supported-in-this-environment") {
      // Navegadores que bloquean la ventana: se va a Google y vuelve aquí.
      try { sessionStorage.setItem(CLAVE_VOLVER, rutaSegura(volver)); } catch (_) {}
      await signInWithRedirect(auth, provider);
      return;
    }
    alert((e && e.message) || "No se pudo iniciar sesión con Google");
  }
}

// Vuelta del inicio de sesión por redirección
getRedirectResult(auth).then((res) => {
  if (!res || !res.user) return;
  let volver = "";
  try { volver = sessionStorage.getItem(CLAVE_VOLVER) || ""; sessionStorage.removeItem(CLAVE_VOLVER); } catch (_) {}
  entrarEnLaTienda(res.user, volver).catch((e) => alert(e.message));
}).catch(() => {});

window.InefableLogin = { google };
window.dispatchEvent(new Event("inefable-login-listo"));
