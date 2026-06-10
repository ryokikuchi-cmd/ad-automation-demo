# 技術スタック ＋ 実行環境の提案（Python中心・低コスト）

作成日: 2026-06-09 / simcle / concept.md v0.3 に対応

## ■前提（「課金したくない」の解釈）

- **クライアント請求機能（Stripe等の課金システム）は作らない**
- **インフラ費用は極小（ほぼ¥0〜数千円/月）に抑える**
- **ロジックはPythonコード中心**で実装
- MVPは **simcleがエージェンシーとして運用**（クライアントログインの自前Web UIは後回し）
  → マルチテナントの認証/課金が不要になり、構成が一気に軽くなる

---

## ■技術スタック（Python中心）

| 領域 | 採用 | 用途 |
|------|------|------|
| 言語 | Python 3.11+ | 全レイヤーの実装 |
| Meta API | `facebook-business`（公式SDK） | ⓪データ取得・⑤入稿 |
| データ処理 | `pandas` | ①BI集計・分析 |
| DB接続 | `SQLAlchemy` + `psycopg2` | DB読み書き |
| スプシ取込 | `gspread`（サービスアカウント） | ②商談取込 |
| 画像分析 | `anthropic`（Claude Vision） | ②ビジュアル因果分析 |
| バナー生成 | banner-prompt.md ロジックをPython化 | ④生成エンジン |
| UI（承認） | `Streamlit` | ⑤提案承認・入稿トリガー |
| スケジュール | cron / GitHub Actions | 日次バッチ |

既存の `cr-analysis.md` `banner-prompt.md` `openpyxl` 資産はそのままPython関数に移植できる。

---

## ■実行環境の提案（3案＋推奨）

### 案A：GitHub Actions ＋ Supabase ＋ Streamlit Cloud（推奨・ほぼ¥0）

```
日次バッチ:   GitHub Actions（cron）でPythonスクリプト実行
              ⓪取得 → ①BI → ②分析 → ③提案 → ④生成 → DB保存
データ:       Supabase（無料枠Postgres 500MB）
承認UI:       Streamlit Community Cloud（無料）で提案カードを表示
入稿:         UIの承認 → Meta API書き込み（Streamlit or Actions）
シークレット: GitHub Secrets / Supabase
```

| 項目 | 評価 |
|------|------|
| コスト | ほぼ¥0（Claude API従量のみ。月数百円〜） |
| 構築速度 | ◎ 最速。サーバ管理不要 |
| 制約 | GitHub Actionsは6h/jobの制限・実行時刻が多少ずれる（日次バッチなら問題なし） |
| Supabase無料枠 | 1週間無アクセスで一時停止 → 日次ジョブが叩くので維持される |
| 向き | MVP・少数クライアント |

### 案B：単一VPS（さくら/ConoHa/Hetzner 等）

```
1台のVPS（月500〜1,500円）に:
  - PostgreSQL
  - Python（cronで日次バッチ）
  - Streamlit（systemdで常駐）
```

| 項目 | 評価 |
|------|------|
| コスト | 月500〜1,500円 |
| 自由度 | ◎ 制限なし。長時間ジョブ・常駐OK |
| 手間 | サーバ運用・バックアップ・セキュリティ更新が自分持ち |
| 向き | クライアント数が増えた段階／Actionsの制約が気になったら移行 |

### 案C：Google Cloud（Cloud Run Jobs ＋ Cloud Scheduler ＋ Cloud SQL）

| 項目 | 評価 |
|------|------|
| コスト | 従量・低額（小規模なら月数百円〜千円台） |
| スケール | ◎ クライアント増加に強い |
| 手間 | 設定はやや複雑。GCP知識が要る |
| 向き | 本格スケール・将来の自前SaaS化を見据える場合 |

---

## ■推奨ルート

**まず案A（GitHub Actions＋Supabase＋Streamlit）でMVPを構築 → 規模が出たら案Bまたは案Cへ移行。**

- 案AはDB(Supabase)もコードもPython、ほぼ無料、サーバ管理ゼロで最速立ち上げ
- DBはPostgreSQL互換なので、案B/Cへの移行時もスキーマ・コードはほぼそのまま流用可
- Streamlitの承認UIはPythonだけで作れ、simcle運用なら認証も最小限で済む

---

## ■想定ディレクトリ構成（Pythonプロジェクト）

```
ad-automation/
├── config/                 # テナント・アカウント設定（YAML）
├── src/
│   ├── ingest/             # ⓪ Meta API取得 → DB（facebook-business）
│   ├── appointments/       # ② 商談スプシ取込（gspread）
│   ├── bi/                 # ① pandas集計 / ビュー定義
│   ├── analysis/           # ② 4象限＋Vision因果分析（cr-analysis移植）
│   ├── proposal/           # ③ 改善提案ロジック
│   ├── creative/           # ④ banner-prompt移植（スクリプト＋コピー生成）
│   ├── publish/            # ⑤ Meta API入稿・予算/停止/複製（監査ログ）
│   └── db/                 # SQLAlchemyモデル・接続
├── app/                    # ⑤ Streamlit承認UI
├── jobs/                   # 日次バッチのエントリポイント
│   └── daily_run.py
├── .github/workflows/      # GitHub Actions（cron）
└── requirements.txt
```

---

## ■日次バッチの流れ（jobs/daily_run.py）

```
1. ⓪ ingest    : 全アカウントのMetaデータを取得 → raw_* テーブルへUPSERT
2. ② appoint   : 商談スプシを取込 → appointments へUPSERT
3. ① bi        : pandas/ビューで標準メトリクス集計
4. ② analysis  : 広告セット別4象限＋画像Vision分析
5. ③ proposal  : 象限別ロジックで改善案生成 → proposals(status=pending)
6. ④ creative  : 採用候補にバナースクリプト＋コピー案を付与
7.   通知       : 「承認待ちN件」をntfy/メールで運用者へ
   （⑤入稿・⑥予算再配分は承認後にStreamlit/別ジョブで実行）
```

---

## ■コスト試算（案A・クライアント数10前後まで）

| 項目 | 月額 |
|------|------|
| GitHub Actions | ¥0（無料枠内） |
| Supabase | ¥0（無料枠） |
| Streamlit Cloud | ¥0（無料枠） |
| Claude API（Vision分析） | 数百〜千円程度（従量） |
| **合計** | **実質 数百〜千円/月** |

---

## ■SaaS化の適性と移行方針（重要）

案AはMVPであると同時に、**SaaSの土台として成長させられる**構成。鍵は「業務ロジックをUI・実行基盤から完全分離」すること。

| 部品 | SaaS適性 | 将来の扱い |
|------|---------|-----------|
| Supabase（DB） | ◎ 最終形まで通用 | RLSでテナント分離・Authでクライアントログイン。そのまま採用 |
| Pythonロジック（src/） | ◎ 不変 | UI/基盤を替えても再利用 |
| GitHub Actions | △ MVP止まり | 多数テナント・リアルタイム化でワーカー/キュー（案C等）へ |
| Streamlit | △ MVP止まり | 自前ログインが必要になったらNext.js/FastAPIへ差し替え |

**設計鉄則**: `src/` には業務ロジックのみを置き、`app/`(Streamlit)・`jobs/`(Actions)は**薄い呼び出し層**に徹する。
これにより、UI・スケジューラを差し替えても `src/` とDBスキーマは無傷で流用できる。

## ■留意点

- **Meta API審査**: ads_management（入稿・予算変更）は審査制。⓪取得（読み取り）と⑤入稿（書き込み）でスコープが異なる。Phase0で申請
- **トークン管理**: access_tokenはDBで暗号化保存（案AならSupabaseのカラム暗号化 or アプリ側で暗号化）
- **無料枠の上限監視**: Supabase 500MB・Actions分数を定期確認（超えたら案Bへ）
- **クライアント自前ログイン**が必要になった段階で、Streamlit→FastAPI+認証 もしくは案Cへ
```
