# 広告自動化SaaS（Meta先行）

Meta広告の **データ取得→BI化→4象限CR分析→改善提案→CR生成案→入稿→日次運用** を
一気通貫で自動化するツール。設計の詳細は以下を参照。

- [concept.md](concept.md) — 全体コンセプト（7レイヤー / ⓪〜⑥）
- [data-model.md](data-model.md) — DBスキーマ＋商談スプシ取込仕様
- [infrastructure.md](infrastructure.md) — 技術スタック・実行環境・SaaS移行方針

## アーキテクチャ方針

**業務ロジック（`src/`）を UI（`app/`）・スケジューラ（`jobs/`）から完全分離。**
これにより、Streamlit→Web、GitHub Actions→ワーカー へ差し替えても `src/` とDBは無傷で流用できる
（= MVPが「成長する土台」になる）。

```
src/        業務ロジック（UI/基盤に非依存）
  db/         SQLAlchemyモデル・接続
  ingest/     ⓪ Meta API取得 → raw_*
  appointments/ ② 商談スプシ取込
  bi/         ① pandas集計（標準メトリクス12列）   ← 実装済み
  analysis/   ② 4象限＋Vision因果分析             ← 4象限ロジック実装済み
  proposal/   ③ 象限別の改善提案                  ← 実装済み
  creative/   ④ banner-prompt移植（生成）
  publish/    ⑤ Meta入稿・予算/停止/複製（監査ログ）
app/        ⑤ Streamlit承認UI（薄い表示層）
jobs/       日次バッチ（薄いオーケストレーション）
config/     テナント・アカウント設定（YAML）
.github/    GitHub Actions（日次cron）
```

## セットアップ

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # 接続情報を記入
cp config/accounts.example.yaml config/accounts.yaml
python -c "from src.db.session import init_db; init_db()"   # テーブル作成
```

## 実行

```bash
python jobs/daily_run.py        # 日次バッチ
streamlit run app/streamlit_app.py   # 承認UI
```

## 実装ステータス

| レイヤー | 状態 |
|---------|------|
| DBスキーマ（src/db/models.py） | ✅ 実装済み（Postgres/SQLite両対応） |
| ⓪ Meta取得（src/ingest/meta.py, store.py） | ✅ **実装・本番API実データで検証済み**／UPSERT冪等性OK |
| ① BI集計（src/bi/aggregate.py） | ✅ 実装済み（pandas） |
| ② 4象限分析（src/analysis/quadrant.py） | ✅ 実装済み（ロジック） |
| ③ 提案（src/proposal/generate.py） | ✅ 実装済み（象限別ロジック） |
| Ⓜ 広告マスタ（src/ingest/ads.py + analysis/naming.py） | ✅ **実API検証済み**（257広告・全件画像URL・ad_id主キーupsert・命名パース） |
| ② 商談取込（src/appointments/import_sheet.py） | ✅ **実データ検証済み**（年月/広告セット/商談数・洗い替え冪等・不一致検知） |
| ② Vision因果分析（src/analysis/vision.py） | ✅ 実装・実画像でAPI直前まで検証（実Claude呼出は ANTHROPIC_API_KEY 必要） |
| ④ バナー生成（src/creative/banner.py） | ✅ 実装・構築検証（③提案時にスクリプト＋コピー生成・実Claude呼出はAPIキー必要） |
| 日次バッチ結線（jobs/daily_run.py） | ✅ **⓪→Ⓜ→②→①→②③→④ 全結線を実データ通貫** |
| ⑤ 承認UI（app/streamlit_app.py） | ✅ **デモ版**（`python app/seed_demo.py` → `streamlit run app/streamlit_app.py`） |
| ⑤ 入稿（src/publish/） | ⬜ Phase4（ads_management審査後）→ 手順は [SETUP-ops.md](SETUP-ops.md) |
| DB本番化（Supabase） | ⬜ 手順は [SETUP-ops.md](SETUP-ops.md) |

### 既知の設計上の注意
- **商談の粒度**: 商談データは月次×広告セット単位。日次バッチの短い窓のリードと結合すると商談率が歪む
  → 分析窓を商談期間（月次）に合わせるか、商談を窓内に按分する処理が必要（CV評価時）。
- **商談取込の認証**: gspreadサービスアカウント（GOOGLE_SERVICE_ACCOUNT_JSON）が必要。未設定時は安全にスキップ。
- **Visionコスト**: 既定モデルは `claude-opus-4-8`。バッチで件数が多い場合は `ANTHROPIC_MODEL=claude-haiku-4-5` 等で約1/5に削減可（config `analysis.vision: true` でgate、既定OFF）。

### 検証メモ
- 取得元: 既存の実績スクリプト `AIレポート/キープサーチ/fetch_incremental.py` のロジックを移植
- 検証コマンド例: `META_ACCESS_TOKEN=... DATABASE_URL=sqlite:///test.db python jobs/daily_run.py`
- ⚠️ **セキュリティ**: 旧スクリプトはトークンをハードコード。SaaSでは `.env`/Secrets経由とし、
  既存トークンは早めにローテーション推奨（露出済みのため）。
```
