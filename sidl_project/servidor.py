"""
SiDL — Smart Interface & Documentation Lens
Backend Python — Servidor HTTP completo sin dependencias externas
Arquitectura: http.server + módulos de análisis propios
Compatible: Python 3.8+

Endpoints disponibles:
  POST /api/analizar-srs      → Parsea el SRS y genera casos de prueba
  POST /api/ejecutar-auditoria → Ejecuta la auditoría visual multimodal
  POST /api/generar-pdf        → Genera el reporte PDF con reportlab
  POST /api/exportar-excel     → Genera el Excel de casos de prueba
  GET  /api/estado             → Estado del servidor y módulos disponibles
  GET  /                       → Sirve el frontend HTML
  GET  /static/*               → Archivos estáticos
"""

import json
import os
import sys
import time
import uuid
import hashlib
import re
import base64
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from io import BytesIO
from datetime import datetime

# ── Módulos disponibles ──────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# ── Directorio del proyecto ──────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_DIR = os.path.join(BASE_DIR, "reportes")
for d in (STATIC_DIR, UPLOAD_DIR, REPORT_DIR):
    os.makedirs(d, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS SRS (Simulación de LangChain + PyMuPDF + Gemini)
# ═══════════════════════════════════════════════════════════════════════
class AnalizadorSRS:
    """
    Simula el pipeline: PyMuPDF → LangChain → Gemini 1.5 Pro
    En producción real: fitz.open(pdf) → LangChain.DocumentLoader → genai.GenerativeModel
    """

    CLAUSULAS_CLAVE = {
        r"botón.*color|color.*botón|CTA.*color|color.*CTA|color corporativo": {
            "ref": "§3.2.1", "tipo": "visual", "componente": "Botón CTA"
        },
        r"contraste|contrast.*ratio|relación.*contraste": {
            "ref": "§5.4", "tipo": "accesibilidad", "componente": "Texto informativo"
        },
        r"visibilidad.*contraseña|contraseña.*toggle|show.*hide|mostrar.*ocultar": {
            "ref": "§3.5.2", "tipo": "usabilidad", "componente": "Campo de contraseña"
        },
        r"aria-label|aria_label|accesibilidad.*lector|lector.*pantalla": {
            "ref": "§5.1", "tipo": "accesibilidad", "componente": "Elementos interactivos"
        },
        r"versión.*footer|footer.*versión|pie.*página.*versión|version.*tag": {
            "ref": "§8.1", "tipo": "metadatos", "componente": "Pie de página"
        },
        r"tabulación|tab.*order|orden.*foco|keyboard.*nav": {
            "ref": "§5.2", "tipo": "accesibilidad", "componente": "Navegación por teclado"
        },
    }

    PLANTILLAS_CASOS = [
        {
            "id": "CP-001", "prioridad": "critical",
            "nombre": "Cumplimiento del Color del Botón CTA Principal",
            "pre": "Usuario en /login, página completamente cargada en entorno de pruebas",
            "pasos": "1. Navegar a la URL de la aplicación\n2. Abrir las herramientas de desarrollo del navegador\n3. Seleccionar el botón CTA principal\n4. Inspeccionar la propiedad CSS background-color\n5. Comparar con el valor especificado en SRS §3.2.1",
            "esperado": "El color del botón es #1565C0 (Azul Corporativo)",
            "ref": "§3.2.1"
        },
        {
            "id": "CP-002", "prioridad": "high",
            "nombre": "Relación de Contraste WCAG 2.1 AA — Texto Informativo",
            "pre": "Página de login renderizada al 100% de zoom en pantalla calibrada",
            "pasos": "1. Identificar todos los elementos de texto informativo\n2. Utilizar herramienta de análisis de contraste (Colour Contrast Analyser)\n3. Medir relación foreground/background\n4. Comparar con umbral mínimo WCAG 2.1 AA (1.4.3)",
            "esperado": "Relación de contraste ≥ 4.5:1 en todos los textos de body",
            "ref": "§5.4"
        },
        {
            "id": "CP-003", "prioridad": "high",
            "nombre": "Presencia del Toggle de Visibilidad en Campo de Contraseña",
            "pre": "Formulario de login renderizado, campo de contraseña visible en DOM",
            "pasos": "1. Localizar el campo input de contraseña\n2. Verificar la existencia del control show/hide adyacente\n3. Hacer clic en el toggle icon\n4. Verificar que el tipo de input cambia a 'text'\n5. Hacer clic nuevamente y verificar retorno a 'password'",
            "esperado": "Toggle presente y funcional; alterna entre password↔text",
            "ref": "§3.5.2"
        },
        {
            "id": "CP-004", "prioridad": "medium",
            "nombre": "Etiquetas ARIA en Todos los Elementos Interactivos",
            "pre": "DOM de la página completamente cargado, sin errores en consola",
            "pasos": "1. Abrir DevTools → pestaña Accessibility\n2. Inspeccionar cada botón, link e input\n3. Verificar presencia del atributo aria-label\n4. Ejecutar escaneo automatizado con axe-core o Lighthouse\n5. Revisar informe de accesibilidad generado",
            "esperado": "Todos los elementos interactivos tienen aria-label descriptivo",
            "ref": "§5.1"
        },
        {
            "id": "CP-005", "prioridad": "medium",
            "nombre": "Cadena de Versión en Pie de Página Coincide con Release Tag",
            "pre": "Aplicación desplegada en entorno de staging con release v2.3.0",
            "pasos": "1. Navegar a cualquier página de la aplicación\n2. Desplazarse al pie de página\n3. Leer la cadena de versión mostrada\n4. Comparar con el tag de release aprobado documentado en §8.1",
            "esperado": "Pie de página muestra exactamente 'v2.3.0'",
            "ref": "§8.1"
        },
        {
            "id": "CP-006", "prioridad": "low",
            "nombre": "Orden de Tabulación y Navegación por Teclado",
            "pre": "Página de login activa, sin foco inicial en ningún elemento",
            "pasos": "1. Posicionar cursor fuera del formulario\n2. Presionar Tab y registrar secuencia de foco\n3. Verificar orden: correo→contraseña→toggle→CTA→enlace recuperación\n4. Confirmar cumplimiento con WCAG 2.4.3 (Focus Order)\n5. Verificar que cada elemento tiene anillo de foco visible",
            "esperado": "Orden de tabulación coincide exactamente con especificación §5.2",
            "ref": "§5.2"
        },
    ]

    def parsear(self, contenido_texto: str, nombre_archivo: str) -> dict:
        """
        Simula: PyMuPDF.extract_text() → LangChain.TextSplitter → Gemini.extract_UVVs()
        En producción real:
            doc = fitz.open(stream=bytes_pdf, filetype='pdf')
            texto = ''.join([p.get_text() for p in doc])
            llm = genai.GenerativeModel('gemini-1.5-pro')
            respuesta = llm.generate_content(prompt_extraccion + texto)
        """
        log = []
        log.append(f"[PyMuPDF] Abriendo documento: {nombre_archivo}")
        time.sleep(0.1)
        log.append(f"[PyMuPDF] Extrayendo texto...")

        # Análisis real del texto si se proporcionó
        clausulas_detectadas = []
        if contenido_texto:
            for patron, info in self.CLAUSULAS_CLAVE.items():
                if re.search(patron, contenido_texto, re.IGNORECASE):
                    clausulas_detectadas.append(info["ref"])
                    log.append(f"[LangChain] Cláusula detectada: {info['ref']} — {info['componente']}")

        total_clausulas = max(len(clausulas_detectadas), 6)
        log.append(f"[LangChain] ✓ {total_clausulas} cláusulas verificables extraídas")
        log.append(f"[Gemini 1.5 Pro] Generando Unidades de Verificación Visual (UVV)...")
        log.append(f"[Gemini 1.5 Pro] ✓ {len(self.PLANTILLAS_CASOS)} casos de prueba estructurados")
        log.append(f"[SISTEMA] ✓ Pipeline completado. Listo para revisión humana.")

        return {
            "casos": self.PLANTILLAS_CASOS,
            "log": log,
            "clausulas_analizadas": total_clausulas,
            "secciones": 8,
            "nombre_archivo": nombre_archivo,
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════
# MOTOR DE AUDITORÍA VISUAL (Simulación de Gemini Vision API)
# ═══════════════════════════════════════════════════════════════════════
class AuditorVisual:
    """
    Simula: Gemini 1.5 Pro Vision analizando la captura de pantalla
    contra los casos de prueba generados del SRS.

    En producción real:
        model = genai.GenerativeModel('gemini-1.5-pro')
        imagen = genai.upload_file(path_imagen)
        respuesta = model.generate_content([prompt_auditoria, imagen])
        hallazgos = json.loads(respuesta.text)
    """

    HALLAZGOS_BASE = [
        {
            "id": "H-001", "severidad": "critical", "ref_caso": "CP-001",
            "titulo": "El Color del Botón CTA Viola la Especificación de Marca",
            "clausula": "§3.2.1 — El botón de acción primario debe usar el color corporativo #1565C0.",
            "descripcion": "El botón 'INICIAR SESIÓN' renderiza con background-color #e57373 (rojo). Esto viola directamente §3.2.1 y genera una señal visual de acción destructiva errónea para el usuario, aumentando la tasa de abandono del formulario en ~18% según estudios de UX (NNG).",
            "esperado": "background-color: #1565C0 (Azul Corporativo)",
            "obtenido": "background-color: #e57373 (Rojo — incorrecto)",
            "tecnicas": ["Análisis Semántico de Interfaz", "Extracción de Propiedades CSS", "Mapeo de Espacio de Color RGB"],
            "bbox": {"x": "8%", "y": "54%", "w": "84%", "h": "9%", "tipo": "error", "etiqueta": "H-001 COLOR INCORRECTO"}
        },
        {
            "id": "H-002", "severidad": "high", "ref_caso": "CP-002",
            "titulo": "Relación de Contraste Por Debajo del Umbral WCAG 2.1 AA",
            "clausula": "§5.4 — Todo texto informativo debe lograr contraste mínimo de 4.5:1 (WCAG 2.1 AA).",
            "descripcion": "La relación de contraste medida en el texto informativo (#b0b0b0 sobre #d0d0d0) es 1.4:1. El criterio WCAG 1.4.3 requiere ≥4.5:1. Esto hace el texto completamente inaccesible para usuarios con baja visión o daltonismo, violando la legislación de accesibilidad digital.",
            "esperado": "Relación de contraste ≥ 4.5:1",
            "obtenido": "Relación de contraste = 1.4:1 (FALLO CRÍTICO DE ACCESIBILIDAD)",
            "tecnicas": ["Algoritmo de Luminancia Relativa WCAG 2.1", "Evaluación Heurística Digital", "Matriz de Contraste Perceptual"],
            "bbox": {"x": "8%", "y": "65%", "w": "84%", "h": "8%", "tipo": "error", "etiqueta": "H-002 FALLO CONTRASTE"}
        },
        {
            "id": "H-003", "severidad": "high", "ref_caso": "CP-003",
            "titulo": "Control de Visibilidad de Contraseña Ausente en el DOM",
            "clausula": "§3.5.2 — El campo de contraseña debe incluir un control de mostrar/ocultar.",
            "descripcion": "El campo de contraseña se renderiza sin ningún control de visibilidad adyacente. Investigación UX (NNG) indica que esto incrementa la tasa de fallo de autenticación en ~23%. El elemento no está presente en el árbol DOM ni en forma de botón, ícono SVG, ni atributo de acción.",
            "esperado": "Botón con ícono de ojo (show/hide) presente y funcional",
            "obtenido": "Sin control toggle en el DOM — elemento completamente ausente",
            "tecnicas": ["Validación de Patrones UX", "Referencia Cruzada de Requisitos", "Análisis de Árbol DOM"],
            "bbox": {"x": "60%", "y": "42%", "w": "30%", "h": "9%", "tipo": "warn", "etiqueta": "H-003 TOGGLE FALTANTE"}
        },
        {
            "id": "H-004", "severidad": "medium", "ref_caso": "CP-004",
            "titulo": "Enlace de Recuperación de Contraseña Sin Etiqueta ARIA",
            "clausula": "§5.1 — Todos los elementos interactivos deben contener atributos aria-label descriptivos.",
            "descripcion": "El enlace '¿Olvidaste tu contraseña?' carece del atributo aria-label requerido. Los lectores de pantalla (NVDA, JAWS, VoiceOver) anunciarán solo el texto literal, incumpliendo WCAG 2.4.6 (Encabezados y Etiquetas, Nivel AA) y exponiendo al sistema a riesgos legales de accesibilidad.",
            "esperado": "aria-label='Recuperar contraseña — ir a página de restablecimiento'",
            "obtenido": "Atributo aria-label completamente ausente en el elemento",
            "tecnicas": ["Inspección del Árbol de Accesibilidad", "Escaneo ARIA Compliance", "Simulación de Lector de Pantalla"],
            "bbox": {"x": "8%", "y": "75%", "w": "70%", "h": "6%", "tipo": "warn", "etiqueta": "H-004 SIN ARIA"}
        },
        {
            "id": "H-005", "severidad": "low", "ref_caso": "CP-005",
            "titulo": "Cadena de Versión en Pie de Página Desactualizada",
            "clausula": "§8.1 — El pie de página debe mostrar la versión alineada con el tag de release actual.",
            "descripcion": "El pie de página muestra 'v2.1' mientras el tag de release aprobado y documentado en §8.1 es v2.3.0. Esta discrepancia genera confusión en ciclos de pruebas de regresión y puede invalidar evidencia de auditoría.",
            "esperado": "Versión mostrada: v2.3.0",
            "obtenido": "Versión mostrada: v2.1 (2 releases de retraso)",
            "tecnicas": ["Validación de Consistencia de Contenido", "Referencia Cruzada de Metadatos", "Comparación de Cadenas de Texto"],
            "bbox": {"x": "0%", "y": "90%", "w": "100%", "h": "8%", "tipo": "ok", "etiqueta": "H-005 VERSIÓN OBSOLETA"}
        },
    ]

    WCAG_RESULTADOS = [
        {"id": "1.4.3", "nombre": "Contraste (Mínimo)", "nivel": "AA", "estado": "falla", "nota": "#b0b0b0 sobre #d0d0d0 = 1.4:1 (requerido 4.5:1)"},
        {"id": "1.3.1", "nombre": "Información y Relaciones", "nivel": "A",  "estado": "pasa", "nota": "Etiquetas de formulario asociadas programáticamente."},
        {"id": "2.1.1", "nombre": "Teclado", "nivel": "A",  "estado": "aviso", "nota": "Control toggle no verificado — elemento ausente."},
        {"id": "2.4.3", "nombre": "Orden del Foco", "nivel": "A",  "estado": "pasa", "nota": "Anillo de foco visible en todos los campos del formulario."},
        {"id": "2.4.6", "nombre": "Encabezados y Etiquetas", "nivel": "AA", "estado": "falla", "nota": "Enlace de recuperación sin aria-label (WCAG Nivel AA)."},
        {"id": "4.1.2", "nombre": "Nombre, Rol, Valor", "nivel": "A",  "estado": "falla", "nota": "Botón CTA sin atributo role y sin estado ARIA."},
        {"id": "1.4.4", "nombre": "Redimensionar Texto", "nivel": "AA", "estado": "pasa", "nota": "Texto escala correctamente hasta 200% sin pérdida de funcionalidad."},
    ]

    def auditar(self, casos_prueba: list, nombre_imagen: str) -> dict:
        """
        Simula el análisis multimodal de Gemini 1.5 Pro Vision.
        En producción real con imagen real:
            model = genai.GenerativeModel('gemini-1.5-pro')
            prompt = self._construir_prompt(casos_prueba)
            img = PIL.Image.open(path_imagen)
            respuesta = model.generate_content([prompt, img])
            return self._parsear_respuesta(respuesta.text)
        """
        log = []
        log.append(f"[Motor Visual] Inicializando análisis multimodal...")
        log.append(f"[Gemini] Cargando imagen: {nombre_imagen}")
        log.append(f"[Gemini] ✓ Árbol de elementos UI detectados: 9 componentes")
        log.append(f"[Comparador] Referenciando {len(casos_prueba)} casos de prueba contra UI...")

        hallazgos_filtrados = []
        for h in self.HALLAZGOS_BASE:
            caso_vinculado = next((c for c in casos_prueba if c.get("id") == h["ref_caso"]), None)
            if caso_vinculado:
                h_copia = dict(h)
                h_copia["caso_nombre"] = caso_vinculado.get("nombre", "")
                hallazgos_filtrados.append(h_copia)
                log.append(f"[Comparador] ⚠ VIOLACIÓN detectada: {h['id']} — {h['clausula'][:60]}...")

        log.append(f"[Reporte] ✓ {len(hallazgos_filtrados)} hallazgos documentados con trazabilidad completa.")

        puntaje = self._calcular_puntaje(hallazgos_filtrados)

        return {
            "hallazgos": hallazgos_filtrados,
            "wcag": self.WCAG_RESULTADOS,
            "puntaje_qa": puntaje,
            "log": log,
            "timestamp": datetime.now().isoformat(),
            "nombre_imagen": nombre_imagen,
        }

    def _calcular_puntaje(self, hallazgos: list) -> int:
        penalizacion = {"critical": 15, "high": 10, "medium": 5, "low": 2}
        base = 100
        for h in hallazgos:
            base -= penalizacion.get(h.get("severidad", "low"), 0)
        return max(base, 0)


# ═══════════════════════════════════════════════════════════════════════
# GENERADOR DE PDF (reportlab real)
# ═══════════════════════════════════════════════════════════════════════
class GeneradorPDF:

    AZUL_OSC   = colors.HexColor("#050b14")
    AZUL_PANEL = colors.HexColor("#0c1829")
    AZUL_CARD  = colors.HexColor("#101f35")
    AZUL_COBA  = colors.HexColor("#0f4c8a")
    CIELO      = colors.HexColor("#38bdf8")
    VERDE      = colors.HexColor("#10b981")
    AMBAR      = colors.HexColor("#f59e0b")
    ROJO       = colors.HexColor("#ef4444")
    MORADO     = colors.HexColor("#a78bfa")
    BLANCO     = colors.white
    GRIS_TEXT  = colors.HexColor("#7ca3c4")
    GRIS_MUT   = colors.HexColor("#3d6484")

    SEV_COLORES = {
        "critical": colors.HexColor("#ef4444"),
        "high":     colors.HexColor("#f59e0b"),
        "medium":   colors.HexColor("#38bdf8"),
        "low":      colors.HexColor("#10b981"),
    }
    SEV_ETIQ = {
        "critical": "CRÍTICO", "high": "ALTO",
        "medium": "MEDIO",     "low": "BAJO"
    }

    def generar(self, datos: dict, ruta_salida: str) -> str:
        buffer = BytesIO()
        ancho, alto = A4
        c = canvas.Canvas(buffer, pagesize=A4)

        self._pagina_portada(c, datos, ancho, alto)
        c.showPage()
        self._pagina_hallazgos(c, datos, ancho, alto)
        c.showPage()
        self._pagina_wcag_casos(c, datos, ancho, alto)

        c.save()

        with open(ruta_salida, 'wb') as f:
            f.write(buffer.getvalue())

        return ruta_salida

    def _fondo_pagina(self, c, ancho, alto):
        c.setFillColor(self.AZUL_OSC)
        c.rect(0, 0, ancho, alto, fill=True, stroke=False)
        # Grid blueprint
        c.setStrokeColor(colors.HexColor("#38bdf8"))
        c.setLineWidth(0.15)
        c.setStrokeAlpha(0.06)
        paso = 20 * mm
        x = 0
        while x <= ancho:
            c.line(x, 0, x, alto)
            x += paso
        y = 0
        while y <= alto:
            c.line(0, y, ancho, y)
            y += paso
        c.setStrokeAlpha(1.0)

    def _borde_pagina(self, c, ancho, alto):
        c.setStrokeColor(self.CIELO)
        c.setLineWidth(0.5)
        margen = 8 * mm
        c.roundRect(margen, margen, ancho - 2*margen, alto - 2*margen, 3*mm, stroke=True, fill=False)

    def _pagina_portada(self, c, datos, ancho, alto):
        self._fondo_pagina(c, ancho, alto)
        self._borde_pagina(c, ancho, alto)

        # Banda superior azul
        c.setFillColor(self.AZUL_COBA)
        c.rect(8*mm, alto - 8*mm - 22*mm, ancho - 16*mm, 22*mm, fill=True, stroke=False)

        # Logo SiDL
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(ancho/2, alto - 8*mm - 14*mm, "SiDL")

        # Subtítulo
        c.setFillColor(self.BLANCO)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(ancho/2, alto - 38*mm, "Smart Interface & Documentation Lens")

        # Badge tipo
        c.setFillColor(self.CIELO)
        badge_w = 90*mm
        badge_x = (ancho - badge_w)/2
        c.roundRect(badge_x, alto - 48*mm, badge_w, 8*mm, 2*mm, fill=True, stroke=False)
        c.setFillColor(self.AZUL_OSC)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(ancho/2, alto - 43*mm, "REPORTE DE AUDITORÍA MULTIMODAL QA")

        # ─ Puntaje QA ─
        puntaje = datos.get("puntaje_qa", 0)
        col_puntaje = self.VERDE if puntaje >= 80 else (self.AMBAR if puntaje >= 55 else self.ROJO)
        radio = 18*mm
        cx, cy = ancho/2, alto - 80*mm
        c.setFillColor(self.AZUL_CARD)
        c.circle(cx, cy, radio + 3*mm, fill=True, stroke=False)
        c.setFillColor(col_puntaje)
        c.circle(cx, cy, radio, fill=True, stroke=False)
        c.setFillColor(self.AZUL_OSC)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(cx, cy - 4*mm, str(puntaje))
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(cx, cy - 9*mm, "PUNTAJE QA / 100")

        # ─ Metadatos del reporte ─
        margen_i = 18*mm
        y_meta = alto - 105*mm
        metas = [
            ("Documento SRS:", datos.get("nombre_srs", "N/A")),
            ("Captura de Pantalla:", datos.get("nombre_imagen", "N/A")),
            ("Fecha de Generación:", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            ("Motor de Análisis:", "Gemini 1.5 Pro + LangChain + PyMuPDF"),
            ("Versión SiDL:", "Beta v1.0"),
            ("Cláusulas Analizadas:", str(datos.get("clausulas_analizadas", 6))),
        ]
        for etq, val in metas:
            c.setFillColor(self.AZUL_CARD)
            c.roundRect(margen_i, y_meta - 3*mm, ancho - 2*margen_i, 6*mm, 1*mm, fill=True, stroke=False)
            c.setFillColor(self.CIELO)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(margen_i + 3*mm, y_meta + 0.5*mm, etq)
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica", 7)
            # Truncar si es muy largo
            val_str = str(val)[:60]
            c.drawString(margen_i + 52*mm, y_meta + 0.5*mm, val_str)
            y_meta -= 7.5*mm

        # ─ Resumen de severidades ─
        hallazgos = datos.get("hallazgos", [])
        conteos = {s: sum(1 for h in hallazgos if h.get("severidad")==s)
                   for s in ("critical","high","medium","low")}
        etiqsev = {"critical":"CRÍTICO","high":"ALTO","medium":"MEDIO","low":"BAJO"}
        y_sev = 42*mm
        caja_w = (ancho - 28*mm) / 4
        for i, (sev, cnt) in enumerate(conteos.items()):
            xb = 14*mm + i * caja_w
            col = self.SEV_COLORES[sev]
            c.setFillColor(self.AZUL_CARD)
            c.roundRect(xb, y_sev, caja_w - 3*mm, 18*mm, 2*mm, fill=True, stroke=False)
            c.setFillColor(col)
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(xb + (caja_w-3*mm)/2, y_sev + 10*mm, str(cnt))
            c.setFont("Helvetica-Bold", 5.5)
            c.drawCentredString(xb + (caja_w-3*mm)/2, y_sev + 5*mm, etiqsev[sev])

        # ─ Pie de portada ─
        c.setFillColor(self.GRIS_MUT)
        c.setFont("Helvetica", 6)
        c.drawCentredString(ancho/2, 20*mm, "Generado automáticamente por SiDL — Plataforma de Auditoría Multimodal QA")
        c.drawCentredString(ancho/2, 16*mm, "Powered by Gemini 1.5 Pro Vision  |  LangChain  |  PyMuPDF  |  reportlab")

    def _pagina_hallazgos(self, c, datos, ancho, alto):
        self._fondo_pagina(c, ancho, alto)
        self._borde_pagina(c, ancho, alto)

        # Encabezado de página
        c.setFillColor(self.AZUL_COBA)
        c.rect(8*mm, alto - 30*mm, ancho - 16*mm, 22*mm, fill=True, stroke=False)
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(13*mm, alto - 21*mm, "HALLAZGOS DETALLADOS — INSIDE THE LENS")
        hallazgos = datos.get("hallazgos", [])
        c.setFillColor(self.GRIS_TEXT)
        c.setFont("Helvetica", 7)
        c.drawRightString(ancho - 13*mm, alto - 21*mm, f"{len(hallazgos)} hallazgos detectados")

        # Número de página
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 6)
        c.drawRightString(ancho - 13*mm, alto - 26*mm, "Página 2 / 3")

        y = alto - 38*mm
        margen = 13*mm
        ancho_util = ancho - 2*margen

        for h in hallazgos:
            sev = h.get("severidad", "low")
            col = self.SEV_COLORES.get(sev, self.CIELO)
            etiq = self.SEV_ETIQ.get(sev, sev.upper())

            altura_bloque = 38*mm
            if y - altura_bloque < 18*mm:
                # Nueva página automática
                c.showPage()
                self._fondo_pagina(c, ancho, alto)
                self._borde_pagina(c, ancho, alto)
                c.setFillColor(self.AZUL_COBA)
                c.rect(8*mm, alto-30*mm, ancho-16*mm, 22*mm, fill=True, stroke=False)
                c.setFillColor(self.CIELO)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(13*mm, alto-21*mm, "HALLAZGOS — CONTINUACIÓN")
                y = alto - 38*mm

            # Encabezado del hallazgo
            c.setFillColor(self.AZUL_CARD)
            c.roundRect(margen, y - altura_bloque, ancho_util, altura_bloque, 2*mm, fill=True, stroke=False)

            # Barra de color por severidad
            c.setFillColor(col)
            c.roundRect(margen, y - altura_bloque, 16*mm, altura_bloque, 2*mm, fill=True, stroke=False)

            # Texto de severidad vertical
            c.saveState()
            c.setFillColor(self.AZUL_OSC)
            c.setFont("Helvetica-Bold", 5.5)
            c.translate(margen + 8*mm, y - altura_bloque/2)
            c.rotate(90)
            c.drawCentredString(0, 0, etiq)
            c.restoreState()

            # ID + Título
            c.setFillColor(self.CIELO)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(margen + 18*mm, y - 5*mm, f"[{h['id']}]")
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica-Bold", 8)
            titulo = h.get("titulo","")[:75]
            c.drawString(margen + 27*mm, y - 5*mm, titulo)

            # Cláusula
            c.setFillColor(colors.HexColor("#072a52"))
            c.roundRect(margen + 17*mm, y - 13*mm, ancho_util - 18*mm, 6.5*mm, 1*mm, fill=True, stroke=False)
            c.setFillColor(self.CIELO)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(margen + 19*mm, y - 9.5*mm, "CLÁUSULA:")
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica", 6)
            clausula = h.get("clausula","")[:95]
            c.drawString(margen + 39*mm, y - 9.5*mm, clausula)

            # Descripción (3 líneas máx)
            c.setFillColor(self.GRIS_TEXT)
            c.setFont("Helvetica", 6.5)
            desc = h.get("descripcion","")
            # Dividir en líneas
            palabras = desc.split()
            lineas, linea_actual = [], ""
            for p in palabras:
                test = linea_actual + (" " if linea_actual else "") + p
                if len(test) > 105:
                    lineas.append(linea_actual)
                    linea_actual = p
                    if len(lineas) >= 2: break
                else:
                    linea_actual = test
            if linea_actual and len(lineas) < 3:
                lineas.append(linea_actual)
            for i_l, l in enumerate(lineas[:2]):
                c.drawString(margen + 18*mm, y - 17*mm - i_l*4*mm, l)

            # Esperado / Obtenido
            y_eo = y - altura_bloque + 14*mm
            mitad = ancho_util/2 - 1*mm
            c.setFillColor(colors.HexColor("#0a1118"))
            c.roundRect(margen + 17*mm, y_eo - 4*mm, mitad - 17*mm, 7*mm, 1*mm, fill=True, stroke=False)
            c.setFillColor(self.VERDE)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(margen + 19*mm, y_eo - 0.5*mm, "ESPERADO:")
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica", 5.5)
            c.drawString(margen + 37*mm, y_eo - 0.5*mm, h.get("esperado","")[:45])

            c.setFillColor(colors.HexColor("#0a1118"))
            c.roundRect(margen + ancho_util/2 + 1*mm, y_eo - 4*mm, mitad - 18*mm, 7*mm, 1*mm, fill=True, stroke=False)
            c.setFillColor(self.ROJO)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(margen + ancho_util/2 + 3*mm, y_eo - 0.5*mm, "OBTENIDO:")
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica", 5.5)
            c.drawString(margen + ancho_util/2 + 21*mm, y_eo - 0.5*mm, h.get("obtenido","")[:45])

            # Técnicas
            c.setFillColor(self.MORADO)
            c.setFont("Helvetica-Oblique", 5.5)
            tecnicas_str = "Técnicas: " + " · ".join(h.get("tecnicas", []))
            c.drawString(margen + 18*mm, y_eo - 7.5*mm, tecnicas_str[:100])

            # Línea separadora
            c.setStrokeColor(colors.HexColor("#1e3a57"))
            c.setLineWidth(0.3)
            c.line(margen, y - altura_bloque - 2*mm, margen + ancho_util, y - altura_bloque - 2*mm)

            y -= (altura_bloque + 5*mm)

        # Pie de página
        c.setFillColor(self.GRIS_MUT)
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(ancho/2, 14*mm, "SiDL Beta v1.0  |  Reporte de Auditoría QA")

    def _pagina_wcag_casos(self, c, datos, ancho, alto):
        self._fondo_pagina(c, ancho, alto)
        self._borde_pagina(c, ancho, alto)

        # Encabezado
        c.setFillColor(self.AZUL_COBA)
        c.rect(8*mm, alto - 30*mm, ancho - 16*mm, 22*mm, fill=True, stroke=False)
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(13*mm, alto - 21*mm, "CUMPLIMIENTO WCAG 2.1 AA + CASOS DE PRUEBA")
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 6)
        c.drawRightString(ancho - 13*mm, alto - 26*mm, "Página 3 / 3")

        y = alto - 36*mm
        margen = 13*mm
        ancho_util = ancho - 2*margen

        # ─ Tabla WCAG ─
        c.setFillColor(self.AZUL_COBA)
        c.roundRect(margen, y - 7*mm, ancho_util, 7*mm, 1*mm, fill=True, stroke=False)
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(margen + 3*mm, y - 4*mm, "WCAG 2.1 — RESUMEN DE ACCESIBILIDAD")
        y -= 9*mm

        col_est = {"pasa": self.VERDE, "falla": self.ROJO, "aviso": self.AMBAR}
        for wcag in datos.get("wcag", []):
            col_bg = self.AZUL_CARD if datos.get("wcag",[]).index(wcag) % 2 == 0 else colors.HexColor("#152741")
            c.setFillColor(col_bg)
            c.roundRect(margen, y - 6*mm, ancho_util, 6*mm, 1*mm, fill=True, stroke=False)

            estado = wcag.get("estado","aviso")
            col_e = col_est.get(estado, self.CIELO)
            etiq_e = {"pasa":"PASA","falla":"FALLA","aviso":"AVISO"}.get(estado,"—")
            c.setFillColor(col_e)
            c.roundRect(margen + 2*mm, y - 5*mm, 14*mm, 4.5*mm, 0.5*mm, fill=True, stroke=False)
            c.setFillColor(self.AZUL_OSC)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawCentredString(margen + 9*mm, y - 2*mm, etiq_e)

            c.setFillColor(self.CIELO)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(margen + 18*mm, y - 2*mm, wcag.get("id",""))
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica", 6)
            c.drawString(margen + 32*mm, y - 2*mm, wcag.get("nombre",""))
            c.setFillColor(self.GRIS_TEXT)
            c.drawString(margen + 80*mm, y - 2*mm, wcag.get("nota","")[:60])

            c.setFillColor(self.MORADO)
            nivel_w = 9*mm
            c.roundRect(margen + ancho_util - nivel_w - 2*mm, y - 5*mm, nivel_w, 4.5*mm, 0.5*mm, fill=True, stroke=False)
            c.setFillColor(self.AZUL_OSC)
            c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(margen + ancho_util - nivel_w/2 - 2*mm, y - 2*mm, wcag.get("nivel",""))

            y -= 7*mm

        y -= 6*mm

        # ─ Tabla de Casos de Prueba ─
        c.setFillColor(self.AZUL_COBA)
        c.roundRect(margen, y - 7*mm, ancho_util, 7*mm, 1*mm, fill=True, stroke=False)
        c.setFillColor(self.CIELO)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(margen + 3*mm, y - 4*mm, f"CASOS DE PRUEBA GENERADOS ({len(datos.get('casos',[]))} total)")
        y -= 9*mm

        casos = datos.get("casos", [])
        etiq_prio = {"critical":"CRÍTICO","high":"ALTO","medium":"MEDIO","low":"BAJO"}
        col_prio  = {"critical": self.ROJO, "high": self.AMBAR, "medium": self.CIELO, "low": self.VERDE}

        for i, caso in enumerate(casos):
            if y < 22*mm:
                break
            col_bg = self.AZUL_CARD if i % 2 == 0 else colors.HexColor("#152741")
            c.setFillColor(col_bg)
            c.roundRect(margen, y - 7*mm, ancho_util, 7*mm, 1*mm, fill=True, stroke=False)

            prio = caso.get("prioridad","low")
            col_p = col_prio.get(prio, self.CIELO)
            c.setFillColor(col_p)
            c.roundRect(margen + 2*mm, y - 6*mm, 13*mm, 4.5*mm, 0.5*mm, fill=True, stroke=False)
            c.setFillColor(self.AZUL_OSC)
            c.setFont("Helvetica-Bold", 5)
            c.drawCentredString(margen + 8.5*mm, y - 3*mm, etiq_prio.get(prio, prio.upper()))

            c.setFillColor(self.CIELO)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(margen + 17*mm, y - 3*mm, caso.get("id",""))
            c.setFillColor(self.BLANCO)
            c.setFont("Helvetica", 6)
            c.drawString(margen + 28*mm, y - 3*mm, caso.get("nombre","")[:55])
            c.setFillColor(self.CIELO)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawRightString(margen + ancho_util - 2*mm, y - 3*mm, caso.get("ref",""))

            y -= 8*mm

        # Pie
        c.setFillColor(self.GRIS_MUT)
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(ancho/2, 14*mm, f"SiDL Beta v1.0  |  Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Auditoría Multimodal QA")


# ═══════════════════════════════════════════════════════════════════════
# GENERADOR DE EXCEL (openpyxl real)
# ═══════════════════════════════════════════════════════════════════════
class GeneradorExcel:

    AZUL      = "0F4C8A"
    CIELO     = "38BDF8"
    VERDE     = "10B981"
    AMBAR     = "F59E0B"
    ROJO      = "EF4444"
    OSC       = "050B14"
    CARD      = "101F35"
    TEXTO     = "F0F8FF"
    GRIS      = "7CA3C4"

    PRIO_COLORES = {
        "critical": "EF4444", "high": "F59E0B",
        "medium":   "38BDF8", "low":  "10B981"
    }
    PRIO_ETIQ = {
        "critical":"CRÍTICO","high":"ALTO",
        "medium":"MEDIO","low":"BAJO"
    }

    def generar(self, casos: list, hallazgos: list, ruta_salida: str) -> str:
        wb = openpyxl.Workbook()

        # ── Hoja 1: Casos de Prueba ──
        ws1 = wb.active
        ws1.title = "Casos de Prueba"
        self._configurar_hoja(ws1)
        self._hoja_casos(ws1, casos)

        # ── Hoja 2: Hallazgos ──
        ws2 = wb.create_sheet("Hallazgos de Auditoría")
        self._configurar_hoja(ws2)
        self._hoja_hallazgos(ws2, hallazgos)

        # ── Hoja 3: WCAG ──
        ws3 = wb.create_sheet("Cumplimiento WCAG")
        self._configurar_hoja(ws3)
        self._hoja_wcag(ws3)

        wb.save(ruta_salida)
        return ruta_salida

    def _configurar_hoja(self, ws):
        ws.sheet_view.showGridLines = False

    def _estilo_celda(self, celda, fondo=None, texto=None, negrita=False,
                      tam=10, alineacion="left", borde=False):
        if fondo:
            celda.fill = PatternFill(start_color=fondo, end_color=fondo, fill_type="solid")
        if texto:
            celda.font = Font(name="Calibri", color=texto, bold=negrita, size=tam)
        else:
            celda.font = Font(name="Calibri", bold=negrita, size=tam)
        alin_map = {"left": "left", "center": "center", "right": "right"}
        celda.alignment = Alignment(horizontal=alin_map.get(alineacion,"left"),
                                    vertical="center", wrap_text=True)
        if borde:
            bd = Side(style="thin", color="1E3A57")
            celda.border = Border(bottom=bd)

    def _hoja_casos(self, ws, casos):
        # Encabezado del reporte
        ws.merge_cells("A1:H1")
        ws["A1"] = "SiDL — CASOS DE PRUEBA GENERADOS POR IA"
        self._estilo_celda(ws["A1"], fondo=self.AZUL, texto=self.CIELO,
                           negrita=True, tam=13, alineacion="center")
        ws.row_dimensions[1].height = 28

        ws.merge_cells("A2:H2")
        ws["A2"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  SiDL Beta v1.0  |  Gemini 1.5 Pro + LangChain"
        self._estilo_celda(ws["A2"], fondo="0C1829", texto=self.GRIS, tam=8, alineacion="center")
        ws.row_dimensions[2].height = 16

        ws.row_dimensions[3].height = 8  # Espacio

        # Encabezados
        headers = ["ID", "PRIORIDAD", "NOMBRE DEL CASO", "PRECONDICIONES",
                   "PASOS DE PRUEBA", "RESULTADO ESPERADO", "REF. SRS", "ESTADO"]
        widths   = [10, 14, 40, 35, 45, 40, 10, 12]
        for i, (h, w) in enumerate(zip(headers, widths), 1):
            col_letra = chr(64 + i)
            celda = ws[f"{col_letra}4"]
            celda.value = h
            self._estilo_celda(celda, fondo="0F4C8A", texto=self.CIELO,
                               negrita=True, tam=9, alineacion="center")
            ws.column_dimensions[col_letra].width = w
        ws.row_dimensions[4].height = 18

        # Datos
        for fila_idx, caso in enumerate(casos, 5):
            prio  = caso.get("prioridad","low")
            etiq  = self.PRIO_ETIQ.get(prio, prio.upper())
            fondo = self.CARD if fila_idx % 2 == 0 else "152741"

            valores = [
                caso.get("id",""),
                etiq,
                caso.get("nombre",""),
                caso.get("pre",""),
                caso.get("pasos",""),
                caso.get("esperado",""),
                caso.get("ref",""),
                "PENDIENTE"
            ]
            for col_idx, val in enumerate(valores, 1):
                col_l = chr(64 + col_idx)
                celda = ws[f"{col_l}{fila_idx}"]
                celda.value = val
                color_texto = self.PRIO_COLORES.get(prio, self.CIELO) if col_idx == 2 else self.TEXTO
                self._estilo_celda(celda, fondo=fondo, texto=color_texto,
                                   negrita=(col_idx == 2), tam=9,
                                   alineacion="center" if col_idx in (1,2,7,8) else "left",
                                   borde=True)
            ws.row_dimensions[fila_idx].height = 36

        # Congelar encabezados
        ws.freeze_panes = "A5"

    def _hoja_hallazgos(self, ws, hallazgos):
        ws.merge_cells("A1:G1")
        ws["A1"] = "SiDL — HALLAZGOS DE AUDITORÍA — INSIDE THE LENS"
        self._estilo_celda(ws["A1"], fondo=self.AZUL, texto=self.CIELO,
                           negrita=True, tam=13, alineacion="center")
        ws.row_dimensions[1].height = 28

        headers = ["ID", "SEVERIDAD", "TÍTULO", "CLÁUSULA SRS",
                   "RESULTADO ESPERADO", "RESULTADO OBTENIDO", "TÉCNICAS"]
        widths   = [10, 14, 42, 48, 38, 38, 45]
        for i, (h, w) in enumerate(zip(headers, widths), 1):
            col_l = chr(64 + i)
            celda = ws[f"{col_l}2"]
            celda.value = h
            self._estilo_celda(celda, fondo="0F4C8A", texto=self.CIELO,
                               negrita=True, tam=9, alineacion="center")
            ws.column_dimensions[col_l].width = w
        ws.row_dimensions[2].height = 18

        sev_etiq = {"critical":"CRÍTICO","high":"ALTO","medium":"MEDIO","low":"BAJO"}
        for fila_idx, h in enumerate(hallazgos, 3):
            sev   = h.get("severidad","low")
            fondo = self.CARD if fila_idx % 2 == 0 else "152741"
            valores = [
                h.get("id",""),
                sev_etiq.get(sev, sev.upper()),
                h.get("titulo",""),
                h.get("clausula",""),
                h.get("esperado",""),
                h.get("obtenido",""),
                " · ".join(h.get("tecnicas",[]))
            ]
            for col_idx, val in enumerate(valores, 1):
                col_l = chr(64 + col_idx)
                celda = ws[f"{col_l}{fila_idx}"]
                celda.value = val
                c_texto = self.PRIO_COLORES.get(sev, self.CIELO) if col_idx == 2 else self.TEXTO
                self._estilo_celda(celda, fondo=fondo, texto=c_texto,
                                   negrita=(col_idx == 2), tam=9,
                                   alineacion="center" if col_idx in (1,2) else "left",
                                   borde=True)
            ws.row_dimensions[fila_idx].height = 40
        ws.freeze_panes = "A3"

    def _hoja_wcag(self, ws):
        wcag_datos = AuditorVisual.WCAG_RESULTADOS if hasattr(AuditorVisual,'WCAG_RESULTADOS') else []
        wcag_datos = [
            {"id": "1.4.3", "nombre": "Contraste (Mínimo)", "nivel": "AA", "estado": "falla", "nota": "#b0b0b0 sobre #d0d0d0 = 1.4:1 (req. 4.5:1)"},
            {"id": "1.3.1", "nombre": "Información y Relaciones", "nivel": "A",  "estado": "pasa", "nota": "Etiquetas de formulario asociadas programáticamente."},
            {"id": "2.1.1", "nombre": "Teclado", "nivel": "A",  "estado": "aviso", "nota": "Control toggle no verificado — elemento ausente en DOM."},
            {"id": "2.4.3", "nombre": "Orden del Foco", "nivel": "A",  "estado": "pasa", "nota": "Anillo de foco visible en todos los campos del formulario."},
            {"id": "2.4.6", "nombre": "Encabezados y Etiquetas", "nivel": "AA", "estado": "falla", "nota": "Enlace de recuperación sin aria-label (WCAG Nivel AA)."},
            {"id": "4.1.2", "nombre": "Nombre, Rol, Valor", "nivel": "A",  "estado": "falla", "nota": "Botón CTA sin atributo role y sin estado ARIA expandido."},
            {"id": "1.4.4", "nombre": "Redimensionar Texto", "nivel": "AA", "estado": "pasa", "nota": "Texto escala correctamente hasta 200%."},
        ]
        ws.merge_cells("A1:E1")
        ws["A1"] = "SiDL — CUMPLIMIENTO WCAG 2.1 AA — ACCESIBILIDAD"
        self._estilo_celda(ws["A1"], fondo=self.AZUL, texto=self.CIELO,
                           negrita=True, tam=13, alineacion="center")
        ws.row_dimensions[1].height = 28

        headers = ["CRITERIO", "NOMBRE", "NIVEL", "RESULTADO", "OBSERVACIÓN"]
        widths   = [14, 36, 12, 14, 55]
        for i, (h, w) in enumerate(zip(headers, widths), 1):
            col_l = chr(64 + i)
            celda = ws[f"{col_l}2"]
            celda.value = h
            self._estilo_celda(celda, fondo="0F4C8A", texto=self.CIELO,
                               negrita=True, tam=9, alineacion="center")
            ws.column_dimensions[col_l].width = w
        ws.row_dimensions[2].height = 18

        col_estado = {"pasa": self.VERDE, "falla": self.ROJO, "aviso": self.AMBAR}
        etiq_estado = {"pasa": "PASA", "falla": "FALLA", "aviso": "AVISO"}
        for fila_idx, w in enumerate(wcag_datos, 3):
            fondo = self.CARD if fila_idx % 2 == 0 else "152741"
            estado = w.get("estado","aviso")
            valores = [w.get("id",""), w.get("nombre",""), w.get("nivel",""),
                       etiq_estado.get(estado,"—"), w.get("nota","")]
            for col_idx, val in enumerate(valores, 1):
                col_l = chr(64 + col_idx)
                celda = ws[f"{col_l}{fila_idx}"]
                celda.value = val
                c_texto = col_estado.get(estado, self.TEXTO) if col_idx == 4 else self.TEXTO
                self._estilo_celda(celda, fondo=fondo, texto=c_texto,
                                   negrita=(col_idx == 4), tam=9,
                                   alineacion="center" if col_idx in (1,3,4) else "left",
                                   borde=True)
            ws.row_dimensions[fila_idx].height = 22
        ws.freeze_panes = "A3"


# ═══════════════════════════════════════════════════════════════════════
# SERVIDOR HTTP
# ═══════════════════════════════════════════════════════════════════════
class SiDLHandler(BaseHTTPRequestHandler):

    analizador = AnalizadorSRS()
    auditor    = AuditorVisual()
    gen_pdf    = GeneradorPDF() if REPORTLAB_OK else None
    gen_excel  = GeneradorExcel() if OPENPYXL_OK else None

    def log_message(self, format, *args):
        print(f"[SiDL API] {self.address_string()} — {format%args}")

    def _enviar_json(self, datos: dict, codigo: int = 200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(cuerpo))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _enviar_archivo(self, ruta: str, tipo_mime: str, nombre_descarga: str):
        with open(ruta, "rb") as f:
            datos = f.read()
        self.send_response(200)
        self.send_header("Content-Type", tipo_mime)
        self.send_header("Content-Length", len(datos))
        self.send_header("Content-Disposition", f'attachment; filename="{nombre_descarga}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(datos)

    def _leer_cuerpo_json(self) -> dict:
        longitud = int(self.headers.get("Content-Length", 0))
        if longitud == 0:
            return {}
        cuerpo = self.rfile.read(longitud)
        return json.loads(cuerpo.decode("utf-8"))

    def _leer_multipart(self) -> dict:
        """Parser simple de multipart/form-data"""
        content_type = self.headers.get("Content-Type", "")
        longitud = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(longitud)

        # Extraer boundary
        boundary_match = re.search(r"boundary=(.+)", content_type)
        if not boundary_match:
            return {}
        boundary = ("--" + boundary_match.group(1).strip()).encode()

        partes = cuerpo.split(boundary)
        resultado = {}

        for parte in partes[1:]:
            if parte.strip() in (b"", b"--", b"--\r\n"):
                continue
            # Separar headers del cuerpo de la parte
            if b"\r\n\r\n" in parte:
                headers_raw, contenido = parte.split(b"\r\n\r\n", 1)
                contenido = contenido.rstrip(b"\r\n--")
            else:
                continue

            headers_str = headers_raw.decode("utf-8", errors="ignore")
            # Nombre del campo
            nombre_match = re.search(r'name="([^"]+)"', headers_str)
            if not nombre_match:
                continue
            nombre_campo = nombre_match.group(1)

            # Nombre del archivo (si es un archivo)
            archivo_match = re.search(r'filename="([^"]+)"', headers_str)
            if archivo_match:
                resultado[nombre_campo] = {
                    "filename": archivo_match.group(1),
                    "content":  contenido
                }
            else:
                resultado[nombre_campo] = contenido.decode("utf-8", errors="ignore")

        return resultado

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        ruta = urlparse(self.path).path

        if ruta == "/" or ruta == "/index.html":
            ruta_html = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(ruta_html):
                with open(ruta_html, "rb") as f:
                    contenido = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(contenido))
                self.end_headers()
                self.wfile.write(contenido)
            else:
                self._enviar_json({"error": "Frontend no encontrado. Coloca el HTML en static/index.html"}, 404)

        elif ruta == "/api/estado":
            self._enviar_json({
                "estado": "activo",
                "version": "SiDL Beta v1.0",
                "modulos": {
                    "reportlab": REPORTLAB_OK,
                    "openpyxl":  OPENPYXL_OK,
                    "PyMuPDF":   False,  # requiere conexión a internet
                    "gemini":    False,  # requiere API key
                },
                "modo": "simulacion_completa",
                "descripcion": "Backend Python activo. Simulación de Gemini 1.5 Pro + LangChain + PyMuPDF habilitada.",
                "timestamp": datetime.now().isoformat()
            })

        elif ruta.startswith("/static/"):
            nombre = ruta[8:]
            ruta_archivo = os.path.join(STATIC_DIR, nombre)
            if os.path.exists(ruta_archivo) and os.path.isfile(ruta_archivo):
                tipo, _ = mimetypes.guess_type(ruta_archivo)
                with open(ruta_archivo, "rb") as f:
                    cont = f.read()
                self.send_response(200)
                self.send_header("Content-Type", tipo or "application/octet-stream")
                self.send_header("Content-Length", len(cont))
                self.end_headers()
                self.wfile.write(cont)
            else:
                self._enviar_json({"error": "Archivo no encontrado"}, 404)

        else:
            self._enviar_json({"error": "Ruta no encontrada"}, 404)

    def do_POST(self):
        ruta = urlparse(self.path).path

        # ── POST /api/analizar-srs ──────────────────────────────────────
        if ruta == "/api/analizar-srs":
            try:
                content_type = self.headers.get("Content-Type","")
                nombre_archivo = "documento.pdf"
                texto_contenido = ""

                if "multipart" in content_type:
                    partes = self._leer_multipart()
                    if "srs" in partes and isinstance(partes["srs"], dict):
                        nombre_archivo = partes["srs"]["filename"]
                        # Intentar leer como texto
                        try:
                            texto_contenido = partes["srs"]["content"].decode("utf-8", errors="ignore")
                        except:
                            texto_contenido = ""
                        # Guardar archivo subido
                        ruta_guardado = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{nombre_archivo}")
                        with open(ruta_guardado, "wb") as f:
                            f.write(partes["srs"]["content"])
                else:
                    datos = self._leer_cuerpo_json()
                    nombre_archivo = datos.get("nombre", "documento.pdf")

                resultado = self.analizador.parsear(texto_contenido, nombre_archivo)
                self._enviar_json({"ok": True, "resultado": resultado})

            except Exception as e:
                self._enviar_json({"ok": False, "error": str(e)}, 500)

        # ── POST /api/ejecutar-auditoria ────────────────────────────────
        elif ruta == "/api/ejecutar-auditoria":
            try:
                content_type = self.headers.get("Content-Type","")
                nombre_imagen = "captura.png"
                casos = []

                if "multipart" in content_type:
                    partes = self._leer_multipart()
                    if "imagen" in partes and isinstance(partes["imagen"], dict):
                        nombre_imagen = partes["imagen"]["filename"]
                        ruta_img = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{nombre_imagen}")
                        with open(ruta_img, "wb") as f:
                            f.write(partes["imagen"]["content"])
                    if "casos" in partes:
                        try:
                            casos = json.loads(partes["casos"])
                        except:
                            casos = self.analizador.PLANTILLAS_CASOS
                else:
                    datos = self._leer_cuerpo_json()
                    nombre_imagen = datos.get("nombre_imagen", "captura.png")
                    casos = datos.get("casos", self.analizador.PLANTILLAS_CASOS)

                resultado = self.auditor.auditar(casos, nombre_imagen)
                self._enviar_json({"ok": True, "resultado": resultado})

            except Exception as e:
                self._enviar_json({"ok": False, "error": str(e)}, 500)

        # ── POST /api/generar-pdf ───────────────────────────────────────
        elif ruta == "/api/generar-pdf":
            if not self.gen_pdf:
                self._enviar_json({"error": "reportlab no disponible"}, 503)
                return
            try:
                datos = self._leer_cuerpo_json()
                nombre_archivo = f"SiDL-Reporte-{uuid.uuid4().hex[:8]}.pdf"
                ruta_pdf = os.path.join(REPORT_DIR, nombre_archivo)
                self.gen_pdf.generar(datos, ruta_pdf)
                self._enviar_archivo(ruta_pdf, "application/pdf", "SiDL-Reporte-Auditoria-QA.pdf")
            except Exception as e:
                self._enviar_json({"error": str(e)}, 500)

        # ── POST /api/exportar-excel ────────────────────────────────────
        elif ruta == "/api/exportar-excel":
            if not self.gen_excel:
                self._enviar_json({"error": "openpyxl no disponible"}, 503)
                return
            try:
                datos = self._leer_cuerpo_json()
                casos = datos.get("casos", self.analizador.PLANTILLAS_CASOS)
                hallazgos = datos.get("hallazgos", self.auditor.HALLAZGOS_BASE)
                nombre_archivo = f"SiDL-CasosPrueba-{uuid.uuid4().hex[:8]}.xlsx"
                ruta_xlsx = os.path.join(REPORT_DIR, nombre_archivo)
                self.gen_excel.generar(casos, hallazgos, ruta_xlsx)
                self._enviar_archivo(ruta_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "SiDL-CasosPrueba.xlsx")
            except Exception as e:
                self._enviar_json({"error": str(e)}, 500)

        else:
            self._enviar_json({"error": "Endpoint no encontrado"}, 404)


# ═══════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    PUERTO = int(os.environ.get("SIDL_PORT", 8000))
    servidor = HTTPServer(("0.0.0.0", PUERTO), SiDLHandler)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║         SiDL — Smart Interface & Documentation Lens     ║
║              Backend Python — v1.0 Beta                 ║
╠══════════════════════════════════════════════════════════╣
║  Servidor:  http://localhost:{PUERTO}                       ║
║  Frontend:  http://localhost:{PUERTO}/                      ║
╠══════════════════════════════════════════════════════════╣
║  ENDPOINTS:                                             ║
║  GET  /api/estado             → Estado del servidor     ║
║  POST /api/analizar-srs       → Parsear SRS (upload)   ║
║  POST /api/ejecutar-auditoria → Auditoría visual        ║
║  POST /api/generar-pdf        → Reporte PDF             ║
║  POST /api/exportar-excel     → Casos de prueba XLSX    ║
╠══════════════════════════════════════════════════════════╣
║  Módulos: reportlab={REPORTLAB_OK!s:<5}  openpyxl={OPENPYXL_OK!s:<5}       ║
║  Modo: Simulación completa de Gemini + LangChain        ║
╚══════════════════════════════════════════════════════════╝
    """)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[SiDL] Servidor detenido.")
        servidor.server_close()
