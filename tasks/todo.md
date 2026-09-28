# ReleaseTune 開発タスク

最終更新: 2026-09-28

このファイルはプロジェクトの開発状況・残タスクの正本です。新しいチャットセッションでもこのファイルを読めば経緯と優先順位が分かるようにしています。作業を進めたら随時更新してください。

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
