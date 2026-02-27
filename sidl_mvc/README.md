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

### 2. Configurar la API Key de Gemini (para análisis REAL)
```bash
# Copiar plantilla
cp .env.example .env

# Editar .env
GEMINI_API_KEY=tu_api_key_aqui
```
> 🔑 Obtén tu API Key gratis en: https://aistudio.google.com/app/apikey

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
         └─ [Gemini 1.5 Pro] Genera casos de prueba desde el SRS
                │
                ▼
         Responde: session_id + casos[]
                │
Usuario edita casos de prueba en la tabla
                │
                ▼
[FastAPI] /api/auditoria/lanzar
         │
         ├─ [Gemini 1.5 Pro Vision] Analiza imagen + casos + SRS → hallazgos[]
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
| `POST` | `/api/auditoria/subir` | Subir SRS + imagen, genera casos con Gemini |
| `POST` | `/api/auditoria/lanzar` | Auditoría visual real con Gemini Vision |
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

### 1. GEMINI_API_KEY (Obligatorio)
Sin esto, la app usa datos de demostración. Con la clave:
- Gemini lee tu SRS **real** y genera casos de prueba específicos
- Gemini Vision **analiza tu captura** y detecta hallazgos reales
- El PDF refleja problemas reales de tu interfaz

### 2. Imagen real de tu UI
Sube una captura de pantalla **real de tu aplicación** para que Gemini Vision la analice.

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
| **Servicios** | Python puro | Gemini API, PyMuPDF, ReportLab |
| **Modelos** | SQLite + sqlite3 | Persistencia real de todos los datos |
| **Vista HTML** | Jinja2-less HTML | Archivo separado, sin lógica |
| **Estilos** | CSS puro (340 líneas) | Variables CSS, responsive, dark theme |
| **JavaScript** | Vanilla JS ES2022 | Fetch API, DOM, estado de la app |
| **IA** | Gemini 1.5 Pro Vision | Análisis de SRS + auditoría visual |
| **Extracción** | PyMuPDF (fitz) | PDF, DOCX, TXT → texto |
| **PDF** | ReportLab | Reporte profesional 3 páginas |
| **Auth** | bcrypt | Hash seguro de contraseñas |
