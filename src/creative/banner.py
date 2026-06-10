"""④ 生成エンジン。banner-prompt-template.md のロジックをClaudeで自動化。

③提案の生成時に、修正版バナースクリプト（再現＋修正プロンプト）とコピー案を生成。
最終画像は人が制作（⑤でアップ）。画像は自前DL→base64（fbcdn期限URL対策）。
モデルは env ANTHROPIC_MODEL（既定 claude-opus-4-8）。
"""
from __future__ import annotations

import json
import os

from ..analysis.vision import download_image

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# action_type → 修正方針（banner-prompt-template.md 修正パターン）
MODIFY_GUIDE = {
    "expand": "訴求・構成は維持し、色や被写体のバリエーションのみ変える（横展開）。",
    "change_appeal": "ビジュアルは維持し、キャッチコピー（訴求文）を差し替える。",
    "change_visual": "訴求は維持し、テキスト量削減・背景/被写体・レイアウトを変える。",
}

# 返却JSON（structured outputs）
CREATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "reproduction_prompt": {"type": "string"},   # PART1 完全再現（英語）
        "modified_prompt": {"type": "string"},        # PART2 修正版（英語・// CHANGED付）
        "changed_notes": {"type": "array", "items": {"type": "string"}},  # 変更点
        "copy_variants": {"type": "array", "items": {"type": "string"}},  # コピー案（日本語）
    },
    "required": ["reproduction_prompt", "modified_prompt", "changed_notes", "copy_variants"],
    "additionalProperties": False,
}


def build_prompt(ad: dict, action_type: str) -> str:
    guide = MODIFY_GUIDE.get(action_type, MODIFY_GUIDE["expand"])
    return (
        "あなたはMeta広告バナーの再現プロンプト生成の専門家です。"
        "添付のバナー画像を分析し、GPT image系で再現→修正するための英語プロンプトを生成してください。\n\n"
        f"広告名: {ad.get('ad_name')} / ビジュアル: {ad.get('visual')} / 訴求軸: {ad.get('appeal_axis')}\n"
        f"改善方針（{action_type}）: {guide}\n\n"
        "出力要件（banner-prompt-template.md 準拠）:\n"
        "- reproduction_prompt: 画像を座標・色コード(#XXXXXX)・フォントサイズ付きで完全再現する英語プロンプト。"
        "日本語テキストは「」で正確に保持。OVERALL CANVAS/TEXT/VISUAL/CTA/COMPOSITION の構成。\n"
        "- modified_prompt: 上記を改善方針に沿って修正した英語プロンプト。変更箇所に `// CHANGED:` コメント。\n"
        "- changed_notes: 変更点の箇条書き（日本語）。\n"
        "- copy_variants: 改善方針に沿ったキャッチコピー案を3つ（日本語）。\n"
        "正方形1080x1080を既定とする。"
    )


def generate_creative(ad: dict, action_type: str, model: str | None = None) -> dict:
    """1提案分のバナースクリプト＋コピー案を生成（要 ANTHROPIC_API_KEY）。"""
    import anthropic

    if not ad.get("image_url"):
        return {"error": "no image_url"}
    img_b64, media_type = download_image(ad["image_url"])
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=6000,
        thinking={"type": "adaptive"},
        output_config={"format": {"type": "json_schema", "schema": CREATIVE_SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": build_prompt(ad, action_type)},
            ],
        }],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)
