"""③ 提案エンジン。4象限の位置に応じた改善アクションを自動生成。

cr-analysis.md STEP5 の象限別ロジックをコード化。
  top_left    → 横展開（訴求・構成維持、バリエーション）
  top_right   → 訴求変更（ビジュアル維持）
  bottom_left → ビジュアル変更（訴求維持、テキスト削減等）
  bottom_right→ 停止（CV実績あれば要検討）
純粋ロジック。生成物（バナースクリプト/コピー）は④ creative に委譲。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

ACTION_BY_QUADRANT = {
    "top_left": "expand",
    "top_right": "change_appeal",
    "bottom_left": "change_visual",
    "bottom_right": "pause",
}


@dataclass
class ProposalDraft:
    adset: str
    ad: str
    quadrant: str
    action_type: str
    detail: dict


def generate_proposals(analyzed: pd.DataFrame, adset: str) -> list[ProposalDraft]:
    """analyze_adset 済みDF（quadrant付き）から提案ドラフトを生成。

    各CRに対し象限別アクションを割り当て、変更方針・根拠を detail に格納する。
    bottom_right は商談(appointments)があれば「CV実績あり要検討」に分岐。
    """
    drafts: list[ProposalDraft] = []
    for _, r in analyzed.iterrows():
        q = r["quadrant"]
        action = ACTION_BY_QUADRANT[q]
        detail = {
            "cpm": float(r["CPM"]), "ctr": float(r["CTR"]),
            "leads": int(r.get("leads", 0)),
            "appointments": int(r.get("appointments", 0)),
            "low_data": bool(r.get("low_data", False)),
            "label": r.get("quadrant_label"),
        }
        if q == "bottom_right" and detail["appointments"] > 0:
            detail["note"] = "CPM/CTRは低いがCV実績あり。CPA基準で要再評価（停止保留）"
            action = "review"
        drafts.append(ProposalDraft(adset=adset, ad=str(r["ad"]),
                                    quadrant=q, action_type=action, detail=detail))
    return drafts
