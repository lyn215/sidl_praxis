"""
CONTROLLER — Autenticación
Rutas: /api/auth/registro, /api/auth/login
"""

from fastapi import APIRouter, HTTPException
from app.schemas.schemas import RegistroRequest, LoginRequest, UsuarioResponse
from app.models import usuario as usuario_model

router = APIRouter()


@router.post("/registro", response_model=UsuarioResponse)
async def registro(req: RegistroRequest):
    """Registra un nuevo usuario en la base de datos SQLite."""
    if req.contrasena != req.confirmar:
        raise HTTPException(400, "Las contraseñas no coinciden.")

    if usuario_model.existe_email(req.email):
        raise HTTPException(400, "Ya existe una cuenta con este correo electrónico.")

    nuevo = usuario_model.crear_usuario(req.nombre, req.email, req.contrasena)
    return UsuarioResponse(
        id=nuevo["id"],
        nombre=nuevo["nombre"],
        email=nuevo["email"],
        num_auditorias=0,
    )


@router.post("/login", response_model=UsuarioResponse)
async def login(req: LoginRequest):
    """Autentica un usuario y retorna sus datos."""
    u = usuario_model.obtener_por_email(req.email)

    if not u:
        raise HTTPException(401, "No existe una cuenta con este correo electrónico.")

    if not usuario_model.verificar_contrasena(req.contrasena, u["contrasena"]):
        raise HTTPException(401, "Contraseña incorrecta.")

    usuario_model.actualizar_ultimo_login(req.email)
    num_aud = usuario_model.contar_auditorias_usuario(u["id"])

    return UsuarioResponse(
        id=u["id"],
        nombre=u["nombre"],
        email=u["email"],
        num_auditorias=num_aud,
    )
