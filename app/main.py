import asyncio, base64, os, re, secrets
from contextlib import asynccontextmanager
from itertools import groupby
from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import exports, models as m, rates, services as s
from .db import Base, SessionLocal, engine, get_db
from .i18n import T
from .seed import seed
from .util import parse_date, parse_float, parse_int, rp, today

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.filters["rp"] = rp
templates.env.globals["logo"] = s.logo


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    task = None if os.getenv("RATES_DISABLED") else asyncio.create_task(rates.loop())
    yield
    if task:
        task.cancel()


app = FastAPI(lifespan=lifespan, title="Budget Tracker")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
PASSWORD = os.getenv("APP_PASSWORD")


@app.middleware("http")
async def auth(req: Request, call_next):
    if PASSWORD and req.url.path != "/healthz":
        ok, h = False, req.headers.get("authorization", "")
        if h.startswith("Basic "):
            try:
                ok = secrets.compare_digest(base64.b64decode(h[6:]).decode().partition(":")[2], PASSWORD)
            except Exception:
                pass
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Budget Tracker"'})
    return await call_next(req)


def lang_of(req):
    return req.cookies.get("lang") if req.cookies.get("lang") in ("id", "en") else "id"


def period_of(req, db):
    return s.current_period(db, req.cookies.get("p"))


def render(req, db, name, **ctx):
    lang = lang_of(req)
    ctx.update(lang=lang, t=lambda k: T(k, lang), per=period_of(req, db), path=req.url.path, today=today(),
               periods=db.scalars(select(m.Period).order_by(m.Period.start.desc())).all())
    return templates.TemplateResponse(req, name, ctx)


def to(url):
    return RedirectResponse(url, 303)


def opt_id(v):
    return int(v) if str(v).isdigit() else None


def lists(db):
    return dict(accounts=db.scalars(select(m.Account).order_by(m.Account.sort, m.Account.id)).all(),
                categories=db.scalars(select(m.Category).order_by(m.Category.id)).all())


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/sw.js")
def sw():
    return FileResponse(BASE / "static" / "sw.js", media_type="text/javascript")


@app.get("/lang/{code}")
def set_lang(code: str, req: Request):
    r = to(req.headers.get("referer") or "/")
    r.set_cookie("lang", code if code in ("id", "en") else "id", max_age=31536000)
    return r


@app.get("/period/{pid}")
def set_period(pid: int, next: str = "/"):
    r = to(next if next.startswith("/") and not next.startswith("//") else "/")
    r.set_cookie("p", str(pid), max_age=31536000)
    return r


# ---------- Beranda ----------
@app.get("/", response_class=HTMLResponse)
def home(req: Request, db: Session = Depends(get_db)):
    per = period_of(req, db)
    q = select(m.Transaction).where(m.Transaction.period_id == per.id)
    bal = s.balances(db)
    return render(req, db, "home.html", sm=s.summary(db, per), bars=s.daily(db, per)[0], bal=bal,
                  total=sum(b["balance"] for b in bal),
                  recent=db.scalars(q.where(m.Transaction.status == "paid").order_by(m.Transaction.date.desc(), m.Transaction.id.desc()).limit(5)).all(),
                  plan=db.scalars(q.where(m.Transaction.status == "planned").order_by(m.Transaction.id)).all())


# ---------- Transaksi ----------
@app.get("/transactions", response_class=HTMLResponse)
def transactions(req: Request, status: str = "all", db: Session = Depends(get_db)):
    per = period_of(req, db)
    allx = db.scalars(select(m.Transaction).where(m.Transaction.period_id == per.id)
                      .order_by(m.Transaction.date.desc(), m.Transaction.id.desc())).all()
    paid = [x for x in allx if x.status == "paid"]
    planned = [x for x in allx if x.status == "planned"]
    groups = [(d, sum(x.amount for x in g), list(g)) for d, g in groupby(paid, key=lambda x: x.date)]
    return render(req, db, "transactions.html", status=status, groups=groups, planned=planned,
                  planned_sum=sum(x.amount for x in planned), **lists(db))


@app.get("/add", response_class=HTMLResponse)
def add_page(req: Request, ok: int = 0, db: Session = Depends(get_db)):
    return render(req, db, "add.html", tx=None, ok=ok, templates_=db.scalars(select(m.Template)).all(), **lists(db))


@app.get("/tx/{tid}", response_class=HTMLResponse)
def edit_page(req: Request, tid: int, db: Session = Depends(get_db)):
    return render(req, db, "add.html", tx=db.get(m.Transaction, tid), ok=0, templates_=[], **lists(db))


@app.post("/tx")
def save_tx(req: Request, tid: str = Form(""), amount: str = Form(""), d: str = Form("", alias="date"),
            status: str = Form("paid"), category_id: str = Form(""), account_id: str = Form(""),
            description: str = Form(""), recurring: str = Form(""), again: str = Form(""), db: Session = Depends(get_db)):
    x = db.get(m.Transaction, int(tid)) if tid.isdigit() else None
    if not x:
        x = m.Transaction(period_id=period_of(req, db).id)
        db.add(x)
    x.amount = abs(parse_int(amount))
    x.status = status if status in ("paid", "planned") else "paid"
    x.date = parse_date(d) or (today() if x.status == "paid" else None)
    x.category_id, x.account_id = opt_id(category_id), opt_id(account_id)
    x.description, x.recurring = description.strip(), bool(recurring)
    db.commit()
    return to("/add?ok=1" if again else "/transactions")


@app.post("/quick/{qid}")
def quick(req: Request, qid: int, db: Session = Depends(get_db)):
    q, per = db.get(m.Template, qid), period_of(req, db)
    if q:
        db.add(m.Transaction(period_id=per.id, date=today(), amount=q.amount, category_id=q.category_id,
                             account_id=q.account_id or per.landing_id, description=q.label, status="paid"))
        db.commit()
    return to("/add?ok=1")


@app.post("/tx/{tid}/pay")
def pay(req: Request, tid: int, account_id: str = Form(""), d: str = Form("", alias="date"), db: Session = Depends(get_db)):
    x = db.get(m.Transaction, tid)
    if x:
        x.status, x.date = "paid", parse_date(d) or today()
        x.account_id = opt_id(account_id) or x.account_id or period_of(req, db).landing_id
        db.commit()
    return to("/transactions")


@app.post("/tx/{tid}/delete")
def delete_tx(tid: int, db: Session = Depends(get_db)):
    x = db.get(m.Transaction, tid)
    if x:
        db.delete(x)
        db.commit()
    return to("/transactions")


# ---------- Rekap ----------
@app.get("/rekap", response_class=HTMLResponse)
def rekap(req: Request, view: str = "daily", db: Session = Depends(get_db)):
    per = period_of(req, db)
    bars, mx = s.daily(db, per)
    return render(req, db, "rekap.html", view=view, bars=bars, mx=mx, cats=s.by_category(db, per),
                  accs=s.by_account(db, per), sm=s.summary(db, per))


# ---------- Asset Management ----------
@app.get("/assets", response_class=HTMLResponse)
def assets(req: Request, db: Session = Depends(get_db)):
    per = period_of(req, db)
    bal = s.balances(db)
    split = {t.to_id: t.amount for t in db.scalars(select(m.Transfer).where(m.Transfer.period_id == per.id, m.Transfer.kind == "split"))}
    return render(req, db, "assets.html", bal=bal, total=sum(b["balance"] for b in bal), split=split, sm=s.summary(db, per),
                  ct=s.crypto_total(db), transfers=db.scalars(select(m.Transfer).where(m.Transfer.period_id == per.id).order_by(m.Transfer.id.desc())).all(),
                  **lists(db))


@app.post("/assets/split")
async def split(req: Request, db: Session = Depends(get_db)):
    form, per = await req.form(), period_of(req, db)
    if per.landing_id:
        for a in db.scalars(select(m.Account)):
            if a.id == per.landing_id or f"amt_{a.id}" not in form:
                continue
            for o in db.scalars(select(m.Transfer).where(m.Transfer.period_id == per.id, m.Transfer.to_id == a.id, m.Transfer.kind == "split")):
                db.delete(o)
            amt = abs(parse_int(form[f"amt_{a.id}"]))
            if amt:
                db.add(m.Transfer(period_id=per.id, from_id=per.landing_id, to_id=a.id, amount=amt, date=today(), kind="split"))
        db.commit()
    return to("/assets")


@app.post("/assets/transfer")
def transfer(req: Request, from_id: int = Form(...), to_id: int = Form(...), amount: str = Form(""), note: str = Form(""), db: Session = Depends(get_db)):
    amt = abs(parse_int(amount))
    if amt and from_id != to_id:
        db.add(m.Transfer(period_id=period_of(req, db).id, from_id=from_id, to_id=to_id, amount=amt, date=today(), kind="manual", note=note.strip()))
        db.commit()
    return to("/assets")


@app.post("/assets/transfer/{tid}/delete")
def del_transfer(tid: int, db: Session = Depends(get_db)):
    x = db.get(m.Transfer, tid)
    if x:
        db.delete(x)
        db.commit()
    return to("/assets")


@app.post("/assets/reconcile/{aid}")
def reconcile(aid: int, actual: str = Form(""), db: Session = Depends(get_db)):
    """Samakan saldo hitungan dengan saldo asli di aplikasi bank: selisih dimasukkan ke saldo awal."""
    a = next((b for b in s.balances(db) if b["a"].id == aid), None)
    if a and actual.strip():
        db.get(m.Account, aid).opening += parse_int(actual) - a["ledger"]
        db.commit()
    return to("/assets")


@app.post("/assets/holding")
def holding(bg: BackgroundTasks, symbol: str = Form(""), quantity: str = Form("0"), manual_usd: str = Form(""), db: Session = Depends(get_db)):
    sym = re.sub(r"[^A-Z0-9]", "", symbol.upper())
    if sym:
        h = db.scalars(select(m.Holding).where(m.Holding.symbol == sym)).first() or m.Holding(symbol=sym)
        h.quantity, h.manual_usd = parse_float(quantity) or 0, parse_float(manual_usd)
        db.add(h)
        db.commit()
        if not os.getenv("RATES_DISABLED"):
            bg.add_task(rates.refresh)
    return to("/assets")


@app.post("/assets/holding/{hid}/delete")
def del_holding(hid: int, db: Session = Depends(get_db)):
    h = db.get(m.Holding, hid)
    if h:
        db.delete(h)
        db.commit()
    return to("/assets")


@app.post("/assets/refresh")
async def refresh():
    await rates.refresh()
    return to("/assets")


# ---------- Pengaturan ----------
@app.get("/settings", response_class=HTMLResponse)
def settings(req: Request, db: Session = Depends(get_db)):
    return render(req, db, "settings.html", tpls=db.scalars(select(m.Template)).all(), **lists(db))


@app.post("/settings/period")
def period_save(pid: str = Form(""), name: str = Form(""), start: str = Form(""), end: str = Form(""), income: str = Form("0"),
                landing_id: str = Form(""), copy_recurring: str = Form(""), db: Session = Depends(get_db)):
    st, en = parse_date(start), parse_date(end)
    if not st or not en or en < st:
        return to("/settings")
    p = db.get(m.Period, int(pid)) if pid.isdigit() else None
    new = p is None
    if new:
        prev = db.scalars(select(m.Period).order_by(m.Period.start.desc())).first()
        p = m.Period()
        db.add(p)
    p.name, p.start, p.end = name.strip() or "Periode", st, en
    p.income, p.landing_id = abs(parse_int(income)), opt_id(landing_id)
    db.flush()
    if new and copy_recurring and prev:
        for x in db.scalars(select(m.Transaction).where(m.Transaction.period_id == prev.id, m.Transaction.recurring == True)):  # noqa: E712
            db.add(m.Transaction(period_id=p.id, date=None, amount=x.amount, category_id=x.category_id, account_id=x.account_id,
                                 description=x.description, status="planned", recurring=True))
    db.commit()
    r = to("/settings")
    if new:
        r.set_cookie("p", str(p.id), max_age=31536000)
    return r


@app.post("/settings/account")
def account_save(aid: str = Form(""), name: str = Form(""), kind: str = Form("bank"), color: str = Form("#475569"),
                 initials: str = Form(""), opening: str = Form("0"), db: Session = Depends(get_db)):
    name = name.strip()
    if name:
        a = db.get(m.Account, int(aid)) if aid.isdigit() else m.Account(sort=99)
        a.name, a.kind, a.color = name, kind if kind in ("bank", "ewallet", "crypto") else "bank", color
        a.initials, a.opening = (initials.strip() or name[:2]).upper()[:3], parse_int(opening)
        db.add(a)
        try:
            db.commit()
        except Exception:
            db.rollback()
    return to("/settings")


@app.post("/settings/category")
def category_add(name: str = Form(""), db: Session = Depends(get_db)):
    name = name.strip()
    if name and not db.scalars(select(m.Category).where(m.Category.name.ilike(name))).first():
        db.add(m.Category(name=name))
        db.commit()
    return to("/settings")


@app.post("/settings/template")
def template_add(label: str = Form(""), amount: str = Form(""), category_id: str = Form(""), account_id: str = Form(""), db: Session = Depends(get_db)):
    if label.strip():
        db.add(m.Template(label=label.strip(), amount=abs(parse_int(amount)), category_id=opt_id(category_id), account_id=opt_id(account_id)))
        db.commit()
    return to("/settings")


@app.post("/settings/template/{qid}/delete")
def template_del(qid: int, db: Session = Depends(get_db)):
    q = db.get(m.Template, qid)
    if q:
        db.delete(q)
        db.commit()
    return to("/settings")


# ---------- Export ----------
@app.get("/export")
def export(req: Request, fmt: str = "xlsx", scope: str = "period", db: Session = Depends(get_db)):
    per = period_of(req, db) if scope == "period" else None
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", f"budget-{per.name if per else 'all'}-{today()}")
    if fmt == "csv":
        data, mt, ext = exports.csv_bytes(db, per), "text/csv", "csv"
    else:
        data, mt, ext = exports.xlsx_bytes(db, per), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    return Response(data, media_type=mt, headers={"Content-Disposition": f'attachment; filename="{name}.{ext}"'})
