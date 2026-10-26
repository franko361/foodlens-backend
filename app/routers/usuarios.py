from fastapi import APIRouter, Depends, HTTPException

from app.core.config import supabase, supabase_admin
from app.core.auth import require_super_admin
from app.schemas.usuario import UsuarioCreate

router = APIRouter()


@router.get("/admin/usuarios")
def listar_usuarios(usuario: dict = Depends(require_super_admin)):
    """Lista todos los usuarios admin de la plataforma - solo super_admin"""
    response = supabase.table("usuarios").select("*").execute()
    return response.data


@router.post("/admin/usuarios")
def crear_usuario(data: UsuarioCreate, usuario: dict = Depends(require_super_admin)):
    """
    Crea un nuevo usuario admin (restaurant_admin o super_admin) - solo super_admin.
    Crea la cuenta en Supabase Auth Y el registro en la tabla usuarios, vinculados.
    """
    if data.rol not in ("restaurant_admin", "super_admin"):
        raise HTTPException(status_code=400, detail="Rol inválido")

    if data.rol == "restaurant_admin" and not data.tenant_id:
        raise HTTPException(status_code=400, detail="Un restaurant_admin necesita un tenant_id")

    # 1. Crear la cuenta de autenticación
    try:
        auth_result = supabase_admin.auth.admin.create_user({
            "email": data.email,
            "password": data.password,
            "email_confirm": True,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error creando cuenta: {str(e)}")

    # 2. Crear el registro en la tabla usuarios, vinculado al auth_id recién creado
    nuevo_usuario = {
        "auth_id": auth_result.user.id,
        "email": data.email,
        "rol": data.rol,
        "tenant_id": data.tenant_id,
    }
    response = supabase.table("usuarios").insert(nuevo_usuario).execute()
    return response.data[0]


@router.delete("/admin/usuarios/{usuario_id}")
def eliminar_usuario(usuario_id: str, usuario: dict = Depends(require_super_admin)):
    """Elimina un usuario admin - solo super_admin"""
    existente = supabase.table("usuarios").select("auth_id").eq("id", usuario_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    auth_id = existente.data[0]["auth_id"]

    # Elimina primero de Auth, luego de la tabla
    if auth_id:
        try:
            supabase_admin.auth.admin.delete_user(auth_id)
        except Exception:
            pass  # si ya no existe en Auth, seguimos igual con la tabla

    supabase.table("usuarios").delete().eq("id", usuario_id).execute()
    return {"mensaje": "Usuario eliminado correctamente"}