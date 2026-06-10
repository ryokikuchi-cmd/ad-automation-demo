# チーム共有の手順（デモUI）

現状はローカル（localhost）のみ。チームに見せる方法は2つ。

---

## 方法A：今すぐ共有（あなたのPCが起動中のみ・5分）

ローカルのStreamlitに公開URLを発行する。アカウント不要の cloudflared が手軽。

```bash
# 1回だけインストール
brew install cloudflared

# ターミナル①：アプリ起動（普段どおり）
cd /Users/kikuchiryou/Desktop/claude-code-file/広告自動化SaaS
DATABASE_URL=sqlite:///demo.db python3 -m streamlit run app/streamlit_app.py

# ターミナル②：トンネルを張る
cloudflared tunnel --url http://localhost:8501
```

→ `https://xxxx.trycloudflare.com` が発行されるので、チームに共有。

- 長所：最速。デプロイ不要
- 制約：**あなたのPCとアプリが起動中だけ**有効／URLは推測困難だが認証なし

---

## 方法B：常時共有（無料・推奨）Streamlit Community Cloud

GitHubにpush → デプロイすると、**PCを切っても見られる常時URL**になる。
※起動時にデータが空なら自動投入する改修済み（`app/streamlit_app.py`）。そのまま動く。

### 手順

1. **GitHubリポジトリを作成**（github.com で新規 private リポジトリ）

2. **ローカルをpush**
   ```bash
   cd /Users/kikuchiryou/Desktop/claude-code-file/広告自動化SaaS
   git init
   git add .
   git commit -m "ad automation demo"
   git branch -M main
   git remote add origin https://github.com/<あなた>/<リポジトリ名>.git
   git push -u origin main
   ```
   ※`.env`・`accounts.yaml`・`demo.db` は `.gitignore` 済みで上がりません（安全）。
   ※`app/demo_images/`（実バナー画像）はコミットされます。

3. **Streamlit Community Cloud でデプロイ**
   - https://share.streamlit.io にGitHubでログイン
   - 「New app」→ 対象リポジトリ／ブランチ `main`
   - **Main file path** に `app/streamlit_app.py` を指定
   - 「Deploy」→ 数分で `https://<アプリ名>.streamlit.app` が発行

4. **チーム限定にする場合**
   - アプリ設定 → Sharing → Private にして、閲覧者のメールアドレスを招待
   - 招待された人はGoogleログインで閲覧可能

### 補足

- 初回アクセス時に自動でデモデータが入る（`RawPlacement`が空なら投入）
- クラウドのDBは一時的（SQLite）。承認/却下の状態は再デプロイで初期化される（デモ用途として問題なし）
- 依存は `requirements.txt`（リポジトリ直下）を自動インストール

---

## どちらを選ぶか

| | 方法A（トンネル） | 方法B（Cloud） |
|---|---|---|
| 手間 | 最小 | GitHub push＋デプロイ |
| 常時アクセス | × PC起動中のみ | ◯ 常時 |
| URL配布 | 都度変わる | 固定URL |
| 用途 | その場で見せる | チームに配って各自確認 |

**チームにURLを配って各自いつでも確認 → 方法B** を推奨。
