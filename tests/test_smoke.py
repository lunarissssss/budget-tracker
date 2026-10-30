import asyncio, io, os, tempfile
from pathlib import Path

os.environ.update(DATA_DIR=tempfile.mkdtemp(), RATES_DISABLED="1", STRICT_I18N="1")
import httpx, pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select

from app import models as m, rates, services as s
from app.db import SessionLocal
from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as cl:
        yield cl


def test_pages_both_languages(c):
    for lang in ("id", "en"):
        c.cookies.set("lang", lang)
        for p in ("/", "/transactions", "/transactions?status=planned", "/add", "/rekap", "/rekap?view=category", "/rekap?view=account", "/assets", "/settings", "/healthz"):
            r = c.get(p)
            assert r.status_code == 200, (lang, p, r.text[:300])
    c.cookies.set("lang", "id")


def test_flow(c):
    # periode: income + landing Seabank
    r = c.post("/settings/period", data=dict(pid="1", name="Oktober", start="2026-09-30", end="2026-10-30", income="9.873.397", landing_id="1"))
    assert r.status_code == 200
    # transaksi
    c.post("/tx", data=dict(amount="729.515", date="2026-09-30", status="paid", category_id="5", account_id="1", description="Credit Card"))
    c.post("/tx", data=dict(amount="175.000", date="2026-09-30", status="paid", category_id="6", account_id="4", description="Cons"))
    c.post("/tx", data=dict(amount="1.500.000", status="planned", category_id="3", description="Bayar Kos", recurring="1"))
    c.post("/quick/1")
    with SessionLocal() as db:
        per = s.current_period(db, 1)
        sm = s.summary(db, per)
        assert sm["paid"] == 729515 + 175000 + 10000 and sm["planned"] == 1500000
        assert sm["net"] == 9873397 - sm["paid"] - sm["planned"]
    # bayar rencana
    with SessionLocal() as db:
        pid = db.scalars(select(m.Transaction).where(m.Transaction.status == "planned")).first().id
    c.post(f"/tx/{pid}/pay", data=dict(account_id="1", date="2026-10-01"))
    # split ke ShopeePay (2) dan BCA (5)
    c.post("/assets/split", data={"amt_2": "500.000", "amt_5": "2.000.000", "amt_3": ""})
    with SessionLocal() as db:
        per = s.current_period(db, 1)
        sm = s.summary(db, per)
        assert sm["moved"] == 2500000 and sm["unmoved"] == 9873397 - 2500000
        b = {x["a"].name: x for x in s.balances(db)}
        assert b["Seabank"]["balance"] == 9873397 - 2500000 - (729515 + 10000 + 1500000)
        assert b["ShopeePay"]["balance"] == 500000 and b["BCA"]["balance"] == 2000000
        assert b["Krom Bank"]["balance"] == -175000
    # split ulang menimpa, bukan menambah
    c.post("/assets/split", data={"amt_2": "300.000"})
    with SessionLocal() as db:
        assert s.summary(db, s.current_period(db, 1))["moved"] == 300000 + 2000000
    # transfer manual + rekonsiliasi
    c.post("/assets/transfer", data=dict(from_id="5", to_id="3", amount="100.000", note="tes"))
    with SessionLocal() as db:
        assert {x["a"].name: x for x in s.balances(db)}["GoPay"]["balance"] == 100000
    c.post("/assets/reconcile/3", data=dict(actual="250.000"))
    with SessionLocal() as db:
        assert {x["a"].name: x for x in s.balances(db)}["GoPay"]["balance"] == 250000
    # periode baru menyalin rencana berulang
    c.post("/settings/period", data=dict(name="Nov", start="2026-10-31", end="2026-11-30", income="9.000.000", landing_id="1", copy_recurring="1"))
    with SessionLocal() as db:
        new = db.scalars(select(m.Period).where(m.Period.name == "Nov")).first()
        xs = db.scalars(select(m.Transaction).where(m.Transaction.period_id == new.id)).all()
        assert [(x.description, x.status, x.amount) for x in xs] == [("Bayar Kos", "planned", 1500000)]
    c.get("/period/1")  # kembali ke Oktober


def test_daily_and_groups(c):
    with SessionLocal() as db:
        bars, mx = s.daily(db, s.current_period(db, 1))
        assert len(bars) == 31 and mx == 1_500_000
        assert any(b["pk"] for b in bars)
        assert s.by_category(db, s.current_period(db, 1))


def test_crypto_value(c):
    c.post("/assets/holding", data=dict(symbol="usdt", quantity="100"))
    c.post("/assets/holding", data=dict(symbol="BTC", quantity="0,01", manual_usd="60000"))
    with SessionLocal() as db:
        rates.save(db, "USDIDR", 16000.0, s.today())
        db.commit()
        ct = s.crypto_total(db)
        assert ct["usd"] == pytest.approx(100 + 600) and ct["idr"] == 11_200_000
        rates.save(db, "TOKEN:BTC", 70000.0, s.today())  # harga otomatis menang atas manual
        db.commit()
        assert s.crypto_total(db)["usd"] == pytest.approx(100 + 700)
    assert c.get("/assets").status_code == 200


def test_exports(c):
    r = c.get("/export?fmt=csv&scope=all")
    assert r.status_code == 200 and "Credit Card" in r.content.decode("utf-8-sig")
    wb = load_workbook(io.BytesIO(c.get("/export?fmt=xlsx&scope=period").content))
    assert {"Transactions", "Summary", "Daily", "Accounts", "Crypto"} <= set(wb.sheetnames)
    assert wb["Transactions"].max_row > 3


def test_rate_parsers():
    def handler(req):
        if "frankfurter" in str(req.url):
            return httpx.Response(200, json={"rates": {"IDR": 16250.5}})
        if "bitget" in str(req.url):
            return httpx.Response(200, json={"code": "00000", "data": [{"symbol": "BTCUSDT", "lastPr": "67123.4"}]})
        return httpx.Response(500)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cl:
            return await rates.fx_usd_idr(cl), await rates.token_usdt(cl, "btc")

    assert asyncio.run(go()) == (16250.5, 67123.4)

    async def fail():  # sumber utama gagal -> pakai cadangan
        calls = []

        def h(req):
            calls.append(str(req.url))
            return httpx.Response(500) if "frankfurter" in str(req.url) else httpx.Response(200, json={"rates": {"IDR": 16000}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as cl:
            return await rates.fx_usd_idr(cl), len(calls)

    assert asyncio.run(fail()) == (16000.0, 2)


def test_auth(monkeypatch, c):
    import app.main as mm
    monkeypatch.setattr(mm, "PASSWORD", "rahasia")
    assert c.get("/").status_code == 401
    assert c.get("/healthz").status_code == 200
    assert c.get("/", auth=("x", "rahasia")).status_code == 200
    assert c.get("/", auth=("x", "salah")).status_code == 401


XLSX = Path("/mnt/user-data/uploads/Journal_Keuangan_Bulanan.xlsx")


@pytest.mark.skipif(not XLSX.exists(), reason="file Excel contoh tidak ada")
def test_import_excel():
    from app import import_excel
    import_excel.run(str(XLSX), sheets=["Oktober"], use_opening=False)
    with SessionLocal() as db:
        p = db.scalars(select(m.Period).where(m.Period.name == "Oktober")).first()
        # periode "Oktober" sudah dibuat oleh test_flow, jadi import dilewati; cek sheet lain
        assert p is not None
    import_excel.run(str(XLSX), sheets=["September"], use_opening=True)
    with SessionLocal() as db:
        p = db.scalars(select(m.Period).where(m.Period.name == "September")).first()
        assert p and str(p.start) == "2026-08-28" and str(p.end) == "2026-09-30" and p.income == 10910155
        assert len(db.scalars(select(m.Transaction).where(m.Transaction.period_id == p.id)).all()) >= 3
