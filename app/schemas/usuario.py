from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class UsuarioCreate(BaseModel):
    email: str
    password: str
    rol: str  # "restaurant_admin" o "super_admin"
    tenant_id: Optional[str] = None