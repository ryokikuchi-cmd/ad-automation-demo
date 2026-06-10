"""広告名の命名規則パース。visual（ビジュアル）/ appeal_axis（訴求軸）を抽出。

SaaSが⑤入稿で付与する標準命名（src/publish/meta_write.standardize_ad_name）の逆変換:
  {広告セット}_{visual}_{appeal}_{NN}
標準に一致しない既存広告は、ヒューリスティック＋フォールバックで補完。
将来はAI推定（Vision/LLM）で精度向上。
"""
from __future__ import annotations

import re

_INDEX_RE = re.compile(r"^\d{1,2}$")  # 末尾の連番（01, 1 等）


def parse_ad_name(ad_name: str, adset: str | None = None) -> tuple[str | None, str | None]:
    """(visual, appeal_axis) を返す。

    1) 標準命名（adset接頭辞を剥がすと visual_appeal_NN）に一致 → そこから抽出
    2) フォールバック: 連番を除いた末尾セグメントを appeal、その手前を visual
    3) 解析不能 → visual=ad_name, appeal=None
    """
    if not ad_name:
        return None, None
    name = ad_name.strip()

    # 1) 標準命名の逆変換
    core = name
    if adset and name.startswith(adset + "_"):
        core = name[len(adset) + 1:]
    segs = core.split("_")
    if _INDEX_RE.match(segs[-1]):  # 末尾が連番なら除去
        segs = segs[:-1]

    if len(segs) >= 2:
        return segs[-2], segs[-1]
    if len(segs) == 1:
        return segs[0], None
    return name, None
