from fastapi import APIRouter, Depends, HTTPException

from app.core.config import supabase
from app.core.auth import require_restaurant_admin
from app.schemas.categoria import CategoriaCreate, CategoriaUpdate

router = APIRouter()

# ---------- CRUD de CATEGORIAS (protegido) ----------

@router.get("/admin/categorias")
def listar_mis_categorias(usuario: dict = Depends(require_restaurant_admin)):
    """Lista todas las categorías del tenant del usuario autenticado"""
    query = supabase.table("categorias").select("*")

    if usuario["rol"] == "restaurant_admin":
        query = query.eq("tenant_id", usuario["tenant_id"])

    response = query.order("orden").execute()
    return response.data


@router.post("/admin/categorias")
def crear_categoria(categoria: CategoriaCreate, usuario: dict = Depends(require_restaurant_admin)):
    """Crea una nueva categoría para el tenant del usuario autenticado"""
    if usuario["rol"] != "restaurant_admin":
        raise HTTPException(status_code=403, detail="Solo un admin de restaurante puede crear categorías")

    nueva_categoria = categoria.model_dump()
    nueva_categoria["tenant_id"] = usuario["tenant_id"]

    response = supabase.table("categorias").insert(nueva_categoria).execute()
    return response.data[0]


@router.put("/admin/categorias/{categoria_id}")
def actualizar_categoria(categoria_id: str, categoria: CategoriaUpdate, usuario: dict = Depends(require_restaurant_admin)):
    """Actualiza una categoría, solo si pertenece al tenant del usuario autenticado"""
    existente = supabase.table("categorias").select("tenant_id").eq("id", categoria_id).execute()

    if not existente.data:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if usuario["rol"] == "restaurant_admin" and existente.data[0]["tenant_id"] != usuario["tenant_id"]:
        raise HTTPException(status_code=403, detail="No puedes editar categorías de otro restaurante")

    datos_actualizados = {k: v for k, v in categoria.model_dump().items() if v is not None}
    response = supabase.table("categorias").update(datos_actualizados).eq("id", categoria_id).execute()
    return response.data[0]


@router.delete("/admin/categorias/{categoria_id}")
def eliminar_categoria(categoria_id: str, usuario: dict = Depends(require_restaurant_admin)):
    """Elimina una categoría, solo si pertenece al tenant del usuario autenticado"""
    existente = supabase.table("categorias").select("tenant_id").eq("id", categoria_id).execute()

    if not existente.data:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if usuario["rol"] == "restaurant_admin" and existente.data[0]["tenant_id"] != usuario["tenant_id"]:
        raise HTTPException(status_code=403, detail="No puedes eliminar categorías de otro restaurante")

    supabase.table("categorias").delete().eq("id", categoria_id).execute()
    return {"mensaje": "Categoría eliminada correctamente"}