"""
SCHEMAS — Modelos Pydantic
Validan los datos de entrada y salida de la API.
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List


# ─── Auth ─────────────────────────────────────────────────────────────────────
class RegistroRequest(BaseModel):
    nombre:     str
    email:      str
    contrasena: str
    confirmar:  str

    @field_validator("nombre")
    @classmethod
    def nombre_no_vacio(cls, v):
        if not v.strip():
            raise ValueError("El nombre no puede estar vacío.")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_valido(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Formato de correo electrónico inválido.")
        return v.lower().strip()

    @field_validator("contrasena")
    @classmethod
    def contrasena_minima(cls, v):
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres.")
        return v


class LoginRequest(BaseModel):
    email:      str
    contrasena: str


class UsuarioResponse(BaseModel):
    id:              str
    nombre:          str
    email:           str
    num_auditorias:  int = 0


# ─── Casos de Prueba ──────────────────────────────────────────────────────────
class CasoPrueba(BaseModel):
    id:       str
    prioridad: str
    nombre:   str
    pre:      str
    pasos:    str
    esperado: str
    ref:      str


# ─── Auditoría ────────────────────────────────────────────────────────────────
class LanzarAuditoriaRequest(BaseModel):
    session_id:  str
    casos:       List[CasoPrueba]
    usuario_id:  Optional[str] = None


class ExportarPDFRequest(BaseModel):
    audit_id: str


# ─── Respuestas ───────────────────────────────────────────────────────────────
class SubirArchivosResponse(BaseModel):
    session_id:         str
    archivo_srs:        str
    archivo_ui:         str
    casos:              List[CasoPrueba]
    fuente:             str
    texto_srs_preview:  str


class AuditoriaResponse(BaseModel):
    audit_id:   str
    puntaje:    int
    hallazgos:  list
    wcag:       list
    casos:      list
