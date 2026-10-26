from pydantic import BaseModel


class TraduccionRequest(BaseModel):
    textos: list[str]
    idioma_destino: str  # código corto: "en", "ru", "de", etc.