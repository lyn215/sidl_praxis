# SiDL MVC v2.0 — Smart Interface & Documentation Lens
### Plataforma de Auditoría QA — Arquitectura MVC | FastAPI + SQLite + Gemini 1.5 Pro

---

## 📁 Estructura del Proyecto (MVC)

```
sidl_mvc/
│
├── main.py                          ← Punto de entrada FastAPI
├── requirements.txt                 ← Dependencias Python
├── .env.example                     ← Plantilla de variables de entorno
├── sidl.db                          ← Base de datos SQLite (se crea sola)
│
├── app/                             ← Módulo principal de la aplicación
│   │
│   ├── models/                      ◄── MODELO (M)
│   │   ├── database.py              ← Conexión SQLite, init_db(), tablas
│   │   ├── usuario.py               ← CRUD de usuarios (crear, buscar, hash)
│   │   └── auditoria.py             ← CRUD de auditorías, hallazgos, WCAG
│   │
│   ├── controllers/                 ◄── CONTROLADOR (C)
│   │   ├── auth_controller.py       ← Rutas /api/auth/* (login, registro)
│   │   ├── auditoria_controller.py  ← Rutas /api/auditoria/* (subir, lanzar, historial)
│   │   └── exportar_controller.py   ← Rutas /api/exportar/* (pdf, csv)
│   │
│   ├── services/                    ← Lógica de negocio (servicios)
│   │   ├── config_service.py        ← Lee .env, expone GEMINI_API_KEY
│   │   ├── gemini_service.py        ← Integración real Gemini 1.5 Pro Vision
│   │   ├── srs_service.py           ← Extracción de texto PDF/DOCX/TXT
│   │   └── pdf_service.py           ← Generación de PDF con ReportLab
│   │
│   └── schemas/
│       └── schemas.py               ← Modelos Pydantic (validación de datos)
│
├── templates/                       ◄── VISTA (V)
│   └── index.html                   ← HTML puro (sin CSS ni JS inline)
│
├── static/
│   ├── css/
│   │   └── sidl.css                 ← Todos los estilos de la aplicación
│   └── js/
│       └── sidl.js                  ← Toda la lógica JavaScript (fetch API)
│
├── uploads/                         ← Archivos SRS y capturas subidos
└── reports/                         ← PDFs generados
```

---

## 🚀 Instalación y Ejecución

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar Proveedor IA (para análisis REAL)
Elige **uno** de los tres proveedores disponibles y configura su API Key en `.env`:

#### Opción A: Google Gemini (recomendado)
```bash
# Copiar plantilla
cp .env.example .env

# Editar .env
GEMINI_API_KEY=tu_api_key_aqui
AI_PROVIDER=gemini
```
> 🔑 Obtén tu API Key gratis en: https://aistudio.google.com/app/apikey

#### Opción B: Groq (más rápido, gratis)
```bash
GROQ_API_KEY=tu_api_key_aqui
AI_PROVIDER=groq
```
> 🔑 Obtén tu API Key en: https://console.groq.com/keys

#### Opción C: Hugging Face (Qwen2.5-VL-7B)
```bash
HUGGINGFACE_API_KEY=tu_api_key_aqui
AI_PROVIDER=huggingface
```
> 🔑 Obtén tu API Key en: https://huggingface.co/settings/tokens

Si no configuras `AI_PROVIDER`, el sistema elegirá automáticamente el primero disponible.

### 3. Ejecutar el servidor
```bash
uvicorn main:app --reload --port 8000
```

### 4. Abrir en el navegador
```
http://localhost:8000
```

La base de datos SQLite (`sidl.db`) se crea automáticamente en el primer inicio.

---

## 🔄 Flujo de Datos Real (Producción)

```
Usuario sube SRS.pdf + captura.png
         │
         ▼
[FastAPI] /api/auditoria/subir
         │
         ├─ [PyMuPDF] Extrae texto del PDF
         ├─ [SQLite]  Guarda sesión_archivo
         └─ [OpenAI-compatible API] Genera casos de prueba desde el SRS
                │
                ▼
         Responde: session_id + casos[]
                │
Usuario edita casos de prueba en la tabla
                │
                ▼
[FastAPI] /api/auditoria/lanzar
         │
         ├─ [OpenAI-compatible API] Analiza imagen + casos + SRS → hallazgos[]
         ├─ [SQLite] Guarda auditoria + hallazgos + casos + wcag
         └─ Responde: audit_id + puntaje + hallazgos[] + wcag[]
                │
                ▼
[FastAPI] /api/exportar/pdf/{audit_id}
         │
         └─ [ReportLab] Lee de SQLite → Genera PDF 3 páginas → Descarga
```

---

## 📡 Endpoints de la API

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET`  | `/` | Sirve el frontend HTML |
| `POST` | `/api/auth/registro` | Registrar usuario (guarda en SQLite con bcrypt) |
| `POST` | `/api/auth/login` | Autenticar usuario |
| `POST` | `/api/auditoria/subir` | Subir SRS + imagen, genera casos con IA |
| `POST` | `/api/auditoria/lanzar` | Auditoría visual real con IA Vision |
| `GET`  | `/api/auditoria/historial/{usuario_id}` | Historial desde SQLite |
| `DELETE` | `/api/auditoria/eliminar/{audit_id}/{usuario_id}` | Eliminar auditoría (CASCADE) |
| `GET`  | `/api/auditoria/detalle/{audit_id}` | Detalle completo de una auditoría |
| `GET`  | `/api/exportar/pdf/{audit_id}` | Genera y descarga PDF (ReportLab) |
| `POST` | `/api/exportar/csv` | Exporta casos de prueba como CSV |

📖 Swagger UI: `http://localhost:8000/docs`

---

## 🗄️ Base de Datos SQLite

Tablas creadas automáticamente:

| Tabla | Descripción |
|-------|-------------|
| `usuarios` | Cuentas con contraseña hasheada (bcrypt) |
| `sesiones_archivo` | Archivos SRS + captura subidos |
| `auditorias` | Cabecera de cada auditoría con puntaje QA |
| `casos_prueba` | Casos de prueba generados/editados |
| `hallazgos` | Hallazgos detectados con bounding boxes |
| `resultados_wcag` | Análisis WCAG 2.1 AA por auditoría |

---

## ✅ Qué cambiar para Producción 100% Real

### 1. Configurar Proveedor IA (Obligatorio)
Sin esto, la app usa datos de demostración. Elige **uno** de los 3 proveedores:

**Gemini (Google)**
- Configura `GEMINI_API_KEY` en `.env`
- Gratis hasta 1M de tokens/mes
- Mejor relación costo-beneficio para texto + visión
- 🔗 https://aistudio.google.com/app/apikey

**Groq (Llama 3.1)**
- Configura `GROQ_API_KEY` en `.env`
- Gratis y ultrarrápido (inferencia <1s)
- Perfecto para análisis bajo demanda
- 🔗 https://console.groq.com/keys

**Hugging Face (Qwen2.5-VL-7B)**
- Configura `HUGGINGFACE_API_KEY` en `.env`
- Modelos open-source alojados
- Buena opción para privacidad + visión multimodal
- 🔗 https://huggingface.co/settings/tokens

Con cualquiera de estas claves, el servicio:
- Lee tu SRS **real** y genera casos de prueba específicos
- **Analiza tu captura** y detecta hallazgos reales
- El PDF refleja problemas reales de tu interfaz

### 2. Imagen real de tu UI
Sube una captura de pantalla **real de tu aplicación** para que la IA Vision la analice.

### 3. SRS real
Sube tu documento PDF/DOCX/TXT de especificación real para que PyMuPDF extraiga los requisitos.

### 4. (Opcional) Migrar a PostgreSQL
Reemplaza las funciones en `app/models/database.py` con `psycopg2` o `SQLAlchemy`.

### 5. (Opcional) Agregar autenticación JWT
Instala `python-jose` y agrega tokens en `auth_controller.py` para APIs protegidas.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología | Función |
|------|-----------|---------|
| **Entrada** | FastAPI (ASGI) | Router, validación Pydantic, CORS |
| **Controladores** | 3 routers FastAPI | auth, auditoria, exportar |
| **Servicios** | Python puro | Gemini/Groq/HF API, PyMuPDF, ReportLab |
| **Modelos** | SQLite + sqlite3 | Persistencia real de todos los datos |
| **Vista HTML** | Jinja2-less HTML | Archivo separado, sin lógica |
| **Estilos** | CSS puro (340 líneas) | Variables CSS, responsive, dark theme |
| **JavaScript** | Vanilla JS ES2022 | Fetch API, DOM, estado de la app |
| **IA** | Gemini 2.0 / Groq / HF Qwen | Análisis de SRS + auditoría visual |
| **Extracción** | PyMuPDF (fitz) | PDF, DOCX, TXT → texto |
| **PDF** | ReportLab | Reporte profesional 3 páginas |
| **Auth** | bcrypt | Hash seguro de contraseñas |
