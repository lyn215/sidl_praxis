"""
MODEL — Base de datos SQLite
Gestiona la conexión y creación de todas las tablas del sistema.

Tablas:
  - usuarios          → Cuentas de usuario con contraseña hasheada
  - sesiones_archivo  → Archivos SRS + UI subidos por sesión
  - casos_prueba      → Casos de prueba generados/editados por el usuario
  - auditorias        → Cabecera de cada auditoría ejecutada
  - hallazgos         → Hallazgos detectados por el motor de análisis
  - resultados_wcag   → Resultados WCAG 2.1 AA por auditoría
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime

DB_PATH = Path("sidl.db")


def get_connection() -> sqlite3.Connection:
    """Retorna una conexión con row_factory para acceso por nombre de columna."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """Crea todas las tablas si no existen. Se llama al iniciar la app."""
    conn = get_connection()
    cur = conn.cursor()

    # ── Tabla: usuarios ────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          TEXT PRIMARY KEY,
            nombre      TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            contrasena  TEXT NOT NULL,
            creado_el   TEXT NOT NULL,
            ultimo_login TEXT
        )
    """)

    # ── Tabla: sesiones_archivo ────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_archivo (
            id              TEXT PRIMARY KEY,
            usuario_id      TEXT,
            archivo_srs     TEXT NOT NULL,
            ruta_srs        TEXT NOT NULL,
            archivo_ui      TEXT,
            ruta_ui         TEXT,
            texto_srs       TEXT,
            creado_el       TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    # ── Tabla: auditorias ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auditorias (
            id              TEXT PRIMARY KEY,
            sesion_id       TEXT NOT NULL,
            usuario_id      TEXT,
            puntaje         INTEGER NOT NULL,
            total_hallazgos INTEGER NOT NULL DEFAULT 0,
            criticos        INTEGER NOT NULL DEFAULT 0,
            altos           INTEGER NOT NULL DEFAULT 0,
            medios          INTEGER NOT NULL DEFAULT 0,
            bajos           INTEGER NOT NULL DEFAULT 0,
            fuente_analisis TEXT NOT NULL DEFAULT 'gemini',
            fecha           TEXT NOT NULL,
            FOREIGN KEY (sesion_id)  REFERENCES sesiones_archivo(id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    # ── Tabla: casos_prueba ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS casos_prueba (
            id              TEXT NOT NULL,
            auditoria_id    TEXT NOT NULL,
            prioridad       TEXT NOT NULL,
            nombre          TEXT NOT NULL,
            precondiciones  TEXT,
            pasos           TEXT,
            esperado        TEXT,
            ref_srs         TEXT,
            PRIMARY KEY (id, auditoria_id),
            FOREIGN KEY (auditoria_id) REFERENCES auditorias(id) ON DELETE CASCADE
        )
    """)

    # ── Tabla: hallazgos ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hallazgos (
            id              TEXT NOT NULL,
            auditoria_id    TEXT NOT NULL,
            severidad       TEXT NOT NULL,
            ref_caso        TEXT,
            titulo          TEXT NOT NULL,
            clausula        TEXT,
            descripcion     TEXT,
            esperado        TEXT,
            obtenido        TEXT,
            tecnicas        TEXT,
            bbox_x          TEXT,
            bbox_y          TEXT,
            bbox_w          TEXT,
            bbox_h          TEXT,
            bbox_tipo       TEXT,
            bbox_etiqueta   TEXT,
            PRIMARY KEY (id, auditoria_id),
            FOREIGN KEY (auditoria_id) REFERENCES auditorias(id) ON DELETE CASCADE
        )
    """)

    # ── Tabla: resultados_wcag ─────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resultados_wcag (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            auditoria_id    TEXT NOT NULL,
            criterio_id     TEXT NOT NULL,
            nombre          TEXT NOT NULL,
            nivel           TEXT NOT NULL,
            estado          TEXT NOT NULL,
            nota            TEXT,
            FOREIGN KEY (auditoria_id) REFERENCES auditorias(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅  Base de datos SQLite iniciada en: {DB_PATH.absolute()}")


def check_status():
    """Imprime resumen del estado de la base de datos al iniciar el servidor."""
    conn = get_connection()
    cur = conn.cursor()
    usuarios   = cur.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    auditorias = cur.execute("SELECT COUNT(*) FROM auditorias").fetchone()[0]
    hallazgos  = cur.execute("SELECT COUNT(*) FROM hallazgos").fetchone()[0]
    conn.close()

    print("\n" + "=" * 55)
    print("  SiDL — Smart Interface & Documentation Lens")
    print("  Backend FastAPI MVC v2.0 — SQLite")
    print("=" * 55)
    print(f"  DB Path:    {DB_PATH.absolute()}")
    print(f"  Usuarios:   {usuarios}")
    print(f"  Auditorías: {auditorias}")
    print(f"  Hallazgos:  {hallazgos}")
    print("=" * 55 + "\n")
