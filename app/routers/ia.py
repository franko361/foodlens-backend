import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from supabase import Client, create_client

from app.core.config import supabase, SUPABASE_URL, SUPABASE_KEY, opciones
from app.core.auth import require_restaurant_admin
from app.schemas.ia import PreguntaGeneral
from app.services.ia_service import gemini_client, hoy_lima, regenerar_si_toca

router = APIRouter()


@router.post("/ia/preguntar-general")
def preguntar_general(data: PreguntaGeneral):
    """
    Ruta PÚBLICA: chat único y flotante del restaurante.
    La IA tiene contexto de TODOS los platos activos + info del negocio,
    para responder cualquier pregunta (sobre un plato específico, comparaciones,
    o sobre el restaurante en general), usando solo datos reales.
    """
    supabase_publico: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=opciones)

    # 1. Buscar el tenant
    tenant_res = supabase_publico.table("tenants").select("*").eq("slug", data.tenant_slug).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")
    tenant = tenant_res.data[0]

    # 2. Traer TODOS los platos activos de ese restaurante (datos reales completos)
    platos_res = (
        supabase_publico.table("platos")
        .select("*")
        .eq("tenant_id", tenant["id"])
        .eq("estado", "activo")
        .execute()
    )
    platos = platos_res.data

    # 3. Armar el listado de platos como texto estructurado para el prompt
    lista_platos = "\n".join(
        f"- {p['nombre']} (S/ {p['precio']}): {p.get('descripcion') or 'sin descripción'}. "
        f"Calorías: {p.get('calorias_estimadas', 'no especificado')}."
        for p in platos
    )

    # 4. Armar el contexto completo (restaurante + menú real)
    contexto = f"""
Eres el asistente virtual de "{tenant['nombre']}", un negocio de alimentos.
SOLO puedes responder usando la información proporcionada a continuación.
Si no tienes la información para responder algo, dilo honestamente en vez de inventar datos.

Información del restaurante:
- Nombre: {tenant['nombre']}
- Dirección: {tenant.get('direccion') or 'No especificada'}
- Horario: {tenant.get('horario') or 'No especificado'}
- Historia / información adicional: {tenant.get('historia_restaurante') or 'No especificada'}

Menú disponible (información real y verificada):
{lista_platos or 'Aún no hay platos publicados.'}

Pregunta del cliente: {data.pregunta}

Responde de forma breve, amable y directa (máximo 6 líneas). No saludes ni digas
"Hola" al inicio de tu respuesta; ve directo a responder la pregunta, como en una
conversación que ya está en curso. Si la pregunta es sobre
un plato específico, usa exactamente los datos de arriba. Si preguntan por comparaciones
(ej. "¿cuál tiene menos calorías?"), compara usando los datos reales listados.
{f"IMPORTANTE: Responde siempre en {data.idioma}, sin importar el idioma de la pregunta." if data.idioma else ""}
"""

    # 5. Consultar a Gemini (con fallback entre modelos)
    modelos = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash"]
    texto_respuesta = None
    ultimo_error = None

    for modelo in modelos:
        for intento in range(2):  # hasta 2 intentos por modelo
            try:
                respuesta_ia = gemini_client.models.generate_content(model=modelo, contents=contexto)
                texto_respuesta = respuesta_ia.text
                if texto_respuesta:
                    break
            except Exception as e:
                ultimo_error = str(e)
                if "429" in ultimo_error:
                    break  # cuota agotada, pasa al siguiente modelo
                time.sleep(2 ** intento)  # espera 1s, 2s, 4s
        if texto_respuesta:
            break

    if not texto_respuesta:
        raise HTTPException(status_code=503, detail=f"Servicio no disponible: {ultimo_error}")

    # 6. Guardar en el historial (sin plato_id específico si es pregunta general)
    supabase_publico.table("consultas_ia").insert({
        "tenant_id": tenant["id"],
        "plato_id": data.plato_actual_id,
        "pregunta": data.pregunta,
        "respuesta": texto_respuesta,
    }, returning="minimal").execute()

    return {
        "restaurante": tenant["nombre"],
        "pregunta": data.pregunta,
        "respuesta": texto_respuesta,
        "sugerencias": tenant.get("sugerencias_chat_general") or [],
    }


@router.get("/tenant/{tenant_slug}/sugerencias-chat")
def get_sugerencias_chat(tenant_slug: str, background_tasks: BackgroundTasks):
    """Devuelve las sugerencias y la bienvenida guardadas (ruta pública).
    Si no se han regenerado hoy, la primera visita del día dispara la regeneración en segundo plano."""
    tenant = (
        supabase.table("tenants")
        .select("id, estado, sugerencias_chat_general, bienvenida_chat_general, sugerencias_actualizadas_en")
        .eq("slug", tenant_slug)
        .execute()
    )
    if not tenant.data:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    datos = tenant.data[0]
    fecha = datos.get("sugerencias_actualizadas_en")
    if datos["estado"] == "activo" and fecha != hoy_lima():
        background_tasks.add_task(regenerar_si_toca, datos["id"], fecha)

    return {
        "sugerencias": datos.get("sugerencias_chat_general") or [],
        "bienvenida": datos.get("bienvenida_chat_general"),
    }


@router.get("/admin/consultas")
def listar_mis_consultas(usuario: dict = Depends(require_restaurant_admin)):
    """Lista el historial de consultas de IA del tenant del usuario autenticado"""
    query = supabase.table("consultas_ia").select("*")

    if usuario["rol"] == "restaurant_admin":
        query = query.eq("tenant_id", usuario["tenant_id"])

    response = query.order("created_at", desc=True).execute()
    return response.data