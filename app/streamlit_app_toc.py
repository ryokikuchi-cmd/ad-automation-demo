"""ToC（EC・購入）版 デモUI（ToB版 streamlit_app.py とは別物・自己完結）。

ToB版との違い:
  指標: 資料請求/商談 → 購入/CVR/CPA/売上/ROAS/客単価(AOV)
  4象限: CPM×CTR → ROAS×CVR（儲かるCRかで評価）
  CV目的: リード → 購入
データはDB不要のメモリ生成（デモ）。
起動: python3 -m streamlit run app/streamlit_app_toc.py
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Meta Ad Automation (ToC)", layout="wide")

# ---------- テーマ（ToB版と共通） ----------
st.markdown("""<style>
:root{--c-primary:#1a3a5c;--c-bg:#f3f5f9;--c-surface:#fff;--c-border:#e8eaed;
--c-text:#1a1a2e;--c-text-secondary:#5f6368;--c-text-muted:#9aa0a6;
--c-success:#0d904f;--c-danger:#d32f2f;--radius:10px;--radius-sm:6px;}
.stApp{background:var(--c-bg);}
header[data-testid="stHeader"]{background:transparent;height:0;}
#MainMenu,footer{visibility:hidden;}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--c-border);}
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1180px;}
.demo-banner{background:#fff3e0;color:#e8710a;text-align:center;font-size:12px;font-weight:600;
padding:7px;border-radius:6px;margin-bottom:10px;border:1px solid #ffe0b2;}
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
section[data-testid="stSidebar"] [role="radiogroup"]{gap:4px;margin-top:4px;}
section[data-testid="stSidebar"] [role="radiogroup"] label{display:flex;align-items:center;width:100%;
padding:9px 12px;border-radius:8px;cursor:pointer;font-size:14px;color:var(--c-text);transition:background .15s;}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:rgba(26,58,92,.06);}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#1a73e8;color:#fff;font-weight:600;}
section[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none;}
div[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:var(--radius);box-shadow:0 1px 3px rgba(0,0,0,.07);}
.card-badge{display:inline-block;background:#e8f5e9;color:#0d904f;font-size:11px;font-weight:600;padding:2px 10px;border-radius:20px;float:right;}
</style>""", unsafe_allow_html=True)

# 月次目標（ToC EC）
TARGETS = {"cost": 2000000, "impressions": 700000, "CPM": 3500, "clicks": 12000, "CPC": 170,
           "CTR": 0.018, "purchases": 600, "CVR": 0.045, "CPA": 3000,
           "revenue": 6000000, "ROAS": 3.0, "AOV": 6500}

# (campaign, adset, ad, cpm, ctr, cvr, aov, img_idx)
CRS = [
    ("新規獲得", "プロスペクティング", "美容液_ビフォーアフター", 3000, 0.020, 0.060, 7000, 0),
    ("新規獲得", "プロスペクティング", "UGC_口コミ動画", 2500, 0.020, 0.045, 6500, 1),
    ("新規獲得", "プロスペクティング", "美容液_成分訴求", 4200, 0.012, 0.040, 6800, 2),
    ("リターゲ", "リターゲティング", "カート_リマインド", 4000, 0.022, 0.090, 7200, 3),
    ("リターゲ", "リターゲティング", "静止画_キャンペーン", 6000, 0.008, 0.020, 6000, 4),
    ("定期", "定期_サブスク訴求", "サプリ_定期初回1980", 2800, 0.025, 0.070, 4980, 5),
]
COPY = {
    "美容液_ビフォーアフター": ["“3日で実感”ビフォーアフターで証明。", "今だけ定期初回50%OFF", "満足度98%※の美容液体験"],
    "UGC_口コミ動画": ["購入者のリアルな声を動画で。", "“もっと早く知りたかった”の声多数", "縦型動画で使用感が伝わる"],
    "美容液_成分訴求": ["話題の◯◯成分を高濃度配合。", "成分で選ぶ、結果にこだわる美容液", "皮膚科医も注目の処方"],
    "カート_リマインド": ["カートの商品、在庫残りわずか。", "今なら送料無料でお届け", "24時間限定クーポンを配布中"],
    "サプリ_定期初回1980": ["定期初回1,980円・送料無料。", "いつでも解約OKの定期便", "続けやすい価格で習慣に"],
}
WEEKDAY = [1.0, 1.05, 0.95, 1.10, 0.90, 1.15, 0.85]
PERIODS = [(date(2026, 6, 1), 30, 1.00), (date(2026, 5, 1), 31, 0.90), (date(2025, 6, 1), 30, 0.72)]
PLACEMENTS = [("android_smartphone", "facebook", "feed", 0.20), ("android_smartphone", "instagram", "feed", 0.18),
              ("android_smartphone", "instagram", "instagram_stories", 0.15), ("android_smartphone", "instagram", "instagram_reels", 0.12),
              ("iphone", "facebook", "feed", 0.13), ("iphone", "instagram", "feed", 0.12), ("iphone", "instagram", "instagram_stories", 0.10)]
AGE_GENDER = [("18-24", "female", 0.10), ("18-24", "male", 0.04), ("25-34", "female", 0.24), ("25-34", "male", 0.10),
              ("35-44", "female", 0.22), ("35-44", "male", 0.08), ("45-54", "female", 0.16), ("45-54", "male", 0.06)]


def _dist(total, weights):
    sw = sum(weights) or 1.0
    raw = [total * w / sw for w in weights]
    base = [int(x) for x in raw]
    rem = total - sum(base)
    order = sorted(range(len(weights)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in range(rem):
        base[order[i % len(order)]] += 1
    return base


@st.cache_data
def generate():
    plc, age = [], []
    for cmp, adset, ad, cpm, ctr, cvr, aov, _img in CRS:
        m_impr = 130000
        for first, ndays, mfac in PERIODS:
            days = [first + timedelta(days=i) for i in range(ndays)]
            dw = [WEEKDAY[d.weekday()] for d in days]
            impr_t = round(m_impr * mfac)
            cost_t = round(cpm * impr_t / 1000)
            clk_t = round(ctr * impr_t)
            pur_t = round(clk_t * cvr)
            rev_t = round(pur_t * aov)
            for cells, weights, store, dims in [
                ([(d, p) for d in days for p in PLACEMENTS],
                 None, plc, ("device", "media", "placement")),
                ([(d, a) for d in days for a in AGE_GENDER],
                 None, age, ("age", "gender"))]:
                w = [dw[i // (len(PLACEMENTS) if store is plc else len(AGE_GENDER))] * cells[i][1][-1]
                     for i in range(len(cells))]
                imp = _dist(impr_t, w); cst = _dist(cost_t, w); clk = _dist(clk_t, w)
                pur = _dist(pur_t, w); rev = _dist(rev_t, w)
                for k, (d, dim) in enumerate(cells):
                    row = dict(date=d, campaign=cmp, adset=adset, ad=ad,
                               cost=cst[k], impressions=imp[k], clicks=clk[k],
                               purchases=pur[k], revenue=rev[k])
                    for di, name in enumerate(dims):
                        row[name] = dim[di]
                    store.append(row)
    return pd.DataFrame(plc), pd.DataFrame(age)


PLC, AGE = generate()


# ---------- 指標 ----------
def yen(x):
    return f"¥{x:,.0f}" if x else "¥-"


def pct(x):
    return f"{x*100:.2f}%"


def num(x):
    return f"{int(x):,}"


def roas(x):
    return f"{x*100:.0f}%" if x else "-"


def derive(df):
    """集計済みDF（cost/impressions/clicks/purchases/revenue）にToC指標を付与。"""
    out = df.copy()
    sd = lambda a, b: (a / b.replace(0, pd.NA)).fillna(0)  # noqa: E731
    out["CPM"] = sd(out["cost"], out["impressions"]) * 1000
    out["CTR"] = sd(out["clicks"], out["impressions"])
    out["CVR"] = sd(out["purchases"], out["clicks"])
    out["CPA"] = sd(out["cost"], out["purchases"])
    out["ROAS"] = sd(out["revenue"], out["cost"])
    out["AOV"] = sd(out["revenue"], out["purchases"])
    return out


def agg(df, keys):
    g = df.groupby(keys, dropna=False)[["cost", "impressions", "clicks", "purchases", "revenue"]].sum().reset_index()
    return derive(g)


def total(df):
    return derive(pd.DataFrame([{c: df[c].sum() for c in ["cost", "impressions", "clicks", "purchases", "revenue"]}])).iloc[0]


def add_months(d, k):
    m = d.month - 1 + k
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def shift(s, e, mode):
    if mode == "前年同月比":
        try:
            return s.replace(year=s.year - 1), e.replace(year=e.year - 1)
        except ValueError:
            return date(s.year - 1, s.month, 1), date(e.year - 1, e.month, 28)
    return add_months(s, -1), add_months(e, -1)


def chg_html(c, p):
    if not p:
        return '<div class="metric-change flat">— 比較なし</div>'
    r = (c - p) / p
    return f'<div class="metric-change {"up" if r>=0 else "down"}">{"▲" if r>=0 else "▼"}{abs(r)*100:.1f}%</div>'


def chg_cell(c, p):
    if not p:
        return '<span class="flat">—</span>'
    r = (c - p) / p
    return f'<span class="{"up" if r>=0 else "down"}">{"▲" if r>=0 else "▼"}{abs(r)*100:.1f}%</span>'


def img_src(i):
    p = Path(__file__).parent / "demo_images_toc" / f"cr{i}.jpg"
    return str(p) if p.exists() else None


def period(df, a, b):
    return df[(df["date"] >= a) & (df["date"] <= b)]


# ---------- ナビ ----------
PLATFORMS = ["META", "Google", "X（旧Twitter）", "LINE", "TikTok"]
platform = st.sidebar.selectbox("広告媒体（プラットフォーム）", PLATFORMS, index=0, key="pf")
st.sidebar.markdown("---")

st.markdown('<div class="demo-banner">DEMO MODE — ToC（EC・購入）版／デモ用サンプルデータで動作しています</div>', unsafe_allow_html=True)
st.markdown(f'<div class="app-header"><div class="app-title">{platform} Ad Automation</div>'
            '<div class="app-meta">D2Cコスメ（デモ）｜ToC・購入最適化</div></div>', unsafe_allow_html=True)
if platform != "META":
    st.info(f"🚧 {platform}広告 は現在開発中です（β）。本デモは「META」でご確認ください。")
    st.stop()

view = st.sidebar.radio("メニュー", ["📊 広告数値レポート", "📈 分析結果", "💡 改善提案", "⚙️ 広告運用設定"], key="nav")


def period_controls(key):
    c1, c2 = st.columns([2, 1.2])
    rng = c1.date_input("期間", value=(date(2026, 6, 1), date(2026, 6, 30)),
                        min_value=PLC["date"].min(), max_value=PLC["date"].max(), key=f"d{key}")
    mode = c2.radio("比較", ["前月比", "前年同月比"], horizontal=True, key=f"m{key}")
    s, e = rng if isinstance(rng, tuple) and len(rng) == 2 else (date(2026, 6, 1), date(2026, 6, 30))
    cs, ce = shift(s, e, mode)
    st.caption(f"当期 {s}〜{e}　／　比較（{mode}）{cs}〜{ce}")
    return s, e, cs, ce, mode


def rep_table(cur, cmp, keys, header):
    a = agg(cur, keys).sort_values("cost", ascending=False)
    prev = cmp.groupby(keys, dropna=False)["cost"].sum().reset_index().rename(columns={"cost": "cp"})
    a = a.merge(prev, on=keys, how="left")
    th = [header, "費用", "前期比", "CPM", "CTR", "購入", "CPA", "売上", "ROAS"]
    head = "".join(f"<th>{t}</th>" for t in th)
    body = ""
    for _, r in a.iterrows():
        label = " / ".join(str(r[k]) for k in keys)
        body += (f'<tr><td>{label}</td><td class="num">{yen(r["cost"])}</td>'
                 f'<td class="num">{chg_cell(r["cost"], r.get("cp"))}</td>'
                 f'<td class="num">{yen(r["CPM"])}</td><td class="num">{pct(r["CTR"])}</td>'
                 f'<td class="num">{num(r["purchases"])}</td><td class="num">{yen(r["CPA"])}</td>'
                 f'<td class="num">{yen(r["revenue"])}</td><td class="num">{roas(r["ROAS"])}</td></tr>')
    return f'<table class="rep"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


# 4象限（ROAS × CVR）
QUAD = {
    "win": ("🟢 勝ちCR", "ROAS◎ × CVR◎（儲かる×売れる）", "横展開：予算集中・複製"),
    "roas_only": ("🟡 ROAS高・CVR低", "客単価で稼ぐが転換率が低い", "訴求変更：オファー/CTA改善"),
    "cvr_only": ("🟡 CVR高・ROAS低", "売れるが単価/コストが重い", "ビジュアル/価格訴求の変更"),
    "lose": ("🔴 停止候補", "ROAS× × CVR×", "停止"),
}
QC = {"win": "#0d904f", "roas_only": "#e8710a", "cvr_only": "#e8710a", "lose": "#d32f2f"}


def classify(r, roas_th, cvr_th):
    hi_r, hi_c = r["ROAS"] >= roas_th, r["CVR"] >= cvr_th
    return "win" if hi_r and hi_c else "roas_only" if hi_r else "cvr_only" if hi_c else "lose"


# ============================ レポート ============================
if view == "📊 広告数値レポート":
    s, e, cs, ce, mode = period_controls("rep")
    cur, cmp = period(PLC, s, e), period(PLC, cs, ce)
    cur_a, cmp_a = period(AGE, s, e), period(AGE, cs, ce)
    tabs = st.tabs(["サマリー", "キャンペーン別", "広告セット別", "CR別", "プレースメント別", "性別・年齢別", "デバイス別"])
    with tabs[0]:
        mc, mp = total(cur), total(cmp)
        cards = [("費用", yen(mc.cost), mc.cost, mp.cost), ("表示", num(mc.impressions), mc.impressions, mp.impressions),
                 ("購入", num(mc.purchases), mc.purchases, mp.purchases), ("CPA", yen(mc.CPA), mc.CPA, mp.CPA),
                 ("売上", yen(mc.revenue), mc.revenue, mp.revenue), ("ROAS", roas(mc.ROAS), mc.ROAS, mp.ROAS),
                 ("CVR", pct(mc.CVR), mc.CVR, mp.CVR), ("客単価", yen(mc.AOV), mc.AOV, mp.AOV)]
        st.markdown('<div class="cards-grid">' + "".join(
            f'<div class="metric-card"><div class="metric-label">{l}</div><div class="metric-value">{v}</div>{chg_html(c,p)}</div>'
            for l, v, c, p in cards) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="sec-title">日次トレンド（費用・売上）</div>', unsafe_allow_html=True)
        d = agg(cur, ["date"]).sort_values("date")
        st.line_chart(d.set_index("date")[["cost", "revenue"]].rename(columns={"cost": "費用", "revenue": "売上"}), height=240)
    for i, (keys, hd, cdf, mdf) in enumerate([
            (["campaign"], "キャンペーン", cur, cmp), (["adset"], "広告セット", cur, cmp),
            (["ad"], "CR", cur, cmp), (["placement"], "配置", cur, cmp),
            (["gender", "age"], "性別 / 年齢", cur_a, cmp_a), (["device"], "デバイス", cur, cmp)], start=1):
        with tabs[i]:
            st.markdown(rep_table(cdf, mdf, keys, hd), unsafe_allow_html=True)

# ============================ 分析結果 ============================
elif view == "📈 分析結果":
    s, e, cs, ce, mode = period_controls("an")
    cur, cmp = period(PLC, s, e), period(PLC, cs, ce)
    mc, mp = total(cur), total(cmp)

    st.markdown('<div class="sec-title">全体配信結果（目標 vs 実績）</div>', unsafe_allow_html=True)
    NARR = [("費用", "cost", yen, "low"), ("Imps", "impressions", num, "high"), ("CPM", "CPM", yen, "low"),
            ("CTR", "CTR", pct, "high"), ("購入", "purchases", num, "high"), ("CVR", "CVR", pct, "high"),
            ("CPA", "CPA", yen, "low"), ("売上", "revenue", yen, "high"), ("ROAS", "ROAS", roas, "high"),
            ("客単価", "AOV", yen, "high")]

    def mark(a, t, mode_):
        if not t:
            return "—"
        ok = a <= t if mode_ == "low" else a >= t
        near = a <= t * 1.2 if mode_ == "low" else a >= t * 0.8
        return "○" if ok else ("△" if near else "×")

    rows = ""
    for label, key, fmt, m_ in NARR:
        a, t = mc[key], TARGETS[key]
        diff = ("+" if a - t >= 0 else "−") + fmt(abs(a - t))
        rows += f'<tr><td>{label}</td><td class="num">{fmt(t)}</td><td class="num">{fmt(a)}</td><td class="num">{diff}</td><td class="num">{mark(a,t,m_)}</td></tr>'
    st.markdown(f'<table class="rep"><thead><tr><th>指標</th><th>目標</th><th>実績</th><th>差分</th><th>評価</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)

    roas_chg = (mc.ROAS - mp.ROAS) / mp.ROAS if mp.ROAS else 0
    cpa_chg = (mc.CPA - mp.CPA) / mp.CPA if mp.CPA else 0
    st.markdown('<div class="sec-title">評価結果</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="eval-note">・<b>ROAS {mark(mc.ROAS,TARGETS["ROAS"],"high")}</b>：実績{roas(mc.ROAS)}'
        f'（目標{roas(TARGETS["ROAS"])}）。{mode} {roas_chg*100:+.1f}%。<br>'
        f'　客単価{yen(mc.AOV)}・CVR{pct(mc.CVR)}。高ROAS面への予算集中とCRの当たり探索が重心。<br>'
        f'・<b>CPA {mark(mc.CPA,TARGETS["CPA"],"low")}</b>：実績{yen(mc.CPA)}（目標{yen(TARGETS["CPA"])}）。'
        f'{mode} {cpa_chg*100:+.1f}%。CVR改善（LP/オファー）がCPA改善の鍵。</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-title">広告セット別 評価結果</div>', unsafe_allow_html=True)
    ac = agg(cur, ["adset"]).sort_values("cost", ascending=False)
    mm = {r["adset"]: r for _, r in agg(cmp, ["adset"]).iterrows()}
    for _, r in ac.iterrows():
        p = mm.get(r["adset"])
        rc = f'{mode} {((r.ROAS-p.ROAS)/p.ROAS*100):+.1f}%' if p is not None and p.ROAS else "（比較なし）"
        st.markdown(
            f'<div class="eval-note"><b>○ {r["adset"]}</b><br>'
            f'・<b>ROAS {mark(r.ROAS,TARGETS["ROAS"],"high")}</b>：{roas(r.ROAS)}（目標{roas(TARGETS["ROAS"])}）。{rc}。<br>'
            f'　CPA{yen(r.CPA)}・CVR{pct(r.CVR)}・客単価{yen(r.AOV)}。<br>'
            f'・購入 {num(r.purchases)}件／売上 {yen(r.revenue)}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-title">クリエイティブ分析ロジック（ROAS × CVR の4象限）</div>', unsafe_allow_html=True)
    st.markdown('<div class="eval-note">広告セット内で <b>ROAS中央値・CVR中央値</b> を閾値に、'
                '<b>ROAS（儲かるか）× CVR（売れるか）</b> で各CRを分類し改善アクションを導出。<br>'
                '🟢勝ち＝横展開／🟡ROAS高CVR低＝訴求変更／🟡CVR高ROAS低＝ビジュアル変更／🔴＝停止</div>', unsafe_allow_html=True)
    for adset in sorted(cur["adset"].dropna().unique()):
        cr = agg(cur[cur["adset"] == adset], ["ad"])
        if cr.empty:
            continue
        rt, ct = cr["ROAS"].median(), cr["CVR"].median()
        cr["q"] = cr.apply(lambda r: classify(r, rt, ct), axis=1)
        st.markdown(f'<div class="sec-title">📦 {adset}　<span style="font-weight:400;font-size:12px;color:var(--c-text-secondary)">'
                    f'閾値：ROAS中央 {roas(rt)} ／ CVR中央 {pct(ct)}</span></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            xenc = alt.X("ROAS:Q", title="ROAS（右ほど高い＝儲かる）", axis=alt.Axis(format="%"))
            yenc = alt.Y("CVR:Q", title="CVR（上ほど高い＝売れる）", axis=alt.Axis(format="%"))
            pts = alt.Chart(cr).mark_circle(size=240, opacity=.85).encode(
                x=xenc, y=yenc, color=alt.Color("q:N", scale=alt.Scale(domain=list(QC), range=list(QC.values())), legend=None),
                tooltip=["ad", "ROAS", "CVR", "CPA"])
            txt = alt.Chart(cr).mark_text(dy=-15, fontSize=11).encode(x=xenc, y=yenc, text="ad")
            vline = alt.Chart(pd.DataFrame({"x": [rt]})).mark_rule(strokeDash=[5, 5], color="#9aa0a6").encode(x="x:Q")
            hline = alt.Chart(pd.DataFrame({"y": [ct]})).mark_rule(strokeDash=[5, 5], color="#9aa0a6").encode(y="y:Q")
            st.altair_chart((vline + hline + pts + txt).properties(height=280), use_container_width=True)
        with col2:
            head = "".join(f"<th>{t}</th>" for t in ["CR", "ROAS", "ROAS判定", "CVR", "CVR判定", "象限", "→ 推奨"])
            body = ""
            for _, r in cr.sort_values("cost", ascending=False).iterrows():
                lbl, interp, act = QUAD[r["q"]]
                body += (f'<tr><td>{r["ad"]}</td><td class="num">{roas(r.ROAS)}</td>'
                         f'<td>{"高◎" if r.ROAS>=rt else "低△"}</td><td class="num">{pct(r.CVR)}</td>'
                         f'<td>{"高◎" if r.CVR>=ct else "低△"}</td><td>{lbl}</td><td><b>{act}</b></td></tr>')
            st.markdown(f'<table class="rep"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>', unsafe_allow_html=True)

# ============================ 改善提案 ============================
elif view == "💡 改善提案":
    if "toc_status" not in st.session_state:
        st.session_state.toc_status = {}
    sub = st.sidebar.radio("提案カテゴリ", ["◾️ 広告予算提案", "◾️ 広告CR別停止提案", "◾️ 新規広告CR提案", "📁 施策履歴"], key="psub")
    cur = period(PLC, date(2026, 6, 1), date(2026, 6, 30))
    ad_agg = agg(cur, ["ad"]).copy()
    ad_agg["adset"] = ad_agg["ad"].map({c[2]: c[1] for c in CRS})
    ad_agg["img"] = ad_agg["ad"].map({c[2]: c[7] for c in CRS})
    aset_agg = agg(cur, ["adset"])

    def status_buttons(pid, labels=("✅ 承認", "❌ 却下")):
        cur_s = st.session_state.toc_status.get(pid)
        b1, b2, _ = st.columns([1, 1, 4])
        if cur_s is None:
            if b1.button(labels[0], key=f"a{pid}"):
                st.session_state.toc_status[pid] = "approved"; st.rerun()
            if b2.button(labels[1], key=f"r{pid}"):
                st.session_state.toc_status[pid] = "rejected"; st.rerun()
        else:
            st.caption("✅ 承認済" if cur_s == "approved" else "❌ 却下")

    if sub == "◾️ 広告予算提案":
        st.markdown('<div class="sec-title">広告予算提案（ROAS基準・広告グループ別）</div>', unsafe_allow_html=True)
        for _, r in aset_agg.sort_values("ROAS", ascending=False).iterrows():
            if r.ROAS >= TARGETS["ROAS"] * 1.1:
                reco, pctv, bcls = "増額", 30, "b-green"
            elif r.ROAS < TARGETS["ROAS"] * 0.7:
                reco, pctv, bcls = "減額", -20, "b-amber"
            else:
                reco, pctv, bcls = "維持", 0, "b-blue"
            reason = f"ROAS{roas(r.ROAS)}（目標{roas(TARGETS['ROAS'])}）・CPA{yen(r.CPA)}。" + \
                     ("目標超過で好調、予算拡大で売上増を狙う" if reco == "増額" else
                      "目標未達。CR入替を優先し一旦抑制" if reco == "減額" else "目標圏内、現状維持")
            st.markdown(f'<div class="prop"><span class="badge {bcls}">{reco} {pctv:+d}%</span>'
                        f'<span class="prop-ad">{r["adset"]}</span>'
                        f'<div class="prop-line">売上 {yen(r.revenue)} ／ ROAS {roas(r.ROAS)} ／ 購入 {num(r.purchases)}</div>'
                        f'<div class="prop-copy">{reason}</div></div>', unsafe_allow_html=True)
            status_buttons(f"bud_{r['adset']}")

    elif sub == "◾️ 広告CR別停止提案":
        st.markdown('<div class="sec-title">広告CR別 停止提案（低ROAS）</div>', unsafe_allow_html=True)
        lows = ad_agg[ad_agg["ROAS"] < TARGETS["ROAS"] * 0.5]
        if lows.empty:
            st.info("停止候補のCRはありません。")
        for _, r in lows.iterrows():
            st.markdown(f'<div class="prop"><span class="badge b-red">停止候補</span>'
                        f'<span class="prop-ad">{r["ad"]}</span> <span class="prop-act">（{r["adset"]}）</span>'
                        f'<div class="prop-line">ROAS {roas(r.ROAS)} ・ CPA {yen(r.CPA)} ・ CVR {pct(r.CVR)} ・ 購入 {num(r.purchases)}</div>'
                        f'<div class="prop-copy" style="color:var(--c-danger)">ROASが目標の半分未満。費用対効果が著しく低く停止推奨</div></div>',
                        unsafe_allow_html=True)
            status_buttons(f"stop_{r['ad']}")

    elif sub == "◾️ 新規広告CR提案":
        st.markdown('<div class="sec-title">新規広告CR提案（分析に基づくクリエイティブ案）</div>', unsafe_allow_html=True)
        st.info("ℹ️ 出力スクリプトで利用者が画像生成→手動入稿します。👍採用/👎見送りは学習用ラベルです。")
        good = ad_agg[ad_agg["ROAS"] >= ad_agg["ROAS"].median()]
        for _, r in good.iterrows():
            variants = COPY.get(r["ad"], [])
            left, right = st.columns([4, 1])
            with left:
                copies = "".join(f'<div class="prop-copy">💬 {c}</div>' for c in variants)
                st.markdown(f'<div class="prop"><span class="badge b-green">勝ちCR</span>'
                            f'<span class="prop-ad">{r["ad"]}</span> <span class="prop-act">→ 横展開（ベースCRを改善）</span>'
                            f'<div class="prop-line">ROAS {roas(r.ROAS)} ・ CVR {pct(r.CVR)} ・ 客単価 {yen(r.AOV)}</div>'
                            f'<div class="prop-line" style="color:var(--c-text-muted);margin-top:6px">新コピー案</div>{copies}</div>',
                            unsafe_allow_html=True)
                status_buttons(f"new_{r['ad']}", labels=("👍 採用", "👎 見送り"))
            with right:
                src = img_src(int(r["img"]))
                if src:
                    st.image(src, use_container_width=True, caption="ベースCR")

    else:  # 履歴
        st.markdown('<div class="sec-title">施策履歴（承認/却下・採用/見送り）</div>', unsafe_allow_html=True)
        if not st.session_state.toc_status:
            st.info("まだラベル付けされた施策はありません。")
        else:
            rows = ""
            for pid, sct in st.session_state.toc_status.items():
                kind = {"bud": "広告予算", "stop": "CR停止", "new": "新規CR"}.get(pid.split("_")[0], "")
                target = pid.split("_", 1)[1]
                badge = '<span class="up">✅ 承認/採用</span>' if sct == "approved" else '<span class="down">❌ 却下/見送り</span>'
                rows += f'<tr><td>{kind}</td><td>{target}</td><td>{badge}</td></tr>'
            st.markdown(f'<table class="rep"><thead><tr><th>種別</th><th>対象</th><th>ステータス</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)

# ============================ 設定 ============================
else:
    st.markdown('<div class="sec-title">広告運用設定（Meta・ToC/購入最適化）</div>', unsafe_allow_html=True)
    target = st.selectbox("対象の広告セット", sorted(PLC["adset"].dropna().unique()))
    st.caption("ToC（EC）向けの主要設定。CV=購入、入札=ROAS基準が中心です。（デモ：保存は擬似動作）")
    with st.container(border=True):
        st.markdown('<div class="sec-title">① キャンペーン設定<span class="card-badge">有効</span></div>', unsafe_allow_html=True)
        c = st.columns(3)
        c[0].selectbox("キャンペーンの目的", ["売上（コンバージョン）", "カタログ販売", "トラフィック", "エンゲージメント"])
        c[1].selectbox("予算最適化", ["キャンペーン予算最適化（Advantage）", "広告セット予算（ABO）"])
        c[2].selectbox("カタログ", ["EC商品カタログ_本店", "なし"])
    with st.container(border=True):
        st.markdown('<div class="sec-title">② 予算・スケジュール</div>', unsafe_allow_html=True)
        c = st.columns(4)
        c[0].selectbox("予算タイプ", ["日予算", "通算予算"])
        b = c[1].number_input("予算額（円）", 1000, value=50000, step=1000)
        ADJ = {"-50%": .5, "-30%": .7, "-20%": .8, "-10%": .9, "±0%": 1.0, "+10%": 1.1, "+20%": 1.2, "+30%": 1.3, "+50%": 1.5}
        adj = c[2].select_slider("予算の増減調整", list(ADJ), value="±0%")
        c[3].metric("調整後", yen(int(b * ADJ[adj])), adj if adj != "±0%" else None)
    with st.container(border=True):
        st.markdown('<div class="sec-title">③ 最適化・入札・計測</div>', unsafe_allow_html=True)
        c = st.columns(3)
        c[0].selectbox("配信の最適化対象", ["コンバージョン", "コンバージョン値（売上最大化）", "ランディングページビュー", "リンククリック"])
        c[1].selectbox("コンバージョンイベント（CV目的）", ["購入", "カートに追加", "決済を開始", "支払い情報の追加", "コンテンツビュー"])
        bid = c[2].selectbox("入札戦略", ["最高ボリューム（自動）", "最小ROAS（ROAS目標）", "目標コスト単価（Cost cap）", "入札価格上限（Bid cap）"])
        c2 = st.columns(3)
        if bid == "最小ROAS（ROAS目標）":
            c2[0].number_input("目標ROAS（%）", 0, value=300, step=10)
        elif bid != "最高ボリューム（自動）":
            c2[0].number_input("目標/上限 CPA（円）", 0, value=3000, step=100)
        else:
            c2[0].caption("自動入札のため金額指定なし")
        c2[1].selectbox("アトリビューション設定", ["クリック後7日＋ビュー後1日（EC既定）", "クリック後7日", "クリック後1日"])
        c2[2].selectbox("計測", ["ピクセル＋コンバージョンAPI（推奨）", "ピクセルのみ"])
    with st.container(border=True):
        st.markdown('<div class="sec-title">④ ターゲティング</div>', unsafe_allow_html=True)
        c = st.columns(4)
        c[0].text_input("地域", "日本")
        c[1].number_input("年齢（下限）", 13, 65, 20)
        c[2].number_input("年齢（上限）", 13, 65, 49)
        c[3].selectbox("性別", ["すべて", "女性", "男性"])
        st.toggle("Advantage+ オーディエンス（自動拡張・推奨）", value=True)
        st.text_input("詳細ターゲット（興味・関心／行動）", "美容, スキンケア, コスメ購入者")
        cc = st.columns(2)
        cc[0].text_input("カスタムオーディエンス（購入者/サイト訪問/カート放棄）", "カート放棄30日")
        cc[1].text_input("類似オーディエンス（%）", "1%（購入者ベース）")
    with st.container(border=True):
        st.markdown('<div class="sec-title">⑤ 配置（プレースメント）</div>', unsafe_allow_html=True)
        pm = st.radio("配置タイプ", ["Advantage+ 配置（自動・推奨）", "手動配置"], horizontal=True)
        if pm == "手動配置":
            st.multiselect("媒体", ["Facebook", "Instagram", "Messenger", "Audience Network"], default=["Facebook", "Instagram"])
            st.multiselect("配置", ["フィード", "ストーリーズ", "リール", "発見タブ", "ショップ", "Marketplace"], default=["フィード", "ストーリーズ", "リール"])
        st.selectbox("デバイス", ["すべて", "モバイルのみ", "デスクトップのみ"])
    st.divider()
    if st.button("💾 設定を保存（デモ）", type="primary"):
        st.success(f"広告セット「{target}」のToC設定を保存しました（デモ）。実Meta反映は ads_management 連携後。")
