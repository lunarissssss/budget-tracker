"""Kurs USD/IDR (Frankfurter/ECB, cadangan open.er-api.com) dan harga token (API publik Bitget, tanpa API key)."""
import asyncio, logging, os
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from . import models as m
from .db import SessionLocal
from .util import today

log = logging.getLogger("rates")
STABLE = {"USDT", "USDC", "USD", "DAI", "FDUSD"}  # dianggap 1 USD
INTERVAL = max(1, int(os.getenv("RATE_REFRESH_MINUTES", "15"))) * 60
FX_SOURCES = ["https://api.frankfurter.dev/v1/latest?base=USD&symbols=IDR", "https://open.er-api.com/v6/latest/USD"]
BITGET = "https://api.bitget.com/api/v2/spot/market/tickers"


def latest_row(db, key):
    return db.scalars(select(m.Rate).where(m.Rate.key == key).order_by(m.Rate.updated_at.desc())).first()


def latest(db, key):
    r = latest_row(db, key)
    return r.value if r else None


def save(db, key, value, day):
    r = db.scalars(select(m.Rate).where(m.Rate.key == key, m.Rate.day == day)).first()
    if r:
        r.value, r.updated_at = value, datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        db.add(m.Rate(key=key, day=day, value=value, updated_at=datetime.now(timezone.utc).replace(tzinfo=None)))


async def fx_usd_idr(c):
    for url in FX_SOURCES:
        try:
            r = await c.get(url)
            r.raise_for_status()
            return float(r.json()["rates"]["IDR"])
        except Exception as e:
            log.warning("fx %s gagal: %s", url, e)
    return None


async def token_usdt(c, symbol):
    try:
        r = await c.get(BITGET, params={"symbol": symbol.upper() + "USDT"})
        r.raise_for_status()
        j = r.json()
        if j.get("code") != "00000":
            return None
        d = j["data"]
        d = d[0] if isinstance(d, list) else d
        return float(d["lastPr"])
    except Exception as e:
        log.warning("harga %s gagal: %s", symbol, e)
        return None


async def refresh():
    with SessionLocal() as db:
        symbols = {h.symbol for h in db.scalars(select(m.Holding))} - STABLE
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "budget-tracker"}) as c:
        fx = await fx_usd_idr(c)
        prices = {s: await token_usdt(c, s) for s in symbols}
    with SessionLocal() as db:
        d = today()
        if fx:
            save(db, "USDIDR", fx, d)
        for s, p in prices.items():
            if p:
                save(db, "TOKEN:" + s, p, d)
        db.commit()
    return fx, prices


async def loop():
    while True:
        try:
            await refresh()
        except Exception:
            log.exception("refresh gagal")
        await asyncio.sleep(INTERVAL)
