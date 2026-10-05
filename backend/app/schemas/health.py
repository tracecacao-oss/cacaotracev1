from pydantic import BaseModel


class SaludRespuesta(BaseModel):
    status: str
    version: str


class SaludBaseRespuesta(BaseModel):
    status: str
    postgis: str
