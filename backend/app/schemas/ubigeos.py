from pydantic import BaseModel


class ProvinciaSalida(BaseModel):
    nombre: str
    distritos: list[str]


class DepartamentoSalida(BaseModel):
    nombre: str
    provincias: list[ProvinciaSalida]


class CatalogoUbigeos(BaseModel):
    fuente: str
    departamentos: list[DepartamentoSalida]
