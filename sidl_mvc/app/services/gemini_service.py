"""
SERVICE — Gemini AI Service
Integración real con Gemini 1.5 Pro para:
1. Generar casos de prueba a partir del texto SRS
2. Auditar visualmente la captura de pantalla contra los casos de prueba
3. Calcular puntaje QA y resultados WCAG

Para activar: configura GEMINI_API_KEY en el archivo .env
"""

import json
import re
import base64
from pathlib import Path
from typing import Optional

try:
    import google.generativeai as genai
    GEMINI_OK = True
except ImportError:
    GEMINI_OK = False

from app.services.config_service import GEMINI_API_KEY

if GEMINI_OK and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ─── Prompt para generar Casos de Prueba desde SRS ───────────────────────────
PROMPT_CASOS = """
Eres un experto en QA con 15 años de experiencia. Analiza el siguiente documento SRS
y genera exactamente 6 casos de prueba detallados en formato JSON.

DOCUMENTO SRS:
{texto_srs}

INSTRUCCIONES:
- Extrae los requisitos funcionales y de interfaz más importantes
- Crea casos de prueba con pasos claros y verificables
- Asigna prioridad real según el impacto del requisito
- Vincula cada caso al párrafo del SRS que lo origina

Responde ÚNICAMENTE con JSON válido, sin markdown, sin explicaciones:
{{
  "casos": [
    {{
      "id": "CP-001",
      "prioridad": "critical",
      "nombre": "Nombre descriptivo del caso de prueba",
      "pre": "Precondiciones necesarias antes de ejecutar",
      "pasos": "1. Paso uno\\n2. Paso dos\\n3. Paso tres",
      "esperado": "Resultado esperado observable y verificable",
      "ref": "§X.X"
    }}
  ]
}}

Prioridades válidas: critical, high, medium, low
"""

# ─── Prompt para Auditoría Visual real ───────────────────────────────────────
PROMPT_AUDITORIA = """
Eres un auditor QA experto en accesibilidad y diseño de interfaces. Analiza esta captura
de pantalla de una interfaz de usuario y compárala con los siguientes casos de prueba y
requisitos del SRS.

CASOS DE PRUEBA A VERIFICAR:
{casos_json}

EXTRACTO DEL SRS:
{texto_srs}

INSTRUCCIONES:
- Observa cada elemento visual en la imagen
- Verifica si cumple los requisitos del SRS y los criterios de los casos de prueba
- Detecta TODOS los problemas reales visibles (colores, contraste, elementos faltantes, texto, versiones)
- Para cada hallazgo, calcula con precisión qué parte de la pantalla está afectada
- Analiza el cumplimiento WCAG 2.1 AA

Responde ÚNICAMENTE con JSON válido:
{{
  "hallazgos": [
    {{
      "id": "H-001",
      "severidad": "critical",
      "refCaso": "CP-001",
      "titulo": "Título claro del problema detectado",
      "clausula": "§X.X — Texto exacto del requisito violado",
      "desc": "Descripción técnica detallada del problema y su impacto",
      "esperado": "Valor o comportamiento esperado según el SRS",
      "obtenido": "Valor o comportamiento real observado en la imagen",
      "tecnicas": ["Técnica 1", "Técnica 2", "Técnica 3"],
      "bbox": {{
        "x": "10%", "y": "50%", "w": "80%", "h": "10%",
        "tipo": "error",
        "etiqueta": "H-001 DESCRIPCIÓN"
      }}
    }}
  ],
  "wcag": [
    {{
      "id": "1.4.3",
      "nombre": "Contraste (Mínimo)",
      "nivel": "AA",
      "estado": "pass",
      "nota": "Descripción del resultado observado"
    }}
  ],
  "puntaje": 75,
  "resumen": "Resumen ejecutivo de la auditoría"
}}

Criterios WCAG a evaluar: 1.4.3, 1.3.1, 2.1.1, 2.4.3, 2.4.6, 4.1.2, 1.4.4
Estados válidos: pass, fail, warn
Severidades: critical, high, medium, low
Tipos de bbox: error (rojo), warn (amarillo), ok (verde)
"""


def _limpiar_json(texto: str) -> str:
    """Elimina bloques markdown y extrae solo el JSON."""
    texto = texto.strip()
    if "```" in texto:
        partes = texto.split("```")
        for p in partes:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                return p
    return texto


def generar_casos_desde_srs(texto_srs: str) -> dict:
    """
    Llama a Gemini para generar casos de prueba reales desde el texto del SRS.
    Retorna {"casos": [...], "fuente": "gemini"|"fallback"}
    """
    if not (GEMINI_OK and GEMINI_API_KEY):
        return {"casos": _casos_fallback(), "fuente": "fallback"}

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = PROMPT_CASOS.format(texto_srs=texto_srs[:5000])
        response = model.generate_content(prompt)
        texto = _limpiar_json(response.text)
        data = json.loads(texto)
        casos = data.get("casos", [])
        if not casos:
            raise ValueError("Gemini retornó lista de casos vacía")
        print(f"✅  Gemini generó {len(casos)} casos de prueba desde el SRS.")
        return {"casos": casos, "fuente": "gemini"}
    except Exception as e:
        print(f"⚠️  Error Gemini (casos): {e} — usando fallback.")
        return {"casos": _casos_fallback(), "fuente": "fallback"}


def auditar_con_vision(texto_srs: str, ruta_imagen: Optional[str], casos: list) -> dict:
    """
    Usa Gemini Vision para auditar la imagen real contra los casos de prueba.
    Si no hay imagen o no está Gemini configurado, usa análisis fallback.
    """
    if not (GEMINI_OK and GEMINI_API_KEY):
        return _resultado_fallback(casos)

    if not ruta_imagen or not Path(ruta_imagen).exists():
        print("⚠️  Sin imagen para analizar — usando fallback de auditoría.")
        return _resultado_fallback(casos)

    try:
        # Leer imagen y convertir a base64
        imagen_bytes = Path(ruta_imagen).read_bytes()
        ext = Path(ruta_imagen).suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}
        mime = mime_map.get(ext, "image/png")

        model = genai.GenerativeModel("gemini-1.5-pro")
        casos_json = json.dumps(casos[:6], ensure_ascii=False, indent=2)
        prompt = PROMPT_AUDITORIA.format(
            casos_json=casos_json,
            texto_srs=texto_srs[:3000]
        )

        response = model.generate_content([
            {"mime_type": mime, "data": imagen_bytes},
            prompt
        ])

        texto = _limpiar_json(response.text)
        data = json.loads(texto)

        hallazgos = data.get("hallazgos", [])
        wcag      = data.get("wcag", _wcag_default())
        puntaje   = data.get("puntaje", _calcular_puntaje(hallazgos))

        print(f"✅  Gemini Vision detectó {len(hallazgos)} hallazgos. Puntaje: {puntaje}/100")
        return {"hallazgos": hallazgos, "wcag": wcag, "puntaje": puntaje, "fuente": "gemini"}

    except Exception as e:
        print(f"⚠️  Error Gemini Vision: {e} — usando fallback.")
        return _resultado_fallback(casos)


def _calcular_puntaje(hallazgos: list) -> int:
    pen = {"critical": 15, "high": 10, "medium": 5, "low": 2}
    total = sum(pen.get(h.get("severidad", "low"), 0) for h in hallazgos)
    return max(0, min(100, 100 - total))


def _wcag_default():
    return [
        {"id": "1.4.3", "nombre": "Contraste (Mínimo)",       "nivel": "AA", "estado": "warn", "nota": "Pendiente de análisis visual."},
        {"id": "1.3.1", "nombre": "Información y Relaciones", "nivel": "A",  "estado": "warn", "nota": "Pendiente de análisis."},
        {"id": "2.1.1", "nombre": "Teclado",                  "nivel": "A",  "estado": "warn", "nota": "Pendiente de análisis."},
        {"id": "2.4.3", "nombre": "Orden del Foco",           "nivel": "A",  "estado": "warn", "nota": "Pendiente de análisis."},
        {"id": "2.4.6", "nombre": "Encabezados y Etiquetas",  "nivel": "AA", "estado": "warn", "nota": "Pendiente de análisis."},
        {"id": "4.1.2", "nombre": "Nombre, Rol, Valor",       "nivel": "A",  "estado": "warn", "nota": "Pendiente de análisis."},
        {"id": "1.4.4", "nombre": "Redimensionar Texto",      "nivel": "AA", "estado": "warn", "nota": "Pendiente de análisis."},
    ]


def _casos_fallback() -> list:
    return [
        {"id":"CP-001","prioridad":"critical","nombre":"Verificar Colores y Contraste de Botón Principal","pre":"Página completamente cargada","pasos":"1. Inspeccionar el botón CTA\n2. Comparar color computado con el SRS\n3. Medir relación de contraste","esperado":"Color y contraste cumplen especificación del SRS","ref":"§—"},
        {"id":"CP-002","prioridad":"high",    "nombre":"Verificar Contraste de Texto WCAG 2.1 AA","pre":"Página renderizada al 100%","pasos":"1. Identificar todos los textos visibles\n2. Medir relación de contraste de cada uno","esperado":"Todos los textos con contraste ≥ 4.5:1","ref":"§—"},
        {"id":"CP-003","prioridad":"high",    "nombre":"Verificar Presencia de Todos los Elementos Requeridos","pre":"Formulario completamente cargado","pasos":"1. Comparar elementos visibles con lista del SRS\n2. Verificar funcionalidad de cada elemento","esperado":"Todos los elementos del SRS presentes y funcionales","ref":"§—"},
        {"id":"CP-004","prioridad":"medium",  "nombre":"Verificar Etiquetas ARIA en Elementos Interactivos","pre":"DOM completamente cargado","pasos":"1. Inspeccionar atributos aria-label\n2. Verificar roles ARIA correctos","esperado":"Todos los elementos interactivos con aria-label","ref":"§—"},
        {"id":"CP-005","prioridad":"medium",  "nombre":"Verificar Consistencia de Versión y Metadatos","pre":"Aplicación en entorno objetivo","pasos":"1. Verificar versión en pie de página\n2. Comparar con release documentado","esperado":"Versión coincide con release aprobado","ref":"§—"},
        {"id":"CP-006","prioridad":"low",     "nombre":"Verificar Navegación por Teclado","pre":"Página activa, sin interacción previa","pasos":"1. Navegar con Tab por todos los elementos\n2. Verificar orden lógico de foco","esperado":"Orden de tabulación correcto y visible","ref":"§—"},
    ]


def _resultado_fallback(casos: list) -> dict:
    """Genera hallazgos demo cuando Gemini no está disponible."""
    hallazgos = [
        {"id":"H-001","severidad":"critical","refCaso":casos[0]["id"] if casos else "CP-001",
         "titulo":"[DEMO] Verificar: Color del Elemento Principal",
         "clausula":"Requisito de color/marca del SRS",
         "desc":"ACTIVA GEMINI para obtener análisis real. Este es un hallazgo de demostración.",
         "esperado":"Color especificado en el SRS","obtenido":"Color detectado en la imagen",
         "tecnicas":["Análisis de Color CSS","Mapeo de Espacio de Color"],
         "bbox":{"x":"8%","y":"50%","w":"84%","h":"10%","tipo":"error","etiqueta":"H-001 DEMO"}},
        {"id":"H-002","severidad":"high","refCaso":casos[1]["id"] if len(casos)>1 else "CP-002",
         "titulo":"[DEMO] Verificar: Contraste de Texto",
         "clausula":"Requisito WCAG 1.4.3 — Contraste mínimo 4.5:1",
         "desc":"ACTIVA GEMINI para análisis real de contraste con valores exactos.",
         "esperado":"Contraste ≥ 4.5:1","obtenido":"Valor pendiente de análisis real",
         "tecnicas":["Algoritmo de Luminancia WCAG 2.1"],
         "bbox":{"x":"8%","y":"62%","w":"84%","h":"8%","tipo":"warn","etiqueta":"H-002 DEMO"}},
    ]
    puntaje = _calcular_puntaje(hallazgos)
    return {"hallazgos": hallazgos, "wcag": _wcag_default(), "puntaje": puntaje, "fuente": "fallback"}
