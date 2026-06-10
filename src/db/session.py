"""DB接続・セッション管理。DATABASE_URL（Supabase / ローカルPostgres）を参照。"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

try:  # .env読込は任意（未インストールでも動作）
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)


def init_db() -> None:
    """全テーブルを作成（初回セットアップ用。本番はマイグレーション推奨）。"""
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()
