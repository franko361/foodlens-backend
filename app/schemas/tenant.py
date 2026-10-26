from typing import Optional
from pydantic import BaseModel


class TenantCreate(BaseModel):
    nombre: str
    slug: str
    direccion: Optional[str] = None
    horario: Optional[str] = None
    color_primario: Optional[str] = "#993C1D"
    forma_boton: Optional[str] = "redondeado"


class TenantUpdate(BaseModel):
    nombre: Optional[str] = None
    logo_url: Optional[str] = None
    color_primario: Optional[str] = None
    forma_boton: Optional[str] = None
    direccion: Optional[str] = None
    horario: Optional[str] = None
    telefono: Optional[str] = None
    estado: Optional[str] = None
    historia_restaurante: Optional[str] = None
    fuente: Optional[str] = None
    disposicion_tarjetas: Optional[str] = None
    tamano_foto: Optional[str] = None
    notas_admin: Optional[str] = None  # solo lo edita el super_admin
    plan: Optional[str] = None  # solo lo edita el super_admin
    motivo_suspension: Optional[str] = None  # solo lo edita el super_admin