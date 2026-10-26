import json
from datetime import datetime, timedelta, timezone

from google import genai

from app.core.config import supabase_admin, GEMINI_API_KEY

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Perú (UTC-5) no usa horario de verano
LIMA = timezone(timedelta(hours=-5))
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def hoy_lima() -> str:
    """Fecha de hoy en Lima, formato YYYY-MM-DD"""
    return datetime.now(LIMA).date().isoformat()


def generar_sugerencias_generales(tenant: dict, platos: list, anteriores: dict | None = None) -> dict:
    """
    Genera, en una sola llamada:
    1. Un mensaje de bienvenida adaptado al tipo de negocio
    2. 4 sugerencias de preguntas breves, variadas (menú + negocio)
    Si recibe `anteriores`, le pide a Gemini que no las repita.
    """
    lista_platos = ", ".join(p["nombre"] for p in platos) or "Aún sin productos publicados"
    ahora = datetime.now(LIMA)

    contexto_anterior = ""
    if anteriores and isinstance(anteriores.get("sugerencias"), list):
        contexto_anterior = (
            "\nContenido anterior (NO lo repitas; genera un saludo y preguntas distintos, "
            "con otro enfoque):\n"
            f"- Bienvenida: {anteriores.get('bienvenida') or 'ninguna'}\n"
            f"- Sugerencias: {', '.join(str(s) for s in anteriores['sugerencias'])}\n"
        )

    prompt = f"""
Analiza este negocio de alimentos y genera contenido para su asistente de chat.
Responde ÚNICAMENTE con un objeto JSON con esta estructura exacta:

{{
  "bienvenida": "mensaje de bienvenida",
  "sugerencias": ["pregunta 1", "pregunta 2", "pregunta 3", "pregunta 4"]
}}

Para "bienvenida": un saludo breve (máximo 3 líneas) que invite al cliente a preguntar
sobre el menú y el negocio. IMPORTANTE: usa el término correcto según el tipo de negocio
que se infiere del nombre y los productos (ej. "platos" para un restaurante, "bebidas" o
"café" para una cafetería, "postres" para una pastelería, "helados" para una heladería).
No asumas que es un restaurante de comida si no lo parece.

Para "sugerencias": 4 preguntas breves (máximo 6 palabras) variadas: sobre el menú/productos
y sobre el negocio (horario, historia), adaptadas al tipo de negocio real.

Hoy es {DIAS[ahora.weekday()]} {ahora.date().isoformat()}. Puedes variar el enfoque según el
día si es natural, pero NO inventes promociones ni datos que no estén abajo.
{contexto_anterior}
Nombre del negocio: {tenant.get('nombre')}
Productos disponibles: {lista_platos}
Historia/información: {tenant.get('historia_restaurante') or 'No especificada'}
"""
    for modelo in ["gemini-3.6-flash", "gemini-3.5-flash"]:
        try:
            respuesta = gemini_client.models.generate_content(model=modelo, contents=prompt)
            texto = respuesta.text.strip()
            if texto.startswith("```"):
                texto = texto.strip("`").replace("json", "", 1).strip()
            resultado = json.loads(texto)
            if isinstance(resultado, dict):
                return resultado
        except Exception:
            continue
    return None


def regenerar_sugerencias_del_tenant(tenant_id: str) -> bool:
    """Genera y guarda bienvenida y sugerencias del tenant. Devuelve True si se guardaron."""
    tenant_res = supabase_admin.table("tenants").select("*").eq("id", tenant_id).execute()
    if not tenant_res.data:
        return False
    tenant = tenant_res.data[0]

    platos_res = (
        supabase_admin.table("platos")
        .select("nombre")
        .eq("tenant_id", tenant_id)
        .eq("estado", "activo")
        .execute()
    )

    anteriores = {
        "bienvenida": tenant.get("bienvenida_chat_general"),
        "sugerencias": tenant.get("sugerencias_chat_general"),
    }
    sugerencias = generar_sugerencias_generales(tenant, platos_res.data, anteriores)
    if not sugerencias:
        return False

    supabase_admin.table("tenants").update({
        "sugerencias_chat_general": sugerencias.get("sugerencias"),
        "bienvenida_chat_general": sugerencias.get("bienvenida"),
        "sugerencias_actualizadas_en": hoy_lima(),
    }).eq("id", tenant_id).execute()
    return True


def regenerar_si_toca(tenant_id: str, fecha_anterior: str | None):
    """
    Regeneración diaria perezosa: la primera petición del día "reclama" el turno
    marcando hoy en la base de datos (UPDATE condicional = candado atómico).
    Si Gemini falla, devuelve la marca anterior para que se reintente en otra visita.
    """
    hoy = hoy_lima()
    reclamado = (
        supabase_admin.table("tenants")
        .update({"sugerencias_actualizadas_en": hoy})
        .eq("id", tenant_id)
        .or_(f"sugerencias_actualizadas_en.is.null,sugerencias_actualizadas_en.lt.{hoy}")
        .execute()
    )
    if not reclamado.data:
        return  # otra petición ya la tomó o ya está al día

    try:
        ok = regenerar_sugerencias_del_tenant(tenant_id)
    except Exception as e:
        print("Error regenerando sugerencias:", e)
        ok = False

    if not ok:
        supabase_admin.table("tenants").update(
            {"sugerencias_actualizadas_en": fecha_anterior}
        ).eq("id", tenant_id).execute()