import re
from datetime import timedelta, timezone
from pathlib import Path
from sqlalchemy import func, select
from . import models as m, rates
from .util import TZ, today

STATIC = Path(__file__).parent / "static"


def logo(a):
    s = re.sub(r"[^a-z0-9]+", "", a.name.lower())
    for ext in ("svg", "png", "webp", "jpg"):
        if (STATIC / "logos" / f"{s}.{ext}").exists():
            return f"/static/logos/{s}.{ext}"


def current_period(db, pid=None):
    if pid and str(pid).isdigit():
        p = db.get(m.Period, int(pid))
        if p:
            return p
    t = today()
    p = db.scalars(select(m.Period).where(m.Period.start <= t, m.Period.end >= t).order_by(m.Period.start.desc())).first()
    return p or db.scalars(select(m.Period).order_by(m.Period.start.desc())).first()


def summary(db, per):
    d = dict(db.execute(select(m.Transaction.status, func.coalesce(func.sum(m.Transaction.amount), 0))
                        .where(m.Transaction.period_id == per.id).group_by(m.Transaction.status)).all())
    moved = db.scalar(select(func.coalesce(func.sum(m.Transfer.amount), 0))
                      .where(m.Transfer.period_id == per.id, m.Transfer.kind == "split")) or 0
    paid, planned = d.get("paid", 0), d.get("planned", 0)
    return dict(income=per.income, paid=paid, planned=planned, net=per.income - paid - planned,
                moved=moved, unmoved=per.income - moved)


def crypto_total(db):
    fx = rates.latest(db, "USDIDR")
    fx_row = rates.latest_row(db, "USDIDR")
    rows, usd = [], 0.0
    for h in db.scalars(select(m.Holding).order_by(m.Holding.symbol)):
        price = 1.0 if h.symbol in rates.STABLE else (rates.latest(db, "TOKEN:" + h.symbol) or h.manual_usd)
        val = h.quantity * price if price is not None else None
        usd += val or 0
        rows.append(dict(h=h, price=price, usd=val, idr=val * fx if (val is not None and fx) else None))
    upd = fx_row.updated_at.replace(tzinfo=timezone.utc).astimezone(TZ) if fx_row else None
    return dict(rows=rows, usd=usd, idr=round(usd * fx) if fx else 0, fx=fx, updated=upd)


def balances(db):
    accs = db.scalars(select(m.Account).order_by(m.Account.sort, m.Account.id)).all()
    g = lambda q: dict(db.execute(q).all())
    inc = g(select(m.Period.landing_id, func.sum(m.Period.income)).group_by(m.Period.landing_id))
    tin = g(select(m.Transfer.to_id, func.sum(m.Transfer.amount)).group_by(m.Transfer.to_id))
    tout = g(select(m.Transfer.from_id, func.sum(m.Transfer.amount)).group_by(m.Transfer.from_id))
    spent = g(select(m.Transaction.account_id, func.sum(m.Transaction.amount))
              .where(m.Transaction.status == "paid").group_by(m.Transaction.account_id))
    cv = crypto_total(db)["idr"]
    out = []
    for a in accs:
        i, ti, to, sp = (inc.get(a.id) or 0), (tin.get(a.id) or 0), (tout.get(a.id) or 0), (spent.get(a.id) or 0)
        ledger = a.opening + i + ti - to - sp
        out.append(dict(a=a, opening=a.opening, income=i, tin=ti, tout=to, spent=sp, ledger=ledger,
                        balance=cv if a.kind == "crypto" else ledger))
    return out


def daily(db, per):
    tot = dict(db.execute(select(m.Transaction.date, func.sum(m.Transaction.amount)).where(
        m.Transaction.period_id == per.id, m.Transaction.status == "paid", m.Transaction.date.isnot(None))
        .group_by(m.Transaction.date)).all())
    days, d = [], per.start
    while d <= per.end and len(days) < 400:
        days.append((d, tot.get(d, 0)))
        d += timedelta(days=1)
    mx = max([v for _, v in days] or [0]) or 1
    return [dict(d=d, total=v, h=round(v * 100 / mx) if v else 0, pk=bool(v) and v == mx) for d, v in days], mx


def _group(db, per, col, namecol):
    rows = db.execute(select(namecol, func.sum(m.Transaction.amount)).select_from(m.Transaction)
                      .outerjoin(col[0], col[1]).where(m.Transaction.period_id == per.id, m.Transaction.status == "paid")
                      .group_by(namecol).order_by(func.sum(m.Transaction.amount).desc())).all()
    tot = sum(v for _, v in rows) or 1
    return [dict(name=n or "—", total=v, pct=round(v * 100 / tot)) for n, v in rows]


def by_category(db, per):
    return _group(db, per, (m.Category, m.Transaction.category_id == m.Category.id), m.Category.name)


def by_account(db, per):
    return _group(db, per, (m.Account, m.Transaction.account_id == m.Account.id), m.Account.name)
