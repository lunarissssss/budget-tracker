from datetime import timedelta
from sqlalchemy import func, select
from . import models as m
from .util import today

ACCOUNTS = [("Seabank", "bank", "#C2410C", "SB"), ("ShopeePay", "ewallet", "#B91C1C", "SP"),
            ("GoPay", "ewallet", "#0369A1", "GP"), ("Krom Bank", "bank", "#6D28D9", "KB"),
            ("BCA", "bank", "#1D4ED8", "BC"), ("OCBC", "bank", "#BE123C", "OC"),
            ("Bitget Wallet", "crypto", "#00E0FF", "BW")]
CATEGORIES = ["Food / Beverages", "Transport", "Home", "Family", "Credit card", "Other"]


def seed(db):
    if db.scalar(select(func.count(m.Account.id))):
        return
    for i, (n, k, c, ini) in enumerate(ACCOUNTS):
        db.add(m.Account(name=n, kind=k, color=c, initials=ini, sort=i))
    for n in CATEGORIES:
        db.add(m.Category(name=n))
    db.flush()
    seabank = db.scalars(select(m.Account).where(m.Account.name == "Seabank")).first()
    cats = {c.name: c.id for c in db.scalars(select(m.Category))}
    t = today()
    db.add(m.Period(name="Periode 1", start=t, end=t + timedelta(days=30), income=0, landing_id=seabank.id))
    db.add(m.Template(label="Parkir", amount=10000, category_id=cats["Transport"], account_id=seabank.id))
    db.add(m.Template(label="Makan siang", amount=25000, category_id=cats["Food / Beverages"], account_id=seabank.id))
    db.commit()
