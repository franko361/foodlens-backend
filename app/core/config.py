import os
import httpx
from dotenv import load_dotenv
from supabase import create_client, Client
from supabase.client import ClientOptions

load_dotenv()


def _requerida(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno {nombre}")
    return valor


SUPABASE_URL = _requerida("SUPABASE_URL")
SUPABASE_KEY = _requerida("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = _requerida("SUPABASE_SERVICE_KEY")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

# Orígenes permitidos por CORS (separados por coma). En producción agrega el dominio de Vercel.
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://192.168.42.92:3000",
    ).split(",")
    if o.strip()
]

# http2=False evita el error httpx.RemoteProtocolError: ConnectionTerminated
opciones = ClientOptions(httpx_client=httpx.Client(http2=False, timeout=30))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, options=opciones)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY, options=opciones)