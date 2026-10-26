from typing import Optional
from pydantic import BaseModel


class CategoriaCreate(BaseModel):
    nombre: str
    orden: Optional[int] = 0


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    orden: Optional[int] = None