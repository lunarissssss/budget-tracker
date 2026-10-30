"""Import dari Excel lama (Journal_Keuangan_Bulanan.xlsx).
Pakai:  python -m app.import_excel file.xlsx [--sheet Oktober ...] [--opening]
- 1 sheet = 1 periode (tanggal diambil dari D2, mis. "30 September - 30 Oktober")
- Transaksi tanpa tanggal dianggap Rencana. Kolom "Akun" dipakai kalau ada.
- "Diterima dari Split" jadi transfer dari akun landing. --opening: pakai "Saldo Awal" sheet terlama.
"""
import argparse, re
from datetime import date, datetime
from openpyxl import load_workbook
from sqlalchemy import select
from . import models as m
from .db import Base, SessionLocal, engine
from .seed import seed

MONTHS = {n: i + 1 for i, n in enumerate("januari februari maret april mei juni juli agustus september oktober november desember".split())}


def parse_range(text, year):
    mt = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)", str(text or ""))
    if not mt or mt[2].lower() not in MONTHS or mt[4].lower() not in MONTHS:
        return None
    sm, em = MONTHS[mt[2].lower()], MONTHS[mt[4].lower()]
    sy = year - 1 if sm > em else year
    return date(sy, sm, int(mt[1])), date(year, em, int(mt[3]))


def _d(v):
    return v.date() if isinstance(v, datetime) else v if isinstance(v, date) else None


def find_row(ws, col, text, lo=1, hi=60):
    for r in range(lo, hi):
        if str(ws.cell(r, col).value or "").strip().lower() == text:
            return r


def get_or_create(db, model, name, **kw):
    obj = db.scalars(select(model).where(model.name.ilike(name))).first()
    if not obj:
        obj = model(name=name, **kw)
        db.add(obj)
        db.flush()
    return obj


def import_sheet(db, ws, landing):
    if db.scalars(select(m.Period).where(m.Period.name == ws.title)).first():
        print(f"- {ws.title}: sudah ada, dilewati")
        return None
    hr = find_row(ws, 2, "date", 15, 40)
    if not hr:
        print(f"- {ws.title}: header 'Date' tidak ketemu, dilewati")
        return None
    heads = {str(ws.cell(hr, c).value or "").strip().lower(): c for c in range(2, 9)}
    rows = []
    for r in range(hr + 1, ws.max_row + 1):
        amt = ws.cell(r, heads.get("amount", 3)).value
        if not isinstance(amt, (int, float)) or amt == 0:
            continue
        rows.append(dict(d=_d(ws.cell(r, 2).value), amt=int(amt), cat=ws.cell(r, heads.get("category", 4)).value,
                         desc=ws.cell(r, heads.get("description", 5)).value, acc=ws.cell(r, heads["akun"]).value if "akun" in heads else None))
    dates = [x["d"] for x in rows if x["d"]]
    year = max(dates).year if dates else date.today().year
    rng = parse_range(ws["D2"].value, year) or ((min(dates), max(dates)) if dates else (date.today(), date.today()))
    per = m.Period(name=ws.title, start=rng[0], end=rng[1], income=int(ws["C4"].value or 0), landing_id=landing.id if landing else None)
    db.add(per)
    db.flush()
    for x in rows:
        cat = get_or_create(db, m.Category, str(x["cat"]).strip()) if x["cat"] else None
        acc = get_or_create(db, m.Account, str(x["acc"]).strip(), initials=str(x["acc"]).strip()[:2].upper()) if x["acc"] else None
        db.add(m.Transaction(period_id=per.id, date=x["d"], amount=x["amt"], category_id=cat.id if cat else None,
                             account_id=acc.id if acc else None, description=str(x["desc"] or "").strip(),
                             status="paid" if x["d"] else "planned", recurring=not x["d"]))
    # tabel Saldo Akun: Akun | Saldo Awal | Diterima dari Split | ...
    opening, sr = {}, find_row(ws, 7, "akun", 5, 15)
    if sr:
        for r in range(sr + 1, sr + 12):
            name = ws.cell(r, 7).value
            if not name or str(name).strip().lower() == "total":
                break
            name = str(name).strip()
            a = db.scalars(select(m.Account).where(m.Account.name.ilike(name))).first()
            if not a:
                continue
            opening[a.id] = int(ws.cell(r, 8).value or 0)
            got = ws.cell(r, 9).value
            if isinstance(got, (int, float)) and got > 0 and landing and a.id != landing.id:
                db.add(m.Transfer(period_id=per.id, from_id=landing.id, to_id=a.id, amount=int(got), date=per.start, kind="split"))
    print(f"- {ws.title}: {len(rows)} transaksi, income {per.income}, periode {per.start} → {per.end}")
    return per, opening


def run(path, sheets=None, use_opening=False):
    Base.metadata.create_all(engine)
    wb = load_workbook(path, data_only=True)
    with SessionLocal() as db:
        seed(db)
        landing = db.scalars(select(m.Account).where(m.Account.name.ilike("seabank"))).first() or db.scalars(select(m.Account)).first()
        done = []
        for ws in wb.worksheets:
            if sheets and ws.title not in sheets:
                continue
            r = import_sheet(db, ws, landing)
            if r:
                done.append(r)
        if use_opening and done:
            per, opening = min(done, key=lambda x: x[0].start)
            for aid, v in opening.items():
                db.get(m.Account, aid).opening = v
            print(f"- saldo awal diambil dari sheet {per.name}")
        if done:  # buang periode contoh dari seed kalau masih kosong
            d = db.scalars(select(m.Period).where(m.Period.name == "Periode 1")).first()
            if d and not db.scalars(select(m.Transaction).where(m.Transaction.period_id == d.id)).first():
                db.delete(d)
        db.commit()
    print("Selesai.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--sheet", action="append")
    ap.add_argument("--opening", action="store_true")
    a = ap.parse_args()
    run(a.file, a.sheet, a.opening)
