# 運用セットアップ手順（⑤入稿API ／ DB本番化）

## ■⑤ 自動入稿に必要なもの（新しいAPIは不要）

**結論：新しいAPIは不要。** 取得（⓪）と同じ **Meta Marketing API** を使う。
違いは**トークンの権限スコープ**だけ。

| 操作 | 必要スコープ |
|------|----------|
| データ取得（⓪・現状） | `ads_read` |
| 入稿・予算変更・停止・複製（⑤） | `ads_management`（書込） |

### 手順（自社/アクセス権のある広告アカウントを管理する場合）

1. business.facebook.com（ビジネスマネージャ）でアプリとビジネスを連携
2. 開発者ダッシュボードでアプリに「Marketing API」製品を追加
3. ビジネス設定 → **システムユーザー**（管理者）を作成
4. システムユーザーに対象の**広告アカウントを割当**（タスク：「広告を管理」）
5. **システムユーザートークンを生成**し、スコープに `ads_read` ＋ `ads_management` を付与
6. このトークンで [src/publish/meta_write.py](src/publish/meta_write.py) の書込（予算/停止/複製/作成）が動く

### App Review が要るかどうか

- **MVP（simcleがエージェンシー運用・管理者権限のあるアカウント）**
  → **Standard Access のシステムユーザートークンで開始可能。App Review 不要**なケースが多い
- **本格外販（アプリをクライアント自身に使わせる／管理権限外のアカウントを広く扱う）**
  → **Advanced Access（App Review＋ビジネス認証）が必要**

### 外部クライアントのアカウントを扱う流れ

- クライアントが自社ビジネスから**パートナー（simcleのビジネス）にアカウントを共有**
- → simcleのシステムユーザートークンでそのアカウントを管理可能に

> まとめ：**MVPは「既存トークンに ads_management を足す」だけで⑤を開始できる。** 審査は外販フェーズで。

---

## ■ DB本番化（Supabase）手順

現状ローカルSQLiteで検証済み。本番はSupabase（無料枠Postgres）へ。**スキーマ・コードは変更不要**（DATABASE_URLを差し替えるだけ）。

### 手順

1. **アカウント作成**：https://supabase.com → サインアップ
2. **New project** 作成
   - Region：**Northeast Asia (Tokyo)** 推奨
   - Database Password：強固なものを設定し控える
3. **接続文字列を取得**：Settings → Database → Connection string → **URI**
   - 例：`postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`
4. **`.env` に設定**（SQLAlchemy用に `postgresql+psycopg2://` へ書換）
   ```
   DATABASE_URL=postgresql+psycopg2://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```
5. **テーブル作成**
   ```bash
   python -c "from src.db.session import init_db; init_db()"
   ```
6. **テナント/アカウント登録 → 日次バッチ実行**
   ```bash
   META_ACCESS_TOKEN=... python jobs/daily_run.py
   ```
7. **GitHub Actions 用**：リポジトリ Settings → Secrets に `DATABASE_URL` を登録（daily.yml が参照）

### 接続の注意

- **GitHub Actions等（短命接続）からは Connection Pooler 推奨**
  - Settings → Database → Connection Pooling の URI（port **6543**）を使用
  - 例：`...@db.xxxx.supabase.co:6543/postgres?pgbouncer=true`
- 常駐プロセス（VPSのStreamlit等）は直結（5432）でOK
- **無料枠**：1週間アクセスが無いと一時停止 → 日次バッチが叩くので維持される

### 将来（外販時）

- **RLS（行レベルセキュリティ）**でテナント分離
- Supabase Auth でクライアントログイン
