# ReleaseTune 開発タスク

最終更新: 2026-10-14

このファイルはプロジェクトの開発状況・残タスクの正本です。新しいチャットセッションでもこのファイルを読めば経緯と優先順位が分かるようにしています。作業を進めたら随時更新してください。

## 進行中: Vercel・Supabase からヘテムルへの移行（2026-10-14〜）

背景: Vercel Pro（月20ドル）と Supabase Pro（月25ドル）を払っている。収益が出るまでは契約済みのヘテムル1本にまとめて費用を抑える。計画の全文は `~/.claude/plans/magical-sniffing-owl.md`。

**方針（ユーザー決定済み）**: サイトは PHP 版に作り替える（ヘテムルは Node.js 非対応で Next.js のサーバーが動かないため。React/Next.js はやめて PHP＋素の JavaScript）/ DB を先に移して Supabase を先に解約し、その後 PHP 版サイトで Vercel を解約する

**調査で分かったこと**: ヘテムルは PHP 8.3〜8.5・MySQL 8.4 の共用サーバー。MySQL は外部から接続できない（公式FAQ）ので、手元のスクリプトと第1段階の Vercel は、ヘテムル上の PHP の API 経由で読み書きする。SSH はポート2222（root なし）、cron は最大20件（cron では rm・wget・find が使えない）。DB のデータは約31MB（tracks 33,378行・track_note_drafts 970行、2026-10-14 実測）

### 第0段階: 下準備
- [ ] ユーザー: ヘテムルで SSH を有効にして公開鍵を登録、MySQL のデータベースを作成、接続情報を設定ファイルに記入
- [ ] SSH で確認: PHP 拡張（pdo_mysql・curl・mbstring・gd＋FreeType）と cron 用 PHP の場所、`.htaccess` の mod_rewrite・mod_headers、URL の `%2F`（「/」入りアーティスト146曲）が 404 にならないか、公開フォルダの向け先、cron から外部 HTTPS、WAF の誤検知

### 第1段階: DB をヘテムルへ → Supabase 解約
手元（Homebrew の MySQL 8.4＋`php -S`、`.claude/launch.json` の `heteml-php`）で作成・検証済み（2026-10-14）。ヘテムル上での動作確認はまだ
- [x] `heteml/schema.sql`（照合は `utf8mb4_bin`、ilike 相当は `LOWER()` で明示。既定の照合だとひらがなとカタカナ・全角と半角が同一視される。アーティストページ用に小文字化した生成列 `artist_lc`）
- [x] 移行: `scripts/heteml/migrate_from_supabase.py export`（Supabase 全行 → `data/backup/supabase_*.jsonl`、35MB）→ `php heteml/bin/import_snapshot.php <file>`（両テーブルを空にして入れ直す・1トランザクション・件数照合。手元で1.5秒）→ `... compare <file>`（API 経由で全行を列ごと・型まで比較）
- [x] `heteml/src/tracks.php`（日付・ID・アーティスト・検索。日付とアーティストは今と同じく最大1000件、検索の `%`・`_` はエスケープ、同じ発売日の並びは id 順で固定）
- [x] `api/db.php`（スクリプト用 select/upsert/update、許可リスト・トークン認証、PostgREST 形式の条件は使っている書き方だけ）と `api/tracks.php`（第1段階の間だけ Vercel が使う、読み取り専用の別トークン）
- [x] `scripts/notes/common.py`: `.env` の `DATA_BACKEND=heteml` で `sb_*` が API を使う（関数の形は同じ。既定は切り替えまで `supabase`）。`review_ops.articles()` の並びに `track_id` を追加（同じ記事の曲の並びが DB 任せだった）
- [x] `backfill_spotify.py` も `DATA_BACKEND=heteml` で API を使うように（取得と更新の2か所。カーソル送りの取得結果が Supabase と同一、更新が反映されることを手元で確認）
- [x] cron を PHP に移植（`heteml/cron/new_releases.php`・`spotify_backfill.php`、`--dry-run` あり。Spotify 照合規則は `lib/spotify.ts` と同じ。打ち切りは45秒→300秒（クォータを使い切れる長さ）。ログは `heteml/logs/` に月ごと、12か月で削除。二重起動防止）
- [x] Vercel 側: `lib/tracks.ts` の取得先を API に（失敗時は例外にして、空の結果がキャッシュに残らないように）、未使用の `getAllArtistNames` を削除。**未コミット・未デプロイ**
- [ ] Vercel 側の残り（切り替え時）: `vercel.json` の cron と `app/api/cron/*`・`lib/spotify.ts` を削除、`@supabase/supabase-js` を外す、Vercel の環境変数に `HETEML_API_URL`・`HETEML_READ_TOKEN`
- 手元での検証結果（2026-10-14）
  - データ: 全 33,378＋970 行を列ごと・型まで比較して差分0（真偽値と数値、`{}` と `[]` の取り違えも検出できることを確認）
  - スクリプト: `export_pending.py`・`fix_search_slash.py apply --dry-run`・`review_ops` の読み取り系が新旧で同一出力。書き込み（upsert の部分上書き、in・NULL・真偽値の update）、`or`・`gt` 条件の件数が Supabase と一致
  - サイト用 API: 372日付・200曲・100アーティスト（「/」入り・大文字小文字違いを含む）・30語の検索が Supabase と一致。違いは上限（1000件・50件）の境目で同じ発売日の曲のどれが入るかだけ（Supabase では決まっていなかった）
  - サイト: 旧（Supabase）と新（API）の Next.js をビルドして23ページを比較し、同じ発売日の並びを揃えると22ページが一致。残り1つは `/search?q=50%`（旧は % をワイルドカード扱い、新は文字として検索。意図した変更）。カード画像もバイト単位で一致
  - ハマりどころ: Supabase は文字列を辞書順（en_US）で並べる（Fantasista → FEARS）。`utf8mb4_bin` のままだと文字コード順になるので、`api/db.php` の order では `utf8mb4_0900_ai_ci` で並べる
  - cron: Spotify 照合の規則テスト（10/5 の誤リンク事例を含む7件）、`new_releases` を手元 DB に本実行して16曲追加・2回目は0曲・ジャケット 600x600、`spotify_backfill --dry-run --limit=3` で見つけた2件をリンク先の曲名・アーティスト・発売日まで確認
- [x] ヘテムルに配置して同じ検証（2026-10-14）
  - サーバー: SSH は `ssh heteml`（`~/.ssh/config`、鍵 `~/.ssh/heteml_releasetune`、ユーザー mincs、users229）。コードは `~/releasetune/heteml/`、公開フォルダは `~/web/releasetune` → `~/releasetune/heteml/public` のシンボリックリンク。第1段階の API は `https://mincs.heteml.net/releasetune/api/*.php`。DB は `mysql402.phy.heteml.lan` の `_releasetune`（MySQL 8.4.8）。`config.php` は `make_config.py` でユーザーが作成済み（600）
  - 反映は `scripts/heteml/deploy.sh`（rsync。config.php・logs/・cache/ は送らない。cron ファイルを 700 に）。サーバーでのコマンドは `scripts/heteml/remote.sh '...'`
  - 環境: `php` コマンドはなく `/usr/local/bin/php8.3`（Web の Apache も 8.3.35）。8.3〜8.5 とも pdo_mysql・intl・gd（FreeType）・imagick・curl あり。git 1.8.3・Python 3.7・mysql クライアント 5.6 と古い。時刻は JST。外部 HTTPS（iTunes・Spotify・YouTube・GitHub）可
  - **ハマりどころ**: ヘテムルの SSH はまれに（6回に1回ほど）PHP とホームが見えない状態でつながる → `remote.sh`・`deploy.sh` は見えなければつなぎ直す
  - **ハマりどころ**: WAF（SiteGuard）が `<script>`・`UNION SELECT`・`../` を含むリクエストを 403 にする → `public/api/.htaccess` の `SiteGuard_User_ExcludeSig all` で api/ だけ対象外（トークン認証・プレースホルダ・許可リストで守っている）。4,100文字の怪しく見える本文の書き込みと読み戻しを確認
  - **第2段階への申し送り**: URL に `%2F` を含むと Apache が 404 を返す（`.htaccess` では変えられない）。「/」入りのアーティスト（146曲）は別の形の URL が必要。日本語のパスは問題なし。mod_rewrite・mod_headers・Authorization ヘッダーは使える
  - 検証: 取り込み4秒、全行の列ごと比較で差分0、認証の拒否（405/401/400）、サイト用 API の比較が手元と同じ結果（違いは上限の境目のみ）、notes・titles スクリプトの出力が Supabase と同一、cron 2本の試運転（ファイルを直接実行する形でも）、Spotify 補完が見つけたリンクの中身を確認
  - 注意: 1回目の比較では178日付で `spotify` 列だけ違った。別セッションの Spotify 誤リンク点検が、書き出しの後に Supabase で誤リンクを検索URLに戻したため。書き出し直して一致を確認。**切り替えは点検が終わってから**（点検は Supabase に書き込む）
- [x] ユーザー: Vercel の環境変数に `HETEML_API_URL`（`https://mincs.heteml.net/releasetune`）と `HETEML_READ_TOKEN`（`.env` と同じ値）を Production と Preview に追加（2026-10-14）
- [x] 切り替え時にコミットする状態を手元に用意（2026-10-14、未コミット）: `vercel.json`・`app/api/cron/*`・`lib/spotify.ts` を削除、`@supabase/supabase-js` をアンインストール。Supabase の環境変数なしで `tsc`・`next build` 通過（`/api/revalidate` は残る）。本物のヘテムル API につないだビルドと Supabase 版で23ページを比較し、22ページ一致（残りは意図した `/search?q=50%`）
  - メモ: 手元の `npx tsc` は、古い `.next/types` が消した cron を参照してエラーになる（`.next` を消すかビルドし直せば消える。実害なし）
- [ ] 切り替え（2026-10-14 21時台に実施、ユーザー指示「点検が終わったら切り替えて」。Spotify 点検は 17:09 に完了済み＝対象315行がすべて Supabase で検索URLに戻っていることを確認）
  1. [x] Supabase から最終の書き出し（`data/backup/supabase_20261014-211128.jsonl`）→ ヘテムルの今のデータ（20:48 取り込み）と比較して tracks は差分0。track_note_drafts は WAF 試験で書いた `waf-test` 行だけ多い（どこからも参照されず無害。SSH 復旧後に削除する）
     - この時 SSH が全く使えなくなった（認証は通るが、どのコマンドも出力なしで exit 254。Web の PHP は正常）。取り込み直しが不要だったので API での比較で代えた
  2. [x] コミット・push（`2abaeda` 部品、`51baad9` 切り替え、`f3316b2` 記録）。HEAD 単体で `tsc`・`next build` 通過を確認してから push。21:15 にデプロイ完了
  3. [x] 本番確認: 主要ページ 200（404 も期待どおり）、`/api/cron/*` は 404、本番の検索「50%」「恋」と10月14日のページの曲がヘテムルの API の結果と一致（＝本番がヘテムルを読んでいる）。SSH 復旧後に `waf-test` 行を削除し、最終書き出しと全行一致（差分0）。サーバーから Vercel のキャッシュ削除（`revalidate_site()`）も成功
  4. [x] ユーザー: ヘテムルのコントロールパネルで cron を2件登録（2026-10-14、画面で確認: 「ReleaseTune 新着取得」`0 0 * * *` `/home/users/2/mincs/releasetune/heteml/cron/new_releases.php`、「ReleaseTune Spotify補完」`0 7 * * *` `.../spotify_backfill.php`）。同じアカウントに別プロジェクトの cron（水曜どうでしょう `0 5 * * *`）もある（上限20件）
  5. [x] 手元の `.env` に `DATA_BACKEND=heteml` と `HETEML_API_URL=https://mincs.heteml.net/releasetune`（scripts/notes などはヘテムルを読み書きする）
  6. [x] 翌日、両 cron のログ（`scripts/heteml/remote.sh 'tail ~/releasetune/heteml/logs/*.log'`）と、新着がサイトに出ることを確認（2026-10-15）
     - 新着取得 0:00: 94件中23曲を追加、21曲に直リンク補完（Spotify 12・YouTube 21）、ジャケット全件600、22秒、キャッシュ削除成功。本番の楽曲ページに表示。Spotify 12件の中身を確認し11件は正しい。PassCode「Ray - EP」（2018）→「Ray [Re:]」（2026年の再録）は規則上は一致だが別の盤 → ユーザー判断でそのまま（2026-10-15）
     - Spotify 補完 7:00: 200曲を処理して144件に直リンク（Vercel 時代は1日平均62件）、429 なし、103秒。無作為20件のリンク先を確認し、すべて同じ曲（アルバムはその収録曲、同じ曲の別の盤を含む）
  - 注意: Supabase はもう書き込み先ではない。ルート直下の古いスクリプト（`migrate_to_supabase.py`・`backfill_jacket_600.py`・`add_spotify.py` など）は Supabase を直接書き換えるので使わない
  - 戻し方（問題が出たら）: `git revert 51baad9` して push すれば、サイトは Supabase を読み、Vercel の cron も戻る（ただし切り替え後にヘテムルで増えたデータは Supabase にない）
- [ ] 1週間様子見 → Supabase の最終バックアップを手元へ → ユーザーが Supabase を解約（CSP の `*.supabase.co` もこのとき外す）

### ⚠ 10/5 の Spotify 誤リンク修正が未コミット（2026-10-14 発見）
- `lib/spotify.ts`・`app/api/cron/*/route.ts`・`backfill_spotify.py`・`fetch_youtube.py` の修正（下の「2026-10-05 誤った直リンクの一括修正」）がコミットされておらず、本番の cron は今も古い照合（一致しなければ先頭の結果を採用）で動いている。直リンクは 10/5 修正後の約1,970件（3,200 − 誤り1,370 ＋ 再検索137 からの推定）から 2,325件（10/14 実測）に増えており、この約360件に誤リンクが混ざっている可能性が高い
- [x] 修正をコミット・デプロイ（2026-10-14、ユーザー指示、`4943ab0`）。`lib/spotify.ts`・cron 2本・`backfill_spotify.py`・`tasks/lessons.md` のみ。コミット単体で `tsc`・`next build` 通過を確認してから push。Vercel のデプロイ成功（本番 `4943ab0`）、主要4ページの 200 を確認。次回の cron（JST 0:00 新着・7:00 補完）から新しい照合で動く。`fetch_youtube.py` の未コミットの変更（スクリプト用の YouTube キー `YOUTUBE_API_KEY_SCRIPTS`）は Spotify と無関係なので含めていない
- [ ] 10/5 以降に増えた直リンクを 10/5 と同じ方法（embed で曲名・アーティスト・発売日を照合）で監査（別セッションで実行中、2026-10-14〜）

### 第2段階: PHP 版サイト → Vercel 解約
2026-10-15 に作成。手元とヘテムルの試験公開（`https://mincs.heteml.net/releasetune/`、noindex）で動作確認済み
- [x] 入口 `heteml/public/index.php`（URL は Next.js 版と同じ。末尾の「/」は 308 で外す）、`.htaccess`（振り分け、セキュリティヘッダー、直下→www 307・http→https 308）
- [x] 各ページ `heteml/src/pages.php`・共通部品 `heteml/src/site.php`（HTML の構造とクラス名を Next.js 版と同じにした）。サブフォルダでも動くよう URL は `u()` で作る
- [x] CSS: Next.js 版の `globals.css`・各 CSS Module を接頭辞付きで機械的に `heteml/public/assets/site.css` へ（hd- ヘッダー / dp- 日付 / td- 楽曲 / ap- アーティスト / sp- 検索 / c- 共通）。素の JS は `heteml/public/assets/site.js`（カレンダー、ジャケット代替、シェア、検索フォーム、GA4 イベント）
- [x] 配信サービスのアイコンは `<symbol>` で1回だけ定義（曲ごとに SVG を埋め込むと日付ページが 570KB になったため）。日付ページは本番 653KB → 324KB
- [x] カード画像 `heteml/src/og_image.php`（GD。Google Fonts から使う文字だけのフォントを取得、行の高さはフォントの hhea から計算、`cache/og/` に1日保存）。URL は今と同じ `/track/{id}/opengraph-image`
- [x] 「/」を含むアーティスト名（Apache が %2F を 404 にする）は `/artist?name=...` で表示し、サイト内のリンクもその形にした。**旧 URL（%2F 入り）は切り替え後 404 になる**（146曲分、避けられない）
- 確認結果（2026-10-15）
  - 見た目: 画面なしの Chrome で全要素の位置・大きさ・色・文字の設定を本番と比較（`scratchpad/vis/dump.mjs`）。375px・1440px でトップ・日付3・楽曲・アーティスト・検索2・プライバシー・404 が一致。違いは (1) 本番は「今日」を UTC で判定するので朝9時まで今日のページに「今日に戻る」が出る（PHP 版は JST で正しい）(2) 検索件数の表示が 1px（Next.js が文字を分けて描くため）(3) 特殊なラテン文字の行の高さ 1px
  - 1月1日（1000曲）は画面の測定が重すぎたので HTML の曲の並びと曲名を比較して一致
  - メタ情報: 15ページで title・description・OGP・twitter・canonical が一致。本番の `/search` と存在しない楽曲は Next.js がメタ情報を `<body>` に出していた（PHP 版は `<head>`）
  - 動き: カレンダー（開閉・月送り・選択で移動）、前日・翌日、シェア文（通常・発売日当日）、検索フォーム、GA4 イベント、ジャケットの代替表示をブラウザで確認
  - カード画像: 新宝島・長い曲名・長いアーティスト名・ジャケットなしで本番と見比べてほぼ同じ（ロゴの文字間が数 px 広い程度）
  - ヘテムル上: 表示 0.1〜0.3 秒（本番 0.4〜2.6 秒）、カード画像は初回 1.7 秒・2回目からは保存済み
- [ ] ユーザーに試験公開の見た目を確認してもらう
- [ ] 切り替え（ユーザー確認のうえ、アクセスの少ない時間に）
  1. ユーザー: ヘテムルの管理画面で独自ドメイン `releasetune.com`・`www.releasetune.com` を追加し、公開フォルダを `web/releasetune` にする
  2. ユーザー: ムームードメインの DNS をヘテムルに向ける → 反映後すぐ、ヘテムルで無料 SSL（Let's Encrypt）を設定（DNS が向くまで発行できないので、数分〜1時間ほど https が警告になる）
  3. 確認: 直下→www の転送、http→https、全ページ、カード画像、GA4
  4. サーバーの `config.php` の `revalidate_url` を空に（Vercel がなくなるため）、`api/tracks.php` を削除
  5. 1週間様子見 → ユーザーが Vercel を解約 → Next.js 一式を削除、`CLAUDE.md`・`README.md` 更新、ルート直下の `debut_artists.csv` は `heteml/data/` に一本化
- [ ] 切り替え後: Search Console でエラーが増えていないか確認

## 完了済み（2026-08-05〜08 セッション）

- [x] `.cache`（Spotifyアクセストークン）のgit漏洩を解消。`.gitignore`のバグ（`.DS_Storenode_modules/`が改行なしで結合）を修正。`.next`等のビルド成果物の追跡解除、`git filter-repo`で履歴から完全削除しforce push
- [x] Next.js 15.3.6→15.5.22に更新。npm脆弱性 36件→5件（その後2026-09-24に0件まで解消、下記参照）
- [x] Supabaseクエリを`unstable_cache`でキャッシュ化、`/date/[mmdd]`・`/track/[id]`・`/artist/[name]`をISR化（Vercel Fast Origin Transfer / Supabase Egress超過対策）
- [x] `React.cache()`でリクエスト内の重複フェッチを解消（`generateMetadata`とページ本体が同じデータを2回ずつ取得していた）
- [x] `Math.random()`起因のHydrationエラー修正（DatePageClientの注目曲選出をmmddベースの決定的な値に変更）
- [x] CSP修正（`img-src`に`www.googletagmanager.com`を追加し、GA4計測ピクセルのブロックを解消）
- [x] `data/tracks.json`のgit追跡解除（Supabase移行後は中間ファイル扱いのため）
- [x] 新着cron（`app/api/cron/new-releases/route.ts`）にSpotify/YouTube直リンク自動取得を追加。新規追加分のみ対象（APIクォータ節約）。本番で動作確認済み（劇団四季「アラジン」で直リンク取得を確認）
- [x] `SvcGrid`/`TrackSvcLinks`の「YouTube」ボタンを「YouTube Music」に変更。`youtubeId`があれば`music.youtube.com`直リンクを優先（既存の検証済みデータにもバックフィルなしで即座に効く）
- [x] Vercel環境変数に`SPOTIFY_CLIENT_ID`・`SPOTIFY_CLIENT_SECRET`・`YOUTUBE_API_KEY`を追加（Production and Preview）
- [x] （2026-09-24）Dependabotアラート10件（Critical 4 / High 4 / Moderate 2）を解消し`npm audit`0件に。Next.js 15.5.22→15.5.26（Image Optimization APIのRCE等）、sharp 0.34.5→0.35.4（libvips/libheif）、postcssは`next`が8.4.31に固定しているため`package.json`の`overrides`で`^8.5.23`に揃えた。Next.jsを更新する際は、この`overrides`がまだ必要か（next側がpostcssを更新したか）確認すること

## 進行中: トップページ（DatePageClient）PC版レイアウト（2026-09-28〜）

方針: スマホ版の見た目は一切変えず、PC（幅960px以上）だけ専用レイアウトにする。`/`と`/date/[mmdd]`は同じ`DatePageClient`を使うため両方に効く。

- [x] 土台: `DatePageClient`のインラインstyleを`DatePageClient.module.css`へ移行（動的な値だけインラインに残す）。JSのhover state（useState）はCSSの`:hover`に置換
- [x] スマホ版の回帰確認: 移行前後で全要素の計算済みスタイル・位置をダンプして差分ゼロを確認
- [x] PC案（960px以上）: コンテナを600px→1200pxに拡張
  - 注目曲: ジャケット左・情報右の2カラムのヒーロー表示（MV埋め込みは右カラム下部、ジャケットはsticky）
  - 他の楽曲: 2列グリッド（年見出しは全幅）
  - デビュー記念日バナー: 2列
  - カレンダー: PCでは幅を380pxに制限（全幅だとセルが巨大化するため）
- [x] PC/タブレット/スマホ幅でブラウザ確認、`tsc`・`next build`通過
- [x] ユーザーレビュー → コミット（2026-09-28、方向性OK）

- [x] 仕上げ1: `SiteHeader`をPC（960px以上）で本文の左右端に揃える。全ページ共通なので他ページのPC表示でもロゴ位置が変わる（スマホは不変）。幅はglobals.cssのCSS変数`--pc-content-width`に集約
- [x] 仕上げ2: PCでカードのジャケットを68px→88pxに。`Jacket`のサイズをCSS変数`--jacket-size`（未指定時は従来の`size`）で上書き可能にした。他ページは変数を指定しないので不変
  - 88pxにするとカードの文字領域が20px減り、ストリーミングボタン4つ（実測428px）が収まらなくなるため、本文幅を1120px→1160pxに拡大（余裕は従来と同じ約14px）
- [x] 回帰確認: トップ/日付ページのスマホ・タブレット、アーティスト・楽曲詳細・検索ページのスマホは差分ゼロ。他ページのPCはヘッダー内の要素のみ変化。`tsc`・`next build`通過
- [x] ユーザーレビュー → コミット

## 進行中: 他ページのPC対応（2026-09-28〜）

トップページと同じ手順: CSS Module化 → スマホ・タブレットの計算済みスタイル比較で差分ゼロ確認 → 960px以上だけPCレイアウト追加。本文幅は`--pc-content-width`を共有。

- [x] 楽曲詳細（`TrackDetailClient`）: トップの注目曲と同じ2カラムヒーロー（ジャケット左・sticky／タイトル・解説・試聴・MV・シェアを右）。同じ日の他の楽曲は3列グリッド
- [x] アーティスト（`ArtistPageClient`）: ヒーローを横並び（丸ジャケット160px左・名前とデビュー情報右）。楽曲一覧は2列グリッド、カードのジャケット60→80px
- [x] 検索（`SearchPageClient`）: 検索フォームは中央720px、結果は2列グリッド、カードのジャケット60→80px
- [x] PCのグリッドで極端に長いアーティスト名（例: 声優が数十人並ぶEP）が同じ行のカードまで間延びさせる問題 → PCのみ省略表示（兄弟カードは1行、楽曲カードは2行まで）。トップページのカードにも適用
- [x] 回帰確認: 375/800pxで全7ページ（トップ、日付×2、楽曲詳細×2、アーティスト、検索×3状態）の計算済みスタイル差分ゼロ。960/1440pxでヘッダーと本文の端揃え・横スクロールなし・ボタン折り返しなし。検索の送信操作も確認。`tsc`・`next build`通過
- [x] ユーザーレビュー → コミット
- メモ: `track.note`（解説文）を持つ曲はSupabase上に現在0件。表示コードは残しているが、PCでの見え方は実データで未確認
- メモ: 開発中、CSS ModuleのクラスをPC用の`@media`内で初めて定義すると、サーバー側が古いCSS Moduleのままでハイドレーション警告が出ることがある（リロードで解消、本番ビルドには影響なし）

### レビュー（2026-09-28）

- **回帰確認の方法**: 375px/800px幅で`/`・`/`（カレンダー展開）・`/date/05-08`（デビュー記念日あり）・`/date/08-26`（注目曲にMV埋め込みあり）の全要素の計算済みスタイルと座標を変更前に保存し、変更後と比較。差分は注目曲の右カラム用に追加したラッパーdiv 1個のみ
- **ハマりどころ**: CSS Modulesは`@keyframes`名もローカル化するため、`animation: fadeUp`と書くとglobals.cssの`fadeUp`を参照できずアニメーションが消える。`animation: global(fadeUp) ...`と書く必要がある
- **1200pxにした理由**: 1120pxだとカード内のストリーミングボタン4つが収まらず「YouTube Music」だけ2行目に落ちた。960〜1200px未満の幅では2行に折り返すが許容範囲と判断
- **次の候補**: 利用規約・プライバシーポリシー（680px 1カラム、読み物なのでPCでもこの幅で妥当）以外の主要ページはPC対応済み

## 進行中: 新着cronのジャケットが170x170で保存される不具合（2026-09-28〜）

- **原因**: `new-releases` cronはRSSの`im:image`から最大サイズを選んでから`"100x100bb"`を`"600x600bb"`に置換していたが、iTunes RSSの画像は55/60/170pxの3種で最大は`170x170bb`。置換が一度もマッチせず、cronで追加された曲はすべて170x170のジャケットで保存されていた（例: `/track/6802135954`）。サイト上は最大約500pxで表示するためぼやける。cron導入前にインポートした行は`600x600bb.jpg`で問題なし
- [x] cron修正: URL末尾を正規表現`/\/\d+x\d+bb\.\w+$/`で`/600x600bb.jpg`に置換。ライブRSS 88件で全件`600x600bb.jpg`になりHEAD 200を確認。`tsc`通過
- [x] 影響件数（2026-09-28、anonキーでcountのみ取得）: 全33,219件中 **`170x170bb.png`が852件**、`600x600bb.jpg`が32,367件。他のサイズ・空・NULLは0件
- [x] バックフィルスクリプト`backfill_jacket_600.py`を作成。`id,jacket`のみ取得・200件ずつページング・`Prefer: return=minimal`で1件ずつPATCH・書き換え後URLがHEAD 200のものだけ更新。**全件ドライラン済み: 852件すべて600x600が取得可能（skip 0）**。HEADを1件ずつ行うので所要約8分（本実行はPATCH分が加わる）
- [x] **バックフィル本実行（2026-09-29）**: 865件を`600x600bb.jpg`に更新（skip 0 / 失敗 0）。調査時の852件から13件増えていたのは、未デプロイの旧cronが9/29 JST 0:00に170x170の新着を追加したため。実行後は全33,232件が`600x600bb`・`170x170bb`は0件
  - 修正をデプロイするまでは毎日のcronで170x170の行が増え続けるので、デプロイ後に`python3 backfill_jacket_600.py`をもう一度実行して取りこぼしを直す（対象がなければ何もせず終わる）
- [ ] 修正をコミット・デプロイし、翌日のcronで追加された新着が`600x600bb.jpg`で保存されていることを確認
- [ ] 反映確認: `lib/tracks.ts`の`unstable_cache`により、日付ページは最大1時間、楽曲・アーティストページは最大24時間は古いURLのまま表示される
- **拡張子は`.jpg`に統一（2026-09-29 ユーザー判断）**: RSSのURLは`.png`だが、mzstaticは同じパスで`.jpg`も返す。既存の正常データ32,367件はすべて`.jpg`。600x600の実測ではPNGが平均約364KB、JPGが約72KB（約5倍）で、`Jacket`は`unoptimized`のため一覧のサムネイル（68〜88px）でもブラウザがこのファイルをそのまま読み込む

## 進行中: 楽曲紹介文（短文・長文）の補完（2026-09-28〜）

`tracks.note`は表示側の実装済みだが全33,219曲が空。Wikipediaを「事実の出典」として使い、Claude Codeが独自の文章を書いて補完する。

**方針（ユーザー決定済み）**: Claude APIは使わず、Claude Codeの定期実行で毎日少しずつ執筆 / 短文（カード・注目曲用、60字以内）と長文（楽曲詳細用、150〜400字）の2本立て / 楽曲詳細に出典（Wikipedia記事へのリンク）を表示 / 抜き取りレビューで承認したものだけ公開 / です・ます調 / 邦楽のみ

**毎日の流れ**: 収集（スクリプトがWikipediaの記事とDBの曲を照合、出典テキストを保存）→ 執筆（Claudeが`STYLE.md`に従って下書き）→ 機械チェック・保存（抜き取り対象を決める）→ レビュー（ローカルのレビュー画面で承認すると即公開）

- [x] Supabaseに列とテーブルを追加（ユーザーがSQL Editorで実行）: `tracks`に`note_long`・`note_source_title`・`note_source_url`、下書き用の`track_note_drafts`（「記事なし」も記録して再調査を防ぐ）
- [x] `scripts/notes/`: 収集（`collect.py`）、執筆用の書き出し（`export_pending.py`）、機械チェック・保存（`import_drafts.py`）、レビュー画面（`review_server.py`）、執筆ルール（`STYLE.md`）、手順書（`ROUTINE.md`）。アーティスト対応表（`artists.csv`）は`collect.py`が自動作成
  - レビュー画面・保存系はテーブル作成後に動作確認する
- [x] 収集テスト（ドライラン、2026-09-28）: 中森明菜 200曲→89曲が記事と一致（50記事）、AAA 159曲→77曲（60記事、曖昧さ回避ページを避けて「AAA (音楽グループ)」に解決）、福山 雅治 114曲→28曲（26記事）
  - 対応したこと: カテゴリ内の転送ページ（例:「恋人 (福山雅治の曲)」→両A面シングルの記事）は転送先の記事を使う。`{{Start date|2014|10|1}}`形式の発売日を読めるようにした
  - 発売日の不一致で正しく除外された例: 中森明菜「難破船」（記事は1984年の加藤登紀子の原曲）、2024年の再発盤「北ウイング」
- [x] 機械チェックのテスト: 長すぎ・である調・出典にない数字（「1位」「100万枚」）・出典の丸写し・出典にない作品名・禁止表現・評価語・根拠なしをすべて検出。数字は「3位」のように単位1文字まで含めて照合する（数字だけだと出典の「3分34秒」などに紛れて見逃すため）
- [x] サイト表示: 楽曲詳細に長文と出典リンク、meta descriptionを長文優先に。一覧系クエリは`note_long`を取得しない（Supabase転送量対策）→ `tsc`・`next build` → レビュー → デプロイ
  - **上の「他ページのPC対応」のコミット後に着手**（`TrackDetailClient`が未コミットの変更と重なるため）
- [x] Supabaseの列・テーブル追加（2026-09-28、ユーザー実行済み）
- [x] 試作50記事を執筆して保存（バッチ`2026-09-28`、全件が要確認、機械チェックの指摘0）。対象は中森明菜・AKB48・浜崎あゆみ・倖田來未 各10、AAA 6、さだまさし 3、氷川きよし 1
- [x] 外部（スマホ等）からもレビューできるよう、claude.ai の非公開ページ（Artifact）を作成（2026-09-29）: https://claude.ai/artifact/LFJqVNK3yBbWEs1un5uDev
  - ページは判断を記録するだけ。本番への反映は Claude が同期したとき（`scripts/notes/sync_review.py`、手順は`ROUTINE.md`の「同期の手順」）。ページのデータベースは Claude の ArtifactData ツールでしか読み書きできないため、同期は「ツールで書き出す → スクリプトで反映 → ツールで書き込む」の3段
  - 閲覧・書き込みはオーナーのみ（db のアクセスルールで admin 以上に制限。`as_level: interact` で読めないことを確認済み）
  - 承認・書き直し・却下の処理はローカルのレビュー画面と共通化（`review_ops.py`）。ローカル画面（8765番は別プロジェクトが使用中のため8787番）も引き続き使える
- [ ] **次: 非公開ページで50記事を全件確認 → 「同期して」と依頼 → 承認分が公開される**
- [x] （2026-09-30）今日（9月30日）リリースの曲の紹介文: `collect.py --mmdd 09-30`（日付指定オプションを追加）で86曲を照合し、29記事の出典を取得して執筆。バッチ`2026-09-30`として保存し、非公開ページに追加（`sync_review.py --upload-only`: ページ上のレビュー途中の判断3件は反映せず残した）
  - 機械チェックの修正: 作品名の中の「。」（『心が叫びたがってるんだ。』）で文を区切っていた誤検知を解消。試作期間（全件確認）の判定を「書いた記事数」から「人がレビューを終えた記事数」に変更
  - 邦楽判定の不具合を修正: 国名のないカテゴリ（「7人組の音楽グループ」など）しかない記事を海外と誤判定していた（Hey! Say! JUMP）。海外と判定するのは「アメリカ合衆国の〜歌手」のように国名付きのカテゴリがあるときだけにした。「演歌歌手」「〜のアーティスト」も音楽家として扱い、記事名の候補に「(フォークグループ)」などを追加（アリス、原田悠里が解決）
  - 特定できないまま残るのは、共演名義（「モーニング娘。&平家みちよ」など）・ミュージカル・海外のアーティスト。共演名義を主アーティストで照合するのは今後の改善候補
  - 注意: DBのアーティスト名が同じでも別人の曲が混ざっている（例:「アリス」名義のイタリア語の曲）。曲名と発売日も一致しないと出典にしないので、誤った紹介文にはならない
- [x] サイト表示の変更（2026-09-30、PC対応のコミット後に着手）: 楽曲詳細は長文を優先し「出典: Wikipedia「◯◯」」のリンクを表示。meta descriptionも長文優先で句点で区切る。一覧系クエリ（日付・アーティスト・検索）は`note_long`と出典を取得しない。`tsc`通過、開発サーバーで日付ページ・楽曲詳細の表示とエラーなしを確認
  - [x] 実データでの見た目の確認（2026-09-30）: Vaundy「忘れる前に」の楽曲詳細で長文（299字）と出典リンク、meta descriptionが句点で区切られること、日付ページのカードに短文のみが出て長文がページのデータに含まれないことを確認（スマホ幅）。`next build`通過
  - [x] ユーザーレビュー → コミット・デプロイ（2026-09-30、`609b184`・`82894e0`）。本番で確認: `/api/revalidate`は認証なしで401、`revalidate_site()`で本番のキャッシュを消した直後に「新宝島」の楽曲詳細に長文・出典リンク・meta description、9月30日の日付ページに短文が表示され、日付ページのHTMLに長文は含まれない
- [x] （2026-09-30）サカナクション「新宝島」（track 1043473928、DB上の曲名は「Shin Takara Jima - Single」）をユーザーの依頼で個別に作成・反映。曲名がローマ字のため自動照合できず、Wikipediaの「新宝島 (曲)」と手動で対応づけた（発売日2015-09-30で一致、`issues`に`manual_match`を記録）
- [x] 反映した紹介文が本番に出るまでの遅れ（データ取得の`unstable_cache`が日付ページ1時間・楽曲詳細24時間）を解消（2026-09-30）: キャッシュにタグ`tracks`を付け、`/api/revalidate`（POST、`CRON_SECRET`のBearer認証）で消せるようにした。同期スクリプトとローカルのレビュー画面が承認の直後に呼ぶ。開発サーバーで認証（401/405）と、呼ぶと日付ページに公開直後の紹介文が出ることを確認
- [x] （2026-09-30）初回の同期: ページの判断5件（浜崎あゆみ3記事、Vaundy「忘れる前に」、Mrs. GREEN APPLE『POPS』）を承認として本番に反映
  - 同期スクリプトの不具合を修正: `--upload-only`追加時に入れた「判断が残る記事は消さない」処理が、反映し終えた判断まで数えていたため、公開済みの記事がページに残るところだった（今回は手動で削除）
  - レビューでの直し方（短文・名詞文の体言止め、人名はフルネーム）を`STYLE.md`に反映し、機械チェックを「常体の文末だけ指摘」に変更。教訓は`tasks/lessons.md`に記録
  - レビューで特に見てほしい点（執筆担当からの申し送り）: 「認定」欄の賞を楽曲の受賞として書いた記事（少女A・セカンド・ラブ・禁区）、CM名の略記（AKB48）、「大胆に」という表現（LOVEppears）、長文が盤の仕様中心で薄い記事（You are you）、番組名の「!」（DRAGON FIRE・ハレルヤ）
- [x] 執筆担当の申し送りから、判断が明確なルールを`STYLE.md`に追記: タイアップがリミックスやカップリングに付いている場合はその旨を書く / 後年のタイアップは時期を明記して長文へ / 「認定」欄の賞は受賞者をはっきりさせる / 出典内で食い違う数字は本文を優先し、判断できなければ書かない / 商品名は「」、固有名詞の「!」は残す
- [ ] ユーザーのレビュー結果を`STYLE.md`に反映。要相談: 短文の優先順位（バラエティ番組のテーマ曲や企業CMより、チャートの記録を優先するか）
- [x] `{{分数|1|2}}`が消える整形の不具合を修正し、試作50記事の出典テキストを取り直した（禁区・トワイライト・1/2の神話・セカンド・ラブの4記事が更新）
- [ ] DBのデータの問題（別タスク候補）: ~~氷川きよしなど曲名がローマ字の曲は照合できない~~ → 2026-09-30に曲名を直し、`collect.py --rematch`で照合し直した（下の「英語・ローマ字表記の曲名を日本語タイトルに修正」参照）。さだまさしのアルバム等の発売日「2004-01-01」、倖田來未「M・a・z・e」の「2002-01-01」は仮の日付とみられる
- [ ] 定期実行（デスクトップアプリの定期タスク、毎日9:00、1日20記事から）を登録し、1回手動で実行して確認

## 進行中: 英語・ローマ字表記の曲名を日本語タイトルに修正（2026-09-30〜）

例: 氷川きよし「Ojiichanchi E Ikou - Single」→「おじいちゃんちへいこう - Single」、スピッツ「Hachimitsu」→「ハチミツ」

- **原因**: 過去の一括収集（`collect_itunes.py`）が iTunes Lookup API を `entity=album` で呼んでいた。アルバム側の名前は `lang=ja_jp` を指定しても英語・ローマ字で返る（APIの癖）。同じAPIでも `entity=song` の曲側の `collectionName` は日本版の表記で返る。毎日の新着cron（RSS）は日本版の表記で入るので、直すのは過去データのみ
- **方式**: `scripts/titles/fix_ja_titles.py`。曲名に日本語を含まない約2.3万曲を iTunes Lookup（`entity=song`、100件ずつ）で照会し、日本版タイトルを取得。ボックスセットは曲側の名前がディスク単位になる（例: デヴィッド・ボウイ「Five Years 1969-1973」→「David Bowie (AKA Space Oddity)」）ため、曲側とアルバム側で収録曲数が違うときは Apple Music の oEmbed（ページの表示タイトル）で確かめる
- 反映時は、保存済みの検索URL（Spotify・Amazon・YouTube列のうち直リンクでないもの）の検索語に含まれる旧曲名も置き換える。変更前の値は `data/titles/applied_*.jsonl` に残し、`revert` で戻せる

- [x] 原因調査・スクリプト作成（`fetch` / `propose` / `apply --dry-run` / `apply` / `revert`）
- [x] 全件取得（`fetch`、22,686曲）→ 候補一覧: 日本語化 6,625件 / 表記の違い 2,286件 / Apple側で名前が変わった 24件 / 同じ 13,521件 / Appleに作品なし 230件
- [x] ユーザー確認（2026-09-30）: 海外アーティストの邦題（約15件、例: アラン・メンケン「Aladdin (Original Motion Picture Soundtrack)」→「アラジン (オリジナル・サウンドトラック)」）も揃える / 表記だけの違い（例: Mr.Children「Bolero」→「BOLERO」）も揃える。方針は「Apple Music日本版の表記に統一」
- [x] 試験反映20件 → 開発サーバーで楽曲詳細・日付ページの表示とリンクを確認 → `revert`で戻せることも確認 → 全件反映（2026-09-30、計8,911件、検索URL 26,000件超も更新）。反映後に`propose`し直して日本語化・表記違いの残りが0件になったことを確認
  - 変更前の値: `data/titles/applied_20260930-131529.jsonl`（試験20件）、`applied_20260930-131555.jsonl`（残り全件）。反映した候補一覧は`proposals_applied_20260930.csv`
  - 本番サイトは`unstable_cache`（楽曲詳細等24時間・日付ページ1時間）のため、最大24時間で新しい曲名に切り替わる
  - **ハマりどころ**: Amazon Musicの検索URLは検索語に「/」があると、そのままではトップページへ、`%2F`では404になる。空白に置き換えると正しく検索できる。反映時は検索語の「/」を空白にした
- [x] `changed`の24件（DBの曲名がAppleの今の英語名とも違う＝取り込み後にApple側で名前が変わった）をユーザーと1件ずつ確認（2026-09-30）
  - 反映した18件（`data/titles/applied_20260930-201117.jsonl`）: 公式表記の更新15件（SEVENTEEN「17 Carat - EP」→「17 CARAT」、X JAPAN「Forever Love」→「Forever Love - Single」など）と、作品名が変わった3件（BOBBY SHANN「Cruel Angel (feat. Yoko Takahashi) - Single」→「Call From The Sky - Single」: Apple側の中身も「Call From The Sky」1曲のみ。Tame Impala & JENNIE「Dracula (Remix)」→「Dracula (with JENNIE)」、aespa「Keychain」の副題）。リンク先のApple Musicと名前を合わせるため
  - 今のまま残した6件（`data/titles/proposals.csv`に残っている）: 揃えると情報が減るもの。NSK「hello, stranger.(feat. Junko Ohashi)」（大橋純子の名前が消える）、Manish Vyas 2件（feat.が消える）、SEVENTEEN「Love&Letter (Repackage Album)」（元のアルバムと区別できなくなる）、テイラー・スウィフトのリミックス（Apple側が「Remix )」と空白の誤り）、私立恵比寿中学「FAMIEN '26 e.p.」（全角「’」になり検索しにくい）
- [x] 後続: 紹介文の収集で曲名がローマ字のため照合できなかった曲を照合し直した（2026-09-30）
  - `collect.py --rematch`を追加: 「記事なし（no_article）」と記録した後に曲名が変わった曲（`issues`に残した照合時の曲名と今の曲名が違う曲）だけを照合し直す。処理済み（done）のアーティストも対象にし、ほかの未照合の曲には手を付けない
  - 結果: 25アーティスト408曲 → **新しい記事83件（95曲）**（氷川きよし33・さだまさし21・AKB48 17・中森明菜2ほか）、発売日不一致10曲、記事なしのまま303曲（今の曲名で記録し直したので次回は調べない）。浜崎あゆみ15曲・AAA 2曲は記事なしのまま
  - 83記事は執筆待ち（sourced）。毎日の定期実行（1日20記事）で順に執筆される。この間、収集は積み残しが20件を切るまで新しい記事を集めない
  - メモ: 「新宝島 (曲)」（別の盤が公開済み）と「ヘビーローテーション (曲)」（別の盤がレビュー待ち）は、同じ記事の紹介文が別のバッチでもう一度書かれる。レビューはバッチ×記事の単位なので既存の分は壊れないが、同じ曲で文面が変わりうる
- [x] 別件: 曲名を変えていない行にも、検索語に「/」をそのまま含むAmazon検索URLが1,255件、Spotify検索URLが1,141件残っていた（以前からの不具合。上のハマりどころ参照）→ 2026-09-30に修正
  - **原因**: 過去の収集スクリプト（`collect_itunes.py`・`collect_all.py`・`collect.py`・`add_spotify.py`）が`requests.utils.quote`（`safe='/'`が既定）で検索語をエンコードしたため、アーティスト名・曲名の「/」がパス区切りとして残っていた
  - **ブラウザでの確認**: Spotifyも「/」のままだと「エラーが発生したようです」になる（2曲で再現）。`%2F`と空白はどちらも正しく検索できる。Amazonと同じく空白に置き換えた。YouTubeは検索語がクエリ文字列なので「/」のままで検索でき、対象外（1,255件そのまま）
  - **方式**: `scripts/titles/fix_search_slash.py`（`apply --dry-run` / `apply --ids` / `apply` / `revert`）。検索語をunquote→「/」を空白→空白を1つにまとめる→`quote(safe="")`。`revert`は反映後に値が変わっていない列だけ戻す（spotify-backfill cronが直リンクに置き換えた列は戻さない）
  - 試験5件（湘南乃風・EXILE / EXILE THE SECOND・DISH//・なにわ男子「勇気100%」・谷村新司）→ ブラウザで検索できることと`revert`を確認 → 全件反映（1,255行、amazon 1,255件・spotify 1,141件）。反映後、PostgRESTの`like`で数えた件数が両列とも0、検索URLの総数（amazon 32,093・spotify 29,542）は変化なし。無作為の3曲（hitomi・DREAMS COME TRUE・Superfly）もAmazon・Spotifyで検索できることを確認
  - 変更前の値: `data/titles/slash_fixed_20260930-134705.jsonl`（試験5件、`revert`済み）、`slash_fixed_20260930-134924.jsonl`（全件）
  - **再発**: 新着cron（`new-releases`）は amazon/spotify/youtube を null で入れ、`spotify-backfill`は直リンクだけを書くので再発しない
  - [x] 古い収集スクリプトも修正（2026-09-30）: `collect.py`・`collect_all.py`・`collect_itunes.py`・`test_collect.py`・`test_collect_v2.py`に`search_query()`（「/」を空白→空白を1つにまとめる→`quote(safe="")`）を追加し、Spotify・Amazon・YouTubeの検索語はすべてこれを通すようにした。git管理外の`add_spotify.py`（メインのチェックアウトにのみある）も同様に修正
    - 確認: 6ファイルとも、今回の修正ログ2,396件の変更前の検索語から作るとDB修正後の値と完全に一致。「/」を含まない既存の検索URL（約9.2万件）は、同じ検索語から作り直すと、連続空白をまとめた273件と既存が半分だけエンコードされていた80件を除いて完全に同じ。`collect_itunes.parse_album`などに「/」入りの曲名を渡して、3サービスとも空白になることを確認
  - メモ: Spotify検索URLのうち80件は検索語が半分だけエンコードされている（空白・日本語が生のまま。例:`Number_i%20GOAT - Single`）。ブラウザが自動でエンコードするので実害はなく、検索語が欠けるのは生の「?」を含む1件（欅坂46「誰がその鐘を鳴らすのか?」、末尾の「?」が落ちるだけ）のみ。未対応

## 進行中: SNS（X・Threads）でのシェアの見栄え改善（2026-09-30〜）

背景: 楽曲詳細のリンクカード画像がジャケット（正方形600×600）のままで、Xでは中央だけ横長に切り取られる。Xのカードは画像とドメインしか出さない（タイトル・説明文は表示されない）ため、画像だけで情報が伝わらない。

**方針（ユーザー決定済み）**: カード画像とシェア文の両方を改善 / シェア文・カード画像では曲名末尾の「 - Single」を消す（「 - EP」は残す、サイト内の表示は変えない）/ リリース日の当日は「🎉 今日で発売から◯年」を先頭に、それ以外の日は今の文面のまま / アーティスト名のハッシュタグを付ける

- [x] `lib/utils.ts`: SNS用の曲名（`socialTitle`、末尾の「 - Single」を除く）と、アーティスト名のハッシュタグ（`artistHashtag`、記号・空白を除く。「&」「feat.」「,」などを含む名前は作らない）
- [x] `app/track/[id]/opengraph-image.tsx`: 1200×630のカード画像を生成（`next/og`）。左にジャケット、右にリリース日・曲名・アーティスト・「◯年前」（今年のリリースは出さない）、右下にロゴとキャッチコピー。日本語フォントはGoogle Fontsから使う文字だけ取得。ジャケットを取得できない曲は♪の代替表示。曲名は長さで4段階の文字サイズ（最大2〜3行）、アーティスト名は最大2行で「…」省略
  - キャッシュ: `next/og`の既定は`immutable, max-age=31536000`（1年間変更なし）で、「◯年前」や曲名の修正が画像に反映されなくなるため、`public, max-age=86400, s-maxage=86400, stale-while-revalidate=86400`に上書き
- [x] `app/track/[id]/page.tsx`: メタデータの画像指定（ジャケット）を外して生成画像に任せた（og:image・twitter:image とも自動で出力される）。og:title・twitter:title は「 - Single」を除く（`<title>`は従来のまま）
- [x] `TrackDetailClient`: シェア文を変更。当日は「🎉 今日で発売から◯年／アーティスト「曲名」／📅 ◯年◯月◯日リリース」、それ以外は従来の形。Xは「#アーティスト #ReleaseTune」、Threadsはタグが1投稿1つまでなのでアーティスト名のタグだけ（作れない名前は#ReleaseTune）
- [x] 確認（2026-09-30）: サカナクション「新宝島」ほか、長い曲名（こえともだち、クリスタルキング）・長いアーティスト名（アニサマ、G-DRAGONほか韓国語名を含む）・今年のリリース（杏里 & 重音テト）・ジャケットなし＋最大行数の組み合わせ（一時的にデータを差し替えて確認、ロゴに重ならない）で画像を確認。シェア文は当日・当日以外・共演名義・今年のリリースをブラウザでボタンを押して確認。本番モード（`next start`）で og:image が `https://releasetune.com/...` になること、キャッシュ指定、存在しないIDは404になることを確認。`tsc`・`next build`通過
  - 開発サーバーが別チャットで動いていたため、`next build`は作業用のコピーで実行した（同じフォルダでビルドすると動作中の開発サーバーの`.next`を壊すため）
- [x] ユーザーレビュー → コミット・デプロイ（2026-09-30）。`TrackDetailClient`・`page.tsx`・`lib/utils.ts`は紹介文表示の未コミット変更と同じファイルなので、SNS改善の変更だけを取り出してコミットした（紹介文表示はレビュー待ちのまま未コミット）
- [x] 本番の確認（2026-09-30、コミット`14425bc`）: サカナクション「新宝島」の楽曲ページで og:title・twitter:title が「新宝島 — サカナクション」、og:image・twitter:image が生成画像になっていること、画像（1200×630）が生成されVercelのCDNにキャッシュされる（2回目は`x-vercel-cache: HIT`）ことを確認
  - 注意: サイトのURL（metadataBase・canonical・シェア文のURL）は`releasetune.com`だが、Vercelのドメイン設定で`www.releasetune.com`へ307リダイレクトされる。カード画像のURLもリダイレクトを1回挟む（X・Metaのクローラーは通常リダイレクトをたどるので動くはずだが、実際の表示で確認する）。どちらを正のドメインにするか揃えるのは別タスク
- [ ] Xの投稿画面やThreadsにURLを貼ってカードの表示を確認（ユーザー）
- メモ: 曲名がローマ字の曲（「Shin Takara Jima」など）は、上の「英語・ローマ字表記の曲名を日本語タイトルに修正」が反映されると画像・シェア文とも日本語になる（カード画像は1日以内に作り直される）
- 次の候補: 日付ページ（`/date/[mmdd]`）・トップページのカード画像（その日の曲のジャケットを並べる等）

## 残タスク（優先順位順）

### 🔴 最優先

- [ ] **Spotify直リンクの一括バックフィル（自動cron稼働中）**
  - **判明した事実（2026-08-17〜18の実測）**: Spotify Web API（Client Credentials flow、Development Mode）は当初想定の「数千件/日」ではなく、**実際は1日あたり約200〜260リクエストで`429 QUOTA_EXCEEDED`**になる。`Retry-After`から逆算すると固定時刻リセットではなく「その日最初の呼び出しから約24時間のローリングウィンドウ」。この制約を前提に運用する方針に変更した
    - 抜本的に速くしたい場合はSpotify Developer Dashboardで「Extended Quota Mode」を申請する必要がある（無料・審査あり・申請はユーザー本人のアカウントで行う必要あり、未着手）
  - **実装**: 手動実行用の`backfill_spotify.py`（ローカルPython、id昇順カーソル方式で中断・再開可）に加えて、`app/api/cron/spotify-backfill/route.ts`で毎日自動実行するcronに移行（2026-08-19実装、`vercel.json`で`0 22 * * *` UTC = JST 7:00）。Spotify共通ロジックは`lib/spotify.ts`に切り出し`new-releases`cronと共有
  - **2026-09-23 検証結果**: デプロイから約35日で直リンク572件→**2,741件**（残り30,435件）。1日平均62件と、設定上限120件よりかなり少ないペースだった
    - **原因判明・修正**: 本番で実測したところ1トラックあたり平均約1.3秒（Spotify検索の実ネットワーク往復。未ヒット時は最大3クエリ試行でさらに長い）。120件処理すると理論上約150秒かかるが`maxDuration`は60秒のため、**Vercelの関数タイムアウトで毎回強制打ち切りになっていた**（クォータ超過ではなくタイムアウトが真のボトルネック）
    - **修正内容**: 固定件数の上限ではなく、**経過時間（45秒）で打ち切る方式に変更**。`SLEEP_MS`を120→80msに短縮。`FETCH_LIMIT`（Supabaseから取得する候補件数）は200に拡大。レスポンスに`elapsedMs`を追加し次回以降の実測がしやすいように
    - **副次的に発見した小さな非効率**: id昇順キューの先頭に恒久的にマッチしない曲（東方神起のライブ盤EPなど）が数件あり、毎日そこに再挑戦してクォータを少し消費している。影響は小さい（1日あたり数リクエスト程度）ため未対応。根本対応には`spotify`列だけでは「検索試行済みだが直リンクなし」を区別できないため、スキーマ変更（試行済みフラグ等の列追加）が必要
  - ローカルPythonスクリプト（`backfill_spotify.py`）は手動での追加実行・動作確認用に残置。使い方は`--dry-run --limit N`でまず確認してから本実行
  - **2026-10-05 誤った直リンクの一括修正**（発端: 星野源「恋」がYU-KA「星月夜」にリンクしていた）
    - **原因（3つ）**: (1) 曲名・アーティストが一致する結果がないと検索結果の先頭を採用していた (2) `Accept-Language`なしで検索していたためアーティスト名がローマ字（Gen Hoshino）で返り、DBの日本語名と一致しなかった (3) Apple Musicの作品名の「 - EP」「 - Single」が付いたまま検索すると結果が0件になる
    - **監査**: 直リンク3,200行（2,813曲）を `open.spotify.com/embed/track/{id}`（`Accept-Language: ja`）で曲名・アーティスト・発売日を取得して照合（Web APIは一括取得が403、1件ずつはクォータ不足のため）。誤り1,370行（曲名・アーティスト・発売日すべて不一致723、曲名だけ一致で別アーティスト151、同アーティストの別の曲で発売日も違う496）。DBがアルバムで同じ発売日の収録曲にリンクしているものは許容として残した
    - **修正**: 誤り1,370行を検索URLに戻した（元の値は`data/spotify/wrong_links_backup_2026-10-05.json`、git管理外）→ 新ロジックでクォータ上限まで再検索して137行に直リンク（無作為20件を目視で確認、すべて正しい曲）。残りは`spotify-backfill` cronが順次埋める
    - **コード**: `lib/spotify.ts`の`searchSpotify`は「曲名が一致」かつ「アーティスト名か発売日が一致」のときだけ採用し、見つからなければ`null`。`Accept-Language: ja`、比較時は空白を無視（「星野 源」）、検索前に「 - EP」「 - Single」を除く。`spotify-backfill`は見つからない曲が先頭に溜まって進まなくなるのを避けるため、取得開始位置を毎回ランダムにずらす。`backfill_spotify.py`も同じロジックに揃えた
    - 根本的には「試行済みだが直リンクなし」を記録する列を追加するのがきれい（スキーマ変更が必要なので未着手）

- [ ] **一括バックフィル完了後、こまめにVercel Usage / Supabase Egressを監視**
  - バックフィル自体がSupabase書き込み・API呼び出しを大量発生させるため、実行中〜直後はコスト面の急増がないか確認する
  - cronでのバックフィルはVercel Function実行時間（1日1回・最大60秒）が追加で発生する点も念のため確認

- [ ] **EP盤・アルバムの Spotify 直リンクの扱いを決める**（2026-10-15 ユーザー指示「要検討」）
  - 今の照合規則（曲名が一致し、アーティスト名か発売日が一致）では、DB が EP・アルバムでも「同じ名前の曲」や「収録曲」の直リンクが入る。再録版（PassCode「Ray - EP」2018 →「Ray [Re:]」2026）や、アルバム → 収録曲（谷村新司のベスト盤 → 「サクラサク」）など
  - 選択肢の例: EP・アルバムは Spotify のアルバムページ（`open.spotify.com/album/`、検索の type=album）にリンクする / 発売年の一致も必須にする / 今のまま
  - 10/5・10/14 の監査では「同じアーティスト・同じ発売日の収録曲」は許容としてきた

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
