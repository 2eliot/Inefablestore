"""Send a test email to mail-tester.com for spam diagnostics."""
import sys, os

# Allow overriding project dir via env or use a fixed known path
project_dir = os.environ.get(
    "PROJECT_DIR",
    "/home/apps/web-a-inefablestore"
)
# Fallback for local dev: detect from script location
if not os.path.exists(os.path.join(project_dir, "app.py")):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

sys.path.insert(0, project_dir)
os.chdir(project_dir)

from dotenv import load_dotenv
env_path = os.path.join(project_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

from app import send_email_html, _email_wrap, _email_style, app

s = _email_style()

parts = []
parts.append('<h2 style="margin:0 0 8px 0; font-size:20px; color:' + s["white"] + ';">Tu codigo de regalo</h2>')
parts.append('<p style="margin:0 0 20px 0; font-size:15px; color:' + s["text"] + '; line-height:1.6;">')
parts.append('    Tu orden <strong style="color:' + s["accent_light"] + ';">#9999</strong> ha sido procesada exitosamente.')
parts.append('    Aqui tienes tu codigo:')
parts.append('</p>')
parts.append('<div style="margin:24px 0 0 0; padding:20px; background-color:#0b0f14; border:2px dashed ' + s["accent"] + '; border-radius:10px; text-align:center;">')
parts.append('    <p style="margin:0; font-size:28px; font-weight:700; color:' + s["accent_light"] + '; letter-spacing:2px; font-family:monospace;">GIFT-ABCD-1234</p>')
parts.append('</div>')

with app.app_context():
    html = _email_wrap('Test', '\n'.join(parts))

    to_email = sys.argv[1] if len(sys.argv) > 1 else 'test-jajc058m8@srv1.mail-tester.com'
    subject = 'Tu codigo de regalo - InefableStore'
    text = 'Orden #9999 aprobada - Codigo: GIFT-ABCD-1234'

    result = send_email_html(to_email, subject, html, text)
    print('Email sent:', result)
