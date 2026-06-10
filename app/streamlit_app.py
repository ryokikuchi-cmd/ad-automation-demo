"""⑤ 分析結果＋広告数値レポート＋改善提案（Streamlit・デモ）。

サイドバーで3ビュー切替（再実行でも維持）:
  📈 分析結果   … 定例報告（目標vs実績・評価・広告セット別所感）＝提案の根拠
  📊 レポート   … 7ブレイクダウンをタブ分割／期間・前月比/前年同月比
  💡 改善提案   … 広告予算提案／CR停止提案／新規CR提案 の3種
起動: DATABASE_URL=sqlite:///demo.db python3 -m streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import calendar
import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.analysis.quadrant import analyze_adset  # noqa: E402
from src.bi.aggregate import add_derived_metrics, aggregate  # noqa: E402
from src.db.models import Appointment, Proposal, RawAgeGender, RawPlacement  # noqa: E402
from src.db.session import get_session  # noqa: E402

st.set_page_config(page_title="Meta Ad Automation", layout="wide")
session = get_session()

# クラウド共有用: 初回起動でDBが空なら自動でデモデータ投入
try:
    from src.db.models import RawPlacement as _RP
    from src.db.session import init_db as _init_db
    _init_db()
    if session.query(_RP).count() == 0:
        sys.path.append(str(Path(__file__).parent))
        import seed_demo
        seed_demo.main()
        session = get_session()
except Exception as _e:  # noqa: BLE001
    st.warning(f"初期データ投入をスキップしました: {_e}")

# 月次目標（定例報告の目標行）
TARGETS = {"cost": 800000, "impressions": 165882, "CPM": 4823, "clicks": 2856, "CPC": 280,
           "CTR": 0.0172, "leads": 123, "資料請求率": 0.0431, "資料請求単価": 6500,
           "appointments": 32, "商談率": 0.26, "商談単価": 25000}

st.markdown("""<style>
:root{--c-primary:#1a3a5c;--c-bg:#f3f5f9;--c-surface:#fff;--c-border:#e8eaed;
--c-text:#1a1a2e;--c-text-secondary:#5f6368;--c-text-muted:#9aa0a6;
--c-success:#0d904f;--c-danger:#d32f2f;--radius:10px;--radius-sm:6px;}
.stApp{background:var(--c-bg);}
header[data-testid="stHeader"]{background:transparent;height:0;}
#MainMenu,footer{visibility:hidden;}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--c-border);}
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1180px;}
.app-header{background:var(--c-primary);color:#fff;border-radius:var(--radius);
padding:14px 22px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;
box-shadow:0 2px 8px rgba(0,0,0,.12);}
.app-title{font-size:17px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;}
.app-meta{font-size:12px;opacity:.85;}
.cards-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:6px 0 18px;}
.metric-card{background:#fff;border:1px solid var(--c-border);border-radius:var(--radius);
padding:15px 18px;box-shadow:0 1px 3px rgba(0,0,0,.08);}
.metric-label{font-size:11px;color:var(--c-text-muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;}
.metric-value{font-size:22px;font-weight:700;color:var(--c-primary);line-height:1.2;}
.metric-change{font-size:12px;font-weight:600;margin-top:4px;}
.up{color:var(--c-success);}.down{color:var(--c-danger);}.flat{color:var(--c-text-muted);}
.sec-title{font-size:14px;font-weight:700;color:var(--c-text);margin:18px 0 8px;
padding-left:8px;border-left:3px solid var(--c-primary);}
table.rep{width:100%;border-collapse:collapse;font-size:13px;background:#fff;
border:1px solid var(--c-border);border-radius:var(--radius);overflow:hidden;}
table.rep thead th{background:#f8f9fa;color:var(--c-text-secondary);text-align:left;
padding:10px 12px;font-weight:600;border-bottom:1px solid var(--c-border);}
table.rep tbody td{padding:9px 12px;border-bottom:1px solid #f0f0f0;color:var(--c-text);}
table.rep tbody tr:nth-child(even){background:#fcfcfd;}
table.rep tbody tr:hover{background:#f5f6f8;}
.num{text-align:right;font-variant-numeric:tabular-nums;}
.eval-note{background:#fff;border:1px solid var(--c-border);border-left:3px solid var(--c-primary);
border-radius:var(--radius-sm);padding:10px 14px;margin:8px 0;font-size:13px;color:var(--c-text);}
.prop{background:#fff;border:1px solid var(--c-border);border-radius:var(--radius);
padding:12px 15px;box-shadow:0 1px 3px rgba(0,0,0,.06);}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600;color:#fff;margin-right:6px;}
.b-green{background:var(--c-success);}.b-amber{background:#e8710a;}.b-red{background:var(--c-danger);}.b-blue{background:#1a73e8;}
.prop-ad{font-weight:700;font-size:14px;color:var(--c-text);}
.prop-act{font-size:12px;color:var(--c-text-secondary);}
.prop-line{font-size:12px;color:var(--c-text-secondary);margin-top:5px;}
.prop-copy{font-size:12px;color:var(--c-text);margin-top:4px;}
/* DEMOバナー */
.demo-banner{background:#fff3e0;color:#e8710a;text-align:center;font-size:12px;font-weight:600;
padding:7px;border-radius:6px;margin-bottom:10px;border:1px solid #ffe0b2;}
/* サイドバー ナビ（参考RPP風・アクティブはブルー） */
section[data-testid="stSidebar"] [role="radiogroup"]{gap:4px;margin-top:4px;}
section[data-testid="stSidebar"] [role="radiogroup"] label{display:flex;align-items:center;width:100%;
padding:9px 12px;border-radius:8px;cursor:pointer;font-size:14px;color:var(--c-text);transition:background .15s;}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(26,58,92,.06);}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#1a73e8;color:#fff;font-weight:600;}
section[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none;}
/* st.container(border=True) をカード化 */
div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:var(--radius);
box-shadow:0 1px 3px rgba(0,0,0,.07);}
.card-badge{display:inline-block;background:#e8f5e9;color:#0d904f;font-size:11px;font-weight:600;
padding:2px 10px;border-radius:20px;float:right;}
</style>""", unsafe_allow_html=True)

# 大項目：広告媒体（プラットフォーム）
PLATFORMS = ["META", "Google", "X（旧Twitter）", "LINE", "TikTok"]
platform = st.sidebar.selectbox("広告媒体（プラットフォーム）", PLATFORMS, index=0, key="platform")
st.sidebar.markdown("---")

st.markdown('<div class="demo-banner">DEMO MODE — このツールはデモ用のサンプルデータで動作しています</div>',
            unsafe_allow_html=True)
st.markdown(f'<div class="app-header"><div class="app-title">{platform} Ad Automation</div>'
            '<div class="app-meta">キープサーチ（デモ）</div></div>', unsafe_allow_html=True)

if platform != "META":
    st.info(f"🚧 {platform}広告 は現在開発中です（β）。本デモは左上で「META」を選択してご確認ください。")
    st.stop()

view = st.sidebar.radio("メニュー", ["📊 広告数値レポート", "📈 分析結果", "💡 改善提案",
                                  "⚙️ 広告運用設定"], key="nav")


def yen(x):
    return f"¥{x:,.0f}" if x else "¥-"


def pct(x):
    return f"{x*100:.2f}%"


def num(x):
    return f"{int(x):,}"


def signed(x, fmt):
    return ("+" if x >= 0 else "−") + fmt(abs(x))


def add_months(d, k):
    m = d.month - 1 + k
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def shift(start, end, mode):
    if mode == "前年同月比":
        try:
            return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
        except ValueError:
            return date(start.year - 1, start.month, 1), date(end.year - 1, end.month, 28)
    return add_months(start, -1), add_months(end, -1)


def chg_html(cur, comp):
    if not comp:
        return '<div class="metric-change flat">— 比較データなし</div>'
    r = (cur - comp) / comp
    return f'<div class="metric-change {"up" if r>=0 else "down"}">{"▲" if r>=0 else "▼"}{abs(r)*100:.1f}%</div>'


def chg_cell(cur, comp):
    if not comp:
        return '<span class="flat">—</span>'
    r = (cur - comp) / comp
    return f'<span class="{"up" if r>=0 else "down"}">{"▲" if r>=0 else "▼"}{abs(r)*100:.1f}%</span>'


def load_df(model):
    extra = ["age", "gender"] if model is RawAgeGender else ["device", "media", "placement"]
    rows = []
    for r in session.query(model).all():
        base = {"date": r.date, "campaign": r.campaign, "adset": r.adset, "ad": r.ad,
                "cost": float(r.cost or 0), "impressions": r.impressions or 0,
                "clicks": r.clicks or 0, "leads": r.leads or 0}
        for e in extra:
            base[e] = getattr(r, e)
        rows.append(base)
    return pd.DataFrame(rows)


def img_src(val):
    """image_url がURLならそのまま、ローカル相対パスなら絶対パスへ解決。"""
    if not val:
        return None
    if str(val).startswith("http"):
        return val
    p = Path(__file__).parent / val
    return str(p) if p.exists() else None


def appt_df(a, b):
    rows = [(x.adset, x.appointments or 0, x.won or 0)
            for x in session.query(Appointment).filter(Appointment.date >= a, Appointment.date <= b)]
    return pd.DataFrame(rows, columns=["adset", "appointments", "won"])


def summary(df, ap):
    return add_derived_metrics(pd.DataFrame([{
        "cost": df["cost"].sum(), "impressions": df["impressions"].sum(),
        "clicks": df["clicks"].sum(), "leads": df["leads"].sum(),
        "appointments": int(ap["appointments"].sum()) if not ap.empty else 0, "won": 0}])).iloc[0]


def period_controls(plc, key):
    dmin, dmax = plc["date"].min(), plc["date"].max()
    c1, c2 = st.columns([2, 1.2])
    rng = c1.date_input("期間", value=(date(2026, 6, 1), date(2026, 6, 30)),
                        min_value=dmin, max_value=dmax, key=f"d{key}")
    mode = c2.radio("比較", ["前月比", "前年同月比"], horizontal=True, key=f"m{key}")
    start, end = rng if isinstance(rng, tuple) and len(rng) == 2 else (date(2026, 6, 1), date(2026, 6, 30))
    cs, ce = shift(start, end, mode)
    st.caption(f"当期 {start}〜{end}　／　比較（{mode}）{cs}〜{ce}")
    return start, end, cs, ce, mode


plc_all = load_df(RawPlacement)
age_all = load_df(RawAgeGender)


def in_period(df, a, b):
    return df[(df["date"] >= a) & (df["date"] <= b)]


def rep_table(cur_df, cmp_df, keys, header, with_appt=False, ap=None):
    acur = aggregate(cur_df, keys, appointments=ap if with_appt else None,
                     appt_keys=keys if with_appt else None).sort_values("cost", ascending=False)
    if cmp_df is not None and not cmp_df.empty:
        prev = cmp_df.groupby(keys, dropna=False)["cost"].sum().reset_index().rename(columns={"cost": "cost_prev"})
        acur = acur.merge(prev, on=keys, how="left")
    else:
        acur["cost_prev"] = None
    th = [header, "費用", "前期比", "CPM", "CTR", "資料請求", "資料請求単価"] + (["商談", "商談率"] if with_appt else [])
    head = "".join(f"<th>{t}</th>" for t in th)
    body = ""
    for _, r in acur.iterrows():
        label = " / ".join(str(r[k]) for k in keys)
        tds = [f"<td>{label}</td>", f'<td class="num">{yen(r["cost"])}</td>',
               f'<td class="num">{chg_cell(r["cost"], r.get("cost_prev"))}</td>',
               f'<td class="num">{yen(r["CPM"])}</td>', f'<td class="num">{pct(r["CTR"])}</td>',
               f'<td class="num">{num(r["leads"])}</td>', f'<td class="num">{yen(r["資料請求単価"])}</td>']
        if with_appt:
            tds += [f'<td class="num">{num(r.get("appointments",0))}</td>', f'<td class="num">{pct(r.get("商談率",0))}</td>']
        body += f"<tr>{''.join(tds)}</tr>"
    return f'<table class="rep"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


# CR分析ロジック（4象限）の象限定義: ラベル / 解釈 / 推奨アクション
QUAD_INFO = {
    "top_left": ("🟢 勝ちCR", "Meta評価◎ × 顧客評価◎（効率良く興味喚起できている）", "横展開：予算集中・複製"),
    "top_right": ("🟡 訴求が弱い", "Meta評価◎ × 顧客評価△（配信は出るがCTRが低い）", "訴求変更：コピー差し替え"),
    "bottom_left": ("🟡 顧客のみ反応", "Meta評価△ × 顧客評価◎（刺さるがCPMが高い）", "ビジュアル/構成変更"),
    "bottom_right": ("🔴 停止候補", "Meta評価△ × 顧客評価△（両方で劣後）", "停止"),
}
QUAD_COLOR = {"top_left": "#0d904f", "top_right": "#e8710a", "bottom_left": "#e8710a", "bottom_right": "#d32f2f"}


def cr_logic_table(an, cpm_th, ctr_th):
    head = "".join(f"<th>{t}</th>" for t in
                   ["CR", "CPM", "CPM判定", "CTR", "CTR判定", "象限", "解釈", "→ 推奨アクション"])
    body = ""
    for _, r in an.sort_values("cost", ascending=False).iterrows():
        cpm_j = "安 ◎" if r["CPM"] <= cpm_th else "高 △"
        ctr_j = "高 ◎" if r["CTR"] >= ctr_th else "低 △"
        lbl, interp, action = QUAD_INFO[r["quadrant"]]
        low = ' <span class="flat">⚠️参考値</span>' if r["low_data"] else ""
        body += (f'<tr><td>{r["ad"]}{low}</td><td class="num">{yen(r["CPM"])}</td><td>{cpm_j}</td>'
                 f'<td class="num">{pct(r["CTR"])}</td><td>{ctr_j}</td><td>{lbl}</td>'
                 f'<td>{interp}</td><td><b>{action}</b></td></tr>')
    return f'<table class="rep"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def cr_scatter(an, cpm_th, ctr_th):
    df = an[["ad", "CPM", "CTR", "quadrant"]].copy()
    xenc = alt.X("CPM:Q", title="CPM（右ほど安い＝Meta評価◎）", scale=alt.Scale(reverse=True))
    yenc = alt.Y("CTR:Q", title="CTR（上ほど高い＝顧客評価◎）", axis=alt.Axis(format="%"))
    pts = alt.Chart(df).mark_circle(size=240, opacity=0.85).encode(
        x=xenc, y=yenc,
        color=alt.Color("quadrant:N", scale=alt.Scale(domain=list(QUAD_COLOR), range=list(QUAD_COLOR.values())), legend=None),
        tooltip=["ad", "CPM", "CTR", "quadrant"])
    txt = alt.Chart(df).mark_text(dy=-15, fontSize=11).encode(x=xenc, y=yenc, text="ad")
    vline = alt.Chart(pd.DataFrame({"x": [cpm_th]})).mark_rule(strokeDash=[5, 5], color="#9aa0a6").encode(
        x=alt.X("x:Q", scale=alt.Scale(reverse=True)))
    hline = alt.Chart(pd.DataFrame({"y": [ctr_th]})).mark_rule(strokeDash=[5, 5], color="#9aa0a6").encode(y="y:Q")
    return (vline + hline + pts + txt).properties(height=280)


def render_cr_logic(cur_df):
    st.markdown(
        '<div class="eval-note">各広告セット内で <b>CPM中央値・CTR中央値</b> を閾値に、'
        '<b>CPM（配信効率＝Meta評価）× CTR（興味喚起＝顧客評価）</b> の4象限で各CRを分類し、'
        '象限ごとに改善アクションを導出します。<br>'
        '🟢勝ち＝横展開／🟡訴求弱＝訴求変更／🟡顧客のみ＝ビジュアル変更／🔴劣後＝停止</div>',
        unsafe_allow_html=True)
    for adset in sorted(cur_df["adset"].dropna().unique()):
        cr = aggregate(cur_df[cur_df["adset"] == adset], ["ad"])
        if cr.empty:
            continue
        an = analyze_adset(cr)
        cpm_th, ctr_th = an.attrs["cpm_threshold"], an.attrs["ctr_threshold"]
        st.markdown(f'<div class="sec-title">📦 {adset}　'
                    f'<span style="font-weight:400;font-size:12px;color:var(--c-text-secondary)">'
                    f'閾値：CPM中央値 {yen(cpm_th)} ／ CTR中央値 {pct(ctr_th)}</span></div>',
                    unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1])
        with col1:
            st.altair_chart(cr_scatter(an, cpm_th, ctr_th), use_container_width=True)
        with col2:
            st.markdown(cr_logic_table(an, cpm_th, ctr_th), unsafe_allow_html=True)


# ============================ 📈 分析結果 ============================
if view == "📈 分析結果":
    if plc_all.empty:
        st.info("データがありません。`python3 app/seed_demo.py` を実行してください。")
        st.stop()
    start, end, cs, ce, mode = period_controls(plc_all, "an")
    cur, cmp = in_period(plc_all, start, end), in_period(plc_all, cs, ce)
    ap_cur, ap_cmp = appt_df(start, end), appt_df(cs, ce)
    mc, mp = summary(cur, ap_cur), summary(cmp, ap_cmp)

    # 全体配信結果（目標 vs 実績 vs 差分 vs 評価）
    st.markdown('<div class="sec-title">全体配信結果（目標 vs 実績）</div>', unsafe_allow_html=True)
    NARR = [("費用", "cost", yen, True), ("Imps", "impressions", num, False), ("CPM", "CPM", yen, True),
            ("Clicks", "clicks", num, False), ("CPC", "CPC", yen, True), ("CTR", "CTR", pct, False),
            ("資料請求", "leads", num, False), ("資料請求率", "資料請求率", pct, False),
            ("資料請求単価", "資料請求単価", yen, True), ("商談", "appointments", num, False),
            ("商談率", "商談率", pct, False), ("商談単価", "商談単価", yen, True)]

    def mark(actual, target, lower):
        if target == 0:
            return "—"
        ok = actual <= target if lower else actual >= target
        near = actual <= target * 1.2 if lower else actual >= target * 0.8
        return "○" if ok else ("△" if near else "×")

    rows = ""
    for label, key, fmt, lower in NARR:
        a, t = mc[key], TARGETS[key]
        rows += (f'<tr><td>{label}</td><td class="num">{fmt(t)}</td><td class="num">{fmt(a)}</td>'
                 f'<td class="num">{signed(a-t, fmt)}</td><td class="num">{mark(a,t,lower)}</td></tr>')
    st.markdown(f'<table class="rep"><thead><tr><th>指標</th><th>目標</th><th>実績</th>'
                f'<th>差分</th><th>評価</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)

    # 評価結果（資料請求単価／商談単価）
    cpl_chg = (mc["資料請求単価"] - mp["資料請求単価"]) / mp["資料請求単価"] if mp["資料請求単価"] else 0
    cpa_chg = (mc["商談単価"] - mp["商談単価"]) / mp["商談単価"] if mp["商談単価"] else 0
    st.markdown('<div class="sec-title">評価結果</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="eval-note">・<b>資料請求単価 {mark(mc["資料請求単価"],TARGETS["資料請求単価"],True)}</b>：'
        f'実績{yen(mc["資料請求単価"])}（目標{yen(TARGETS["資料請求単価"])}）。{mode} {cpl_chg*100:+.1f}%。<br>'
        f'　主因はCPM{yen(mc["CPM"])}・CTR{pct(mc["CTR"])}。新規CR/セグメント追加で改善余地。<br>'
        f'・<b>商談単価 {mark(mc["商談単価"],TARGETS["商談単価"],True)}</b>：'
        f'実績{yen(mc["商談単価"])}（目標{yen(TARGETS["商談単価"])}）。{mode} {cpa_chg*100:+.1f}%。<br>'
        f'　商談率{pct(mc["商談率"])}。資料請求単価の改善が商談単価改善の重心。</div>', unsafe_allow_html=True)

    # 広告セット別 配信結果
    st.markdown('<div class="sec-title">広告セット毎の配信結果</div>', unsafe_allow_html=True)
    st.markdown(rep_table(cur, cmp, ["adset"], "広告セット", with_appt=True, ap=ap_cur), unsafe_allow_html=True)

    # 広告セット別 評価結果（資料請求単価／商談単価）
    st.markdown('<div class="sec-title">広告セット別 評価結果</div>', unsafe_allow_html=True)
    aset_cur = aggregate(cur, ["adset"], appointments=ap_cur, appt_keys=["adset"]).sort_values("cost", ascending=False)
    aset_cmp = aggregate(cmp, ["adset"], appointments=ap_cmp, appt_keys=["adset"])
    cmpmap = {r["adset"]: r for _, r in aset_cmp.iterrows()}

    def chg_txt(curv, prevv):
        return f"{mode} {((curv-prevv)/prevv)*100:+.1f}%" if prevv else "（比較データなし）"

    for _, r in aset_cur.iterrows():
        prev = cmpmap.get(r["adset"])
        has = r["appointments"] > 0
        m_cpl = mark(r["資料請求単価"], TARGETS["資料請求単価"], True)
        m_cpa = mark(r["商談単価"], TARGETS["商談単価"], True) if has else "—"
        cpl_c = chg_txt(r["資料請求単価"], prev["資料請求単価"] if prev is not None else 0)
        cpa_c = chg_txt(r["商談単価"], prev["商談単価"] if prev is not None and prev["appointments"] > 0 else 0)
        cpa_line = (f'実績{yen(r["商談単価"])}（目標{yen(TARGETS["商談単価"])}）。{cpa_c}。<br>'
                    f'　商談率{pct(r["商談率"])}。資料請求単価の改善が商談単価改善の重心。'
                    if has else "この期間の商談データなし。")
        st.markdown(
            f'<div class="eval-note"><b>○ {r["adset"]}</b><br>'
            f'・<b>資料請求単価 {m_cpl}</b>：実績{yen(r["資料請求単価"])}（目標{yen(TARGETS["資料請求単価"])}）。{cpl_c}。<br>'
            f'　主因はCPM{yen(r["CPM"])}・CTR{pct(r["CTR"])}。新規CR/セグメント追加で改善余地。<br>'
            f'・<b>商談単価 {m_cpa}</b>：{cpa_line}</div>', unsafe_allow_html=True)

    # CR別パフォーマンス（実数）
    st.markdown('<div class="sec-title">クリエイティブ別パフォーマンス</div>', unsafe_allow_html=True)
    st.markdown(rep_table(cur, cmp, ["ad"], "CR"), unsafe_allow_html=True)

    # CR分析ロジック（改善提案の導出過程を可視化）
    st.markdown('<div class="sec-title">クリエイティブ分析ロジック（改善提案の導出過程）</div>', unsafe_allow_html=True)
    render_cr_logic(cur)

# ============================ 📊 レポート ============================
elif view == "📊 広告数値レポート":
    if plc_all.empty:
        st.info("データがありません。`python3 app/seed_demo.py` を実行してください。")
        st.stop()
    start, end, cs, ce, mode = period_controls(plc_all, "rep")
    cur, cmp = in_period(plc_all, start, end), in_period(plc_all, cs, ce)
    cur_a, cmp_a = in_period(age_all, start, end), in_period(age_all, cs, ce)
    ap_cur = appt_df(start, end)

    tabs = st.tabs(["サマリー", "キャンペーン別", "広告セット別", "CR別",
                    "プレースメント別", "性別・年齢別", "デバイス別"])
    with tabs[0]:
        mc, mp = summary(cur, ap_cur), summary(cmp, appt_df(cs, ce))
        cards = [("費用", yen(mc["cost"]), mc["cost"], mp["cost"]), ("表示", num(mc["impressions"]), mc["impressions"], mp["impressions"]),
                 ("CPM", yen(mc["CPM"]), mc["CPM"], mp["CPM"]), ("CTR", pct(mc["CTR"]), mc["CTR"], mp["CTR"]),
                 ("資料請求", num(mc["leads"]), mc["leads"], mp["leads"]), ("資料請求単価", yen(mc["資料請求単価"]), mc["資料請求単価"], mp["資料請求単価"]),
                 ("商談", num(mc["appointments"]), mc["appointments"], mp["appointments"]), ("商談単価", yen(mc["商談単価"]), mc["商談単価"], mp["商談単価"])]
        st.markdown('<div class="cards-grid">' + "".join(
            f'<div class="metric-card"><div class="metric-label">{l}</div>'
            f'<div class="metric-value">{v}</div>{chg_html(c, p)}</div>' for l, v, c, p in cards) + "</div>",
            unsafe_allow_html=True)
        st.markdown('<div class="sec-title">日次トレンド</div>', unsafe_allow_html=True)
        daily = aggregate(cur, ["date"]).sort_values("date")
        st.line_chart(daily.set_index("date")[["cost", "leads"]].rename(columns={"cost": "費用", "leads": "資料請求"}), height=240)
    with tabs[1]:
        st.markdown(rep_table(cur, cmp, ["campaign"], "キャンペーン"), unsafe_allow_html=True)
    with tabs[2]:
        st.markdown(rep_table(cur, cmp, ["adset"], "広告セット", with_appt=True, ap=ap_cur), unsafe_allow_html=True)
    with tabs[3]:
        st.markdown(rep_table(cur, cmp, ["ad"], "CR"), unsafe_allow_html=True)
    with tabs[4]:
        st.markdown(rep_table(cur, cmp, ["placement"], "配置"), unsafe_allow_html=True)
    with tabs[5]:
        st.markdown(rep_table(cur_a, cmp_a, ["gender", "age"], "性別 / 年齢"), unsafe_allow_html=True)
    with tabs[6]:
        st.markdown(rep_table(cur, cmp, ["device"], "デバイス"), unsafe_allow_html=True)

# ============================ ⚙️ 広告運用設定 ============================
elif view == "⚙️ 広告運用設定":
    st.markdown('<div class="sec-title">広告運用設定（Meta）</div>', unsafe_allow_html=True)
    adsets = sorted(plc_all["adset"].dropna().unique()) if not plc_all.empty else ["（データなし）"]
    target = st.selectbox("対象の広告セット", adsets)
    st.caption("Meta広告で変更できる主要項目です。階層：キャンペーン → 広告セット → 配置。"
               "（デモ：保存は擬似動作。実際のMeta反映は ads_management 連携後）")

    # ① キャンペーン設定
    with st.container(border=True):
        st.markdown('<div class="sec-title">① キャンペーン設定'
                    '<span class="card-badge">有効</span></div>', unsafe_allow_html=True)
        c = st.columns(3)
        objective = c[0].selectbox("キャンペーンの目的", [
            "売上（コンバージョン）", "リード", "トラフィック", "エンゲージメント", "認知度", "アプリの宣伝"])
        cbo = c[1].selectbox("予算最適化", ["広告セット予算（ABO）", "キャンペーン予算最適化（CBO/Advantage）"])
        special = c[2].selectbox("特別広告カテゴリ", ["なし", "信用", "雇用", "住宅", "社会問題・選挙・政治"])

    # ② 予算・スケジュール
    with st.container(border=True):
        st.markdown('<div class="sec-title">② 予算・配信スケジュール</div>', unsafe_allow_html=True)
        c = st.columns(4)
        budget_type = c[0].selectbox("予算タイプ", ["日予算", "通算予算"])
        budget = c[1].number_input("予算額（円）", min_value=500, value=12000, step=500)
        ADJ = {"-50%": .5, "-30%": .7, "-20%": .8, "-10%": .9, "±0%": 1.0,
               "+10%": 1.1, "+20%": 1.2, "+30%": 1.3, "+50%": 1.5}
        adj = c[2].select_slider("予算の増減調整", options=list(ADJ), value="±0%")
        new_budget = int(budget * ADJ[adj])
        c[3].metric("調整後の予算", yen(new_budget), adj if adj != "±0%" else None)
        cc = st.columns(3)
        start = cc[0].date_input("開始日", value=date(2026, 6, 1))
        use_end = cc[1].selectbox("終了設定", ["終了日なし（継続）", "終了日を設定"])
        end = cc[2].date_input("終了日", value=date(2026, 6, 30), disabled=(use_end == "終了日なし（継続）"))
        sched = st.multiselect("配信時間帯（広告のスケジュール・任意）",
                               [f"{h:02d}時" for h in range(24)], default=[])

    # ③ 最適化・入札・計測
    with st.container(border=True):
        st.markdown('<div class="sec-title">③ 最適化・入札・計測</div>', unsafe_allow_html=True)
        c = st.columns(3)
        opt_goal = c[0].selectbox("配信の最適化対象", [
            "コンバージョン", "ランディングページビュー", "リンククリック", "リーチ", "インプレッション",
            "動画の継続視聴", "リード（インスタントフォーム）"])
        cv_event = c[1].selectbox("コンバージョンイベント（CV目的）", [
            "購入", "リード", "カートに追加", "決済を開始", "支払い情報の追加", "登録完了",
            "コンテンツビュー", "検索", "アプリインストール", "お問い合わせ"])
        bid = c[2].selectbox("入札戦略", [
            "最高ボリューム（自動）", "入札価格上限（Bid cap）", "目標コスト単価（Cost cap）", "最小ROAS（ROAS目標）"])
        c2 = st.columns(3)
        if bid == "最小ROAS（ROAS目標）":
            c2[0].number_input("目標ROAS（%）", min_value=0, value=300, step=10)
        elif bid != "最高ボリューム（自動）":
            c2[0].number_input("上限/目標 単価（円）", min_value=0, value=5000, step=100)
        else:
            c2[0].caption("自動入札のため金額指定なし")
        attribution = c2[1].selectbox("アトリビューション設定",
                                      ["クリック後7日（既定）", "クリック後1日", "クリック後7日＋ビュー後1日", "クリック後1日＋ビュー後1日"])
        billing = c2[2].selectbox("課金対象", ["インプレッション（CPM）", "リンククリック（CPC）"])

    # ④ ターゲティング
    with st.container(border=True):
        st.markdown('<div class="sec-title">④ ターゲティング（オーディエンス）</div>', unsafe_allow_html=True)
        c = st.columns(4)
        geo = c[0].text_input("地域", "日本")
        age_min = c[1].number_input("年齢（下限）", 13, 65, 25)
        age_max = c[2].number_input("年齢（上限）", 13, 65, 54)
        gender = c[3].selectbox("性別", ["すべて", "男性", "女性"])
        adv_aud = st.toggle("Advantage+ オーディエンス（自動拡張・推奨）", value=True)
        interests = st.text_input("詳細ターゲット（興味・関心／行動／属性）", "経営者, 採用・人事, 中小企業")
        cc = st.columns(2)
        custom_aud = cc[0].text_input("カスタムオーディエンス（除外/含む）", "")
        lookalike = cc[1].text_input("類似オーディエンス（%）", "1%")

    # ⑤ 配置（プレースメント）
    with st.container(border=True):
        st.markdown('<div class="sec-title">⑤ 配置（プレースメント）</div>', unsafe_allow_html=True)
        place_mode = st.radio("配置タイプ", ["Advantage+ 配置（自動・推奨）", "手動配置"], horizontal=True)
        if place_mode == "手動配置":
            media = st.multiselect("媒体", ["Facebook", "Instagram", "Messenger", "Audience Network"],
                                   default=["Facebook", "Instagram"])
            positions = st.multiselect("配置（ポジション）",
                                       ["フィード", "ストーリーズ", "リール", "発見タブ", "検索結果",
                                        "Marketplace", "インストリーム動画", "右側広告（FB）"],
                                       default=["フィード", "ストーリーズ", "リール"])
        device = st.selectbox("デバイス", ["すべて", "モバイルのみ", "デスクトップのみ"])
        freq_on = st.toggle("フリークエンシーキャップを設定", value=False)
        if freq_on:
            fc = st.columns(2)
            fc[0].number_input("上限表示回数", 1, 20, 2)
            fc[1].number_input("期間（日）", 1, 30, 7)

    # 保存
    st.divider()
    if st.button("💾 設定を保存（デモ）", type="primary"):
        st.success(f"広告セット「{target}」の設定を保存しました（デモ）。"
                   "実際のMeta反映は ads_management 連携後に有効化されます。")
        st.json({
            "広告セット": target,
            "キャンペーン": {"目的": objective, "予算最適化": cbo, "特別カテゴリ": special},
            "予算": {"タイプ": budget_type, "現予算": budget, "調整": adj, "調整後": new_budget,
                   "開始": str(start), "終了": ("なし" if use_end.startswith("終了日なし") else str(end))},
            "最適化・入札": {"最適化対象": opt_goal, "CVイベント": cv_event, "入札戦略": bid,
                       "アトリビューション": attribution, "課金対象": billing},
            "ターゲティング": {"地域": geo, "年齢": f"{age_min}-{age_max}", "性別": gender,
                        "Advantage+オーディエンス": adv_aud, "詳細ターゲット": interests,
                        "類似": lookalike},
            "配置": {"タイプ": place_mode, "デバイス": device, "フリークエンシーキャップ": freq_on},
        })

# ============================ 💡 改善提案 ============================
else:
    sub = st.sidebar.radio("提案カテゴリ", ["◾️ 広告予算提案", "◾️ 広告CR別停止提案",
                                       "◾️ 新規広告CR提案", "📁 施策履歴（承認/却下）"], key="psub")
    props = session.query(Proposal).order_by(Proposal.id).all()

    def buttons(p, labels=("✅ 承認", "❌ 却下"), done=("✅ 承認済", "❌ 却下")):
        b1, b2, _ = st.columns([1, 1, 4])
        if p.status == "pending":
            if b1.button(labels[0], key=f"a{p.id}"):
                p.status = "approved"; session.commit(); st.rerun()
            if b2.button(labels[1], key=f"r{p.id}"):
                p.status = "rejected"; session.commit(); st.rerun()
        else:
            st.caption({"approved": done[0], "rejected": done[1]}.get(p.status, p.status))

    if sub == "◾️ 広告予算提案":
        st.markdown('<div class="sec-title">広告予算提案（広告グループ別の増減・停止）</div>', unsafe_allow_html=True)
        items = [p for p in props if p.action_type == "budget"]
        for p in items:
            d = p.detail_json or {}
            reco = d.get("reco")
            bcls = {"増額": "b-green", "減額": "b-amber", "停止": "b-red"}.get(reco, "b-blue")
            st.markdown(
                f'<div class="prop"><span class="badge {bcls}">{reco} {d.get("change_pct",0):+d}%</span>'
                f'<span class="prop-ad">{p.adset}</span>'
                f'<div class="prop-line">日予算 {yen(d.get("current_budget",0))} → '
                f'<b>{yen(d.get("recommended_budget",0))}</b></div>'
                f'<div class="prop-copy">{d.get("reason","")}</div></div>', unsafe_allow_html=True)
            buttons(p)

    elif sub == "◾️ 広告CR別停止提案":
        st.markdown('<div class="sec-title">広告CR別 停止提案</div>', unsafe_allow_html=True)
        items = [p for p in props if p.action_type == "pause"]
        if not items:
            st.info("停止候補のCRはありません。")
        for p in items:
            d = p.detail_json or {}
            st.markdown(
                f'<div class="prop"><span class="badge b-red">停止候補</span>'
                f'<span class="prop-ad">{p.ad}</span>'
                f'<span class="prop-act">（{p.adset}）</span>'
                f'<div class="prop-line">CPM {yen(d.get("cpm",0))} ・ CTR {pct(d.get("ctr",0))} ・ '
                f'資料 {d.get("leads",0)} ・ 商談(セット) {d.get("adset_appointments",0)}</div>'
                f'<div class="prop-copy" style="color:var(--c-danger)">{d.get("note","")}</div></div>',
                unsafe_allow_html=True)
            buttons(p)

    elif sub == "◾️ 新規広告CR提案":
        st.markdown('<div class="sec-title">新規広告CR提案（分析に基づくクリエイティブ案）</div>', unsafe_allow_html=True)
        st.info("ℹ️ 出力されたバナースクリプトを使い、利用者が画像を生成→手動で入稿します。"
                "下の **👍 採用 / 👎 見送り** は広告管理画面を操作せず、**今後のCR学習用ラベル**として記録します。")
        ACTION = {"expand": "横展開", "change_appeal": "訴求変更", "change_visual": "ビジュアル変更"}
        BADGE = {"top_left": ("b-green", "勝ちCR"), "top_right": ("b-amber", "訴求弱"), "bottom_left": ("b-amber", "顧客のみ")}
        items = [p for p in props if p.action_type in ACTION]
        for p in items:
            d = p.detail_json or {}
            bcls, blabel = BADGE.get(p.quadrant or "", ("b-blue", p.quadrant))
            cv = p.copy_variants or {}
            variants = cv.get("variants") or []
            left, right = st.columns([4, 1])
            with left:
                copies = "".join(f'<div class="prop-copy">💬 {c}</div>' for c in variants)
                st.markdown(
                    f'<div class="prop"><span class="badge {bcls}">{blabel}</span>'
                    f'<span class="prop-ad">{p.ad}</span> '
                    f'<span class="prop-act">→ {ACTION[p.action_type]}（ベースCRを改善）</span>'
                    f'<div class="prop-line">CPM {yen(d.get("cpm",0))} ・ CTR {pct(d.get("ctr",0))} ・ '
                    f'資料 {d.get("leads",0)}{" ⚠️参考値" if d.get("low_data") else ""}</div>'
                    f'<div class="prop-line" style="margin-top:6px;color:var(--c-text-muted)">新コピー案</div>'
                    f'{copies}</div>', unsafe_allow_html=True)
                buttons(p, labels=("👍 採用", "👎 見送り"), done=("👍 採用（学習）", "👎 見送り（学習）"))
                if p.banner_prompt or variants:
                    with st.expander("バナースクリプト（画像生成用）／変更方針"):
                        if cv.get("changed_notes"):
                            st.write("**変更方針:**", "　/　".join(cv["changed_notes"]))
                        if p.banner_prompt:
                            st.code(p.banner_prompt)
            with right:
                src = img_src(d.get("image_url"))
                if src:
                    st.image(src, use_container_width=True, caption="ベースCR")

    else:  # 📁 施策履歴
        st.markdown('<div class="sec-title">施策履歴（承認・却下／採用・見送り）</div>', unsafe_allow_html=True)
        KIND = {"budget": "広告予算", "pause": "CR停止"}
        STAT = {"approved": '<span class="up">✅ 承認/採用</span>',
                "rejected": '<span class="down">❌ 却下/見送り</span>',
                "pending": '<span class="flat">⏳ 未処理</span>'}
        f = st.selectbox("ステータス絞り込み", ["全て", "承認/採用", "却下/見送り", "未処理"])
        fmap = {"承認/採用": "approved", "却下/見送り": "rejected", "未処理": "pending"}
        rows = ""
        for p in props:
            if f != "全て" and p.status != fmap.get(f):
                continue
            d = p.detail_json or {}
            kind = KIND.get(p.action_type, "新規CR")
            target = p.ad or p.adset
            if p.action_type == "budget":
                content = f'{d.get("reco","")} {d.get("change_pct",0):+d}%（{yen(d.get("current_budget",0))}→{yen(d.get("recommended_budget",0))}）'
            elif p.action_type == "pause":
                content = "CR停止"
            else:
                content = f'{p.action_type}：{(p.copy_variants or {}).get("variants",[""])[0]}'
            rows += (f'<tr><td>{kind}</td><td>{target}</td><td>{content}</td>'
                     f'<td>{STAT.get(p.status,p.status)}</td></tr>')
        st.markdown('<table class="rep"><thead><tr><th>種別</th><th>対象</th><th>内容</th>'
                    f'<th>ステータス</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        st.caption("※承認/採用・却下/見送りのラベルは、今後のCR最適化の学習データとして蓄積されます。")
