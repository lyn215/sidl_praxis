"""
SiDL — Smart Interface & Documentation Lens
Punto de entrada principal de la aplicación FastAPI MVC

Ejecución:
    uvicorn main:app --reload --port 8000
"""

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates


from app.models.database import init_db
from app.controllers import auth_controller, auditoria_controller, exportar_controller

# ─── Inicializar base de datos SQLite ─────────────────────────────────────────
init_db()

# ─── Crear aplicación FastAPI ──────────────────────────────────────────────────
app = FastAPI(
    title="SiDL API",
    description="Smart Interface & Documentation Lens — Plataforma de Auditoría QA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Montar archivos estáticos ─────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Registrar routers (controladores) ────────────────────────────────────────
app.include_router(auth_controller.router,      prefix="/api/auth",     tags=["Autenticación"])
app.include_router(auditoria_controller.router, prefix="/api/auditoria",tags=["Auditoría"])
app.include_router(exportar_controller.router,  prefix="/api/exportar", tags=["Exportar"])

# ─── Ruta raíz → sirve el frontend HTML ───────────────────────────────────────
from fastapi.responses import FileResponse

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("templates/index.html")

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from app.models.database import check_status
    check_status()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
