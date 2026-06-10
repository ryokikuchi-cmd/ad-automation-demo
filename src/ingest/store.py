"""⓪ 取得したインサイトを raw_* テーブルへUPSERT（store層・DB依存）。

UNIQUE制約キーで ON CONFLICT DO UPDATE（同日再取得は上書き＝遅延CV対応）。
PostgreSQL／SQLite 両対応（dialectで insert を切替）。
"""
from __future__ import annotations

from ..db.models import RawAgeGender, RawPlacement

PLACEMENT_CONFLICT = ["ad_account_id", "date", "campaign", "adset", "ad",
                      "device", "media", "placement"]
AGE_GENDER_CONFLICT = ["ad_account_id", "date", "campaign", "adset", "ad", "age", "gender"]
_UPDATE_COLS = ["cost", "impressions", "clicks", "leads"]


def _insert_for(dialect: str):
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
        return insert
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
        return insert
    from sqlalchemy import insert  # フォールバック（UPSERTなし）
    return insert


def _upsert(session, model, ad_account_id: int, rows: list[dict], conflict_cols: list[str]) -> int:
    if not rows:
        return 0
    payload = []
    for r in rows:
        rec = {k: v for k, v in r.items() if k != "meta_account_id"}
        rec["ad_account_id"] = ad_account_id
        payload.append(rec)

    dialect = session.bind.dialect.name
    insert = _insert_for(dialect)
    stmt = insert(model).values(payload)
    if hasattr(stmt, "on_conflict_do_update"):
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_cols,
            set_={c: stmt.excluded[c] for c in _UPDATE_COLS},
        )
    session.execute(stmt)
    session.commit()
    return len(payload)


def upsert_placement(session, ad_account_id: int, rows: list[dict]) -> int:
    return _upsert(session, RawPlacement, ad_account_id, rows, PLACEMENT_CONFLICT)


def upsert_age_gender(session, ad_account_id: int, rows: list[dict]) -> int:
    return _upsert(session, RawAgeGender, ad_account_id, rows, AGE_GENDER_CONFLICT)
