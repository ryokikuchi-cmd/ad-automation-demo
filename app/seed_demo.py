"""承認UI＋レポート＋分析結果のデモ用 合成データ投入（ANTHROPIC/Metaトークン不要）。

月次総額が目標水準（≈¥750k/月）になるよう調整し、定例報告（目標vs実績）が成立する。
3期間（当月2026-06 / 前月2026-05 / 前年同月2025-06）× 多次元で生成。

使い方:
    DATABASE_URL=sqlite:///demo.db python3 app/seed_demo.py
    DATABASE_URL=sqlite:///demo.db python3 -m streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.db.models import (  # noqa: E402
    AdAccount, AnalysisRun, Appointment, Proposal, RawPlacement, RawAgeGender, Tenant)
from src.db.session import get_session, init_db  # noqa: E402

# 本物のバナー画像（ライブのMeta広告からDL済み・app/demo_images/）
IMG = "demo_images/cr{}.jpg"

# 本物の改善コピー案（CRのテーマに沿った3案）
COPY = {
    "ソーシャルセーリング_01": ["「応募が来ない」を、AIで解決。", "採用単価を半分に。AIが応募を自動最適化", "100名以上の応募実績。AI採用で母集団形成"],
    "20万_何人採用しても": ["何人採用しても、月額20万円。", "成功報酬ゼロ。定額で採用し放題", "採用コストを固定化。月20万で母集団形成"],
    "ソーシャルセーリング_03": ["採用担当の工数を80%削減。", "「もう採用に悩まない」現場の声", "母集団形成を自動化。担当者の手間ゼロへ"],
    "100名以上応募_介護": ["介護職、100名以上の応募実績。", "人手不足の介護現場へ、安定採用を。", "介護特化の採用支援で応募数3倍"],
    "動画_3秒_採用ブランディング": ["3秒で伝わる、採用ブランディング動画。", "スマホ縦型動画で若手応募を増やす", "動画で差をつける、これからの採用広報"],
}
# action別の変更方針
CHANGED = {
    "expand": ["訴求・構成は維持し、配色と被写体のバリエーションを追加", "勝ち要素（数値実績）を強調"],
    "change_appeal": ["ビジュアルは維持し、メインコピーを工数削減訴求へ変更", "ベネフィットを定量で提示"],
    "change_visual": ["訴求は維持し、テキスト量を3割削減・余白を確保", "背景を実写から図解へ変更しCTA帯を追加"],
}

# (campaign, adset, ad, cpm, ctr, monthly_impr, monthly_leads, quadrant, action, low)
CRS = [
    ("獲得CP_A", "ノンタゲ_0418_リード獲得", "ソーシャルセーリング_01", 4155, 0.0150, 30000, 31, "top_left", "expand", False),
    ("獲得CP_A", "ノンタゲ_0418_リード獲得", "20万_何人採用しても", 9344, 0.0153, 12000, 8, "bottom_left", "change_visual", False),
    ("獲得CP_A", "ノンタゲ_0418_リード獲得", "ソーシャルセーリング_03", 5869, 0.0086, 15000, 6, "top_right", "change_appeal", True),
    ("獲得CP_B", "ノンタゲ_0424_リード獲得-test", "100名以上応募_介護", 3951, 0.0174, 22000, 24, "top_left", "expand", False),
    ("獲得CP_B", "ノンタゲ_0424_リード獲得-test", "採用応募が来ない_建築", 11400, 0.0050, 8000, 2, "bottom_right", "pause", True),
    ("認知CP_C", "認知_動画_リーチ", "動画_3秒_採用ブランディング", 2800, 0.0210, 25000, 12, "top_left", "expand", False),
]
PLACEMENTS = [
    ("android_smartphone", "facebook", "feed", 0.20), ("android_smartphone", "instagram", "feed", 0.18),
    ("android_smartphone", "instagram", "instagram_stories", 0.15), ("android_smartphone", "instagram", "instagram_reels", 0.12),
    ("iphone", "facebook", "feed", 0.13), ("iphone", "instagram", "feed", 0.12),
    ("iphone", "instagram", "instagram_stories", 0.10),
]
AGE_GENDER = [
    ("18-24", "male", 0.06), ("18-24", "female", 0.05), ("25-34", "male", 0.18), ("25-34", "female", 0.16),
    ("35-44", "male", 0.16), ("35-44", "female", 0.14), ("45-54", "male", 0.10), ("45-54", "female", 0.09),
]
WEEKDAY = [1.0, 1.05, 0.95, 1.10, 0.90, 1.15, 0.85]
PERIODS = [(date(2026, 6, 1), 30, 1.00), (date(2026, 5, 1), 31, 0.90), (date(2025, 6, 1), 30, 0.72)]
APPT = {
    "ノンタゲ_0418_リード獲得": {date(2026, 6, 1): 12, date(2026, 5, 1): 11, date(2025, 6, 1): 7},
    "ノンタゲ_0424_リード獲得-test": {date(2026, 6, 1): 5, date(2026, 5, 1): 4, date(2025, 6, 1): 3},
    "認知_動画_リーチ": {date(2026, 6, 1): 3, date(2026, 5, 1): 2, date(2025, 6, 1): 1},
}
# (adset, 現状日予算, 推奨, 増減%, 理由)
BUDGET = [
    ("ノンタゲ_0418_リード獲得", 12000, "増額", 20,
     "勝ちCR『ソーシャルセーリング_01』が好調（CPM安×CTR高）。商談単価も目標圏内。予算拡大で獲得増を狙う"),
    ("ノンタゲ_0424_リード獲得-test", 6000, "減額", -20,
     "『採用応募が来ない_建築』がCPM高×CTR低・CV無し。停止対象CRを含むため一旦減額しCR入替を優先"),
    ("認知_動画_リーチ", 4000, "増額", 30,
     "CTR2.1%・CPM¥2,800と効率良好。動画フォーマットの拡大余地が大きい"),
]


def _days(first, n):
    return [first + timedelta(days=i) for i in range(n)]


def _distribute(total, weights):
    sw = sum(weights) or 1.0
    raw = [total * w / sw for w in weights]   # 重みを正規化（合計=total保証）
    base = [int(x) for x in raw]
    rem = total - sum(base)
    order = sorted(range(len(weights)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in range(rem):
        base[order[i % len(order)]] += 1
    return base


def main() -> None:
    init_db()
    s = get_session()
    s.add(Tenant(name="キープサーチ(デモ)"))
    s.commit()
    s.add(AdAccount(tenant_id=1, meta_account_id="act_demo", name="デモアカウント"))
    s.commit()

    place_rows, age_rows = [], []
    for cmp, adset, ad, cpm, ctr, m_impr, m_leads, *_ in CRS:
        for first, ndays, mfac in PERIODS:
            days = _days(first, ndays)
            dw = [WEEKDAY[d.weekday()] for d in days]
            impr_t = round(m_impr * mfac)
            cost_t = round(cpm * impr_t / 1000)
            clicks_t = round(ctr * impr_t)
            leads_t = round(m_leads * mfac)
            # placement: (day × placement) セルへ分配
            pcells = [(d, p) for d in days for p in PLACEMENTS]
            pw = [dw[i // len(PLACEMENTS)] * pcells[i][1][3] for i in range(len(pcells))]
            pi, pc, pk, pl = (_distribute(impr_t, pw), _distribute(cost_t, pw),
                              _distribute(clicks_t, pw), _distribute(leads_t, pw))
            for k, (d, (dev, med, plc, _w)) in enumerate(pcells):
                place_rows.append(dict(ad_account_id=1, date=d, campaign=cmp, adset=adset, ad=ad,
                                       device=dev, media=med, placement=plc,
                                       cost=pc[k], impressions=pi[k], clicks=pk[k], leads=pl[k]))
            # age_gender
            acells = [(d, a) for d in days for a in AGE_GENDER]
            aw = [dw[i // len(AGE_GENDER)] * acells[i][1][2] for i in range(len(acells))]
            ai, ac, ak, al = (_distribute(impr_t, aw), _distribute(cost_t, aw),
                              _distribute(clicks_t, aw), _distribute(leads_t, aw))
            for k, (d, (age, gender, _w)) in enumerate(acells):
                age_rows.append(dict(ad_account_id=1, date=d, campaign=cmp, adset=adset, ad=ad,
                                     age=age, gender=gender,
                                     cost=ac[k], impressions=ai[k], clicks=ak[k], leads=al[k]))
    s.bulk_insert_mappings(RawPlacement, place_rows)
    s.bulk_insert_mappings(RawAgeGender, age_rows)
    s.commit()

    for adset, months in APPT.items():
        for mdate, n in months.items():
            s.add(Appointment(ad_account_id=1, date=mdate, adset=adset, appointments=n, won=0))
    s.commit()

    run = AnalysisRun(ad_account_id=1, run_date=date(2026, 6, 30), status="done", params_json={})
    s.add(run)
    s.commit()
    appt_now = {a: m.get(date(2026, 6, 1), 0) for a, m in APPT.items()}

    # 新規CR提案＋CR停止提案（CR単位）
    for i, (cmp, adset, ad, cpm, ctr, m_impr, m_leads, quad, action, low) in enumerate(CRS):
        a = appt_now.get(adset, 0)
        detail = {"cpm": cpm, "ctr": ctr, "leads": m_leads, "low_data": low,
                  "adset_appointments": a, "adset_商談率": (a / m_leads) if m_leads else 0,
                  "visual": ad.split("_")[0], "appeal_axis": ad.split("_")[-1],
                  "image_url": IMG.format(i), "label": quad}
        if action == "pause":
            detail["note"] = "CPM高×CTR低・CV実績なし → 停止候補"
        cv, bp = None, None
        if action in ("expand", "change_appeal", "change_visual"):
            variants = COPY.get(ad, [f"{ad} 改善案A", f"{ad} 改善案B", f"{ad} 改善案C"])
            cv = {"variants": variants, "changed_notes": CHANGED.get(action, [])}
            bp = (f"Create a square Japanese recruitment ad banner, 1080x1080px, for Meta/Instagram feed.\n"
                  f"Reproduce the layout of the base creative, then modify per the improvement plan.\n"
                  f'Headline (Japanese, keep exactly): 「{variants[0]}」\n'
                  f"Sub copy: emphasize concrete results (e.g. 100+ applicants) with a gold badge.\n"
                  f"Background: clean BtoB navy-to-white gradient (#1a3a5c → #ffffff), high readability.\n"
                  f"CTA band at bottom: 「無料で資料請求」 on an orange button (#e8710a).\n"
                  f"// CHANGED ({action}): {' / '.join(CHANGED.get(action, []))}\n"
                  f"Use bold Noto Sans JP. Avoid distorted Japanese.")
        s.add(Proposal(analysis_run_id=run.id, adset=adset, ad=ad, quadrant=quad, action_type=action,
                       detail_json=detail, banner_prompt=bp, copy_variants=cv, status="pending"))

    # 広告予算提案（広告セット単位）
    for adset, cur, reco, pctv, reason in BUDGET:
        s.add(Proposal(analysis_run_id=run.id, adset=adset, ad=None, quadrant=None,
                       action_type="budget",
                       detail_json={"current_budget": cur, "recommended_budget": round(cur * (1 + pctv / 100)),
                                    "change_pct": pctv, "reco": reco, "reason": reason},
                       status="pending"))
    s.commit()
    print(f"デモ投入完了: placement {len(place_rows)}行 / age {len(age_rows)}行 / "
          f"商談 {sum(len(m) for m in APPT.values())}件 / 提案 {len(CRS)+len(BUDGET)}件")
    print("起動: python3 -m streamlit run app/streamlit_app.py")
    s.close()


if __name__ == "__main__":
    main()
