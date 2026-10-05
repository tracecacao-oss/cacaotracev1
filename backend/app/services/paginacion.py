"""Listados paginados: ?pagina=1&por_pagina=25, máximo 100."""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Paginacion:
    pagina: int
    por_pagina: int


def parametros_paginacion(
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 25,
) -> Paginacion:
    return Paginacion(pagina=pagina, por_pagina=por_pagina)


ParametrosPaginacion = Annotated[Paginacion, Depends(parametros_paginacion)]


def paginar(sesion: Session, consulta: Select, paginacion: Paginacion) -> tuple[list[Any], int]:
    total = sesion.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    filas = sesion.execute(
        consulta.limit(paginacion.por_pagina).offset((paginacion.pagina - 1) * paginacion.por_pagina)
    ).all()
    return filas, total
