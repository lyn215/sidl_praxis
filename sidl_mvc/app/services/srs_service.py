"""
SERVICE — Extracción de Texto SRS
Extrae texto de documentos PDF, DOCX y TXT usando PyMuPDF.
"""

from pathlib import Path

try:
    import fitz  # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False
    print("⚠️  PyMuPDF no instalado. Instala con: pip install pymupdf")


def extraer_texto(ruta: Path) -> str:
    """
    Extrae texto del documento SRS.
    Soporta: PDF, TXT, y texto plano.
    Retorna cadena de texto (máx. 8000 caracteres para no exceder tokens de Gemini).
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return "Archivo no encontrado."

    ext = ruta.suffix.lower()

    # ── TXT ───────────────────────────────────────────────────────────────────
    if ext == ".txt":
        try:
            return ruta.read_text(encoding="utf-8", errors="ignore")[:8000]
        except Exception as e:
            return f"Error al leer TXT: {e}"

    # ── PDF ───────────────────────────────────────────────────────────────────
    if ext == ".pdf":
        if not PYMUPDF_OK:
            return (
                "PyMuPDF no instalado. No se puede leer el PDF.\n"
                "Instala con: pip install pymupdf\n"
                "O sube un archivo .txt con el contenido del SRS."
            )
        try:
            doc = fitz.open(str(ruta))
            texto = ""
            for pagina in doc:
                texto += pagina.get_text()
            doc.close()
            texto = texto.strip()
            if not texto:
                return "El PDF no contiene texto extraíble (puede ser escaneado). Usa un TXT."
            print(f"✅  PyMuPDF extrajo {len(texto)} caracteres del PDF.")
            return texto[:8000]
        except Exception as e:
            return f"Error al leer PDF: {e}"

    # ── DOCX (básico sin python-docx) ─────────────────────────────────────────
    if ext == ".docx":
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            textos = []
            with zipfile.ZipFile(str(ruta), 'r') as z:
                with z.open("word/document.xml") as f:
                    tree = ET.parse(f)
                    for elem in tree.iter():
                        if elem.tag.endswith("}t") and elem.text:
                            textos.append(elem.text)
            resultado = " ".join(textos)
            print(f"✅  DOCX extraído: {len(resultado)} caracteres.")
            return resultado[:8000]
        except Exception as e:
            return f"Error al leer DOCX: {e}"

    return f"Formato no soportado: {ext}. Usa PDF, DOCX o TXT."
