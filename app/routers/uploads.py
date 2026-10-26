import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.config import supabase, supabase_admin
from app.core.auth import require_restaurant_admin

router = APIRouter()


# ---------- Subida de imágenes de platos (Supabase Storage) ----------

@router.post("/admin/platos/{plato_id}/imagen")
async def subir_imagen_plato(
    plato_id: str,
    file: UploadFile = File(...),
    usuario: dict = Depends(require_restaurant_admin),
):
    """Sube una imagen para un plato específico y actualiza su imagen_url"""
    # Verificar que el plato pertenece al tenant del usuario
    existente = supabase.table("platos").select("tenant_id, imagen_url").eq("id", plato_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Plato no encontrado")
    if usuario["rol"] == "restaurant_admin" and existente.data[0]["tenant_id"] != usuario["tenant_id"]:
        raise HTTPException(status_code=403, detail="No puedes editar platos de otro restaurante")

    # Generar un nombre único para el archivo
    extension = file.filename.split(".")[-1]
    nombre_archivo = f"{plato_id}-{uuid.uuid4().hex[:8]}.{extension}"

    contenido = await file.read()
    if len(contenido) > 1 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no debe superar 1 MB")

    # Subir a Supabase Storage
    supabase.storage.from_("Platos-imagenes").upload(
        nombre_archivo,
        contenido,
        {"content-type": file.content_type},
    )

    # Obtener la URL pública del archivo recién subido
    url_publica = supabase.storage.from_("Platos-imagenes").get_public_url(nombre_archivo)

    # Guardar esa URL en el plato
    supabase.table("platos").update({"imagen_url": url_publica}).eq("id", plato_id).execute()
    url_anterior = existente.data[0].get("imagen_url")
    if url_anterior:
        try:
            supabase.storage.from_("Platos-imagenes").remove(
                [url_anterior.split("/")[-1].split("?")[0]]
            )
        except Exception as e:
            print("No se pudo borrar la imagen anterior:", e)

    return {"imagen_url": url_publica}


# ---------- Subida de logo de tenants (Supabase Storage) ----------
@router.post("/admin/tenant/logo")
async def subir_logo_tenant(
    file: UploadFile = File(...),
    usuario: dict = Depends(require_restaurant_admin),
):
    """Sube el logo del restaurante del usuario a Storage y guarda su URL en tenants.logo_url"""
    if usuario["rol"] != "restaurant_admin":
        raise HTTPException(status_code=403, detail="Solo un admin de restaurante puede cambiar su logo")

    tenant_id = usuario["tenant_id"]

    contenido = await file.read()
    if len(contenido) > 1024 * 1024:
        raise HTTPException(status_code=400, detail="El logo no debe superar 1 MB")

    extension = file.filename.split(".")[-1]
    nombre_archivo = f"{tenant_id}-{uuid.uuid4().hex[:8]}.{extension}"

    # Se usa supabase_admin porque el bucket nuevo aún no tiene política de subida
    supabase_admin.storage.from_("tenants-logos").upload(
        nombre_archivo,
        contenido,
        {"content-type": file.content_type},
    )
    url_publica = supabase_admin.storage.from_("tenants-logos").get_public_url(nombre_archivo)

    # Guardar la URL y borrar el logo anterior si estaba en Storage
    anterior = supabase.table("tenants").select("logo_url").eq("id", tenant_id).execute()
    supabase.table("tenants").update({"logo_url": url_publica}).eq("id", tenant_id).execute()

    url_anterior = anterior.data[0].get("logo_url") if anterior.data else None
    if url_anterior and "tenants-logos" in url_anterior:
        try:
            supabase_admin.storage.from_("tenants-logos").remove(
                [url_anterior.split("/")[-1].split("?")[0]]
            )
        except Exception as e:
            print("No se pudo borrar el logo anterior:", e)

    return {"logo_url": url_publica}


# ---------- Subida de modelos 3D de platos (Supabase Storage) ----------
@router.post("/admin/platos/{plato_id}/modelo3d")
async def subir_modelo3d_plato(
    plato_id: str,
    file: UploadFile = File(...),
    usuario: dict = Depends(require_restaurant_admin),
):
    """Sube un modelo 3D (.glb) para un plato específico y actualiza su modelo_3d_url"""
    existente = supabase.table("platos").select("tenant_id, modelo_3d_url").eq("id", plato_id).execute()
    if not existente.data:
        raise HTTPException(status_code=404, detail="Plato no encontrado")
    if usuario["rol"] == "restaurant_admin" and existente.data[0]["tenant_id"] != usuario["tenant_id"]:
        raise HTTPException(status_code=403, detail="No puedes editar platos de otro restaurante")

    extension = file.filename.split(".")[-1]
    if extension.lower() != "glb":
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .glb")

    nombre_archivo = f"{plato_id}-{uuid.uuid4().hex[:8]}.glb"
    contenido = await file.read()
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El modelo 3D no debe superar 10 MB")

    supabase.storage.from_("platos-modelos3d").upload(
        nombre_archivo,
        contenido,
        {"content-type": "model/gltf-binary"},
    )

    url_publica = supabase.storage.from_("platos-modelos3d").get_public_url(nombre_archivo)

    supabase.table("platos").update({"modelo_3d_url": url_publica}).eq("id", plato_id).execute()
    url_anterior = existente.data[0].get("modelo_3d_url")
    if url_anterior:
        try:
            supabase.storage.from_("platos-modelos3d").remove(
                [url_anterior.split("/")[-1].split("?")[0]]
            )
        except Exception as e:
            print("No se pudo borrar el modelo anterior:", e)

    return {"modelo_3d_url": url_publica}