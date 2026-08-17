# ReleaseTune

日本語の音楽リリースカレンダーサイト。「今日はあの曲のリリース日」をテーマに、日付・楽曲・アーティスト単位でリリース情報とストリーミングリンクを表示する。

## 開発タスク

**開発の状況・残タスク・優先順位は [tasks/todo.md](tasks/todo.md) を参照。** 新しいセッションで開発を続ける場合は、まずこのファイルを読むこと。作業を進めたら随時更新する。

## 技術スタック

- Next.js 15 (App Router) / React 19 / TypeScript
- Supabase（`tracks`テーブルが正データソース。`data/tracks.json`はgit管理外のローカル中間ファイル）
- Vercel（本番ホスティング、Cron Jobsで新着取得を自動化）

## 主要ファイル

- `app/api/cron/new-releases/route.ts` — 毎日JST 0:00に実行。iTunes RSSから新着取得→Supabaseにupsert→新規追加分のみSpotify/YouTube直リンクを自動補完
- `lib/tracks.ts` — Supabaseへのデータアクセス層。各関数は`cache()`（リクエスト内メモ化）+`unstable_cache`（持続キャッシュ）の二重ラップ
- `components/SvcLinks.tsx` — Spotify/Apple Music/Amazon Music/YouTube Musicのリンクボタン
