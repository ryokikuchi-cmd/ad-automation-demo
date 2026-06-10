"""SQLAlchemyモデル定義。data-model.md のスキーマに対応。

UI・スケジューラから独立した純粋なデータ定義。
PostgreSQL（Supabase）想定だが、SQLiteでも動作する。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Postgresでは JSONB、SQLite等では JSON（可搬性のため）
JSONType = JSON().with_variant(JSONB(), "postgresql")
# Postgresでは BIGINT、SQLiteでは自動採番INTEGER（主キー用）
PK = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


# ----- テナント・アカウント -----

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    accounts: Mapped[list["AdAccount"]] = relationship(back_populates="tenant")


class AdAccount(Base):
    __tablename__ = "ad_accounts"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    meta_account_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)  # act_xxx
    name: Mapped[Optional[str]] = mapped_column(Text)
    access_token_enc: Mapped[Optional[str]] = mapped_column(Text)  # Fernetで暗号化
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="accounts")


# ----- 広告メタデータ master -----

class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (UniqueConstraint("ad_account_id", "meta_ad_id"),)
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    meta_ad_id: Mapped[Optional[str]] = mapped_column(Text)
    ad_name: Mapped[str] = mapped_column(Text, nullable=False)
    campaign: Mapped[Optional[str]] = mapped_column(Text)
    adset: Mapped[Optional[str]] = mapped_column(Text)
    visual: Mapped[Optional[str]] = mapped_column(Text)        # 広告名パース or AI推定
    appeal_axis: Mapped[Optional[str]] = mapped_column(Text)   # 訴求軸
    creative_type: Mapped[Optional[str]] = mapped_column(Text)  # image/video/carousel
    image_url: Mapped[Optional[str]] = mapped_column(Text)      # Vision分析用
    status: Mapped[Optional[str]] = mapped_column(Text)
    first_seen: Mapped[Optional[date]] = mapped_column(Date)
    last_seen: Mapped[Optional[date]] = mapped_column(Date)


# ----- Rawレイヤー -----

class RawPlacement(Base):
    """Raw_媒体配置 相当（日次・最小粒度）"""
    __tablename__ = "raw_placement"
    __table_args__ = (
        UniqueConstraint("ad_account_id", "date", "campaign", "adset", "ad",
                         "device", "media", "placement"),
    )
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    campaign: Mapped[Optional[str]] = mapped_column(Text)
    adset: Mapped[Optional[str]] = mapped_column(Text)
    ad: Mapped[Optional[str]] = mapped_column(Text)
    device: Mapped[Optional[str]] = mapped_column(Text)
    media: Mapped[Optional[str]] = mapped_column(Text)       # facebook/instagram
    placement: Mapped[Optional[str]] = mapped_column(Text)   # feed/stories/reels
    cost: Mapped[Optional[float]] = mapped_column(Numeric)
    impressions: Mapped[Optional[int]] = mapped_column(BigInteger)
    clicks: Mapped[Optional[int]] = mapped_column(BigInteger)
    leads: Mapped[Optional[int]] = mapped_column(BigInteger)  # 資料請求
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RawAgeGender(Base):
    """Raw_年齢性別 相当"""
    __tablename__ = "raw_age_gender"
    __table_args__ = (
        UniqueConstraint("ad_account_id", "date", "campaign", "adset", "ad", "age", "gender"),
    )
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    campaign: Mapped[Optional[str]] = mapped_column(Text)
    adset: Mapped[Optional[str]] = mapped_column(Text)
    ad: Mapped[Optional[str]] = mapped_column(Text)
    age: Mapped[Optional[str]] = mapped_column(Text)
    gender: Mapped[Optional[str]] = mapped_column(Text)
    cost: Mapped[Optional[float]] = mapped_column(Numeric)
    impressions: Mapped[Optional[int]] = mapped_column(BigInteger)
    clicks: Mapped[Optional[int]] = mapped_column(BigInteger)
    leads: Mapped[Optional[int]] = mapped_column(BigInteger)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ----- 商談レイヤー（クライアント記入スプシ取込） -----

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    campaign: Mapped[Optional[str]] = mapped_column(Text)
    adset: Mapped[Optional[str]] = mapped_column(Text)
    ad: Mapped[Optional[str]] = mapped_column(Text)       # 流入広告（分かる場合）
    appointments: Mapped[int] = mapped_column(Integer, default=0)  # 商談数
    won: Mapped[int] = mapped_column(Integer, default=0)           # 成約数
    source_sheet: Mapped[Optional[str]] = mapped_column(Text)         # 取込元（監査用）
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ----- 分析・提案・ログ -----

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    run_date: Mapped[Optional[date]] = mapped_column(Date)
    params_json: Mapped[Optional[dict]] = mapped_column(JSONType)
    status: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Proposal(Base):
    """③改善提案 ＋ ④生成物"""
    __tablename__ = "proposals"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id"))
    adset: Mapped[Optional[str]] = mapped_column(Text)
    ad: Mapped[Optional[str]] = mapped_column(Text)
    quadrant: Mapped[Optional[str]] = mapped_column(Text)      # top_left/top_right/bottom_left/bottom_right
    action_type: Mapped[Optional[str]] = mapped_column(Text)   # expand/change_appeal/change_visual/pause/budget
    detail_json: Mapped[Optional[dict]] = mapped_column(JSONType)
    banner_prompt: Mapped[Optional[str]] = mapped_column(Text)  # ④生成
    copy_variants: Mapped[Optional[dict]] = mapped_column(JSONType)  # ④生成
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending/approved/rejected/executed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActionLog(Base):
    """⑤入稿アクションの監査ログ"""
    __tablename__ = "action_logs"
    id: Mapped[int] = mapped_column(PK, primary_key=True)
    proposal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("proposals.id"))
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    action_type: Mapped[Optional[str]] = mapped_column(Text)  # budget/pause/duplicate/create
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONType)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    result_json: Mapped[Optional[dict]] = mapped_column(JSONType)
    executed_by: Mapped[Optional[str]] = mapped_column(Text)
