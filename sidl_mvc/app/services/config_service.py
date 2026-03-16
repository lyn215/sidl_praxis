"""
SERVICE — Configuración Central
Lee variables de entorno del archivo .env y las expone al resto de la app.
"""

import os
from pathlib import Path

# Cargar .env manualmente (sin dependencia de python-dotenv)
_env_path = Path(".env")
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# ─── Variables de entorno ─────────────────────────────────────────────────────
GROQ_API_KEY:       str = os.getenv("GROQ_API_KEY", "")
HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")
HOST:               str = os.getenv("HOST", "0.0.0.0")
PORT:               int = int(os.getenv("PORT", "8000"))
UPLOADS_DIR:        Path = Path("uploads")
REPORTS_DIR:        Path = Path("reports")

# Crear directorios necesarios
for d in [UPLOADS_DIR, REPORTS_DIR]:
    d.mkdir(exist_ok=True)

# Verificar configuración de proveedores IA
GROQ_ACTIVO = bool(GROQ_API_KEY)
HUGGINGFACE_ACTIVO = bool(HUGGINGFACE_API_KEY)

if GROQ_ACTIVO and HUGGINGFACE_ACTIVO:
    print("✅  GROQ_API_KEY y HUGGINGFACE_API_KEY detectadas — análisis real activado.")
elif GROQ_ACTIVO or HUGGINGFACE_ACTIVO:
    print("⚠️  Solo una API IA está configurada. Se necesitan AMBAS para funcionalidad completa.")
    if not GROQ_ACTIVO:
        print("    Falta: GROQ_API_KEY en .env")
    if not HUGGINGFACE_ACTIVO:
        print("    Falta: HUGGINGFACE_API_KEY en .env")
else:
    print("⚠️  Ningún proveedor IA configurado — se usarán datos de demostración.")
    print("    Para activar el análisis real: agrega en .env:")
    print("      GROQ_API_KEY=tu_key_groq")
    print("      HUGGINGFACE_API_KEY=tu_key_huggingface")
