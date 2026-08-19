# ReleaseTune 開発タスク

最終更新: 2026-08-19

このファイルはプロジェクトの開発状況・残タスクの正本です。新しいチャットセッションでもこのファイルを読めば経緯と優先順位が分かるようにしています。作業を進めたら随時更新してください。

## 完了済み（2026-08-05〜08 セッション）

- [x] `.cache`（Spotifyアクセストークン）のgit漏洩を解消。`.gitignore`のバグ（`.DS_Storenode_modules/`が改行なしで結合）を修正。`.next`等のビルド成果物の追跡解除、`git filter-repo`で履歴から完全削除しforce push
- [x] Next.js 15.3.6→15.5.22に更新。npm脆弱性 36件→5件（残りはNext.js 16メジャー更新が必要、保留中）
- [x] Supabaseクエリを`unstable_cache`でキャッシュ化、`/date/[mmdd]`・`/track/[id]`・`/artist/[name]`をISR化（Vercel Fast Origin Transfer / Supabase Egress超過対策）
- [x] `React.cache()`でリクエスト内の重複フェッチを解消（`generateMetadata`とページ本体が同じデータを2回ずつ取得していた）
- [x] `Math.random()`起因のHydrationエラー修正（DatePageClientの注目曲選出をmmddベースの決定的な値に変更）
- [x] CSP修正（`img-src`に`www.googletagmanager.com`を追加し、GA4計測ピクセルのブロックを解消）
- [x] `data/tracks.json`のgit追跡解除（Supabase移行後は中間ファイル扱いのため）
- [x] 新着cron（`app/api/cron/new-releases/route.ts`）にSpotify/YouTube直リンク自動取得を追加。新規追加分のみ対象（APIクォータ節約）。本番で動作確認済み（劇団四季「アラジン」で直リンク取得を確認）
- [x] `SvcGrid`/`TrackSvcLinks`の「YouTube」ボタンを「YouTube Music」に変更。`youtubeId`があれば`music.youtube.com`直リンクを優先（既存の検証済みデータにもバックフィルなしで即座に効く）
- [x] Vercel環境変数に`SPOTIFY_CLIENT_ID`・`SPOTIFY_CLIENT_SECRET`・`YOUTUBE_API_KEY`を追加（Production and Preview）

## 残タスク（優先順位順）

### 🔴 最優先

- [ ] **Spotify直リンクの一括バックフィル（自動cronに移行済み、要デプロイ）**
  - **判明した事実（2026-08-17〜18の実測）**: Spotify Web API（Client Credentials flow、Development Mode）は当初想定の「数千件/日」ではなく、**実際は1日あたり約200〜260リクエストで`429 QUOTA_EXCEEDED`**になる。`Retry-After`から逆算すると固定時刻リセットではなく「その日最初の呼び出しから約24時間のローリングウィンドウ」。この制約を前提に運用する方針に変更した
    - 抜本的に速くしたい場合はSpotify Developer Dashboardで「Extended Quota Mode」を申請する必要がある（無料・審査あり・申請はユーザー本人のアカウントで行う必要あり、未着手）
  - **2026-08-18時点の進捗**: 直リンク572件（1.7%）、残り32,261件（新着cronで日々総曲数も増えるため純減ではない）
  - **実装**: 手動実行用の`backfill_spotify.py`（ローカルPython、id昇順カーソル方式で中断・再開可）に加えて、**`app/api/cron/spotify-backfill/route.ts`を新設し毎日自動実行するcronに移行**（2026-08-19実装）
    - `vercel.json`に`0 22 * * *`（UTC）= JST 7:00 で登録（クォータのリセット目安 JST 6:53頃の直後を狙った時刻）
    - 1回の実行で最大120件処理、429検知で即座に打ち切りレスポンスを返す（安全マージン込み。新着cronの当日分Spotify消費とクォータを共有するため余裕を残す設計）
    - Spotify共通ロジック（トークン取得・検索）は`lib/spotify.ts`に切り出し、`new-releases`cronと共有（`searchSpotify`は`{url, quotaExceededRetryAfter}`を返す形に変更）
    - `?limit=N`クエリパラメータで手動テスト時の処理件数を絞れる（本番実行では未指定=120件上限）
  - **⚠️ 未デプロイ**: 上記の変更はローカルのみ。`git push`してVercelにデプロイしないとcronは動かない。デプロイ後、初回実行（翌日のJST 7:00）を確認すること
  - ローカルPythonスクリプト（`backfill_spotify.py`）は手動での追加実行・動作確認用に残置。使い方は`--dry-run --limit N`でまず確認してから本実行

- [ ] **一括バックフィル完了後、こまめにVercel Usage / Supabase Egressを監視**
  - バックフィル自体がSupabase書き込み・API呼び出しを大量発生させるため、実行中〜直後はコスト面の急増がないか確認する
  - cronでのバックフィルはVercel Function実行時間（1日1回・最大60秒）が追加で発生する点も念のため確認

### 🟡 中優先（制約あり）

- [ ] **YouTube直リンクの一括バックフィル**
  - 現状: `youtube_id`設定済みは420件（1.3%）、未設定32,406件（98.7%）
  - 制約: YouTube Data API無料枠は10,000 unit/日、`search.list`1回100 unit消費 → 実質100件/日が上限。全件処理に約320日かかる計算
  - 選択肢:
    - (A) Google Cloud Consoleでクォータ増枠申請（無料、審査あり）
    - (B) 100件/日ペースで地道に継続実行（cronに組み込むか、専用バッチを毎日回す）
    - (C) 優先度の高いアーティスト・楽曲から手動で絞り込んで処理

### 🟢 低優先（実害小さい、後回し可）

- [ ] ルート直下に散在するPython/CSV/logスクリプト（`add_spotify.py`, `fix_titles_*.py`等）を`scripts/`配下に整理
- [ ] `README.md`を現状の構成（Supabase・cron・ISR）に合わせて更新（現状は旧Next.js移行手順のまま）
- [ ] ESLint未設定（`npm run lint`が対話プロンプトで固まる。最低限のNext.js推奨設定を導入）
- [ ] `sitemap.xml` / `robots.txt`を追加（`app/sitemap.ts` / `app/robots.ts`）
- [ ] `tools/`配下の管理用HTML（`admin.html`, `duplicate-manager.html`, `youtube-manager.html`）が認証なしで公開領域に置かれていないか確認

## 技術的な背景メモ（新しいチャット向け）

- **データソース**: Supabaseの`tracks`テーブルが正データ。`data/tracks.json`はローカルの中間ファイル（`add_spotify.py`等で編集→`migrate_to_supabase.py`でSupabaseに反映、という旧運用の名残。git管理外）
- **cron**: `app/api/cron/new-releases/route.ts`が毎日JST 0:00（`vercel.json`のcron設定）に実行。iTunes RSSから新着取得→Supabaseにupsert（`ignoreDuplicates: true`）→実際に新規挿入された行のみSpotify/YouTube検索で直リンク補完
- **キャッシュ構成**: `lib/tracks.ts`の各データ取得関数は`cache()`（Reactのリクエスト内メモ化）+`unstable_cache`（デプロイをまたいだ持続キャッシュ、`getTracksByMmdd`は1時間・`getTrackById`/`getArtistByName`等は24時間）の二重ラップ
- **Amazon Music**: 公式の検索/カタログAPIが提供されていないため、検索URル（`music.amazon.co.jp/search/...`）方式を維持する方針で確定済み
- **YouTube**: `youtube_id`+`youtube_verified`で埋め込みプレイヤー（`youtube.com/embed/`）を制御。ボタンリンクは`youtubeId`があれば`music.youtube.com`、なければ`links.youtube`（旧検索URL）にフォールバック
- **Vercel環境変数**: `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`/`YOUTUBE_API_KEY`/`CRON_SECRET`/`SUPABASE_SERVICE_ROLE_KEY`等はProduction/Previewに設定済み（2026-08-08時点で本番動作確認済み）
- **`.env`のローカル値**: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`は1個ずつ、`YOUTUBE_API_KEY`は有効な1個に整理済み（2026-08-08、重複していた無効なキーを削除）。`SUPABASE_SERVICE_ROLE_KEY`は新旧2形式が重複したまま残っているが動作に支障なし（要クリーンアップだが緊急性なし）
