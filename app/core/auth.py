from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import supabase

security = HTTPBearer()


def get_usuario_actual(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        user_response = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    perfil = (
        supabase.table("usuarios")
        .select("rol, tenant_id, email")
        .eq("auth_id", user_response.user.id)
        .execute()
    )

    if not perfil.data:
        raise HTTPException(status_code=404, detail="Usuario sin perfil asociado")

    usuario_data = perfil.data[0]

    # Si es admin de un restaurante, verificamos que su tenant siga activo
    # (bloquea el acceso si fue suspendido, ej. por falta de pago)
    if usuario_data["rol"] == "restaurant_admin" and usuario_data.get("tenant_id"):
        tenant = (
            supabase.table("tenants")
            .select("estado")
            .eq("id", usuario_data["tenant_id"])
            .execute()
        )
        if not tenant.data or tenant.data[0].get("estado") != "activo":
            raise HTTPException(
                status_code=403,
                detail="Tu cuenta está suspendida. Contacta al soporte de la plataforma."
            )

    return usuario_data


def require_restaurant_admin(usuario: dict = Depends(get_usuario_actual)):
    if usuario["rol"] not in ("restaurant_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="No tienes permisos para esta acción")
    return usuario


def require_super_admin(usuario: dict = Depends(get_usuario_actual)):
    if usuario["rol"] != "super_admin":
        raise HTTPException(status_code=403, detail="Solo el super admin puede realizar esta acción")
    return usuario