"""Phase1-残 広告マスタ取込。Meta APIで広告ID・名・クリエイティブ画像URLを取得し
ads テーブルへ upsert（主キー: meta_ad_id）。

raw_* は広告「名」で集計、ads は広告「ID」で一意管理 → ad_idで突合できる。
visual/appeal_axis は命名規則パース（src/analysis/naming.py）で付与。
"""
from __future__ import annotations

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.api import FacebookAdsApi

from ..analysis.naming import parse_ad_name
from ..db.models import Ad

# creative のサブフィールドを展開して画像URLを取得
AD_FIELDS = ["id", "name", "status",
             "adset{name}", "campaign{name}",
             "creative{id,image_url,thumbnail_url,object_type}"]


def _creative_image(creative: dict | None) -> tuple[str | None, str | None]:
    """creativeから (image_url, creative_type) を抽出。画像が無ければthumbnail。"""
    if not creative:
        return None, None
    url = creative.get("image_url") or creative.get("thumbnail_url")
    ctype = creative.get("object_type")  # PHOTO/VIDEO/SHARE 等
    return url, ctype


def fetch_ads(account_id: str, access_token: str, limit: int = 500) -> list[dict]:
    """アカウントの全広告（メタデータ＋クリエイティブ画像URL）を取得。"""
    FacebookAdsApi.init(access_token=access_token)
    account = AdAccount(account_id)
    out: list[dict] = []
    for ad in account.get_ads(fields=AD_FIELDS, params={"limit": limit}):
        d = ad.export_all_data()
        img, ctype = _creative_image(d.get("creative"))
        name = d.get("name", "")
        adset = (d.get("adset") or {}).get("name")
        visual, appeal = parse_ad_name(name, adset)
        out.append({
            "meta_ad_id": d.get("id"), "ad_name": name,
            "campaign": (d.get("campaign") or {}).get("name"),
            "adset": adset, "status": d.get("status"),
            "image_url": img, "creative_type": ctype,
            "visual": visual, "appeal_axis": appeal,
        })
    return out


def upsert_ads(session, ad_account_id: int, rows: list[dict]) -> int:
    """meta_ad_id 単位でupsert（既存は更新、新規は追加）。"""
    for r in rows:
        existing = session.query(Ad).filter(
            Ad.ad_account_id == ad_account_id, Ad.meta_ad_id == r["meta_ad_id"]).one_or_none()
        if existing:
            for k, v in r.items():
                setattr(existing, k, v)
        else:
            session.add(Ad(ad_account_id=ad_account_id, **r))
    session.commit()
    return len(rows)


def fetch_and_store_ads(session, ad_account, access_token: str) -> int:
    rows = fetch_ads(ad_account.meta_account_id, access_token)
    return upsert_ads(session, ad_account.id, rows)
