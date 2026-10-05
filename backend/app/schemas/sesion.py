from pydantic import BaseModel


class MeRespuesta(BaseModel):
    id: str
    email: str | None
