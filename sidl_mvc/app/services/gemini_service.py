"""
SERVICE — Cloud AI Service (Groq)
Integración gratuita ultrarrápida utilizando modelos Llama 3 alojados en Groq.
"""

import json
import re
import base64
import requests
import os
import io
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from PIL import Image

# Cargar variables de entorno
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── Prompt para generar Casos de Prueba desde SRS ───────────────────────────
PROMPT_CASOS = """
Eres un experto en QA con 15 años de experiencia. Analiza el siguiente documento SRS.

DOCUMENTO SRS:
{texto_srs}

INSTRUCCIONES:
1. Extrae SOLAMENTE los requisitos funcionales, reglas de negocio y de interfaz. Ignora introducciones, índices y relleno.
2. Crea exactamente 6 casos de prueba con pasos claros y verificables.
3. Asigna prioridad (critical, high, medium, low).

Responde ÚNICAMENTE con JSON válido, sin markdown:
{{
  "requisitos_extraidos": "Escribe aquí una lista limpia (con saltos de línea \\n) SOLO con los requisitos explícitos que encontraste en el documento. Esto se mostrará en el visor de auditoría.",
  "casos": [
    {{
      "id": "CP-001",
      "prioridad": "critical",
      "nombre": "Nombre del caso",
      "pre": "Precondiciones",
      "pasos": "1. Paso uno\\n2. Paso dos",
      "esperado": "Resultado esperado",
      "ref": "§X.X"
    }}
  ]
}}
"""

# ─── Prompt para Auditoría Visual real ───────────────────────────────────────
PROMPT_AUDITORIA = """
Actúa como un script automatizado de QA. Ejecuta los Casos de Prueba sobre la imagen.

CASOS DE PRUEBA:
{casos_json}

REGLAS DE EVALUACIÓN:
1. Si la imagen NO corresponde al sistema o es irrelevante, falla TODOS los casos.
2. Si el elemento exigido por un caso NO ESTÁ, es un defecto crítico.
3. Evalúa estrictamente colores, textos y diseño.

REGLAS DE FORMATO (CRÍTICO):
1. Responde SOLO con JSON válido. Ni una palabra más.
2. PROHIBIDO usar comillas dobles dentro de los valores de texto. Si necesitas citar algo, usa comillas simples ('texto').
3. No uses markdown (```json).
4. El campo "refCaso" debe ser el ID del caso (ej. CP-001).

FORMATO JSON A SEGUIR:
{{
  "hallazgos": [
    {{
      "id": "H-001",
      "severidad": "critical",
      "refCaso": "CP-001",
      "titulo": "Elemento faltante o distinto",
      "clausula": "Ref del caso",
      "desc": "El caso pedia X pero se obtuvo Y",
      "esperado": "Lo exigido",
      "obtenido": "Lo de la imagen",
      "tecnicas": ["Inspeccion"],
      "bbox": {{"x": "10%", "y": "10%", "w": "80%", "h": "80%", "tipo": "error", "etiqueta": "DEFECTO"}}
    }}
  ],
  "wcag": [
    {{"id": "1.4.3", "nombre": "Contraste", "nivel": "AA", "estado": "fail", "nota": "Evaluado"}}
  ],
  "puntaje": 20,
  "resumen": "Resumen sin comillas dobles."
}}
"""

def _limpiar_json(texto: str) -> str:
    match = re.search(r'\{.*\}|\[.*\]', texto.strip(), re.DOTALL)
    return match.group(0) if match else texto.strip()

def generar_casos_desde_srs(texto_srs: str) -> dict:
    if not GROQ_API_KEY:
        return {"casos": _casos_fallback(), "fuente": "fallback"}

    try:
        prompt = PROMPT_CASOS.format(texto_srs=texto_srs[:8000])
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = json.loads(_limpiar_json(response.json()["choices"][0]["message"]["content"]))
        casos = data.get("casos", [])
        requisitos = data.get("requisitos_extraidos", "No se pudieron extraer los requisitos.")
        
        print(f"✅ Groq generó {len(casos)} casos y extrajo los requisitos limpios.")
        return {"casos": casos, "requisitos_extraidos": requisitos, "fuente": "groq-llama3.1"}
        
    except Exception as e:
        print(f"⚠️ Error Groq (casos): {e}")
        return {"casos": _casos_fallback(), "requisitos_extraidos": "Error de conexión.", "fuente": "fallback"}

def auditar_con_vision(texto_srs: str, ruta_imagen: Optional[str], casos: list) -> dict:
    if not GROQ_API_KEY or not ruta_imagen or not Path(ruta_imagen).exists():
        return _resultado_fallback(casos)

    try:
        # COMPRESIÓN DE IMAGEN PARA EVITAR RECHAZO DE GROQ
        img = Image.open(ruta_imagen)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((800, 800)) # Bajamos un poco más la resolución para estar seguros
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)
        img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        casos_json = json.dumps(casos[:6], ensure_ascii=False)
        prompt = PROMPT_AUDITORIA.format(casos_json=casos_json)

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }],
            # Quitamos la temperatura que a veces causa bug en Groq Vision y agregamos max_tokens
            "max_tokens": 1024 
        }

        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=40)
        
        # SI FALLA, QUE NOS IMPRIMA EL MOTIVO EXACTO EN LA TERMINAL
        if not response.ok:
            print(f"\n❌ GROQ RECHAZÓ LA PETICIÓN: {response.text}\n")
            
        response.raise_for_status()

        data = json.loads(_limpiar_json(response.json()["choices"][0]["message"]["content"]))
        hallazgos = data.get("hallazgos", [])
        print(f"✅ Groq Vision detectó {len(hallazgos)} hallazgos reales.")
        
        return {
            "hallazgos": hallazgos, 
            "wcag": data.get("wcag", _wcag_default()), 
            "puntaje": data.get("puntaje", _calcular_puntaje(hallazgos)), 
            "fuente": "groq-vision"
        }

    except Exception as e:
        print(f"⚠️ ERROR FATAL Groq Vision: {e}")
        return _resultado_fallback(casos)

def _calcular_puntaje(hallazgos: list) -> int:
    pen = {"critical": 15, "high": 10, "medium": 5, "low": 2}
    total = sum(pen.get(h.get("severidad", "low"), 0) for h in hallazgos)
    return max(0, min(100, 100 - total))

def _wcag_default():
    return [{"id": "1.4.3", "nombre": "Contraste", "nivel": "AA", "estado": "warn", "nota": "Pendiente visual."}]

def _casos_fallback():
    return [{"id":"CP-001","prioridad":"critical","nombre":"Fallo de API","pre":"","pasos":"","esperado":"","ref":"§—"}]

def _resultado_fallback(casos: list) -> dict:
    hallazgos = [
        {
            "id": "ERR-SISTEMA",
            "severidad": "critical",
            "refCaso": casos[0]["id"] if casos else "CP-001",
            "titulo": "Fallo en el Motor de Visión Groq",
            "clausula": "Error interno",
            "desc": "El modelo de IA devolvió un JSON corrupto, falló por tiempo de espera o rechazó la imagen.",
            "esperado": "Análisis visual completado con JSON válido",
            "obtenido": "Respuesta vacía o error de servidor",
            "tecnicas": ["Revisar terminal de Python"],
            "bbox": {"x": "5%", "y": "5%", "w": "90%", "h": "90%", "tipo": "error", "etiqueta": "ERROR DE CONEXIÓN IA"}
        }
    ]
    return {"hallazgos": hallazgos, "wcag": _wcag_default(), "puntaje": 0, "fuente": "error-fallback"}