"""
CONTROLLER — Auditoría
Rutas: /api/auditoria/subir, /api/auditoria/lanzar, /api/auditoria/historial, /api/auditoria/eliminar
"""

import uuid
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.schemas.schemas import LanzarAuditoriaRequest, AuditoriaResponse
from app.services import srs_service, gemini_service
from app.services.config_service import UPLOADS_DIR
from app.models import auditoria as auditoria_model

router = APIRouter()


@router.post("/subir")
async def subir_archivos(
    srs:     UploadFile = File(...),
    captura: UploadFile = File(None),
):
    """
    Recibe SRS + captura de pantalla.
    Extrae texto del SRS con PyMuPDF y genera casos de prueba con Gemini 1.5 Pro.
    """
    # ── Guardar archivos en disco ──────────────────────────────────────────────
    sid = str(uuid.uuid4())
    dir_sesion = UPLOADS_DIR / sid
    dir_sesion.mkdir(parents=True, exist_ok=True)

    # Validar tipo de archivo SRS
    ext_srs = Path(srs.filename).suffix.lower()
    if ext_srs not in [".pdf", ".docx", ".txt"]:
        raise HTTPException(400, f"Formato de SRS no soportado: {ext_srs}. Usa PDF, DOCX o TXT.")

    ruta_srs = dir_sesion / srs.filename
    ruta_srs.write_bytes(await srs.read())

    # Captura de pantalla (opcional)
    nombre_ui = "sin-captura.png"
    ruta_ui   = None
    if captura and captura.filename:
        ext_ui = Path(captura.filename).suffix.lower()
        if ext_ui not in [".png", ".jpg", ".jpeg", ".webp"]:
            raise HTTPException(400, f"Formato de imagen no soportado: {ext_ui}. Usa PNG, JPG o WebP.")
        nombre_ui = captura.filename
        ruta_ui   = dir_sesion / captura.filename
        ruta_ui.write_bytes(await captura.read())

    # ── Extraer texto del SRS ──────────────────────────────────────────────────
    texto_srs = srs_service.extraer_texto(ruta_srs)
    preview   = texto_srs  # <-- Ahora enviamos todo el documento
    # ── Generar casos de prueba con Gemini (ahora Groq) ───────────────────────
    resultado = gemini_service.generar_casos_desde_srs(texto_srs)
    casos     = resultado["casos"]
    fuente    = resultado["fuente"]
    
    # EXTRAER LOS REQUISITOS LIMPIOS QUE DEVOLVIÓ LA IA
    req_extraidos = resultado.get("requisitos_extraidos", texto_srs[:500])

    # ── Guardar sesión en SQLite usando los requisitos limpios ─────────────────
    session_id = auditoria_model.crear_sesion_archivo(
        archivo_srs=srs.filename,
        ruta_srs=str(ruta_srs),
        archivo_ui=nombre_ui,
        ruta_ui=str(ruta_ui) if ruta_ui else "",
        texto_srs=req_extraidos,  # <--- GUARDAR AQUÍ
    )

    return {
        "session_id":        session_id,
        "archivo_srs":       srs.filename,
        "archivo_ui":        nombre_ui,
        "casos":             casos,
        "fuente":            fuente,
        "texto_srs_preview": req_extraidos,  # <--- MANDAR AL FRONTEND AQUÍ
    }

@router.post("/lanzar", response_model=AuditoriaResponse)
async def lanzar_auditoria(req: LanzarAuditoriaRequest):
    """
    Ejecuta la auditoría visual real con Gemini Vision.
    Guarda todos los resultados en SQLite (auditorias, hallazgos, casos, wcag).
    """
    casos_dict = [c.dict() for c in req.casos]

    # Recuperar sesión para obtener la ruta de la imagen y el texto SRS
    sesion = auditoria_model.obtener_sesion(req.session_id)
    texto_srs = ""
    ruta_ui   = None
    if sesion:
        texto_srs = sesion.get("texto_srs", "")
        ruta_ui   = sesion.get("ruta_ui", None)

    # ── Auditoría Visual con Gemini 1.5 Pro ───────────────────────────────────
    resultado = gemini_service.auditar_con_vision(
        texto_srs=texto_srs,
        ruta_imagen=ruta_ui,
        casos=casos_dict,
    )

    hallazgos = resultado["hallazgos"]
    wcag      = resultado["wcag"]
    puntaje   = resultado["puntaje"]
    fuente    = resultado.get("fuente", "gemini")

    # ── Guardar en SQLite ─────────────────────────────────────────────────────
    audit_id = auditoria_model.crear_auditoria(
        sesion_id=req.session_id,
        puntaje=puntaje,
        hallazgos=hallazgos,
        casos=casos_dict,
        wcag=wcag,
        fuente=fuente,
        usuario_id=req.usuario_id,
    )

    return AuditoriaResponse(
        audit_id=audit_id,
        puntaje=puntaje,
        hallazgos=hallazgos,
        wcag=wcag,
        casos=casos_dict,
    )


@router.get("/historial/{usuario_id}")
async def obtener_historial(usuario_id: str):
    """Retorna el historial de auditorías del usuario desde SQLite."""
    lista = auditoria_model.obtener_historial_usuario(usuario_id)
    return {"auditorias": lista}


@router.delete("/eliminar/{audit_id}/{usuario_id}")
async def eliminar_auditoria(audit_id: str, usuario_id: str):
    """Elimina una auditoría y todos sus datos relacionados (CASCADE)."""
    ok = auditoria_model.eliminar_auditoria(audit_id, usuario_id)
    if not ok:
        raise HTTPException(404, "Auditoría no encontrada o no tienes permiso para eliminarla.")
    return {"ok": True}


@router.get("/detalle/{audit_id}")
async def detalle_auditoria(audit_id: str):
    """Retorna la auditoría completa con hallazgos, casos y WCAG."""
    data = auditoria_model.obtener_auditoria_completa(audit_id)
    if not data:
        raise HTTPException(404, "Auditoría no encontrada.")
    return data
