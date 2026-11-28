"""Pure offline candidate. Shape qualification only; never authorizes ingestion."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", re.ASCII)
_PRICE = re.compile(r"[0-9]{1,6}(?:\.[0-9]{1,12})?", re.ASCII)

class Rejected(ValueError):
    """Fixed diagnostic codes only, never provider text."""

@dataclass(frozen=True)
class Bar:
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

@dataclass(frozen=True)
class ShapeQualified:
    bars: tuple[Bar, ...]
    provider: str = "TWELVE_DATA"
    symbol: str = "EUR/USD"
    interval: str = "1day"
    session_timezone: str = "Australia/Sydney"
    status: str = "OFFLINE_SHAPE_ONLY"
    market_admitted: bool = False

def _date(value):
    if type(value) is not str or not _DATE.fullmatch(value):
        raise Rejected("DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Rejected("DATE_INVALID") from None

def _price(value):
    if type(value) is not str or len(value) > 19 or not _PRICE.fullmatch(value):
        raise Rejected("PRICE_INVALID")
    result = Decimal(value)
    if result <= 0:
        raise Rejected("PRICE_INVALID")
    return result

def qualify(payload, *, first_day, last_day, completed_before):
    """No network, no calendar completeness, no timestamp/volume invention.

    Caller-supplied completed_before is an EXCLUSIVE local session-date bound,
    not proof of actual market close. Dates are provider dates, not UTC instants.
    """
    if any(type(x) is not date for x in (first_day,last_day,completed_before)):
        raise Rejected("SCOPE_INVALID")
    if not first_day <= last_day < completed_before or not 150 <= (last_day-first_day).days <= 190:
        raise Rejected("SCOPE_INVALID")
    if type(payload) is not dict:
        raise Rejected("ENVELOPE_INVALID")
    if payload.get("status") != "ok" or any(k in payload for k in ("code","message","error")):
        raise Rejected("PROVIDER_NOT_OK")
    meta=payload.get("meta")
    if type(meta) is not dict or meta.get("symbol") != "EUR/USD" or meta.get("interval") != "1day":
        raise Rejected("IDENTITY_INVALID")
    # FX-specific metadata availability must be checked against a real response.
    if meta.get("currency_base") != "EUR" or meta.get("currency_quote") != "USD":
        raise Rejected("IDENTITY_INVALID")
    if "exchange_timezone" in meta and meta["exchange_timezone"] != "Australia/Sydney":
        raise Rejected("TIMEZONE_UNVERIFIED")
    values=payload.get("values")
    if type(values) is not list or not 100 <= len(values) <= 160:
        raise Rejected("COUNT_INVALID")
    bars=[]
    previous=None
    for row in values:
        if type(row) is not dict:
            raise Rejected("ROW_INVALID")
        d=_date(row.get("datetime"))
        if not first_day <= d <= last_day:
            raise Rejected("DATE_OUTSIDE_SCOPE")
        if previous is not None and d >= previous:
            raise Rejected("DATE_ORDER")
        previous=d
        o,h,l,c=(_price(row.get(k)) for k in ("open","high","low","close"))
        if l > min(o,c) or h < max(o,c) or h < l:
            raise Rejected("OHLC_ORDER")
        bars.append(Bar(d,o,h,l,c))
    if (bars[0].session_date-bars[-1].session_date).days < 150:
        raise Rejected("SPAN_INVALID")
    # Descending provider order verified first, then reverse for analysis.
    return ShapeQualified(tuple(reversed(bars)))
