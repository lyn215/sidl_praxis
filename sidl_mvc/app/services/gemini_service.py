"""
SERVICE — Cloud AI Service (Gemini/Groq/Hugging Face)
Integración con Gemini, Groq o Hugging Face según variables de entorno.
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

# ─── Variables de entorno de proveedores IA ───────────────────────────────────
_raw_groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
_raw_gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
_raw_huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY", "").strip()

# Compatibilidad: si guardaron por error una key de Gemini en GROQ_API_KEY (suele empezar con AIza)
GEMINI_API_KEY = _raw_gemini_api_key or (_raw_groq_api_key if _raw_groq_api_key.startswith("AIza") else "")
GROQ_API_KEY = _raw_groq_api_key if _raw_groq_api_key and not _raw_groq_api_key.startswith("AIza") else ""
HUGGINGFACE_API_KEY = _raw_huggingface_api_key

AI_PROVIDER = os.getenv("AI_PROVIDER", os.getenv("IA_PROVIDER", "auto")).strip().lower()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL_TEXT = os.getenv("GROQ_MODEL_TEXT", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_MODEL_VISION = os.getenv("GROQ_MODEL_VISION", GROQ_MODEL_TEXT)

GEMINI_MODEL_TEXT = os.getenv("GEMINI_MODEL_TEXT", "gemini-2.0-flash")
GEMINI_MODEL_VISION = os.getenv("GEMINI_MODEL_VISION", "gemini-2.0-flash")

HUGGINGFACE_MODEL_TEXT = os.getenv("HUGGINGFACE_MODEL_TEXT", "Qwen/Qwen2.5-VL-7B-Instruct")
HUGGINGFACE_MODEL_VISION = os.getenv("HUGGINGFACE_MODEL_VISION", "Qwen/Qwen2.5-VL-7B-Instruct")
HUGGINGFACE_URL = "https://router.huggingface.co/v1/chat/completions"

# ─── Routing fijo por tarea (para reducir sobrecarga en Qwen) ─────────────────
CASOS_PROVIDER = "groq"
CASOS_MODEL = "llama-3.1-8b-instant"
AUDITORIA_PROVIDER = "huggingface"
AUDITORIA_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct"

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

Cuando hayas terminado, responde SOLO con el JSON, sin markdown ni explicaciones, ni nada más. 
Asegúrate de que el JSON sea perfectamente válido, revisa si faltan comas y si hay caracteres que lo puedan hacer inválido al momento de ser procesado.
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

Cuando hayas terminado, responde SOLO con el JSON, sin markdown ni explicaciones, ni nada más. 
Asegúrate de que el JSON sea perfectamente válido, revisa si faltan comas y si hay caracteres que lo puedan hacer inválido al momento de ser procesado.
"""

def _proveedor_activo() -> str:
    if AI_PROVIDER in {"gemini", "groq", "huggingface"}:
        return AI_PROVIDER
    if GEMINI_API_KEY:
        return "gemini"
    if GROQ_API_KEY:
        return "groq"
    if HUGGINGFACE_API_KEY:
        return "huggingface"
    return "none"

def _hay_proveedor_configurado() -> bool:
    return _proveedor_activo() in {"gemini", "groq", "huggingface"}

def _fuente_activa() -> str:
    provider = _proveedor_activo()
    if provider == "gemini":
        return "gemini"
    if provider == "groq":
        return "groq"
    if provider == "huggingface":
        return "huggingface"
    return "fallback"

def _extraer_texto_respuesta(provider: str, body: dict) -> str:
    if provider == "groq" or provider == "huggingface":
        return body["choices"][0]["message"]["content"]

    candidates = body.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini no devolvió candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    textos = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    contenido = "\n".join(textos).strip()
    if not contenido:
        raise ValueError("Gemini devolvió respuesta vacía")
    return contenido

def _llamar_modelo(
    prompt: str,
    contexto: str,
    imagen_b64: Optional[str] = None,
    timeout: int = 30,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    provider = provider_override or _proveedor_activo()
    if provider == "none":
        raise ValueError("No hay proveedor IA configurado. Define GEMINI_API_KEY, GROQ_API_KEY o HUGGINGFACE_API_KEY")

    es_vision = bool(imagen_b64)

    if provider == "groq":
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        model = model_override or (GROQ_MODEL_VISION if es_vision else GROQ_MODEL_TEXT)

        if es_vision:
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}}
                    ]
                }],
                "max_tokens": 2048
            }
        else:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }

        response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=timeout)
        if not response.ok:
            print(f"\n❌ GROQ RECHAZÓ LA PETICIÓN ({contexto}): {response.text}\n")
        response.raise_for_status()
        return _extraer_texto_respuesta("groq", response.json())

    if provider == "huggingface":
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}", "Content-Type": "application/json"}
        model = model_override or (HUGGINGFACE_MODEL_VISION if es_vision else HUGGINGFACE_MODEL_TEXT)
        hf_url = f"{HUGGINGFACE_URL}"

        if es_vision:
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"}}
                    ]
                }],
                "max_tokens": 2048
            }
        else:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 4096
            }

        response = requests.post(hf_url, headers=headers, json=payload, timeout=timeout)
        if not response.ok:
            print(f"\n❌ HUGGINGFACE RECHAZÓ LA PETICIÓN ({contexto}): {response.text}\n")
        response.raise_for_status()
        return _extraer_texto_respuesta("huggingface", response.json())

    model = model_override or (GEMINI_MODEL_VISION if es_vision else GEMINI_MODEL_TEXT)
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    parts = [{"text": prompt}]
    if es_vision:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": imagen_b64
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    response = requests.post(gemini_url, headers=headers, json=payload, timeout=timeout)
    if not response.ok:
        print(f"\n❌ GEMINI RECHAZÓ LA PETICIÓN ({contexto}): {response.text}\n")
    response.raise_for_status()
    return _extraer_texto_respuesta("gemini", response.json())

def _limpiar_json(texto: str) -> str:
    """Extrae JSON de un texto que puede contener markdown o caracteres extra."""
    match = re.search(r'\{.*\}|\[.*\]', texto.strip(), re.DOTALL)
    return match.group(0) if match else texto.strip()

def _validar_y_reparar_json(texto_json: str, contexto: str = "JSON genérico") -> dict:
    """
    Valida y repara JSON malformado usando una segunda llamada a IA.
    
    Args:
        texto_json: String JSON potencialmente corrupto
        contexto: Descripción del tipo de JSON para ayudar a la reparación
    
    Returns:
        Diccionario con 'exito' (bool) y 'datos' (dict) o 'error' (str)
    """
    # 1. Intentar parsing directo
    try:
        datos = json.loads(texto_json)
        print(f"✅ JSON válido al primer intento: {contexto}")
        return {"exito": True, "datos": datos}
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON inválido en {contexto}: {e}")
    
    # 2. Intentar limpiezas automáticas comunes
    texto_limpio = texto_json.strip()
    
    # Remover markdown JSON blocks
    texto_limpio = re.sub(r'^```json\s*', '', texto_limpio)
    texto_limpio = re.sub(r'\s*```$', '', texto_limpio)
    
    try:
        datos = json.loads(texto_limpio)
        print(f"✅ JSON válido después de limpiar markdown: {contexto}")
        return {"exito": True, "datos": datos}
    except json.JSONDecodeError:
        pass
    
    # 3. Si no hay proveedor IA, retornar error
    if not _hay_proveedor_configurado():
        return {"exito": False, "error": "Sin proveedor IA para reparación de JSON"}
    
    # 4. Usar IA para reparar el JSON
    print(f"\n🔧 Enviando JSON malformado a IA para reparación: {contexto}\n")
    try:
        prompt = f"""Eres un experto en JSON. Recibiste este JSON corrupto:

{texto_json[:2000]}

INSTRUCCIONES:
1. Identifica los errores (comillas sin escapar, caracteres especiales, estructura rota, etc.)
2. Repara el JSON para que sea válido
3. Responde SOLO con el JSON reparado, sin explicaciones ni markdown

Contexto del JSON: {contexto}
Valida que el JSON sea perfectamente válido y parseable."""

        contenido = _llamar_modelo(prompt=prompt, contexto=f"Reparación JSON - {contexto}", timeout=30)
        json_reparado = _limpiar_json(contenido)
        
        # Intentar parsear el JSON reparado
        datos = json.loads(json_reparado)
        print(f"✅ IA reparó el JSON exitosamente: {contexto}")
        return {"exito": True, "datos": datos}
        
    except json.JSONDecodeError as e:
        error_msg = f"IA no pudo reparar el JSON: {e}. Contenido original: {texto_json[:500]}"
        print(f"❌ {error_msg}")
        return {"exito": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Error llamando a IA para reparación: {e}"
        print(f"❌ {error_msg}")
        return {"exito": False, "error": error_msg}

def generar_casos_desde_srs(texto_srs: str) -> dict:
    if not GROQ_API_KEY:
        return {"casos": _casos_fallback(), "fuente": "fallback"}

    try:
        prompt = PROMPT_CASOS.format(texto_srs=texto_srs[:8000])
        contenido = _llamar_modelo(
            prompt=prompt,
            contexto="Generación de casos SRS",
            timeout=30,
            provider_override=CASOS_PROVIDER,
            model_override=CASOS_MODEL,
        )
        contenido_json = _limpiar_json(contenido)
        resultado_validacion = _validar_y_reparar_json(contenido_json, "Casos de Prueba SRS")
        
        if not resultado_validacion["exito"]:
            print(f"❌ No se pudo reparar JSON de casos: {resultado_validacion['error']}")
            return {"casos": _casos_fallback(), "requisitos_extraidos": "Error de JSON", "fuente": "fallback"}
        
        data = resultado_validacion["datos"]
        casos = data.get("casos", [])
        requisitos = data.get("requisitos_extraidos", "No se pudieron extraer los requisitos.")
        
        print(f"✅ Groq ({CASOS_MODEL}) generó {len(casos)} casos y extrajo los requisitos limpios.")
        return {"casos": casos, "requisitos_extraidos": requisitos, "fuente": "groq"}
        
    except Exception as e:
        print(f"⚠️ Error IA (casos): {e}")
        return {"casos": _casos_fallback(), "requisitos_extraidos": "Error de conexión.", "fuente": "fallback"}

def auditar_con_vision(texto_srs: str, ruta_imagen: Optional[str], casos: list) -> dict:
    if not HUGGINGFACE_API_KEY or not ruta_imagen or not Path(ruta_imagen).exists():
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

        contenido = _llamar_modelo(
            prompt=prompt,
            contexto="Auditoría visual",
            imagen_b64=img_b64,
            timeout=40,
            provider_override=AUDITORIA_PROVIDER,
            model_override=AUDITORIA_MODEL,
        )
        contenido_json = _limpiar_json(contenido)
        resultado_validacion = _validar_y_reparar_json(contenido_json, "Auditoría Visual IA")
        
        if not resultado_validacion["exito"]:
            print(f"❌ No se pudo reparar JSON de auditoría: {resultado_validacion['error']}")
            return _resultado_fallback(casos)
        
        data = resultado_validacion["datos"]
        hallazgos = data.get("hallazgos", [])
        print(f"✅ HuggingFace ({AUDITORIA_MODEL}) detectó {len(hallazgos)} hallazgos reales.")
        
        return {
            "hallazgos": hallazgos, 
            "wcag": data.get("wcag", _wcag_default()), 
            "puntaje": data.get("puntaje", _calcular_puntaje(hallazgos)), 
            "fuente": "huggingface"
        }

    except Exception as e:
        print(f"⚠️ ERROR FATAL IA Vision: {e}")
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
            "titulo": "Fallo en el Motor de Visión IA",
            "clausula": "Error interno",
            "desc": "El modelo de IA devolvió un JSON corrupto, falló por tiempo de espera o rechazó la imagen.",
            "esperado": "Análisis visual completado con JSON válido",
            "obtenido": "Respuesta vacía o error de servidor",
            "tecnicas": ["Revisar terminal de Python"],
            "bbox": {"x": "5%", "y": "5%", "w": "90%", "h": "90%", "tipo": "error", "etiqueta": "ERROR DE CONEXIÓN IA"}
        }
    ]
    return {"hallazgos": hallazgos, "wcag": _wcag_default(), "puntaje": 0, "fuente": "error-fallback"}