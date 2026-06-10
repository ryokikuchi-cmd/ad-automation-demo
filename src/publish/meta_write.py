"""⑤ 入稿・実行層。承認された提案を Meta API で実行し action_logs に記録。

書き込みスコープ（ads_management）が必要。安全装置:
  - dry_run デフォルトTrue（実行前に必ず差分を提示）
  - 予算上限ガード（一度の変更幅に上限）
  - 全操作を action_logs に監査記録
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_BUDGET_CHANGE_RATIO = 0.30  # 一度の予算変更は±30%まで（事故防止）


@dataclass
class ExecutionResult:
    proposal_id: int
    action_type: str
    dry_run: bool
    ok: bool
    detail: dict


def execute(session, ad_account, proposal, access_token: str,
            dry_run: bool = True, executed_by: str = "system") -> ExecutionResult:
    """承認済み提案を実行。

    action_type 別:
      budget    → AdSet予算を変更（MAX_BUDGET_CHANGE_RATIOガード）
      pause     → 広告/広告セットを停止
      duplicate → 勝ちCRを複製して横展開
      create    → 人がアップした画像でCRを新規作成（命名はSaaSが統一付与）

    dry_run=True なら API を叩かず差分のみ返す。
    いずれも action_logs に記録（payload/result/dry_run/executed_by）。
    """
    raise NotImplementedError("Phase4で実装（ads_management審査後）")


def standardize_ad_name(adset: str, visual: str, appeal: str, index: int) -> str:
    """⑤入稿時に統一命名を付与（命名規則の標準化＝分類精度の担保）。"""
    return f"{adset}_{visual}_{appeal}_{index:02d}"
