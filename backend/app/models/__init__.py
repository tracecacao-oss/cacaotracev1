"""Modelos SQLAlchemy. Cada parte agrega aquí sus tablas; Alembic las detecta desde Base.metadata."""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres de restricciones estables para que las migraciones autogeneradas sean reproducibles.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


class ConFechas:
    """creado_en y actualizado_en en UTC; la interfaz las muestra en hora de Lima."""

    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


from app.models.acceso import (  # noqa: E402
    ESTADOS_AFILIACION,
    ESTADOS_COOPERATIVA,
    ORIGENES_CONSENTIMIENTO,
    ROLES,
    ROLES_PERSONAL,
    Afiliacion,
    Auditoria,
    Cooperativa,
    Perfil,
    Productor,
)
from app.models.declaracion import (  # noqa: E402
    DeclaracionProducto,
    DeclaracionProductor,
)
from app.models.dex import (  # noqa: E402
    Certificacion,
    ConfiguracionPlataforma,
    Dex,
)
from app.models.diligencia import (  # noqa: E402
    ActuacionDiligencia,
    ActuacionProductor,
    PoliticaOrganizacion,
)
from app.models.exportacion import (  # noqa: E402
    DeclaracionAduanera,
    Importador,
    Lote,
    LoteAsignacion,
    LoteGenealogia,
    OrdenCompra,
    Recomprobacion,
)
from app.models.habilitacion import (  # noqa: E402
    AnalisisCobertura,
    DecisionHabilitacion,
    ExencionDocumento,
    VisitaCampo,
)
from app.models.imagenes import (  # noqa: E402
    ConsumoImagenes,
    ImagenParcela,
    RevisionImagenes,
)
from app.models.legalidad import (  # noqa: E402
    ParcelaIncidencia,
    ParcelaVariable,
)
from app.models.padron import (  # noqa: E402
    ESTADOS_HABILITACION,
    ESTADOS_MIDAGRI,
    TIPOS_DOCUMENTO,
    TIPOS_LEGALES,
    Documento,
    LimiteDistrital,
    Parcela,
    Superposicion,
)
from app.models.proceso import (  # noqa: E402
    Calidad,
    Corrida,
    CorridaEtapa,
    CorridaTanda,
    Dpp,
    PlantillaEtapa,
    TandaFinal,
)
from app.models.recepcion import (  # noqa: E402
    ConfiguracionCooperativa,
    Correlativo,
    DecisionTanda,
    Dop,
    Lugar,
    Tanda,
)

__all__ = [
    "ActuacionDiligencia",
    "ActuacionProductor",
    "PoliticaOrganizacion",
    "DeclaracionProducto",
    "DeclaracionProductor",
    "Certificacion",
    "ConfiguracionPlataforma",
    "Dex",
    "DeclaracionAduanera",
    "Importador",
    "Lote",
    "LoteAsignacion",
    "LoteGenealogia",
    "OrdenCompra",
    "Recomprobacion",
    "Calidad",
    "Corrida",
    "CorridaEtapa",
    "CorridaTanda",
    "Dpp",
    "PlantillaEtapa",
    "TandaFinal",
    "ConsumoImagenes",
    "ImagenParcela",
    "ParcelaIncidencia",
    "ParcelaVariable",
    "RevisionImagenes",
    "ConfiguracionCooperativa",
    "Correlativo",
    "DecisionTanda",
    "Dop",
    "Lugar",
    "Tanda",
    "ESTADOS_HABILITACION",
    "ESTADOS_MIDAGRI",
    "TIPOS_DOCUMENTO",
    "TIPOS_LEGALES",
    "AnalisisCobertura",
    "DecisionHabilitacion",
    "ExencionDocumento",
    "VisitaCampo",
    "Documento",
    "LimiteDistrital",
    "Parcela",
    "Superposicion",
    "ESTADOS_AFILIACION",
    "ESTADOS_COOPERATIVA",
    "ORIGENES_CONSENTIMIENTO",
    "ROLES",
    "ROLES_PERSONAL",
    "Afiliacion",
    "Auditoria",
    "Base",
    "ConFechas",
    "Cooperativa",
    "Perfil",
    "Productor",
]
