from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.config import supabase
from app.core.auth import require_restaurant_admin
from app.schemas.plato import PlatoCreate, PlatoUpdate
from app.services.ia_service import hoy_lima, regenerar_si_toca, regenerar_sugerencias_del_tenant

router = APIRouter()


# ---------- Ruta pública: menú del restaurante ----------
@router.get("/platos/{tenant_slug}")
def get_platos_by_tenant(tenant_slug: str, background_tasks: BackgroundTasks):
    tenant = supabase.table("tenants").select("id, estado, sugerencias_actualizadas_en").eq("slug", tenant_slug).execute()
    if not tenant.data:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")
    if tenant.data[0]["estado"] != "activo":
        raise HTTPException(status_code=403, detail="Este menú no está disponible temporalmente")

    tenant_id = tenant.data[0]["id"]
    # Regeneración diaria de bienvenida y sugerencias del chat (la primera visita del día la dispara)
    fecha_sugerencias = tenant.data[0].get("sugerencias_actualizadas_en")
    if fecha_sugerencias != hoy_lima():
        background_tasks.add_task(regenerar_si_toca, tenant_id, fecha_sugerencias)
    platos = (
        supabase.table("platos")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("estado", "activo")
        .execute()
    )

    # Traemos las categorías del tenant y armamos un mapa {id: nombre},
    # para incluir el nombre real de cada categoría en la respuesta
    # (sin esto, el frontend solo tendría el categoria_id, no el texto).
    categorias = supabase.table("categorias").select("id, nombre").eq("tenant_id", tenant_id).execute()
    mapa_categorias = {c["id"]: c["nombre"] for c in categorias.data}

    resultado = []
    for p in platos.data:
        p["categoria_nombre"] = mapa_categorias.get(p.get("categoria_id"))
        resultado.append(p)

    return resultado


# ---------- CRUD de PLATOS (protegido) ----------
@router.get("/admin/platos")
def listar_mis_platos(usuario: dict = Depends(require_restaurant_admin)):
    """Lista TODOS los platos del tenant del usuario autenticado (activos, pendientes e inactivos)"""
    query = supabase.table("platos").select("*")

    # Si es restaurant_admin, solo ve los de su tenant. Si es super_admin, ve todos.
    if usuario["rol"] == "restaurant_admin":
        query = query.eq("tenant_id", usuario["tenant_id"])

    response = query.execute()
    return response.data


@router.post("/admin/platos")
def crear_plato(plato: PlatoCreate, background_tasks: BackgroundTasks, usuario: dict = Depends(require_restaurant_admin)):
    """Crea un nuevo plato, asignado automáticamente al tenant del usuario autenticado"""
    if usuario["rol"] != "restaurant_admin":
        raise HTTPException(status_code=403, detail="Solo un admin de restaurante puede crear platos")

    nuevo_plato = plato.model_dump()
    nuevo_plato["tenant_id"] = usuario["tenant_id"]

    response = supabase.table("platos").insert(nuevo_plato).execute()
    plato_creado = response.data[0]

    # Actualiza bienvenida y sugerencias del chat en segundo plano
    background_tasks.add_task(regenerar_sugerencias_del_tenant, usuario["tenant_id"])

    return plato_creado


@router.put("/admin/platos/{plato_id}")
def actualizar_plato(plato_id: str, plato: PlatoUpdate, background_tasks: BackgroundTasks, usuario: dict = Depends(require_restaurant_admin)):
    """Actualiza un plato, solo si pertenece al tenant del usuario autenticado"""
    existente = supabase.table("platos").select("tenant_id, nombre, descripcion").eq("id", plato_id).execute()

    if not existente.data:
        raise HTTPException(status_code=404, detail="Plato no encontrado")

    if usuario["rol"] == "restaurant_admin" and existente.data[0]["tenant_id"] != usuario["tenant_id"]:
        raise HTTPException(status_code=403, detail="No puedes editar platos de otro restaurante")

    # Solo los campos que el cliente envió, incluidos los que vienen vacíos (null)
    datos_actualizados = plato.model_dump(exclude_unset=True)
    # Estos campos no pueden quedar vacíos
    for campo in ("nombre", "precio", "estado"):
        if datos_actualizados.get(campo) is None:
            datos_actualizados.pop(campo, None)
    if not datos_actualizados:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")
    response = supabase.table("platos").update(datos_actualizados).eq("id", plato_id).execute()
    plato_actualizado = response.data[0]

    # Solo si el nombre o la descripción cambiaron de verdad, actualiza el chat en segundo plano
    anterior = existente.data[0]
    cambio_texto = (
        ("nombre" in datos_actualizados and datos_actualizados["nombre"] != anterior.get("nombre"))
        or ("descripcion" in datos_actualizados and datos_actualizados["descripcion"] != anterior.get("descripcion"))
    )
    if cambio_texto:
        background_tasks.add_task(regenerar_sugerencias_del_tenant, anterior["tenant_id"])

    return plato_actualizado


@router.delete("/admin/platos/{plato_id}")
def eliminar_plato(plato_id: str, usuario: dict = Depends(require_restaurant_admin)):
    """Elimina un plato, solo si pertenece al tenant del usuario autenticado"""
    existente = supabase.table("platos").select("tenant_id").eq("id", plato_id).execute()

    if not existente.data:
        raise HTTPException(status_code=404, detail="Plato no encontrado")

    if usuario["rol"] == "restaurant_admin" and existente.data[0]["tenant_id"] != usuario["tenant_id"]:
        raise HTTPException(status_code=403, detail="No puedes eliminar platos de otro restaurante")

    supabase.table("platos").delete().eq("id", plato_id).execute()
    return {"mensaje": "Plato eliminado correctamente"}