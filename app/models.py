import datetime as dt
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    kind: Mapped[str] = mapped_column(String(10), default="bank")  # bank | ewallet | crypto
    color: Mapped[str] = mapped_column(String(9), default="#475569")
    initials: Mapped[str] = mapped_column(String(3), default="")
    opening: Mapped[int] = mapped_column(Integer, default=0)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)


class Period(Base):
    __tablename__ = "periods"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    start: Mapped[dt.date] = mapped_column(Date)
    end: Mapped[dt.date] = mapped_column(Date)
    income: Mapped[int] = mapped_column(Integer, default=0)
    landing_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    landing = relationship("Account", foreign_keys=[landing_id], lazy="joined")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(8), default="paid")  # paid | planned
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    category = relationship("Category", lazy="joined")
    account = relationship("Account", lazy="joined")


class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id"), index=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    to_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(8), default="split")  # split | manual
    note: Mapped[str] = mapped_column(String(120), default="")
    src = relationship("Account", foreign_keys=[from_id], lazy="joined")
    dst = relationship("Account", foreign_keys=[to_id], lazy="joined")


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(60))
    amount: Mapped[int] = mapped_column(Integer, default=0)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    category = relationship("Category", lazy="joined")


class Holding(Base):
    __tablename__ = "holdings"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    manual_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class Rate(Base):
    """Snapshot kurs/harga per hari. key: USDIDR atau TOKEN:BTC (harga dalam USDT)."""
    __tablename__ = "rates"
    __table_args__ = (UniqueConstraint("key", "day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(30), index=True)
    day: Mapped[dt.date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime)
