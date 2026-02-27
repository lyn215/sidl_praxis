# SiDL — Smart Interface & Documentation Lens
### Plataforma de Auditoría Multimodal QA con Python + FastAPI

---

## 🚀 Instalación Rápida

### 1. Requisitos previos
- Python 3.10 o superior
- pip

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar la API Key de Gemini (opcional)
```bash
# Copia el archivo de ejemplo
cp .env.example .env

# Edita .env y agrega tu API Key
# Obtén la tuya gratis en: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=tu_api_key_aqui
```
> Si no configuras la API Key, la app funciona en **modo simulado** con datos de demostración.

### 4. Ejecutar el servidor
```bash
uvicorn main:app --reload --port 8000
```

### 5. Abrir en el navegador
```
http://localhost:8000
```

---

## 📁 Estructura del Proyecto

```
sidl_project/
├── main.py              ← Backend FastAPI (toda la lógica Python)
├── requirements.txt     ← Dependencias Python
├── .env.example         ← Plantilla de variables de entorno
├── db.json              ← Base de datos JSON (se crea automáticamente)
├── static/
│   └── index.html       ← Frontend completo (servido por FastAPI)
├── uploads/             ← Archivos SRS y capturas subidos
└── reports/             ← PDFs generados
```

---

## 🛠️ Stack Tecnológico

| Componente | Tecnología | Función |
|---|---|---|
| **Backend** | FastAPI + Python | API REST, lógica de negocio |
| **Servidor** | Uvicorn (ASGI) | Servidor web asíncrono |
| **PDF** | ReportLab | Generación de reportes profesionales |
| **Documentos** | PyMuPDF (fitz) | Extracción de texto de SRS |
| **IA Generativa** | Gemini 1.5 Pro | Generación de casos de prueba |
| **Autenticación** | bcrypt + SHA-256 | Hash seguro de contraseñas |
| **Base de Datos** | JSON (db.json) | Persistencia de usuarios y auditorías |
| **Frontend** | HTML5 + JS + Bootstrap 5 | Interfaz de usuario |

---

## 📡 Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Sirve el frontend |
| `POST` | `/api/registro` | Registrar nuevo usuario |
| `POST` | `/api/login` | Iniciar sesión |
| `POST` | `/api/subir-archivos` | Subir SRS + captura, genera casos de prueba |
| `POST` | `/api/lanzar-auditoria` | Ejecutar auditoría con los casos editados |
| `GET` | `/api/exportar-pdf/{audit_id}` | Descargar reporte PDF (ReportLab) |
| `POST` | `/api/exportar-csv` | Exportar casos de prueba como CSV |
| `GET` | `/api/historial/{email}` | Obtener historial de auditorías |
| `DELETE` | `/api/historial/{audit_id}` | Eliminar una auditoría |

Documentación interactiva Swagger: `http://localhost:8000/docs`

---

## 🔄 Flujo de la Aplicación

```
1. INGESTA
   └── Usuario sube SRS (PDF/DOCX) + Captura de pantalla
   └── FastAPI extrae texto con PyMuPDF
   └── Gemini 1.5 Pro genera casos de prueba automáticamente

2. CASOS DE PRUEBA
   └── Tabla editable con los casos generados por IA
   └── Usuario puede editar, agregar o eliminar casos
   └── Exportar a CSV/Excel o TestRail

3. VISOR DUAL
   └── Documento SRS con cláusulas violadas resaltadas
   └── Captura de pantalla con Bounding Boxes sobre errores
   └── Log en tiempo real del motor de análisis Python

4. RESULTADOS — INSIDE THE LENS
   └── Puntaje QA calculado por el backend
   └── Hallazgos con explicabilidad técnica
   └── Tabla WCAG 2.1 AA de accesibilidad
   └── Tickets Jira listos para copiar
   └── Reporte PDF generado con ReportLab (3 páginas)
```

---

## ⚙️ Configuración Avanzada

### Usar PostgreSQL (en lugar de JSON)
Instala `psycopg2` y modifica las funciones `cargar_db()` y `guardar_db()` en `main.py`.

### Variables de entorno disponibles
```bash
GEMINI_API_KEY=...   # API Key de Google Gemini
PORT=8000            # Puerto del servidor
HOST=0.0.0.0         # Host del servidor
```

### Modo producción
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 📄 Reporte PDF

El reporte generado por **ReportLab** incluye:
- **Página 1 — Portada**: Metadatos, puntaje QA, resumen por severidad
- **Página 2 — Hallazgos**: Detalle de cada hallazgo con técnicas de detección
- **Página 3 — WCAG + Casos**: Tabla de accesibilidad y casos de prueba

---

## 🧑‍💻 Equipo

Proyecto desarrollado como MVP para demostración de capacidades de QA automatizado con IA Generativa.

**Stack**: Python · FastAPI · Gemini 1.5 Pro · ReportLab · PyMuPDF · HTML5 · Bootstrap 5
