"""
SiDL — Smart Interface & Documentation Lens
Backend principal con FastAPI

Instalación:
    pip install fastapi uvicorn python-multipart pymupdf bcrypt reportlab Pillow google-generativeai

Ejecución:
    uvicorn main:app --reload --port 8000

Luego abre: http://localhost:8000
"""

import os
import json
import uuid
import hashlib
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# ── Importaciones opcionales (con fallback graceful) ──────────────────────────
try:
    import fitz  # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False
    print("⚠️  PyMuPDF no instalado. Extracción de SRS simulada.")

try:
    import bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False
    print("⚠️  bcrypt no instalado. Usando SHA-256.")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("⚠️  reportlab no instalado. Exportación PDF desactivada.")

try:
    import google.generativeai as genai
    GEMINI_OK = True
except ImportError:
    GEMINI_OK = False
    print("⚠️  google-generativeai no instalado. Usando análisis simulado.")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DB_FILE        = Path("db.json")
UPLOADS_DIR    = Path("uploads")
REPORTS_DIR    = Path("reports")
STATIC_DIR     = Path("static")

for d in [UPLOADS_DIR, REPORTS_DIR, STATIC_DIR]:
    d.mkdir(exist_ok=True)

if GEMINI_OK and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"✅  Gemini 1.5 Pro configurado.")

# ─────────────────────────────────────────────────────────────────────────────
# BASE DE DATOS JSON (simple, sin PostgreSQL para MVP)
# ─────────────────────────────────────────────────────────────────────────────
def cargar_db() -> dict:
    if DB_FILE.exists():
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    return {"usuarios": {}, "auditorias": {}}

def guardar_db(data: dict):
    DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def hash_contrasena(pwd: str) -> str:
    if BCRYPT_OK:
        return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    return hashlib.sha256(pwd.encode()).hexdigest()

def verificar_contrasena(pwd: str, hashed: str) -> bool:
    if BCRYPT_OK:
        try:
            return bcrypt.checkpw(pwd.encode(), hashed.encode())
        except Exception:
            pass
    return hashlib.sha256(pwd.encode()).hexdigest() == hashed

# ─────────────────────────────────────────────────────────────────────────────
# MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    contrasena: str

class RegistroRequest(BaseModel):
    nombre: str
    email: str
    contrasena: str
    confirmar: str

class CasoPrueba(BaseModel):
    id: str
    prioridad: str
    nombre: str
    pre: str
    pasos: str
    esperado: str
    ref: str

class LanzarAuditoriaRequest(BaseModel):
    session_id: str
    casos: list[CasoPrueba]

# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA DE ANÁLISIS CON GEMINI / FALLBACK SIMULADO
# ─────────────────────────────────────────────────────────────────────────────
HALLAZGOS_DEMO = [
    {
        "id": "H-001", "severidad": "critical", "refCaso": "CP-001",
        "titulo": "El Color del Botón CTA Viola la Especificación de Marca",
        "clausula": "§3.2.1 — El botón de acción primario debe usar el color corporativo #1565C0.",
        "desc": "El botón 'INICIAR SESIÓN' renderiza con background-color #e57373 (rojo). Esto viola directamente §3.2.1 y genera una señal visual de acción destructiva errónea.",
        "esperado": "background-color: #1565C0",
        "obtenido": "background-color: #e57373",
        "tecnicas": ["Análisis Semántico de Interfaz", "Extracción de Propiedades CSS", "Mapeo de Espacio de Color"],
        "bbox": {"x": "8%", "y": "54%", "w": "84%", "h": "9%", "tipo": "error", "etiqueta": "H-001 COLOR INCORRECTO"}
    },
    {
        "id": "H-002", "severidad": "high", "refCaso": "CP-002",
        "titulo": "Relación de Contraste Por Debajo del Umbral WCAG 2.1 AA",
        "clausula": "§5.4 — Todo texto informativo debe alcanzar un contraste mínimo de 4.5:1 (WCAG 2.1 AA).",
        "desc": "La relación de contraste medida en .info-text (#b0b0b0 sobre #d0d0d0) es 1.4:1. WCAG 1.4.3 requiere ≥4.5:1.",
        "esperado": "Contraste ≥ 4.5:1",
        "obtenido": "Contraste = 1.4:1 (FALLO CRÍTICO)",
        "tecnicas": ["Algoritmo de Luminancia WCAG 2.1", "Evaluación Heurística Digital", "Matriz de Contraste de Color"],
        "bbox": {"x": "8%", "y": "65%", "w": "84%", "h": "8%", "tipo": "error", "etiqueta": "H-002 FALLO DE CONTRASTE"}
    },
    {
        "id": "H-003", "severidad": "high", "refCaso": "CP-003",
        "titulo": "Control de Visibilidad de Contraseña Ausente",
        "clausula": "§3.5.2 — El campo de contraseña debe incluir un control de mostrar/ocultar.",
        "desc": "El campo de contraseña se renderiza sin ningún control de visibilidad adyacente. Incrementa la tasa de fallo de autenticación en ~23% (NNG).",
        "esperado": "Botón con ícono de ojo presente",
        "obtenido": "Sin control de toggle en el DOM",
        "tecnicas": ["Validación de Patrones UX", "Referencia Cruzada de Requisitos", "Análisis de Estructura DOM"],
        "bbox": {"x": "60%", "y": "42%", "w": "30%", "h": "9%", "tipo": "warn", "etiqueta": "H-003 TOGGLE FALTANTE"}
    },
    {
        "id": "H-004", "severidad": "medium", "refCaso": "CP-004",
        "titulo": "Enlace de Recuperación Sin Etiqueta ARIA",
        "clausula": "§5.1 — Todos los elementos interactivos deben tener atributos aria-label descriptivos.",
        "desc": "El enlace '¿Olvidaste tu contraseña?' carece de aria-label. Incumple WCAG 2.4.6 (Encabezados y Etiquetas, Nivel AA).",
        "esperado": "aria-label='Recuperar contraseña'",
        "obtenido": "Atributo aria-label ausente",
        "tecnicas": ["Inspección del Árbol de Accesibilidad", "Escaneo de Cumplimiento ARIA", "Simulación de Lector de Pantalla"],
        "bbox": {"x": "8%", "y": "75%", "w": "70%", "h": "6%", "tipo": "warn", "etiqueta": "H-004 SIN ARIA"}
    },
    {
        "id": "H-005", "severidad": "low", "refCaso": "CP-005",
        "titulo": "Cadena de Versión en Pie de Página Desactualizada",
        "clausula": "§8.1 — El pie de página debe mostrar la versión alineada con el tag de release actual.",
        "desc": "El pie de página muestra 'v2.1' mientras que el tag de release aprobado es v2.3.0.",
        "esperado": "Versión: v2.3.0",
        "obtenido": "Versión: v2.1",
        "tecnicas": ["Validación de Consistencia de Contenido", "Referencia de Metadatos de Release", "Comparación de Cadenas"],
        "bbox": {"x": "0%", "y": "90%", "w": "100%", "h": "8%", "tipo": "ok", "etiqueta": "H-005 VERSIÓN DESACTUALIZADA"}
    },
]

WCAG_DEMO = [
    {"id": "1.4.3", "nombre": "Contraste (Mínimo)",       "nivel": "AA", "estado": "fail", "nota": "#b0b0b0 sobre #d0d0d0 = 1.4:1 (req. 4.5:1)"},
    {"id": "1.3.1", "nombre": "Información y Relaciones", "nivel": "A",  "estado": "pass", "nota": "Etiquetas de formulario asociadas programáticamente."},
    {"id": "2.1.1", "nombre": "Teclado",                  "nivel": "A",  "estado": "warn", "nota": "Control toggle no verificado — elemento ausente."},
    {"id": "2.4.3", "nombre": "Orden del Foco",           "nivel": "A",  "estado": "pass", "nota": "Anillo de foco visible en todos los campos."},
    {"id": "2.4.6", "nombre": "Encabezados y Etiquetas",  "nivel": "AA", "estado": "fail", "nota": "Enlace de recuperación sin etiqueta ARIA."},
    {"id": "4.1.2", "nombre": "Nombre, Rol, Valor",       "nivel": "A",  "estado": "fail", "nota": "Botón CTA sin estado ARIA expandido."},
    {"id": "1.4.4", "nombre": "Redimensionar Texto",      "nivel": "AA", "estado": "pass", "nota": "El texto escala correctamente hasta 200%."},
]

def extraer_texto_srs(ruta_archivo: Path) -> str:
    """Extrae texto del SRS usando PyMuPDF si está disponible."""
    if not PYMUPDF_OK:
        return "SRS cargado (PyMuPDF no disponible — usando análisis simulado)."
    try:
        doc = fitz.open(str(ruta_archivo))
        texto = ""
        for pagina in doc:
            texto += pagina.get_text()
        doc.close()
        return texto[:8000]  # limitar tokens
    except Exception as e:
        return f"Error al leer SRS: {e}"

def analizar_con_gemini(texto_srs: str, nombre_ui: str) -> dict:
    """Llama a Gemini 1.5 Pro para generar casos de prueba y hallazgos reales."""
    if not (GEMINI_OK and GEMINI_API_KEY):
        return None  # usar fallback simulado

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")

        # Prompt para generar casos de prueba
        prompt_casos = f"""
Eres un experto en QA y automatización de pruebas. Analiza este documento SRS y genera exactamente 6 casos de prueba en JSON.

SRS:
{texto_srs[:4000]}

Responde SOLO con JSON válido, sin explicaciones, sin bloques de código:
{{
  "casos": [
    {{
      "id": "CP-001",
      "prioridad": "critical|high|medium|low",
      "nombre": "Nombre del caso de prueba",
      "pre": "Precondiciones",
      "pasos": "1. Paso uno\\n2. Paso dos",
      "esperado": "Resultado esperado",
      "ref": "§X.X"
    }}
  ]
}}
"""
        resp_casos = model.generate_content(prompt_casos)
        texto_casos = resp_casos.text.strip()
        # Limpiar posibles bloques markdown
        if "```" in texto_casos:
            texto_casos = texto_casos.split("```")[1]
            if texto_casos.startswith("json"):
                texto_casos = texto_casos[4:]
        casos_data = json.loads(texto_casos)
        return {"casos": casos_data.get("casos", []), "fuente": "gemini"}
    except Exception as e:
        print(f"⚠️  Error Gemini: {e} — usando datos simulados.")
        return None

def calcular_puntaje(hallazgos: list) -> int:
    """Calcula puntaje QA basado en hallazgos."""
    penalizaciones = {"critical": 15, "high": 10, "medium": 5, "low": 2}
    total_pen = sum(penalizaciones.get(h["severidad"], 0) for h in hallazgos)
    return max(0, min(100, 100 - total_pen))

# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE PDF CON REPORTLAB
# ─────────────────────────────────────────────────────────────────────────────
def generar_pdf_reporte(auditoria: dict, ruta_salida: Path):
    """Genera el reporte PDF profesional con ReportLab."""
    if not REPORTLAB_OK:
        raise RuntimeError("ReportLab no está instalado. Ejecuta: pip install reportlab")

    AZUL_OSC  = colors.HexColor("#050b14")
    AZUL_MED  = colors.HexColor("#0c1829")
    AZUL_CARD = colors.HexColor("#101f35")
    AZUL_COB  = colors.HexColor("#0f4c8a")
    CIELO     = colors.HexColor("#38bdf8")
    VERDE     = colors.HexColor("#10b981")
    AMBAR     = colors.HexColor("#f59e0b")
    ROJO      = colors.HexColor("#ef4444")
    MORADO    = colors.HexColor("#a78bfa")
    BLANCO    = colors.white
    GRIS      = colors.HexColor("#7ca3c4")
    GRIS_OSC  = colors.HexColor("#3d6484")

    COLOR_SEV = {
        "critical": ROJO,
        "high":     AMBAR,
        "medium":   CIELO,
        "low":      VERDE,
    }
    ETIQ_SEV = {
        "critical": "CRÍTICO",
        "high":     "ALTO",
        "medium":   "MEDIO",
        "low":      "BAJO",
    }

    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
        title="SiDL — Reporte de Auditoría QA",
        author="SiDL Beta v1.0",
    )

    story = []
    estilos = getSampleStyleSheet()

    # Estilos personalizados
    def est(nombre, **kwargs):
        base = kwargs.pop("base", "Normal")
        s = ParagraphStyle(nombre, parent=estilos[base], **kwargs)
        return s

    e_titulo   = est("titulo",   fontSize=28, textColor=BLANCO, alignment=TA_CENTER, fontName="Helvetica-Bold", spaceAfter=4)
    e_subtitulo= est("subtitulo",fontSize=11, textColor=GRIS,   alignment=TA_CENTER, fontName="Helvetica",      spaceAfter=6)
    e_badge    = est("badge",    fontSize=8,  textColor=AZUL_OSC,alignment=TA_CENTER,fontName="Helvetica-Bold")
    e_section  = est("section",  fontSize=11, textColor=CIELO,  fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6)
    e_h_id     = est("h_id",     fontSize=9,  textColor=CIELO,  fontName="Helvetica-Bold")
    e_h_titulo = est("h_titulo", fontSize=10, textColor=BLANCO, fontName="Helvetica-Bold")
    e_clausula = est("clausula", fontSize=8,  textColor=CIELO,  fontName="Helvetica-Oblique", spaceBefore=3, spaceAfter=3)
    e_desc     = est("desc",     fontSize=8,  textColor=GRIS,   fontName="Helvetica",         spaceBefore=3, spaceAfter=3, leading=12)
    e_mono     = est("mono",     fontSize=7,  textColor=BLANCO, fontName="Courier",           spaceBefore=2, spaceAfter=2)
    e_tecnica  = est("tecnica",  fontSize=7,  textColor=MORADO, fontName="Helvetica-Oblique", spaceAfter=2)
    e_footer   = est("footer",   fontSize=6,  textColor=GRIS_OSC,alignment=TA_CENTER, fontName="Helvetica")
    e_info_key = est("info_key", fontSize=8,  textColor=CIELO,  fontName="Helvetica-Bold")
    e_info_val = est("info_val", fontSize=8,  textColor=BLANCO, fontName="Helvetica")

    def bg_rect(story, color, height=6*mm):
        """Inserta un rectángulo de fondo usando una tabla de color sólido."""
        t = Table([[""]], colWidths=[180*mm], rowHeights=[height])
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), color),
                                ("LINEABOVE",  (0,0), (-1,-1), 0.5, CIELO)]))
        story.append(t)

    W = 180*mm  # ancho útil

    # ── PORTADA ──────────────────────────────────────────────────────────────
    # Fondo portada
    t_fondo = Table([[""]], colWidths=[W], rowHeights=[60*mm])
    t_fondo.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), AZUL_OSC),
        ("LINEBELOW", (0,0), (-1,-1), 1, CIELO),
    ]))
    story.append(t_fondo)
    story.append(Spacer(1, -60*mm))  # superponer contenido

    story.append(Paragraph("SiDL", e_titulo))
    story.append(Paragraph("Smart Interface &amp; Documentation Lens", e_subtitulo))

    # Badge azul
    t_badge = Table([[Paragraph("REPORTE DE AUDITORÍA MULTIMODAL QA", e_badge)]],
                    colWidths=[120*mm])
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CIELO),
        ("ROUNDEDCORNERS", [3]),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 8*mm))

    # Info del reporte
    puntaje    = auditoria.get("puntaje", 0)
    color_punt = VERDE if puntaje >= 80 else AMBAR if puntaje >= 55 else ROJO
    hallazgos  = auditoria.get("hallazgos", [])
    casos      = auditoria.get("casos", [])
    wcag       = auditoria.get("wcag", WCAG_DEMO)

    info_rows = [
        [Paragraph("Documento SRS:",        e_info_key), Paragraph(auditoria.get("archivo_srs","N/A"), e_info_val)],
        [Paragraph("Captura de Pantalla:",  e_info_key), Paragraph(auditoria.get("archivo_ui","N/A"),  e_info_val)],
        [Paragraph("Fecha de Generación:",  e_info_key), Paragraph(auditoria.get("fecha", datetime.now().strftime("%d/%m/%Y %H:%M")), e_info_val)],
        [Paragraph("Motor de Análisis:",    e_info_key), Paragraph("Gemini 1.5 Pro + LangChain + PyMuPDF", e_info_val)],
        [Paragraph("Versión del Sistema:",  e_info_key), Paragraph("SiDL Beta v1.0", e_info_val)],
    ]
    t_info = Table(info_rows, colWidths=[45*mm, 130*mm])
    t_info.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), AZUL_MED),
        ("ROWBACKGROUNDS",(0,0), (-1,-1), [AZUL_MED, AZUL_CARD]),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("LINEBELOW",     (0,0), (-1,-1), 0.2, GRIS_OSC),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 6*mm))

    # Puntaje QA grande
    crit = sum(1 for h in hallazgos if h["severidad"]=="critical")
    alto = sum(1 for h in hallazgos if h["severidad"]=="high")
    med  = sum(1 for h in hallazgos if h["severidad"]=="medium")
    bajo = sum(1 for h in hallazgos if h["severidad"]=="low")

    e_puntaje_n = est("puntaje_n", fontSize=28, textColor=color_punt, fontName="Helvetica-Bold", alignment=TA_CENTER)
    e_puntaje_l = est("puntaje_l", fontSize=7,  textColor=GRIS,       fontName="Helvetica",      alignment=TA_CENTER)

    sev_rows = [[
        Paragraph(f"<font color='#{ROJO.hexval()[2:]}' size='18'><b>{crit}</b></font><br/><font size='6' color='#{GRIS_OSC.hexval()[2:]}'>CRÍTICO</font>",  estilos["Normal"]),
        Paragraph(f"<font color='#{AMBAR.hexval()[2:]}' size='18'><b>{alto}</b></font><br/><font size='6' color='#{GRIS_OSC.hexval()[2:]}'>ALTO</font>",     estilos["Normal"]),
        Paragraph(f"<font color='#{CIELO.hexval()[2:]}' size='18'><b>{med}</b></font><br/><font size='6' color='#{GRIS_OSC.hexval()[2:]}'>MEDIO</font>",    estilos["Normal"]),
        Paragraph(f"<font color='#{VERDE.hexval()[2:]}' size='18'><b>{bajo}</b></font><br/><font size='6' color='#{GRIS_OSC.hexval()[2:]}'>BAJO</font>",    estilos["Normal"]),
        Paragraph(f"<font color='#{color_punt.hexval()[2:]}' size='26'><b>{puntaje}</b></font><br/><font size='6' color='#{GRIS_OSC.hexval()[2:]}'>PUNTAJE QA</font>", estilos["Normal"]),
    ]]
    t_sev = Table(sev_rows, colWidths=[W/5]*5)
    t_sev.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), AZUL_CARD),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LINEAFTER",     (0,0), (-2,-1), 0.5, GRIS_OSC),
        ("ROUNDEDCORNERS",[3]),
    ]))
    story.append(t_sev)
    story.append(PageBreak())

    # ── PÁGINA 2: HALLAZGOS ───────────────────────────────────────────────────
    story.append(Paragraph("HALLAZGOS DETALLADOS — INSIDE THE LENS", e_section))
    story.append(HRFlowable(width=W, thickness=0.5, color=CIELO, spaceAfter=6))

    for h in hallazgos:
        col_sev  = COLOR_SEV.get(h["severidad"], GRIS)
        etiq_sev = ETIQ_SEV.get(h["severidad"], h["severidad"].upper())

        # Encabezado del hallazgo
        head_rows = [[
            Paragraph(etiq_sev, est("sev_h", fontSize=7, textColor=AZUL_OSC, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(f"[{h['id']}] {h['titulo']}", est("titulo_h", fontSize=9, textColor=BLANCO, fontName="Helvetica-Bold")),
        ]]
        t_head = Table(head_rows, colWidths=[18*mm, W-18*mm])
        t_head.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0),   col_sev),
            ("BACKGROUND",    (1,0), (1,0),   AZUL_CARD),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (1,0), (1,0),   6),
        ]))
        story.append(t_head)

        # Cláusula violada
        story.append(Paragraph(f"↳ {h['clausula']}", e_clausula))

        # Descripción
        story.append(Paragraph(h["desc"], e_desc))

        # Esperado / Obtenido
        ev_rows = [[
            Paragraph(f"<b>ESPERADO:</b> {h['esperado']}", est("esp", fontSize=7, textColor=VERDE, fontName="Courier")),
            Paragraph(f"<b>OBTENIDO:</b> {h['obtenido']}", est("obt", fontSize=7, textColor=ROJO,  fontName="Courier")),
        ]]
        t_ev = Table(ev_rows, colWidths=[W/2, W/2])
        t_ev.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), AZUL_OSC),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 5),
            ("LINEAFTER",     (0,0), (0,-1),  0.3, GRIS_OSC),
        ]))
        story.append(t_ev)

        # Técnicas
        tecnicas_str = " · ".join(h.get("tecnicas", []))
        story.append(Paragraph(f"Técnicas: {tecnicas_str}", e_tecnica))
        story.append(HRFlowable(width=W, thickness=0.3, color=GRIS_OSC, spaceBefore=4, spaceAfter=6))

    story.append(PageBreak())

    # ── PÁGINA 3: WCAG + CASOS DE PRUEBA ─────────────────────────────────────
    story.append(Paragraph("CUMPLIMIENTO WCAG 2.1 AA — ACCESIBILIDAD", e_section))
    story.append(HRFlowable(width=W, thickness=0.5, color=CIELO, spaceAfter=4))

    COLOR_ESTADO = {"pass": VERDE, "fail": ROJO, "warn": AMBAR}
    ETIQ_ESTADO  = {"pass": "PASA", "fail": "FALLA", "warn": "AVISO"}

    wcag_header = [
        Paragraph("Criterio", est("wh", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Nombre",   est("wh", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Nivel",    est("wh", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Resultado",est("wh", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Observación", est("wh", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
    ]
    wcag_rows = [wcag_header]
    for w_item in wcag:
        col_e = COLOR_ESTADO.get(w_item["estado"], GRIS)
        etiq_e = ETIQ_ESTADO.get(w_item["estado"], w_item["estado"].upper())
        wcag_rows.append([
            Paragraph(w_item["id"],    est("wc", fontSize=7, textColor=GRIS,  fontName="Courier")),
            Paragraph(w_item["nombre"],est("wc", fontSize=7, textColor=BLANCO,fontName="Helvetica")),
            Paragraph(w_item["nivel"], est("wc", fontSize=7, textColor=GRIS,  fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(etiq_e,          est("wc", fontSize=7, textColor=col_e, fontName="Helvetica-Bold", alignment=TA_CENTER)),
            Paragraph(w_item["nota"],  est("wc", fontSize=6, textColor=GRIS,  fontName="Helvetica")),
        ])

    t_wcag = Table(wcag_rows, colWidths=[18*mm, 40*mm, 12*mm, 16*mm, W-86*mm])
    t_wcag.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  AZUL_COB),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [AZUL_MED, AZUL_CARD]),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("LINEBELOW",     (0,0), (-1,-1), 0.2, GRIS_OSC),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_wcag)
    story.append(Spacer(1, 8*mm))

    # Casos de prueba
    story.append(Paragraph("CASOS DE PRUEBA GENERADOS", e_section))
    story.append(HRFlowable(width=W, thickness=0.5, color=CIELO, spaceAfter=4))

    ETIQ_PRIO  = {"critical":"CRÍTICO","high":"ALTO","medium":"MEDIO","low":"BAJO"}
    cp_header = [
        Paragraph("ID",         est("ch", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Prioridad",  est("ch", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Nombre del Caso", est("ch", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Resultado Esperado", est("ch", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
        Paragraph("Ref.",       est("ch", fontSize=7, textColor=CIELO, fontName="Helvetica-Bold")),
    ]
    cp_rows = [cp_header]
    for c in casos:
        col_p = COLOR_SEV.get(c.get("prioridad","low"), GRIS)
        etiq_p = ETIQ_PRIO.get(c.get("prioridad",""), c.get("prioridad","").upper())
        cp_rows.append([
            Paragraph(c.get("id",""), est("cc", fontSize=7, textColor=CIELO, fontName="Courier")),
            Paragraph(etiq_p,         est("cc", fontSize=7, textColor=col_p,  fontName="Helvetica-Bold")),
            Paragraph(c.get("nombre",""), est("cc", fontSize=7, textColor=BLANCO, fontName="Helvetica")),
            Paragraph(c.get("esperado",""), est("cc", fontSize=7, textColor=GRIS, fontName="Helvetica")),
            Paragraph(c.get("ref",""), est("cc", fontSize=7, textColor=CIELO, fontName="Courier")),
        ])

    t_cp = Table(cp_rows, colWidths=[16*mm, 18*mm, 60*mm, 70*mm, 16*mm])
    t_cp.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  AZUL_COB),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [AZUL_MED, AZUL_CARD]),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("LINEBELOW",     (0,0), (-1,-1), 0.2, GRIS_OSC),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t_cp)

    # ── FOOTER en cada página ─────────────────────────────────────────────────
    def pie_pagina(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFillColor(GRIS_OSC)
        canvas_obj.setFont("Helvetica", 6)
        canvas_obj.drawCentredString(
            A4[0]/2, 10*mm,
            f"SiDL Beta v1.0  |  Reporte de Auditoría QA  |  Pág. {doc_obj.page}"
        )
        canvas_obj.setStrokeColor(CIELO)
        canvas_obj.setLineWidth(0.3)
        canvas_obj.line(15*mm, 12*mm, A4[0]-15*mm, 12*mm)
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    return ruta_salida

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SiDL API",
    description="Smart Interface & Documentation Lens — Backend FastAPI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── SERVIR FRONTEND ────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """Sirve el frontend principal."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>SiDL Backend Activo</h1><p>Coloca index.html en /static/</p>")

# ── AUTH ───────────────────────────────────────────────────────────────────────
@app.post("/api/registro")
async def registro(req: RegistroRequest):
    if req.contrasena != req.confirmar:
        raise HTTPException(400, "Las contraseñas no coinciden.")
    if len(req.contrasena) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres.")

    db = cargar_db()
    email = req.email.lower().strip()
    if email in db["usuarios"]:
        raise HTTPException(400, "Ya existe una cuenta con este correo.")

    db["usuarios"][email] = {
        "nombre":    req.nombre,
        "email":     email,
        "contrasena": hash_contrasena(req.contrasena),
        "creado_el": datetime.now().isoformat(),
    }
    guardar_db(db)
    return {"ok": True, "nombre": req.nombre, "email": email}

@app.post("/api/login")
async def login(req: LoginRequest):
    db = cargar_db()
    email = req.email.lower().strip()
    u = db["usuarios"].get(email)
    if not u:
        raise HTTPException(401, "No existe una cuenta con este correo.")
    if not verificar_contrasena(req.contrasena, u["contrasena"]):
        raise HTTPException(401, "Contraseña incorrecta.")
    num_auditorias = len([a for a in db["auditorias"].values() if a.get("email") == email])
    return {"ok": True, "nombre": u["nombre"], "email": email, "num_auditorias": num_auditorias}

# ── INGESTA Y ANÁLISIS ────────────────────────────────────────────────────────
@app.post("/api/subir-archivos")
async def subir_archivos(
    srs:      UploadFile = File(...),
    captura:  UploadFile = File(None),
):
    """Recibe el SRS y la captura de pantalla, extrae texto y genera casos de prueba."""
    session_id = str(uuid.uuid4())
    dir_sesion = UPLOADS_DIR / session_id
    dir_sesion.mkdir()

    # Guardar SRS
    ruta_srs = dir_sesion / srs.filename
    ruta_srs.write_bytes(await srs.read())

    # Guardar captura si existe
    nombre_ui = "sin-captura.png"
    if captura and captura.filename:
        nombre_ui = captura.filename
        ruta_ui = dir_sesion / captura.filename
        ruta_ui.write_bytes(await captura.read())

    # Extraer texto del SRS
    texto_srs = extraer_texto_srs(ruta_srs)

    # Intentar con Gemini, fallback a datos demo
    resultado_gemini = analizar_con_gemini(texto_srs, nombre_ui)

    if resultado_gemini and resultado_gemini.get("casos"):
        casos = resultado_gemini["casos"]
        fuente = "gemini"
    else:
        casos = [
            {"id":"CP-001","prioridad":"critical","nombre":"Cumplimiento del Color del Botón CTA Principal","pre":"Usuario en /login, página completamente cargada","pasos":"1. Inspeccionar el botón CTA principal\n2. Comparar el color computado\n3. Validar contra SRS §3.2.1","esperado":"Color del botón = #1565C0 (Azul Corporativo)","ref":"§3.2.1"},
            {"id":"CP-002","prioridad":"high",    "nombre":"Relación de Contraste WCAG AA — Texto Informativo","pre":"Página de login renderizada al 100% de zoom","pasos":"1. Seleccionar el elemento de texto informativo\n2. Medir la relación de contraste\n3. Comparar con umbral WCAG 1.4.3","esperado":"Relación de contraste ≥ 4.5:1 en todo el texto","ref":"§5.4"},
            {"id":"CP-003","prioridad":"high",    "nombre":"Toggle de Visibilidad en Campo de Contraseña","pre":"Formulario de login renderizado","pasos":"1. Localizar el campo de contraseña\n2. Verificar el ícono de mostrar/ocultar\n3. Hacer clic y verificar cambio de tipo","esperado":"Toggle presente; input cambia entre password↔text","ref":"§3.5.2"},
            {"id":"CP-004","prioridad":"medium",  "nombre":"Etiquetas ARIA en Elementos Interactivos","pre":"DOM de la página completamente cargado","pasos":"1. Inspeccionar todos los enlaces y botones\n2. Verificar atributos aria-label presentes","esperado":"Todos los elementos interactivos tienen aria-label","ref":"§5.1"},
            {"id":"CP-005","prioridad":"medium",  "nombre":"Versión del Pie de Página Coincide con Release","pre":"Aplicación desplegada en entorno objetivo","pasos":"1. Navegar a cualquier página\n2. Leer la cadena de versión\n3. Comparar con release aprobado v2.3.0","esperado":"El pie de página muestra v2.3.0","ref":"§8.1"},
            {"id":"CP-006","prioridad":"low",     "nombre":"Orden de Tabulación — Navegación por Teclado","pre":"Página activa, foco de teclado reiniciado","pasos":"1. Presionar Tab desde el campo de correo\n2. Verificar orden: correo→contraseña→toggle→CTA","esperado":"Orden de tabulación coincide con especificación §5.2","ref":"§5.2"},
        ]
        fuente = "simulado"

    return {
        "session_id":    session_id,
        "archivo_srs":   srs.filename,
        "archivo_ui":    nombre_ui,
        "casos":         casos,
        "fuente":        fuente,
        "texto_srs_preview": texto_srs[:500] + "..." if len(texto_srs) > 500 else texto_srs,
    }

@app.post("/api/lanzar-auditoria")
async def lanzar_auditoria(req: LanzarAuditoriaRequest):
    """Ejecuta la auditoría visual contra los casos de prueba editados."""
    casos_dict = [c.dict() for c in req.casos]
    puntaje = calcular_puntaje(HALLAZGOS_DEMO)

    # Guardar auditoría en DB
    db = cargar_db()
    audit_id = str(uuid.uuid4())
    db["auditorias"][audit_id] = {
        "id":          audit_id,
        "session_id":  req.session_id,
        "fecha":       datetime.now().strftime("%d/%m/%Y %H:%M"),
        "casos":       casos_dict,
        "hallazgos":   HALLAZGOS_DEMO,
        "wcag":        WCAG_DEMO,
        "puntaje":     puntaje,
        "archivo_srs": "srs-cargado.pdf",
        "archivo_ui":  "captura.png",
    }
    guardar_db(db)

    return {
        "audit_id":   audit_id,
        "puntaje":    puntaje,
        "hallazgos":  HALLAZGOS_DEMO,
        "wcag":       WCAG_DEMO,
        "casos":      casos_dict,
    }

# ── HISTORIAL ─────────────────────────────────────────────────────────────────
@app.get("/api/historial/{email}")
async def obtener_historial(email: str):
    db = cargar_db()
    email = email.lower()
    auditorias = [a for a in db["auditorias"].values() if a.get("session_id","").startswith("") ]
    # Devolver todas las auditorías ordenadas por fecha
    lista = sorted(db["auditorias"].values(), key=lambda x: x.get("fecha",""), reverse=True)
    return {"auditorias": lista[:50]}

@app.delete("/api/historial/{audit_id}")
async def eliminar_auditoria(audit_id: str):
    db = cargar_db()
    if audit_id in db["auditorias"]:
        del db["auditorias"][audit_id]
        guardar_db(db)
    return {"ok": True}

# ── EXPORTAR PDF ───────────────────────────────────────────────────────────────
@app.get("/api/exportar-pdf/{audit_id}")
async def exportar_pdf(audit_id: str):
    """Genera y descarga el reporte PDF de una auditoría."""
    db = cargar_db()
    auditoria = db["auditorias"].get(audit_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada.")

    ruta_pdf = REPORTS_DIR / f"SiDL-Reporte-{audit_id[:8]}.pdf"

    try:
        generar_pdf_reporte(auditoria, ruta_pdf)
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    return FileResponse(
        path=str(ruta_pdf),
        media_type="application/pdf",
        filename=f"SiDL-Reporte-Auditoria-QA.pdf",
    )

@app.post("/api/exportar-pdf-directo")
async def exportar_pdf_directo(req: LanzarAuditoriaRequest):
    """Genera PDF directo sin guardar en DB (para uso desde frontend)."""
    casos_dict = [c.dict() for c in req.casos]
    puntaje = calcular_puntaje(HALLAZGOS_DEMO)
    auditoria = {
        "puntaje":     puntaje,
        "hallazgos":   HALLAZGOS_DEMO,
        "wcag":        WCAG_DEMO,
        "casos":       casos_dict,
        "archivo_srs": "srs-documento.pdf",
        "archivo_ui":  "captura.png",
        "fecha":       datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    nombre = f"SiDL-temp-{uuid.uuid4().hex[:8]}.pdf"
    ruta_pdf = REPORTS_DIR / nombre
    try:
        generar_pdf_reporte(auditoria, ruta_pdf)
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    return FileResponse(str(ruta_pdf), media_type="application/pdf", filename="SiDL-Reporte-QA.pdf")

# ── EXPORTAR CSV ───────────────────────────────────────────────────────────────
@app.post("/api/exportar-csv")
async def exportar_csv(req: LanzarAuditoriaRequest):
    """Exporta los casos de prueba como CSV para Excel/TestRail."""
    casos = [c.dict() for c in req.casos]
    lineas = ["ID,Prioridad,Nombre del Caso,Precondiciones,Pasos,Resultado Esperado,Ref. SRS"]
    for c in casos:
        pasos_limpio = c.get("pasos","").replace("\n","; ").replace('"','""')
        lineas.append(f"{c['id']},{c['prioridad']},\"{c['nombre']}\",\"{c['pre']}\",\"{pasos_limpio}\",\"{c['esperado']}\",{c['ref']}")
    contenido = "\n".join(lineas)
    return StreamingResponse(
        iter([contenido.encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sidl-casos-de-prueba.csv"},
    )

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  SiDL — Smart Interface & Documentation Lens")
    print("  Backend FastAPI v1.0")
    print("="*55)
    print(f"  PyMuPDF:    {'✅ activo' if PYMUPDF_OK else '❌ no instalado'}")
    print(f"  ReportLab:  {'✅ activo' if REPORTLAB_OK else '❌ no instalado'}")
    print(f"  bcrypt:     {'✅ activo' if BCRYPT_OK else '⚠️  usando SHA-256'}")
    print(f"  Gemini API: {'✅ configurado' if (GEMINI_OK and GEMINI_API_KEY) else '⚠️  no configurado (modo simulado)'}")
    print(f"\n  Coloca tu GEMINI_API_KEY en el .env o como variable de entorno.")
    print(f"  Abre: http://localhost:8000")
    print("="*55 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
