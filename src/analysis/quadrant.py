"""② 4象限分析（cr-analysis.md の中核ロジックをPython化）。

広告セット別に、セット内のCPM中央値・CTR中央値を閾値として各CRを4象限に分類する。
純粋ロジック（pandas）。Vision因果分析（画像を見る部分）は vision.py に分離予定。
"""
from __future__ import annotations

import pandas as pd

# 4象限の定義（cr-analysis.md 準拠）
#             CTR高              CTR低
# CPM安   top_left(勝ち)        top_right(訴求弱)
# CPM高   bottom_left(顧客のみ)  bottom_right(停止候補)
QUADRANT_LABELS = {
    "top_left": "🟢 勝ちCR（横展開）",
    "top_right": "🟡 Meta評価のみ（訴求を変える）",
    "bottom_left": "🟡 顧客のみ反応（ビジュアルを変える）",
    "bottom_right": "🔴 両方ダメ（停止候補）",
}


def classify_quadrant(cpm: float, ctr: float, cpm_th: float, ctr_th: float) -> str:
    cpm_cheap = cpm <= cpm_th        # CPMが安い = Meta評価◎
    ctr_high = ctr >= ctr_th         # CTRが高い = 顧客評価◎
    if cpm_cheap and ctr_high:
        return "top_left"
    if cpm_cheap and not ctr_high:
        return "top_right"
    if not cpm_cheap and ctr_high:
        return "bottom_left"
    return "bottom_right"


def analyze_adset(cr_df: pd.DataFrame,
                  min_impressions: int = 5000,
                  min_leads: int = 5) -> pd.DataFrame:
    """1つの広告セットに属するCR集計DF（add_derived_metrics済み）を4象限分類。

    cr_df 必須列: ad, cost, impressions, clicks, leads, CPM, CTR (, appointments)
    返り値: cr_df + quadrant, quadrant_label, low_data(参考値フラグ)
    閾値は「このセット内の中央値」（cr-analysis.md 準拠）。
    """
    df = cr_df.copy()
    if df.empty:
        return df

    cpm_th = df["CPM"].median()
    ctr_th = df["CTR"].median()

    df["quadrant"] = df.apply(
        lambda r: classify_quadrant(r["CPM"], r["CTR"], cpm_th, ctr_th), axis=1)
    df["quadrant_label"] = df["quadrant"].map(QUADRANT_LABELS)
    # データ不足は「参考値」（cr-analysis.md 注意事項）
    df["low_data"] = (df["impressions"] < min_impressions) | (df["leads"] < min_leads)
    df.attrs["cpm_threshold"] = cpm_th
    df.attrs["ctr_threshold"] = ctr_th
    return df


def active_adsets(daily_adset: pd.DataFrame, as_of: pd.Timestamp,
                  active_days: int = 5) -> list[str]:
    """直近 active_days 日で費用>0 の広告セット名を返す（日別×広告セットDFから）。

    daily_adset 必須列: date, adset, cost
    """
    cutoff = as_of - pd.Timedelta(days=active_days)
    recent = daily_adset[(daily_adset["date"] > cutoff) & (daily_adset["cost"] > 0)]
    return sorted(recent["adset"].dropna().unique().tolist())
