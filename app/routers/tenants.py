from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.config import supabase
from app.core.auth import get_usuario_actual, require_restaurant_admin, require_super_admin
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.ia_service import regenerar_sugerencias_del_tenant

router = APIRouter()

FUENTES_VALIDAS = {"moderna", "elegante", "clasica", "redondeada", "marcada"}
DISPOSICIONES_VALIDAS = {"lista", "cuadricula"}
TAMANOS_FOTO_VALIDOS = {"pequena", "grande"}


# ---------- Ruta pública ----------
COLUMNAS_PUBLICAS = (
    "id, nombre, slug, logo_url, color_primario, forma_boton, direccion, horario, "
    "telefono, historia_restaurante, fuente, disposicion_tarjetas, tamano_foto, estado"
)


@router.get("/tenants")
def get_tenants():
    response = (
        supabase.table("tenants")
        .select(COLUMNAS_PUBLICAS)
        .eq("estado", "activo")
        .execute()
    )
    return response.data


@router.get("/admin/mi-tenant")
def get_mi_tenant(usuario: dict = Depends(require_restaurant_admin)):
    """Datos del restaurante del admin autenticado (sin notas internas del super_admin)"""
    if not usuario.get("tenant_id"):
        raise HTTPException(status_code=404, detail="No tienes un restaurante asociado")
    response = (
        supabase.table("tenants")
        .select(COLUMNAS_PUBLICAS + ", plan")
        .eq("id", usuario["tenant_id"])
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="No se encontró tu restaurante")
    return response.data[0]
    

# ---------- CRUD de TENANTS ----------
@router.get("/admin/tenants")
def listar_todos_los_tenants(usuario: dict = Depends(require_super_admin)):
    """Lista TODOS los restaurantes (activos, pendientes, suspendidos) - solo super_admin"""
    response = supabase.table("tenants").select("*").execute()
    return response.data


@router.post("/admin/tenants")
def crear_tenant(tenant: TenantCreate, usuario: dict = Depends(require_super_admin)):
    """Registra un nuevo restaurante en la plataforma - solo super_admin"""
    nuevo_tenant = tenant.model_dump()
    nuevo_tenant["estado"] = "activo"

    response = supabase.table("tenants").insert(nuevo_tenant).execute()
    return response.data[0]


@router.put("/admin/tenants/{tenant_id}")
def actualizar_tenant(tenant_id: str, tenant: TenantUpdate, background_tasks: BackgroundTasks, usuario: dict = Depends(get_usuario_actual)):
    """
    Actualiza un tenant.
    - super_admin: puede editar cualquier tenant (incluido el estado: aprobar/suspender)
    - restaurant_admin: solo puede editar SU propio tenant, y NO puede cambiar el estado
    """
    existente = supabase.table("tenants").select("*").eq("id", tenant_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    estado_anterior = existente.data[0]["estado"]
    datos_actualizados = {k: v for k, v in tenant.model_dump().items() if v is not None}
    if "fuente" in datos_actualizados and datos_actualizados["fuente"] not in FUENTES_VALIDAS:
        raise HTTPException(status_code=400, detail="Fuente no válida")
    if "disposicion_tarjetas" in datos_actualizados and datos_actualizados["disposicion_tarjetas"] not in DISPOSICIONES_VALIDAS:
        raise HTTPException(status_code=400, detail="Disposición no válida")
    if "tamano_foto" in datos_actualizados and datos_actualizados["tamano_foto"] not in TAMANOS_FOTO_VALIDOS:
        raise HTTPException(status_code=400, detail="Tamaño de foto no válido")

    if usuario["rol"] == "restaurant_admin":
        if tenant_id != usuario["tenant_id"]:
            raise HTTPException(status_code=403, detail="No puedes editar otro restaurante")
        datos_actualizados.pop("estado", None)
        datos_actualizados.pop("notas_admin", None)  # solo el super_admin gestiona notas internas
        datos_actualizados.pop("plan", None)  # solo el super_admin cambia el plan
        datos_actualizados.pop("motivo_suspension", None)
    elif usuario["rol"] != "super_admin":
        raise HTTPException(status_code=403, detail="No tienes permisos para esta acción")

    response = supabase.table("tenants").update(datos_actualizados).eq("id", tenant_id).execute()

    # Si el super_admin cambió el estado, lo registramos en el historial
    if usuario["rol"] == "super_admin" and "estado" in datos_actualizados:
        nuevo_estado = datos_actualizados["estado"]
        if nuevo_estado != estado_anterior:
            supabase.table("historial_tenants").insert({
                "tenant_id": tenant_id,
                "estado_anterior": estado_anterior,
                "estado_nuevo": nuevo_estado,
            }, returning="minimal").execute()

    if "historia_restaurante" in datos_actualizados:
        background_tasks.add_task(regenerar_sugerencias_del_tenant, tenant_id)

    return response.data[0]


@router.delete("/admin/tenants/{tenant_id}")
def eliminar_tenant(tenant_id: str, usuario: dict = Depends(require_super_admin)):
    """Elimina un restaurante de la plataforma - solo super_admin"""
    existente = supabase.table("tenants").select("id").eq("id", tenant_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    supabase.table("tenants").delete().eq("id", tenant_id).execute()
    return {"mensaje": "Restaurante eliminado correctamente"}