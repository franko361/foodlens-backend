from fastapi import APIRouter, Depends, HTTPException

from app.core.config import supabase
from app.core.auth import get_usuario_actual
from app.schemas.usuario import LoginRequest

router = APIRouter()


@router.post("/auth/login")
def login(data: LoginRequest):
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": data.email, "password": data.password}
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    perfil = (
        supabase.table("usuarios")
        .select("rol, tenant_id, email")
        .eq("auth_id", result.user.id)
        .execute()
    )

    if not perfil.data:
        raise HTTPException(status_code=404, detail="Usuario sin perfil asociado")

    return {
        "access_token": result.session.access_token,
        "usuario": perfil.data[0],
    }


@router.get("/auth/me")
def get_me(usuario: dict = Depends(get_usuario_actual)):
    return usuario