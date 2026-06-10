"""⓪ Meta Marketing APIからインサイトを取得（fetch層）。

実績ある取得ロジック（AIレポート/キープサーチ/fetch_incremental.py）を移植。
読み取り（ads_read）で動作。トークン取得済みのため即実行可能。

設計: fetch（このファイル・API依存／DB非依存）と store（store.py・DB依存）を分離。
      → SDKだけで fetch を単体テストできる。
"""
from __future__ import annotations

import time
from datetime import date as _date

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.api import FacebookAdsApi


def _parse_date(v):
    """Meta APIの date_start（'YYYY-MM-DD' 文字列）を date に変換。"""
    if v is None or isinstance(v, _date):
        return v
    return _date.fromisoformat(str(v)[:10])

INSIGHT_FIELDS = ["ad_id", "ad_name", "adset_name", "campaign_name",
                  "spend", "impressions", "clicks", "actions"]
PLACEMENT_BREAKDOWNS = ["impression_device", "publisher_platform", "platform_position"]
AGE_GENDER_BREAKDOWNS = ["age", "gender"]
LEAD_ACTION_TYPES = ("lead", "offsite_conversion.fb_pixel_lead")


def _lead(entry) -> int:
    leads = 0
    for a in (entry.get("actions") or []):
        if a.get("action_type") in LEAD_ACTION_TYPES:
            leads = max(leads, int(a["value"]))
    return leads


def _placement_row(e, account_id: str) -> dict:
    return {
        "meta_account_id": account_id, "date": _parse_date(e.get("date_start")),
        "campaign": e.get("campaign_name"), "adset": e.get("adset_name"), "ad": e.get("ad_name"),
        "device": e.get("impression_device"), "media": e.get("publisher_platform"),
        "placement": e.get("platform_position"),
        "cost": float(e.get("spend", 0)), "impressions": int(e.get("impressions", 0)),
        "clicks": int(e.get("clicks", 0)), "leads": _lead(e),
    }


def _age_gender_row(e, account_id: str) -> dict:
    return {
        "meta_account_id": account_id, "date": _parse_date(e.get("date_start")),
        "campaign": e.get("campaign_name"), "adset": e.get("adset_name"), "ad": e.get("ad_name"),
        "age": e.get("age"), "gender": e.get("gender"),
        "cost": float(e.get("spend", 0)), "impressions": int(e.get("impressions", 0)),
        "clicks": int(e.get("clicks", 0)), "leads": _lead(e),
    }


def fetch_insights(account_id: str, access_token: str, since: str, until: str,
                   breakdowns: list[str], row_fn, retries: int = 6) -> list[dict]:
    """指定期間・breakdownのインサイトを日次粒度で取得（リトライ付き）。"""
    FacebookAdsApi.init(access_token=access_token)
    account = AdAccount(account_id)
    params = {"level": "ad", "time_range": {"since": since, "until": until},
              "breakdowns": breakdowns, "time_increment": 1}
    for r in range(retries):
        try:
            return [row_fn(e, account_id)
                    for e in account.get_insights(fields=INSIGHT_FIELDS, params=params)]
        except Exception as ex:  # noqa: BLE001
            if r == retries - 1:
                raise
            time.sleep(60 * (r + 1))
    return []


def fetch_placement(account_id: str, access_token: str, since: str, until: str) -> list[dict]:
    """raw_placement 用（デバイス×媒体×配置）。"""
    return fetch_insights(account_id, access_token, since, until,
                          PLACEMENT_BREAKDOWNS, _placement_row)


def fetch_age_gender(account_id: str, access_token: str, since: str, until: str) -> list[dict]:
    """raw_age_gender 用（年齢×性別）。"""
    return fetch_insights(account_id, access_token, since, until,
                          AGE_GENDER_BREAKDOWNS, _age_gender_row)


def fetch_and_store(session, ad_account, access_token: str, since: str, until: str) -> dict:
    """1アカウント分を取得 → DBへUPSERT（store層を遅延import）。

    ad_account: AdAccount ORMインスタンス（id と meta_account_id を持つ）
    遅延CV対策: since は until-7日程度で再取得・上書きする運用。
    """
    from . import store  # 遅延import（fetch単体テスト時はsqlalchemy不要）

    plc = fetch_placement(ad_account.meta_account_id, access_token, since, until)
    age = fetch_age_gender(ad_account.meta_account_id, access_token, since, until)
    n_plc = store.upsert_placement(session, ad_account.id, plc)
    n_age = store.upsert_age_gender(session, ad_account.id, age)
    return {"placement": n_plc, "age_gender": n_age, "since": since, "until": until}
