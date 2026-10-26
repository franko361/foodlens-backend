from fastapi import APIRouter, Depends, HTTPException

from app.core.config import supabase
from app.core.auth import require_super_admin

router = APIRouter()


@router.get("/admin/tenants/buscar")
def buscar_tenants(
    q: str = "",
    estado: str = "",
    orden: str = "recientes",  # "recientes" | "antiguos" | "mas_consultas"
    usuario: dict = Depends(require_super_admin),
):
    """Busca/filtra/ordena tenants. Solo super_admin."""
    query = supabase.table("tenants").select("*")
    if estado:
        query = query.eq("estado", estado)
    response = query.execute()
    resultados = response.data

    if q:
        q_lower = q.lower()
        resultados = [t for t in resultados if q_lower in t["nombre"].lower()]

    if orden == "mas_consultas":
        consultas = supabase.table("consultas_ia").select("tenant_id").execute()
        conteo = {}
        for c in consultas.data:
            conteo[c["tenant_id"]] = conteo.get(c["tenant_id"], 0) + 1
        resultados.sort(key=lambda t: conteo.get(t["id"], 0), reverse=True)
    elif orden == "antiguos":
        resultados.sort(key=lambda t: t.get("created_at", ""))
    else:  # "recientes" por defecto
        resultados.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    return resultados


@router.get("/admin/tenants/{tenant_id}/detalle")
def detalle_tenant(tenant_id: str, usuario: dict = Depends(require_super_admin)):
    """Vista completa de un tenant: datos, uso, y actividad reciente."""
    tenant = supabase.table("tenants").select("*").eq("id", tenant_id).execute()
    if not tenant.data:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    platos = supabase.table("platos").select("*").eq("tenant_id", tenant_id).execute()
    categorias = supabase.table("categorias").select("*").eq("tenant_id", tenant_id).execute()
    consultas = (
        supabase.table("consultas_ia")
        .select("id, created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .execute()
    )
    historial = (
        supabase.table("historial_tenants")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .execute()
    )

    archivos_subidos = len([p for p in platos.data if p.get("imagen_url")]) + \
                       len([p for p in platos.data if p.get("modelo_3d_url")])

    return {
        "tenant": tenant.data[0],
        "total_platos": len(platos.data),
        "total_categorias": len(categorias.data),
        "total_consultas_ia": len(consultas.data),
        "ultima_actividad": consultas.data[0]["created_at"] if consultas.data else None,
        "archivos_subidos": archivos_subidos,
        "historial": historial.data,
    }


@router.get("/admin/metricas-globales")
def metricas_globales(usuario: dict = Depends(require_super_admin)):
    """Métricas agregadas de toda la plataforma, incluyendo ranking y uso de almacenamiento."""
    tenants = supabase.table("tenants").select("id, nombre, estado").execute()
    platos = supabase.table("platos").select("id, tenant_id, modelo_3d_url, imagen_url").execute()
    consultas = supabase.table("consultas_ia").select("id, tenant_id").execute()

    # Ranking: tenants con más consultas a la IA (top 5)
    conteo_por_tenant = {}
    for c in consultas.data:
        conteo_por_tenant[c["tenant_id"]] = conteo_por_tenant.get(c["tenant_id"], 0) + 1

    mapa_nombres = {t["id"]: t["nombre"] for t in tenants.data}
    ranking = sorted(
        [{"tenant_id": tid, "nombre": mapa_nombres.get(tid, "—"), "consultas": count}
         for tid, count in conteo_por_tenant.items()],
        key=lambda x: x["consultas"],
        reverse=True,
    )[:5]

    # Uso de "almacenamiento" aproximado: cantidad de archivos subidos (fotos + modelos 3D)
    total_imagenes = len([p for p in platos.data if p.get("imagen_url")])
    total_modelos_3d = len([p for p in platos.data if p.get("modelo_3d_url")])

    return {
        "total_tenants": len(tenants.data),
        "tenants_activos": len([t for t in tenants.data if t["estado"] == "activo"]),
        "tenants_pendientes": len([t for t in tenants.data if t["estado"] == "pendiente"]),
        "tenants_suspendidos": len([t for t in tenants.data if t["estado"] == "suspendido"]),
        "total_platos": len(platos.data),
        "total_imagenes_subidas": total_imagenes,
        "total_modelos_3d": total_modelos_3d,
        "total_consultas_ia": len(consultas.data),
        "ranking_actividad": ranking,
    }