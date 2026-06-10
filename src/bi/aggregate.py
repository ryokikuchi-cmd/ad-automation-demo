"""① BI集計層。Rawデータ＋商談を標準メトリクス12列に集計する。

純粋なpandas処理（DB非依存・テスト可能）。UI/スケジューラから独立。
標準メトリクス: 費用/Imps/CPM/Clicks/CPC/CTR/資料請求/資料請求率/資料請求単価/
                商談/商談率/商談単価
"""
from __future__ import annotations

import pandas as pd


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a / b.replace(0, pd.NA)).fillna(0)


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """cost/impressions/clicks/leads/appointments を持つ集計済みDFに派生指標を付与。

    data-model.md の計算式に準拠。
    """
    out = df.copy()
    out["CPM"] = _safe_div(out["cost"], out["impressions"]) * 1000
    out["CTR"] = _safe_div(out["clicks"], out["impressions"])
    out["CPC"] = _safe_div(out["cost"], out["clicks"])
    out["資料請求単価"] = _safe_div(out["cost"], out["leads"])
    out["資料請求率"] = _safe_div(out["leads"], out["clicks"])
    if "appointments" in out.columns:
        out["商談率"] = _safe_div(out["appointments"], out["leads"])
        out["商談単価"] = _safe_div(out["cost"], out["appointments"])
    return out


def aggregate(raw: pd.DataFrame, group_keys: list[str],
              appointments: pd.DataFrame | None = None,
              appt_keys: list[str] | None = None) -> pd.DataFrame:
    """Rawを group_keys で集計し、必要なら商談を結合して派生指標まで算出。

    raw: cost/impressions/clicks/leads を含む最小粒度DF
    group_keys: 集計軸（例 ['ad'] でCR別、['date'] で日別、['adset'] で広告セット別）
    appointments: ad_account/date/adset/ad/appointments/won を含むDF（任意）
    appt_keys: 商談の結合キー（例 ['ad'] / ['adset']）
    """
    base = (raw.groupby(group_keys, dropna=False)[["cost", "impressions", "clicks", "leads"]]
            .sum().reset_index())

    if appointments is not None and appt_keys:
        appt = (appointments.groupby(appt_keys, dropna=False)[["appointments", "won"]]
                .sum().reset_index())
        base = base.merge(appt, how="left", left_on=appt_keys, right_on=appt_keys)
        base[["appointments", "won"]] = base[["appointments", "won"]].fillna(0)

    return add_derived_metrics(base)


# 既存スプシのシートに対応する代表的な集計軸
GROUP_PRESETS: dict[str, list[str]] = {
    "summary": [],            # サマリー（全体）→ group_keys空はaggregate側で要対応
    "daily": ["date"],        # 各日数値
    "campaign": ["campaign"],  # CP別
    "adset": ["adset"],       # CPGr別
    "cr": ["ad"],             # CR別（4象限の入力）
    "placement": ["placement"],
    "age": ["age"],
    "gender": ["gender"],
    "visual": ["visual"],
    "appeal": ["appeal_axis"],
}
