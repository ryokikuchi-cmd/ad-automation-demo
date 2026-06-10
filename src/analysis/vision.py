"""② Vision因果分析（cr-analysis.md STEP4 をClaudeで自動化）。

広告画像＋実績指標（CPM/CTR/象限）をClaudeに渡し、「なぜ効くか/効かないか」を
視覚的要因として構造化抽出する。画像は自前DL→base64で送付（fbcdnは期限付きURLのため）。

モデルは env ANTHROPIC_MODEL（既定 claude-opus-4-8）。コスト優先なら
ANTHROPIC_MODEL=claude-haiku-4-5 等に切替可能（バッチVisionは件数が多いほど効く）。
fetch/構築（テスト可能）と API呼び出しを分離。
"""
from __future__ import annotations

import base64
import json
import os

import requests

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# 返却JSONの構造（structured outputs / json_schema）
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "visual_summary": {"type": "string"},          # 画像構成の要約
        "why_effective": {"type": "array", "items": {"type": "string"}},  # 効く視覚要因
        "why_weak": {"type": "array", "items": {"type": "string"}},       # 弱い視覚要因
        "improvement_hints": {"type": "array", "items": {"type": "string"}},  # 改善ヒント
    },
    "required": ["visual_summary", "why_effective", "why_weak", "improvement_hints"],
    "additionalProperties": False,
}


def download_image(url: str, timeout: int = 20) -> tuple[str, str]:
    """画像URLをDL → (base64データ, media_type) を返す（certifiでSSL検証）。"""
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "ad-automation/1.0"})
    r.raise_for_status()
    media_type = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
    if media_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        media_type = "image/jpeg"
    return base64.standard_b64encode(r.content).decode("utf-8"), media_type


def build_prompt(ad: dict, metrics: dict) -> str:
    """cr-analysis STEP4 のビジュアル因果分析プロンプト（日本語）。"""
    return (
        "あなたはMeta広告のクリエイティブ分析の専門家です。"
        "以下のバナー画像と実績を踏まえ、視覚的要因の因果を分析してください。\n\n"
        f"広告名: {ad.get('ad_name')}\n"
        f"ビジュアル: {ad.get('visual')} / 訴求軸: {ad.get('appeal_axis')}\n"
        f"実績: CPM={metrics.get('CPM'):.0f} / CTR={metrics.get('CTR'):.4f} / "
        f"象限={metrics.get('quadrant')}（{metrics.get('quadrant_label', '')}）\n\n"
        "CPMが安い=Meta評価が高い（配信効率良）、CTRが高い=顧客の興味喚起ができている、"
        "という前提で、画像の何が効いている/弱いのかを視覚的に説明してください。"
        "改善ヒントは具体的な構成変更（テキスト量・色・被写体・レイアウト等）で示してください。"
    )


def build_messages(image_b64: str, media_type: str, prompt: str) -> list[dict]:
    return [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": prompt},
        ],
    }]


def analyze_creative(ad: dict, metrics: dict, model: str | None = None) -> dict:
    """1広告のVision因果分析を実行して構造化結果を返す。

    ANTHROPIC_API_KEY が必要。画像URLは ad['image_url']。
    """
    import anthropic

    if not ad.get("image_url"):
        return {"error": "no image_url"}
    img_b64, media_type = download_image(ad["image_url"])
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA}},
        messages=build_messages(img_b64, media_type, build_prompt(ad, metrics)),
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)
