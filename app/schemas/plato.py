from typing import Optional
from pydantic import BaseModel


class PlatoCreate(BaseModel):
    categoria_id: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    modelo_3d_url: Optional[str] = None
    imagen_url: Optional[str] = None
    calorias_estimadas: Optional[int] = None
    proteinas: Optional[float] = None
    carbohidratos: Optional[float] = None
    estado: Optional[str] = "activo"


class PlatoUpdate(BaseModel):
    categoria_id: Optional[str] = None
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    modelo_3d_url: Optional[str] = None
    imagen_url: Optional[str] = None
    calorias_estimadas: Optional[int] = None
    proteinas: Optional[float] = None
    carbohidratos: Optional[float] = None
    estado: Optional[str] = None