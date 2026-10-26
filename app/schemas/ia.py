from pydantic import BaseModel


class PreguntaGeneral(BaseModel):
    tenant_slug: str
    pregunta: str
    idioma: str | None = None
    plato_actual_id: str | None = None  # opcional: si el cliente estaba viendo un plato específico