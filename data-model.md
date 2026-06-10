# DBスキーマ設計 ＋ 商談スプシ取込仕様（Meta先行）

作成日: 2026-06-09 / simcle / concept.md v0.3 に対応

## ■設計方針

- 既存スプシ「キープサーチ様_詳細レポート」の3層（Raw / BI / 商談）をDBに移植
- **Raw と 商談・提案・ログはテーブル**、**BI集計はビュー（VIEW）** で持つ
  （集計を都度計算 → データ二重管理を避け、Pythonのpandasでも同等処理が可能）
- DBはPostgreSQL想定（Supabase無料枠 or ローカルPostgresで可）

---

## ■テーブル定義（PostgreSQL想定）

### テナント・アカウント

```sql
-- クライアント企業
CREATE TABLE tenants (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Meta広告アカウント（1テナントに複数可）
CREATE TABLE ad_accounts (
  id                BIGSERIAL PRIMARY KEY,
  tenant_id         BIGINT REFERENCES tenants(id),
  meta_account_id   TEXT NOT NULL,          -- 例: act_1347442399638203
  name              TEXT,
  access_token_enc  TEXT,                   -- 暗号化して保存
  token_expires_at  TIMESTAMPTZ,
  status            TEXT DEFAULT 'active',
  created_at        TIMESTAMPTZ DEFAULT now(),
  UNIQUE (meta_account_id)
);
```

### 広告メタデータ master（広告単位）

```sql
-- 広告ごとのビジュアル/訴求軸/画像URL等を保持（4象限・生成エンジンの参照元）
CREATE TABLE ads (
  id             BIGSERIAL PRIMARY KEY,
  ad_account_id  BIGINT REFERENCES ad_accounts(id),
  meta_ad_id     TEXT,
  ad_name        TEXT NOT NULL,
  campaign       TEXT,
  adset          TEXT,
  visual         TEXT,        -- 広告名パース or AI推定で付与
  appeal_axis    TEXT,        -- 同上（訴求軸）
  creative_type  TEXT,        -- image / video / carousel
  image_url      TEXT,        -- Vision分析用
  status         TEXT,        -- active / paused
  first_seen     DATE,
  last_seen      DATE,
  UNIQUE (ad_account_id, meta_ad_id)
);
```

### Rawレイヤー（⓪ API直格納・日次最小粒度）

```sql
-- Raw_媒体配置 相当
CREATE TABLE raw_placement (
  id             BIGSERIAL PRIMARY KEY,
  ad_account_id  BIGINT REFERENCES ad_accounts(id),
  date           DATE NOT NULL,
  campaign       TEXT,
  adset          TEXT,
  ad             TEXT,
  device         TEXT,
  media          TEXT,        -- facebook / instagram / ...
  placement      TEXT,        -- feed / stories / reels / ...
  cost           NUMERIC,
  impressions    BIGINT,
  clicks         BIGINT,
  leads          BIGINT,      -- 資料請求（Meta API由来）
  ingested_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (ad_account_id, date, campaign, adset, ad, device, media, placement)
);

-- Raw_年齢性別 相当
CREATE TABLE raw_age_gender (
  id             BIGSERIAL PRIMARY KEY,
  ad_account_id  BIGINT REFERENCES ad_accounts(id),
  date           DATE NOT NULL,
  campaign       TEXT,
  adset          TEXT,
  ad             TEXT,
  age            TEXT,        -- 25-34 等
  gender         TEXT,        -- male / female / unknown
  cost           NUMERIC,
  impressions    BIGINT,
  clicks         BIGINT,
  leads          BIGINT,
  ingested_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (ad_account_id, date, campaign, adset, ad, age, gender)
);
```

UPSERT前提（同日再取得で上書き）：`ON CONFLICT (...) DO UPDATE`。

### 商談レイヤー（① クライアント記入スプシ取込）

```sql
CREATE TABLE appointments (
  id             BIGSERIAL PRIMARY KEY,
  ad_account_id  BIGINT REFERENCES ad_accounts(id),
  date           DATE NOT NULL,        -- 商談発生日 or リード獲得日（運用で統一）
  campaign       TEXT,
  adset          TEXT,
  ad             TEXT,                 -- 流入広告（分かる場合）。不明ならNULL
  appointments   INT DEFAULT 0,        -- 商談数
  won            INT DEFAULT 0,        -- 成約数（任意）
  source_sheet   TEXT,                 -- 取込元スプシID/行（監査用）
  imported_at    TIMESTAMPTZ DEFAULT now()
);
```

### 分析・提案・生成・ログ（②〜⑤）

```sql
-- 分析実行単位
CREATE TABLE analysis_runs (
  id             BIGSERIAL PRIMARY KEY,
  ad_account_id  BIGINT REFERENCES ad_accounts(id),
  run_date       DATE,
  params_json    JSONB,       -- 閾値・対象期間など
  status         TEXT,
  created_at     TIMESTAMPTZ DEFAULT now()
);

-- 改善提案（③）＋ 生成物（④）
CREATE TABLE proposals (
  id                BIGSERIAL PRIMARY KEY,
  analysis_run_id   BIGINT REFERENCES analysis_runs(id),
  adset             TEXT,
  ad                TEXT,
  quadrant          TEXT,      -- top_left / top_right / bottom_left / bottom_right
  action_type       TEXT,      -- expand / change_appeal / change_visual / pause / budget
  detail_json       JSONB,     -- 変更前後・根拠など
  banner_prompt     TEXT,      -- ④生成: 修正版バナースクリプト
  copy_variants     JSONB,     -- ④生成: コピー案
  status            TEXT DEFAULT 'pending',  -- pending/approved/rejected/executed
  created_at        TIMESTAMPTZ DEFAULT now()
);

-- 入稿アクション監査ログ（⑤）
CREATE TABLE action_logs (
  id             BIGSERIAL PRIMARY KEY,
  proposal_id    BIGINT REFERENCES proposals(id),
  ad_account_id  BIGINT REFERENCES ad_accounts(id),
  action_type    TEXT,        -- budget / pause / duplicate / create
  payload_json   JSONB,
  dry_run        BOOLEAN DEFAULT true,
  executed_at    TIMESTAMPTZ,
  result_json    JSONB,
  executed_by    TEXT
);
```

---

## ■BI集計ビュー（① 標準メトリクス12列）

派生指標は全ビュー共通の式で算出する。

| 指標 | 計算式 |
|------|--------|
| CPM | cost / impressions * 1000 |
| CTR | clicks / impressions |
| CPC | cost / clicks |
| 資料請求単価 | cost / leads |
| 商談率 | 商談 / leads |
| 商談単価 | cost / 商談 |

例：CR別ビュー（4象限の入力。商談を結合）

```sql
CREATE VIEW v_bi_cr AS
SELECT
  r.ad_account_id,
  r.ad,
  a.visual,
  a.appeal_axis,
  a.image_url,
  SUM(r.cost)         AS cost,
  SUM(r.impressions)  AS impressions,
  SUM(r.clicks)       AS clicks,
  SUM(r.leads)        AS leads,
  SUM(r.cost) / NULLIF(SUM(r.impressions),0) * 1000 AS cpm,
  SUM(r.clicks)::numeric / NULLIF(SUM(r.impressions),0) AS ctr,
  COALESCE(ap.appointments,0) AS appointments
FROM raw_placement r
LEFT JOIN ads a  ON a.ad_account_id = r.ad_account_id AND a.ad_name = r.ad
LEFT JOIN (
  SELECT ad_account_id, ad, SUM(appointments) AS appointments
  FROM appointments GROUP BY ad_account_id, ad
) ap ON ap.ad_account_id = r.ad_account_id AND ap.ad = r.ad
GROUP BY r.ad_account_id, r.ad, a.visual, a.appeal_axis, a.image_url, ap.appointments;
```

同様に `v_bi_daily` `v_bi_adset` `v_bi_campaign` `v_bi_placement` `v_bi_age` `v_bi_gender` を定義。
（Pythonで処理する場合はpandasの`groupby`で同等。ビューと二者択一）

---

## ■商談スプシ取込仕様（② 必須機能）

### テンプレート（クライアントが記入するシート）

| 列 | 必須 | 内容 | 例 |
|----|------|------|----|
| 日付 | ◯ | 商談発生日（YYYY-MM-DD） | 2026-06-03 |
| 広告セット | ◯ | 流入元の広告セット名 | ノンタゲ_0418_リード獲得 |
| 広告 | △ | 流入元の広告名（分かれば） | ノンタゲ_04_ソーシャルセーリング |
| 商談数 | ◯ | その行の商談件数 | 1 |
| 成約数 | △ | 成約に至った件数 | 0 |
| 備考 | × | 補足 | 電話通電 |

- 1行=1商談（イベント単位）でも、日次集計（件数まとめ）でもどちらも可
- **結合キー: (ad_account, 広告 or 広告セット, 日付)**

### 取込フロー（日次バッチ）

1. テナント設定に登録された商談スプシID + シート名を取得
2. `gspread`（サービスアカウント認証）でシートを読み取り
3. バリデーション
   - 日付形式チェック（不正行はスキップ＋エラーレポート）
   - 必須列（日付・広告セット・商談数）の欠損チェック
   - 広告セット/広告名が `ads` テーブルに存在するか照合（不一致は警告）
   - 重複行検知
4. `appointments` テーブルへUPSERT（source_sheetに行番号を記録）
5. 取込結果サマリ（取込件数・スキップ件数・不一致名）を運用ログ/通知へ

### 広告紐付けの注意（重要）

- Metaのリードは広告単位で取れるが、**「どのリードが商談化したか」はクライアントのCRM側情報**
- クライアントが「広告」列まで埋められれば広告単位で商談を結合（4象限のCV評価が精密に）
- 埋められない場合は**広告セット単位**でしか結合できない → テンプレートで広告列の記入を推奨
- 命名規則をSaaSが統一付与（⑤）するため、運用が回ると広告名の一致率が上がる

---

## ■インデックス・運用メモ

- `raw_placement(ad_account_id, date)` / `raw_age_gender(ad_account_id, date)` に複合インデックス
- 日次UPSERTは「直近N日を再取得して上書き」方式（遅延コンバージョン対応）
- データ量は小さい（1アカウント日次で数百〜数千行）→ 単一の小規模Postgresで複数テナント収容可能
```
