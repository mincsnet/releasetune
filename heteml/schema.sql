-- ReleaseTune の MySQL テーブル定義（ヘテムル MySQL 8.4）
-- Supabase（PostgreSQL）の列をそのまま再現する。
--
-- 照合は utf8mb4_bin にする。MySQL 既定の utf8mb4_0900_ai_ci だと、ひらがなとカタカナ、
-- 全角と半角が同じ文字として比べられ、別のアーティストの曲が混ざるため。
-- 大文字小文字を区別しない比較（Supabase で使っていた ilike）は、クエリ側で LOWER() を明示する。
--
-- 日時（updated_at）は UTC で保存する。接続ごとに time_zone = '+00:00' を設定すること（src/db.php）。

CREATE TABLE IF NOT EXISTS tracks (
  id                VARCHAR(64)   NOT NULL,
  title             TEXT          NOT NULL,
  artist            VARCHAR(1024) NOT NULL,
  release_date      DATE          NOT NULL,
  mmdd              CHAR(5)       NOT NULL,
  jacket            TEXT          NULL,
  note              TEXT          NULL,
  note_verified     TINYINT(1)    NULL DEFAULT 0,
  spotify           TEXT          NULL,
  apple             TEXT          NULL,
  amazon            TEXT          NULL,
  youtube           TEXT          NULL,
  youtube_id        VARCHAR(64)   NULL,
  youtube_verified  TINYINT(1)    NULL DEFAULT 0,
  note_long         TEXT          NULL,
  note_source_title TEXT          NULL,
  note_source_url   TEXT          NULL,
  -- iTunes のジャンル名（アルバム単位。例: J-Pop）。新着は RSS、既存の曲は bin/backfill_genre.php が Lookup API で入れる。
  -- 2026-10-24 に追加。既存の DB には ALTER TABLE tracks ADD COLUMN genre VARCHAR(64) NULL AFTER note_source_url
  genre             VARCHAR(64)   NULL,
  -- 作品（id は Apple の作品 ID）の収録曲数。シングル・EP・アルバムの見分けに使う（src/releases.php の release_kind）。
  -- 新着は cron/new_releases.php、既存の作品は bin/backfill_track_count.php が Lookup API で入れる。
  -- 2026-11-01 に追加。既存の DB には ALTER TABLE tracks ADD COLUMN track_count SMALLINT NULL AFTER genre
  track_count       SMALLINT      NULL,
  -- 試聴に使う曲（作品の収録曲のうち、曲名が作品名と同じもの、なければ1曲目）の Apple の曲 ID と30秒の試聴 URL。
  -- 新着は cron/new_releases.php、既存の作品は bin/backfill_preview.php が Lookup API（entity=song）で入れる。
  -- 2026-11-01 に追加。既存の DB には ALTER TABLE tracks ADD COLUMN apple_track_id BIGINT NULL AFTER track_count, ADD COLUMN preview_url TEXT NULL AFTER apple_track_id, ADD COLUMN spotify_checked_at DATETIME NULL AFTER preview_url
  apple_track_id    BIGINT        NULL,
  preview_url       TEXT          NULL,
  -- Spotify で直リンクを探して見つからなかった日時（UTC）。cron/spotify_backfill.php はこの日から30日は探し直さない
  spotify_checked_at DATETIME     NULL,
  -- アーティストページ（大文字小文字を区別しない一致）用。索引を効かせるため小文字化した値を持つ
  artist_lc         VARCHAR(1024) AS (LOWER(artist)) STORED,
  PRIMARY KEY (id),
  KEY idx_tracks_mmdd (mmdd, release_date),
  KEY idx_tracks_artist (artist(255)),
  KEY idx_tracks_artist_lc (artist_lc(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS track_note_drafts (
  track_id         VARCHAR(64)  NOT NULL,
  status           VARCHAR(32)  NOT NULL,
  wiki_title       VARCHAR(512) NULL,
  wiki_url         TEXT         NULL,
  wiki_revid       BIGINT       NULL,
  source_text      MEDIUMTEXT   NULL,
  note_short       TEXT         NULL,
  note_long        TEXT         NULL,
  facts            JSON         NULL,
  issues           JSON         NOT NULL,
  batch_id         VARCHAR(64)  NULL,
  review_required  TINYINT(1)   NOT NULL DEFAULT 0,
  reviewer_comment TEXT         NULL,
  updated_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (track_id),
  KEY idx_drafts_status (status),
  KEY idx_drafts_batch (batch_id),
  KEY idx_drafts_wiki_title (wiki_title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
