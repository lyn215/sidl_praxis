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
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
HOST:           str = os.getenv("HOST", "0.0.0.0")
PORT:           int = int(os.getenv("PORT", "8000"))
UPLOADS_DIR:    Path = Path("uploads")
REPORTS_DIR:    Path = Path("reports")

# Crear directorios necesarios
for d in [UPLOADS_DIR, REPORTS_DIR]:
    d.mkdir(exist_ok=True)

GEMINI_ACTIVO = bool(GEMINI_API_KEY)

if GEMINI_ACTIVO:
    print(f"✅  GEMINI_API_KEY detectada — análisis real activado.")
else:
    print("⚠️  GEMINI_API_KEY no configurada — se usarán datos de demostración.")
    print("    Para activar el análisis real: agrega GEMINI_API_KEY=tu_key en el archivo .env")
