# ReleaseTune — Next.js 移行ガイド

## 移行の概要

`index.html`（React + Babel CDN）から **Next.js 15 App Router** への移行です。

---

## ディレクトリ構成

```
releasetune/
├── app/
│   ├── layout.tsx              # ルートレイアウト（フォント・GA・OGP基盤）
│   ├── globals.css             # グローバルスタイル
│   ├── page.tsx                # / → /date/今日 にリダイレクト
│   ├── not-found.tsx           # 404ページ
│   ├── date/[mmdd]/
│   │   └── page.tsx            # /date/04-06 日付ページ（SSR + OGP）
│   └── track/[id]/
│       └── page.tsx            # /track/xxx 楽曲詳細（SSR + 楽曲OGP）
├── components/
│   ├── SiteHeader.tsx          # スティッキーヘッダー
│   ├── SiteHeader.module.css
│   ├── DatePageClient.tsx      # 日付ページUI（Client Component）
│   ├── TrackDetailClient.tsx   # 楽曲詳細UI（Client Component）
│   ├── Jacket.tsx              # ジャケット画像（エラーフォールバック付き）
│   ├── SvcLinks.tsx            # Spotify/Apple/Amazon/YouTube リンク
│   ├── Icons.tsx               # SVGアイコン
│   └── GoogleAnalytics.tsx     # GA4 + ページビュー計測
├── lib/
│   ├── tracks.ts               # サーバー専用データアクセス層
│   └── utils.ts                # クライアント・サーバー共通ユーティリティ
├── data/
│   └── tracks.json             # ← そのままコピー（変更不要）
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

## デプロイ手順

### 1. 既存リポジトリに移行コードを追加

```bash
# リポジトリをクローン
git clone https://github.com/mincsnet/releasetune.git
cd releasetune

# 古い index.html を削除（data/ と Pythonスクリプトはそのまま）
rm index.html

# 移行ファイルをコピー
# （このREADMEと同じディレクトリにある全ファイルをコピー）
cp -r app/ components/ lib/ next.config.ts package.json tsconfig.json .gitignore ./

# 依存関係をインストール
npm install

# ローカルで動作確認
npm run dev
# → http://localhost:3000 で確認
```

### 2. Vercel の設定を更新

Vercel ダッシュボード → Project Settings → General:

| 設定 | 値 |
|------|-----|
| Framework Preset | **Next.js** |
| Build Command | `npm run build`（自動検出） |
| Output Directory | `.next`（自動） |
| Install Command | `npm install` |

### 3. GitHub に push → 自動デプロイ

```bash
git add -A
git commit -m "feat: Next.js App Router に移行"
git push origin main
```

Vercel が自動的に検出してビルド・デプロイします。

---

## 実装のポイント

### ルーティング

| URL | 動作 |
|-----|------|
| `/` | 今日の日付（`/date/MM-DD`）にリダイレクト |
| `/date/04-06` | 4月6日のリリース楽曲一覧（SSR） |
| `/track/[id]` | 楽曲詳細 + 楽曲ごとのOGP（SSR） |

### OGP（楽曲詳細ページ）

```
og:title   = "曲名 — アーティスト名"
og:image   = ジャケット画像URL（tracks.json の jacket フィールド）
og:type    = music.song
twitter:card = summary_large_image
```

### data/tracks.json の扱い

- ファイルはリポジトリに含めたまま（変更不要）
- サーバー側で `fs.readFile` で読み込み（`lib/tracks.ts`）
- インメモリキャッシュで同一リクエスト内の重複読み込みを防止
- Vercel のビルド時にバンドルに含まれる

### Google Analytics

- `G-3SDZ478Y78` はそのまま引き継ぎ
- Next.js の `next/script` で非同期読み込み
- `usePathname` でページ遷移を自動計測
- `gaEvent()` でストリーミングサービスのクリック・シェアを計測

---

## ローカル開発

```bash
npm install
npm run dev      # 開発サーバー起動 (http://localhost:3000)
npm run build    # 本番ビルド確認
npm run start    # 本番サーバー起動
```
