from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS
from app.routers import (
    auth,
    categorias,
    ia,
    platos,
    superadmin,
    tenants,
    traduccion,
    uploads,
    usuarios,
)

app = FastAPI(title="FoodLens API")

# Permitir que el frontend (Next.js) pueda hacer peticiones a este backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categorias.router)
app.include_router(platos.router)
app.include_router(uploads.router)
app.include_router(superadmin.router)
app.include_router(tenants.router)
app.include_router(usuarios.router)
app.include_router(ia.router)
app.include_router(traduccion.router)


# ---------- Ruta pública ----------

@app.get("/")
def read_root():
    return {"mensaje": "FoodLens API funcionando correctamente 🚀"}
