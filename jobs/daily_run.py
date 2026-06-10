"""日次バッチのエントリポイント（薄いオーケストレーション層）。

業務ロジックは src/ に集約。このファイルは「呼び出すだけ」に徹する
（→ UI/スケジューラを差し替えても src/ を無傷で流用するための分離）。

フロー: ⓪ingest → ②appointments → ①bi → ②analysis → ③proposal → ④creative → 通知
  ⑤入稿・⑥予算再配分は承認後に app(Streamlit) / 別ジョブで実行。
トークン: 各アカウントの access_token_enc（復号）優先、無ければ env META_ACCESS_TOKEN。
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.analysis.quadrant import active_adsets, analyze_adset  # noqa: E402
from src.appointments.import_sheet import import_appointments  # noqa: E402
from src.bi.aggregate import aggregate  # noqa: E402
from src.db.models import Ad, AdAccount, AnalysisRun, Appointment, Proposal, RawPlacement  # noqa: E402
from src.db.session import get_session, init_db  # noqa: E402
from src.ingest import ads as ads_ingest  # noqa: E402
from src.ingest import meta  # noqa: E402
from src.proposal.generate import generate_proposals  # noqa: E402


def load_config(path: str = "config/accounts.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _token_for(account: AdAccount) -> str | None:
    # MVP: 単一クライアントは env、複数化時はDBの暗号化トークンを復号
    return os.environ.get("META_ACCESS_TOKEN")  # TODO: decrypt(account.access_token_enc)


def _raw_to_df(session, account_id: int) -> pd.DataFrame:
    recs = [(r.ad, r.adset, r.date, float(r.cost or 0), r.impressions or 0, r.clicks or 0, r.leads or 0)
            for r in session.execute(
                select(RawPlacement).where(RawPlacement.ad_account_id == account_id)).scalars()]
    return pd.DataFrame(recs, columns=["ad", "adset", "date", "cost", "impressions", "clicks", "leads"])


def _run_vision(session, run_id: int, limit: int = 10) -> None:
    """提案のうち画像URLがある上位N件にVision因果分析を付与（任意ステップ）。"""
    from src.analysis.vision import analyze_creative

    props = (session.query(Proposal)
             .filter(Proposal.analysis_run_id == run_id)
             .filter(Proposal.quadrant.in_(["top_left", "top_right", "bottom_left"]))
             .limit(limit).all())
    done = 0
    for p in props:
        d = p.detail_json or {}
        if not d.get("image_url"):
            continue
        try:
            res = analyze_creative(
                {"ad_name": p.ad, "visual": d.get("visual"), "appeal_axis": d.get("appeal_axis"),
                 "image_url": d.get("image_url")},
                {"CPM": d.get("cpm", 0), "CTR": d.get("ctr", 0),
                 "quadrant": p.quadrant, "quadrant_label": d.get("label", "")})
            d["vision"] = res
            p.detail_json = d
            done += 1
        except Exception as ex:  # noqa: BLE001
            print(f"    vision skip {p.ad[:16]}: {type(ex).__name__}")
    session.commit()
    print(f"  ② Vision因果分析: {done}件")


def _run_creative(session, run_id: int, limit: int = 10) -> None:
    """④ バナースクリプト＋コピー案を提案に付与（新規CRを作る象限のみ）。"""
    from src.creative.banner import generate_creative

    props = (session.query(Proposal)
             .filter(Proposal.analysis_run_id == run_id)
             .filter(Proposal.action_type.in_(["expand", "change_appeal", "change_visual"]))
             .limit(limit).all())
    done = 0
    for p in props:
        d = p.detail_json or {}
        if not d.get("image_url"):
            continue
        try:
            res = generate_creative(
                {"ad_name": p.ad, "visual": d.get("visual"),
                 "appeal_axis": d.get("appeal_axis"), "image_url": d.get("image_url")},
                p.action_type)
            p.banner_prompt = res.get("modified_prompt") or res.get("reproduction_prompt")
            p.copy_variants = {"variants": res.get("copy_variants", []),
                               "reproduction_prompt": res.get("reproduction_prompt"),
                               "changed_notes": res.get("changed_notes", [])}
            done += 1
        except Exception as ex:  # noqa: BLE001
            print(f"    creative skip {p.ad[:16]}: {type(ex).__name__}")
    session.commit()
    print(f"  ④ バナー生成: {done}件")


def run(config_path: str = "config/accounts.yaml", lookback_days: int = 7) -> None:
    init_db()
    cfg = load_config(config_path)
    until = date.today()
    since = until - timedelta(days=lookback_days)
    session = get_session()

    for tenant in cfg.get("tenants", []):
        for acc_cfg in tenant.get("ad_accounts", []):
            mid = acc_cfg["meta_account_id"]
            account = session.execute(
                select(AdAccount).where(AdAccount.meta_account_id == mid)).scalar_one_or_none()
            if account is None:
                print(f"  [skip] {mid} 未登録（先にtenants/ad_accountsへ登録）")
                continue
            token = _token_for(account)
            print(f"=== {tenant['name']} / {mid} ===")

            # ⓪ Meta取得 → raw_*
            if token:
                res = meta.fetch_and_store(session, account, token,
                                           since.isoformat(), until.isoformat())
                print(f"  ⓪ ingest: placement={res['placement']} age_gender={res['age_gender']}")
                # Phase1: 広告マスタ（ad_id主キー・画像URL・命名パース）
                n_ads = ads_ingest.fetch_and_store_ads(session, account, token)
                print(f"  Ⓜ ads master: {n_ads}件")
            else:
                print("  ⓪ ingest: スキップ（META_ACCESS_TOKEN未設定）")

            # ② 商談取込（特定スプシ）→ appointments
            sheet_cfg = acc_cfg.get("appointments_sheet")
            if sheet_cfg and not str(sheet_cfg.get("spreadsheet_id", "")).startswith("REPLACE"):
                known = {a.adset for a in session.query(Ad).filter(Ad.ad_account_id == account.id)}
                try:
                    rep = import_appointments(session, account, sheet_cfg, known_adsets=known or None)
                    print(f"  ② 商談取込: {rep.imported}件 / skip {rep.skipped} / 不一致セット {len(set(rep.unmatched_adsets))}")
                except Exception as ex:  # noqa: BLE001
                    print(f"  ② 商談取込スキップ（{type(ex).__name__}: {str(ex)[:60]}）")

            # ①②③ 分析・提案
            params = acc_cfg.get("analysis", {})
            df = _raw_to_df(session, account.id)
            if df.empty:
                print("  raw無し → 分析スキップ")
                continue

            # 広告メタ（visual/appeal/image_url）と 広告セット別商談 を準備
            ad_meta = {a.ad_name: a for a in session.query(Ad).filter(Ad.ad_account_id == account.id)}
            appt_rows = session.query(Appointment).filter(Appointment.ad_account_id == account.id).all()
            adset_appt: dict[str, int] = {}
            for ap in appt_rows:
                adset_appt[ap.adset] = adset_appt.get(ap.adset, 0) + (ap.appointments or 0)

            daily_adset = df.groupby(["date", "adset"], as_index=False)["cost"].sum()
            actives = active_adsets(daily_adset, pd.Timestamp(until),
                                    params.get("active_days", 5))
            run_row = AnalysisRun(ad_account_id=account.id, run_date=until,
                                  params_json=params, status="running")
            session.add(run_row)
            session.commit()

            total = 0
            for adset in actives:
                sub = df[df["adset"] == adset]
                an = analyze_adset(aggregate(sub, ["ad"]),
                                   params.get("min_impressions", 5000),
                                   params.get("min_leads", 5))
                # 広告セット別CV（商談は広告セット単位で結合）
                a_cost = float(sub["cost"].sum())
                a_leads = int(sub["leads"].sum())
                a_appt = adset_appt.get(adset, 0)
                cv = {"adset_appointments": a_appt,
                      "adset_商談率": (a_appt / a_leads) if a_leads else 0,
                      "adset_商談単価": (a_cost / a_appt) if a_appt else 0}
                for d in generate_proposals(an, adset):
                    meta_ad = ad_meta.get(d.ad)
                    d.detail.update(cv)
                    if meta_ad:
                        d.detail.update({"visual": meta_ad.visual, "appeal_axis": meta_ad.appeal_axis,
                                         "image_url": meta_ad.image_url})
                    session.add(Proposal(analysis_run_id=run_row.id, adset=d.adset, ad=d.ad,
                                         quadrant=d.quadrant, action_type=d.action_type,
                                         detail_json=d.detail, status="pending"))
                    total += 1
            run_row.status = "done"
            session.commit()
            print(f"  ①②③ 分析完了: アクティブ広告セット{len(actives)}件 / 提案{total}件(pending)")
            # ② Vision因果分析（任意・コスト高のためconfigでgate）
            if params.get("vision") and os.environ.get("ANTHROPIC_API_KEY"):
                _run_vision(session, run_row.id, limit=params.get("vision_limit", 10))
            # ④ バナー生成（③提案時にスクリプト生成・configでgate）
            if params.get("creative") and os.environ.get("ANTHROPIC_API_KEY"):
                _run_creative(session, run_row.id, limit=params.get("creative_limit", 10))
            # 通知・⑤入稿は承認後に実行

    session.close()
    print("done.")


if __name__ == "__main__":
    run()
