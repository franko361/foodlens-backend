import deepl
from fastapi import APIRouter, HTTPException

from app.core.config import supabase, DEEPL_API_KEY
from app.schemas.traduccion import TraduccionRequest

router = APIRouter()

deepl_client = deepl.Translator(DEEPL_API_KEY)

# Códigos de idioma de nuestra app -> código que espera DeepL
DEEPL_CODIGOS = {
    "en": "EN-US", "pt": "PT-BR", "fr": "FR", "de": "DE",
    "it": "IT", "zh": "ZH", "ja": "JA", "ko": "KO", "ru": "RU",
}


@router.post("/traducir")
def traducir_textos(data: TraduccionRequest):
    """
    Traduce una lista de textos al idioma indicado, usando ÚNICAMENTE DeepL.
    1. Busca cada texto en la tabla `traducciones` (estructura JSONB).
    2. Solo traduce con DeepL los que faltan.
    3. Guarda las traducciones nuevas con `upsert_traduccion`.
    """
    if not data.textos:
        return {"traducciones": []}

    if any(len(t) > 2000 for t in data.textos):
        raise HTTPException(status_code=400, detail="Texto muy largo")

    codigo_deepl = DEEPL_CODIGOS.get(data.idioma_destino)
    if not codigo_deepl:
        raise HTTPException(
            status_code=400,
            detail=f"Idioma '{data.idioma_destino}' no soportado por DeepL"
        )

    resultado = [None] * len(data.textos)
    pendientes_indices = []
    pendientes_textos = []

    textos_no_vacios = [t for t in data.textos if t]
    existentes = (
        supabase.table("traducciones")
        .select("texto_original, traducciones")
        .in_("texto_original", textos_no_vacios)
        .execute()
    )
    mapa_existente = {row["texto_original"]: row["traducciones"] for row in existentes.data}

    for i, texto in enumerate(data.textos):
        if not texto:
            resultado[i] = texto
            continue
        traducciones_guardadas = mapa_existente.get(texto, {})
        if data.idioma_destino in traducciones_guardadas:
            resultado[i] = traducciones_guardadas[data.idioma_destino]
        else:
            pendientes_indices.append(i)
            pendientes_textos.append(texto)

    if not pendientes_textos:
        return {"traducciones": resultado}

    # Traducir con DeepL solo los textos únicos que faltan, en tandas de 50
    unicos = list(dict.fromkeys(pendientes_textos))
    mapa_nuevo = {}
    try:
        for i in range(0, len(unicos), 50):
            lote = unicos[i:i + 50]
            resultados_deepl = deepl_client.translate_text(lote, target_lang=codigo_deepl)
            for orig, r in zip(lote, resultados_deepl):
                mapa_nuevo[orig] = r.text
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de DeepL: {str(e)}")

    # Rellenar el resultado primero, así la respuesta no depende del guardado
    for idx in pendientes_indices:
        resultado[idx] = mapa_nuevo[data.textos[idx]]

    # Guardar en la base de datos (si falla, no rompe la respuesta)
    for texto, traduccion in mapa_nuevo.items():
        try:
            supabase.rpc("upsert_traduccion", {
                "p_texto": texto,
                "p_idioma": data.idioma_destino,
                "p_valor": traduccion,
            }).execute()
        except Exception as e:
            print("Error guardando traducción:", e)

    return {"traducciones": resultado}