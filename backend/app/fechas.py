"""Fechas de referencia: las reglas de vencimiento y vigencia se cuentan en días de Lima."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LIMA = ZoneInfo("America/Lima")


def ahora() -> datetime:
    return datetime.now(UTC)


def hoy_lima() -> date:
    return datetime.now(LIMA).date()


def dia_lima(momento: datetime) -> date:
    return momento.astimezone(LIMA).date()
