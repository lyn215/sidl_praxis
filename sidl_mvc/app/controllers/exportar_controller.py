"""
CONTROLLER — Exportaciones
Rutas: /api/exportar/pdf/{audit_id}, /api/exportar/csv
"""

import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import csv
import io

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
    casos = [c.dict() for c in req.casos]
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    
    writer.writerow(["ID", "Prioridad", "Nombre del Caso", "Precondiciones", "Pasos", "Resultado Esperado", "Ref. SRS"])
    for c in casos:
        writer.writerow([
            c.get('id', ''),
            c.get('prioridad', ''),
            c.get('nombre', ''),
            c.get('pre', ''),
            c.get('pasos', '').replace('\n', '; '),
            c.get('esperado', ''),
            c.get('ref', '')
        ])
    
    # Resetear el cursor y codificar
    output.seek(0)
    contenido = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([contenido]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sidl-casos-de-prueba.csv"}
    )
