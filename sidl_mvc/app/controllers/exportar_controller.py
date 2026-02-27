"""
CONTROLLER — Exportaciones
Rutas: /api/exportar/pdf/{audit_id}, /api/exportar/csv
"""

import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.schemas import LanzarAuditoriaRequest
from app.services.pdf_service import generar_pdf
from app.services.config_service import REPORTS_DIR
from app.models.auditoria import obtener_auditoria_completa

router = APIRouter()


@router.get("/pdf/{audit_id}")
async def exportar_pdf(audit_id: str):
    """
    Genera el reporte PDF con ReportLab a partir de los datos guardados en SQLite.
    """
    auditoria = obtener_auditoria_completa(audit_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada.")

    ruta_pdf = REPORTS_DIR / f"SiDL-{audit_id[:8]}.pdf"

    try:
        generar_pdf(auditoria, ruta_pdf)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error al generar PDF: {e}")

    return FileResponse(
        path=str(ruta_pdf),
        media_type="application/pdf",
        filename="SiDL-Reporte-Auditoria-QA.pdf",
    )


@router.post("/csv")
async def exportar_csv(req: LanzarAuditoriaRequest):
    """
    Genera y descarga el CSV de casos de prueba para Excel / TestRail.
    """
    casos = [c.dict() for c in req.casos]
    lineas = [
        "ID,Prioridad,Nombre del Caso,Precondiciones,Pasos,Resultado Esperado,Ref. SRS"
    ]
    for c in casos:
        pasos = c.get("pasos", "").replace("\n", "; ").replace('"', '""')
        lineas.append(
            f"{c['id']},{c['prioridad']},"
            f"\"{c['nombre']}\",\"{c['pre']}\",\"{pasos}\","
            f"\"{c['esperado']}\",{c['ref']}"
        )
    contenido = "\n".join(lineas)

    return StreamingResponse(
        iter([contenido.encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sidl-casos-de-prueba.csv"},
    )
