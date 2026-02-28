"""
MODEL — Auditoría, Hallazgos, Casos de Prueba, WCAG
Operaciones CRUD sobre todas las tablas relacionadas con la auditoría.
"""

import uuid
import json
from datetime import datetime
from typing import Optional

from app.models.database import get_connection


# ─── Sesión de Archivo ────────────────────────────────────────────────────────
def crear_sesion_archivo(
    archivo_srs: str, ruta_srs: str,
    archivo_ui: str, ruta_ui: str,
    texto_srs: str, usuario_id: Optional[str] = None
) -> str:
    """Guarda los archivos subidos y retorna el session_id."""
    conn = get_connection()
    sid = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO sesiones_archivo
        (id, usuario_id, archivo_srs, ruta_srs, archivo_ui, ruta_ui, texto_srs, creado_el)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (sid, usuario_id, archivo_srs, ruta_srs, archivo_ui, ruta_ui, texto_srs,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return sid


def obtener_sesion(session_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM sesiones_archivo WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Auditoría ────────────────────────────────────────────────────────────────
def crear_auditoria(
    sesion_id: str, puntaje: int,
    hallazgos: list, casos: list, wcag: list,
    fuente: str = "gemini",
    usuario_id: Optional[str] = None
) -> str:
    """Guarda la auditoría completa en SQLite. Retorna el audit_id."""
    conn = get_connection()
    aid = str(uuid.uuid4())
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    crit = sum(1 for h in hallazgos if h.get("severidad") == "critical")
    alto = sum(1 for h in hallazgos if h.get("severidad") == "high")
    med  = sum(1 for h in hallazgos if h.get("severidad") == "medium")
    bajo = sum(1 for h in hallazgos if h.get("severidad") == "low")

    # Cabecera de la auditoría
    conn.execute("""
        INSERT INTO auditorias
        (id, sesion_id, usuario_id, puntaje, total_hallazgos, criticos, altos, medios, bajos, fuente_analisis, fecha)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (aid, sesion_id, usuario_id, puntaje, len(hallazgos), crit, alto, med, bajo, fuente, ahora))

    # Casos de prueba
    for c in casos:
        # Normalizar valores que podrían venir como listas
        nombre = c.get("nombre","")
        if isinstance(nombre, list):
            nombre = " ".join(str(item) for item in nombre)
        
        pasos = c.get("pasos","")
        if isinstance(pasos, list):
            pasos = " ".join(str(item) for item in pasos)
        
        esperado = c.get("esperado","")
        if isinstance(esperado, list):
            esperado = " ".join(str(item) for item in esperado)
        
        conn.execute("""
            INSERT OR REPLACE INTO casos_prueba
            (id, auditoria_id, prioridad, nombre, precondiciones, pasos, esperado, ref_srs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (c.get("id",""), aid, c.get("prioridad","medium"),
              nombre, c.get("pre",""), pasos, esperado, c.get("ref","")))

    # Hallazgos
    for h in hallazgos:
        bbox = h.get("bbox", {})
        # Normalizar valores que podrían venir como listas en lugar de strings
        desc = h.get("desc", "")
        if isinstance(desc, list):
            desc = " ".join(str(item) for item in desc)
        
        esperado = h.get("esperado", "")
        if isinstance(esperado, list):
            esperado = " ".join(str(item) for item in esperado)
        
        obtenido = h.get("obtenido", "")
        if isinstance(obtenido, list):
            obtenido = " ".join(str(item) for item in obtenido)
        
        tecnicas = h.get("tecnicas", [])
        if isinstance(tecnicas, list):
            tecnicas = json.dumps(tecnicas, ensure_ascii=False)
        else:
            tecnicas = json.dumps([tecnicas], ensure_ascii=False)
        
        conn.execute("""
            INSERT OR REPLACE INTO hallazgos
            (id, auditoria_id, severidad, ref_caso, titulo, clausula, descripcion,
             esperado, obtenido, tecnicas, bbox_x, bbox_y, bbox_w, bbox_h, bbox_tipo, bbox_etiqueta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (h.get("id",""), aid, h.get("severidad","medium"),
              h.get("refCaso",""), h.get("titulo",""), h.get("clausula",""),
              desc, esperado, obtenido, tecnicas,
              bbox.get("x",""), bbox.get("y",""), bbox.get("w",""), bbox.get("h",""),
              bbox.get("tipo",""), bbox.get("etiqueta","")))

    # Resultados WCAG
    for w in wcag:
        # Normalizar valores que podrían venir como listas
        nombre = w.get("nombre", "")
        if isinstance(nombre, list):
            nombre = " ".join(str(item) for item in nombre)
        
        nota = w.get("nota", "")
        if isinstance(nota, list):
            nota = " ".join(str(item) for item in nota)
        
        conn.execute("""
            INSERT INTO resultados_wcag
            (auditoria_id, criterio_id, nombre, nivel, estado, nota)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (aid, w.get("id",""), nombre, w.get("nivel",""),
              w.get("estado",""), nota))

    conn.commit()
    conn.close()
    return aid


def obtener_auditoria_completa(audit_id: str) -> Optional[dict]:
    """Carga la auditoría con todos sus hallazgos, casos y WCAG desde SQLite."""
    conn = get_connection()

    auditoria = conn.execute(
        "SELECT a.*, s.archivo_srs, s.archivo_ui FROM auditorias a JOIN sesiones_archivo s ON a.sesion_id = s.id WHERE a.id = ?",
        (audit_id,)
    ).fetchone()

    if not auditoria:
        conn.close()
        return None

    result = dict(auditoria)

    # Casos de prueba
    casos_rows = conn.execute(
        "SELECT * FROM casos_prueba WHERE auditoria_id = ?", (audit_id,)
    ).fetchall()
    result["casos"] = [dict(r) for r in casos_rows]

    # Hallazgos
    h_rows = conn.execute(
        "SELECT * FROM hallazgos WHERE auditoria_id = ? ORDER BY CASE severidad WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END",
        (audit_id,)
    ).fetchall()
    result["hallazgos"] = []
    for r in h_rows:
        h = dict(r)
        h["tecnicas"] = json.loads(h.get("tecnicas") or "[]")
        h["refCaso"]  = h.pop("ref_caso", "")
        h["desc"]     = h.pop("descripcion", "")
        h["bbox"] = {
            "x": h.pop("bbox_x",""), "y": h.pop("bbox_y",""),
            "w": h.pop("bbox_w",""), "h": h.pop("bbox_h",""),
            "tipo": h.pop("bbox_tipo",""), "etiqueta": h.pop("bbox_etiqueta","")
        }
        result["hallazgos"].append(h)

    # WCAG
    wcag_rows = conn.execute(
        "SELECT criterio_id as id, nombre, nivel, estado, nota FROM resultados_wcag WHERE auditoria_id = ?",
        (audit_id,)
    ).fetchall()
    result["wcag"] = [dict(r) for r in wcag_rows]

    conn.close()
    return result


def obtener_historial_usuario(usuario_id: str, limite: int = 50) -> list:
    """Lista las auditorías de un usuario ordenadas por fecha descendente."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.id, a.puntaje, a.total_hallazgos, a.criticos, a.altos, a.medios, a.bajos,
               a.fuente_analisis, a.fecha, s.archivo_srs, s.archivo_ui
        FROM auditorias a
        JOIN sesiones_archivo s ON a.sesion_id = s.id
        WHERE a.usuario_id = ?
        ORDER BY a.fecha DESC
        LIMIT ?
    """, (usuario_id, limite)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def eliminar_auditoria(audit_id: str, usuario_id: str) -> bool:
    """Elimina auditoría (con CASCADE a hallazgos, casos, wcag). Verifica propietario."""
    conn = get_connection()
    row = conn.execute(
        "SELECT usuario_id FROM auditorias WHERE id = ?", (audit_id,)
    ).fetchone()
    if not row or row["usuario_id"] != usuario_id:
        conn.close()
        return False
    conn.execute("DELETE FROM auditorias WHERE id = ?", (audit_id,))
    conn.commit()
    conn.close()
    return True
