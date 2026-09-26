#!/usr/bin/env bash
# Regenera static/css/tailwind.css con las clases de Tailwind que usa la portada.
# Correr después de agregar o cambiar clases de Tailwind en templates/index.html.
# Requiere Node (usa npx, no deja node_modules en el repo).
set -e
cd "$(dirname "$0")/.."
cfg=$(mktemp -d)
printf '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n' > "$cfg/in.css"
echo "module.exports = { content: ['./templates/index.html'] }" > "$cfg/tailwind.config.js"
npx -y tailwindcss@3.4.17 -c "$cfg/tailwind.config.js" -i "$cfg/in.css" -o static/css/tailwind.css --minify
rm -rf "$cfg"
