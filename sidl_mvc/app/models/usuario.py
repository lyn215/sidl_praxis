"""
MODEL — Usuario
Operaciones CRUD sobre la tabla `usuarios`.
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional

from app.models.database import get_connection

try:
    import bcrypt
    BCRYPT_OK = True
except ImportError:
    BCRYPT_OK = False


# ─── Hashing ──────────────────────────────────────────────────────────────────
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


# ─── CRUD ─────────────────────────────────────────────────────────────────────
def crear_usuario(nombre: str, email: str, contrasena: str) -> dict:
    """Inserta un nuevo usuario. Retorna el usuario creado."""
    conn = get_connection()
    uid = str(uuid.uuid4())
    ahora = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO usuarios (id, nombre, email, contrasena, creado_el) VALUES (?, ?, ?, ?, ?)",
        (uid, nombre, email.lower().strip(), hash_contrasena(contrasena), ahora)
    )
    conn.commit()
    conn.close()
    return {"id": uid, "nombre": nombre, "email": email.lower().strip()}


def obtener_por_email(email: str) -> Optional[dict]:
    """Busca un usuario por email. Retorna dict o None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE email = ?", (email.lower().strip(),)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def existe_email(email: str) -> bool:
    return obtener_por_email(email) is not None


def actualizar_ultimo_login(email: str):
    conn = get_connection()
    conn.execute(
        "UPDATE usuarios SET ultimo_login = ? WHERE email = ?",
        (datetime.now().isoformat(), email.lower().strip())
    )
    conn.commit()
    conn.close()


def contar_auditorias_usuario(usuario_id: str) -> int:
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM auditorias WHERE usuario_id = ?", (usuario_id,)
    ).fetchone()[0]
    conn.close()
    return n
