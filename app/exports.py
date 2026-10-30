import csv, io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from . import models as m, services as s

FMT = '[$IDR]\\ #,##0'
HEAD = ["Date", "Amount", "Category", "Description", "Account", "Status", "Period"]


def _tx(db, per):
    q = select(m.Transaction).order_by(m.Transaction.period_id, m.Transaction.date, m.Transaction.id)
    if per:
        q = q.where(m.Transaction.period_id == per.id)
    names = {p.id: p.name for p in db.scalars(select(m.Period))}
    return [[x.date, x.amount, x.category.name if x.category else "", x.description,
             x.account.name if x.account else "", x.status, names.get(x.period_id, "")] for x in db.scalars(q)]


def csv_bytes(db, per):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEAD)
    for r in _tx(db, per):
        w.writerow([r[0].isoformat() if r[0] else ""] + r[1:])
    return buf.getvalue().encode("utf-8-sig")  # BOM supaya terbuka rapi di Excel


def _sheet(ws, header, rows, money=()):
    ws.append(header)
    for c in ws[1]:
        c.font, c.fill = Font(bold=True), PatternFill("solid", fgColor="DDEFF3")
    for r in rows:
        ws.append(r)
    for i in money:
        for c in ws.iter_cols(min_col=i, max_col=i, min_row=2):
            for cell in c:
                cell.number_format = FMT
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(12, max(len(str(c.value or "")) for c in col) + 2))
    ws.freeze_panes = "A2"


def xlsx_bytes(db, per):
    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"
    rows = _tx(db, per)
    _sheet(ws, HEAD, rows, money=(2,))
    for c in ws.iter_cols(min_col=1, max_col=1, min_row=2):
        for cell in c:
            cell.number_format = "dd/mm/yyyy"
    if per:
        _sheet(wb.create_sheet("Summary"), ["Category", "Spent", "%"], [[c["name"], c["total"], c["pct"]] for c in s.by_category(db, per)], money=(2,))
        bars, _ = s.daily(db, per)
        ws2 = wb.create_sheet("Daily")
        _sheet(ws2, ["Date", "Spent"], [[b["d"], b["total"]] for b in bars], money=(2,))
        for c in ws2.iter_cols(min_col=1, max_col=1, min_row=2):
            for cell in c:
                cell.number_format = "dd/mm/yyyy"
    _sheet(wb.create_sheet("Accounts"), ["Account", "Opening", "Income in", "Transfer in", "Transfer out", "Spent", "Balance"],
           [[b["a"].name, b["opening"], b["income"], b["tin"], b["tout"], b["spent"], b["balance"]] for b in s.balances(db)], money=(2, 3, 4, 5, 6, 7))
    ct = s.crypto_total(db)
    _sheet(wb.create_sheet("Crypto"), ["Symbol", "Quantity", "Price USD", "Value USD", "Value IDR"],
           [[r["h"].symbol, r["h"].quantity, r["price"], r["usd"], r["idr"]] for r in ct["rows"]])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
