// Spotify Web API（Client Credentials flow）共通ロジック。
// cron/new-releases（新着のみ）と cron/spotify-backfill（既存曲の一括バックフィル）で共有する。

let tokenCache: { token: string; expiresAt: number } | null = null;

export async function getSpotifyToken(): Promise<string | null> {
  const clientId = process.env.SPOTIFY_CLIENT_ID;
  const clientSecret = process.env.SPOTIFY_CLIENT_SECRET;
  if (!clientId || !clientSecret) return null;

  if (tokenCache && tokenCache.expiresAt > Date.now()) {
    return tokenCache.token;
  }

  try {
    const resp = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization:
          "Basic " + Buffer.from(`${clientId}:${clientSecret}`).toString("base64"),
      },
      body: "grant_type=client_credentials",
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    tokenCache = {
      token: data.access_token,
      expiresAt: Date.now() + (data.expires_in - 60) * 1000,
    };
    return tokenCache.token;
  } catch {
    return null;
  }
}

// 空白も除く（Spotifyの日本語表記は「星野 源」のように姓名の間に空白が入ることがある）
function normalize(s: string): string {
  return s.normalize("NFKC").toLowerCase().replace(/\s+/g, "");
}

function artistMatch(spotifyArtists: { name: string }[], queryArtist: string): boolean {
  const q = normalize(queryArtist);
  return spotifyArtists.some((a) => {
    const n = normalize(a.name ?? "");
    return n.length > 0 && (q.includes(n) || n.includes(q));
  });
}

interface SpotifyTrackItem {
  name: string;
  artists: { name: string }[];
  album?: { release_date?: string };
  external_urls?: { spotify?: string };
}

// 曲名が近いだけでは別アーティストの同名曲を拾うため、アーティスト名か発売日のどちらかの一致を必須にする。
// アーティスト名は Accept-Language: ja で日本語表記を受け取って比べるが、日本語表記が登録されていない
// アーティストもいるため、発売日（Spotifyで日まで分かる場合 YYYY-MM-DD のみ）の一致でも同じ曲とみなす。
function isSameTrack(item: SpotifyTrackItem, title: string, artist: string, releaseDate?: string): boolean {
  const titleNorm = normalize(title);
  const spTitle = normalize(item.name ?? "");
  if (!spTitle || !(titleNorm.includes(spTitle) || spTitle.includes(titleNorm))) return false;
  if (artistMatch(item.artists ?? [], artist)) return true;
  return !!releaseDate && item.album?.release_date === releaseDate;
}

export interface SpotifySearchResult {
  url: string | null;
  // 429（QUOTA_EXCEEDED）を検出した場合、Retry-After秒数が入る。
  // 呼び出し側が「これ以上呼んでも無駄」と判断して早期に打ち切るためのシグナル。
  quotaExceededRetryAfter?: number;
}

// 一致する曲が見つからなければ url: null を返す（検索結果の先頭を代わりに採用すると、
// 無関係な曲の直リンクが入ってしまうため。呼び出し側は検索URLのままにしておく）。
export async function searchSpotify(
  token: string,
  title: string,
  artist: string,
  releaseDate?: string
): Promise<SpotifySearchResult> {
  // Apple Music の作品名に付く「 - Single」「 - EP」が残っていると Spotify の検索結果が0件になる
  title = title.replace(/\s+-\s+(Single|EP)$/i, "");
  const queries = [
    `track:"${title}" artist:"${artist}"`,
    `track:${title} artist:${artist}`,
    `${artist} ${title}`,
  ];

  for (const query of queries) {
    try {
      const url = new URL("https://api.spotify.com/v1/search");
      url.searchParams.set("q", query);
      url.searchParams.set("type", "track");
      url.searchParams.set("market", "JP");
      url.searchParams.set("limit", "10");

      // Accept-Language を付けないとアーティスト名がローマ字表記（星野源 → Gen Hoshino）で返り、
      // DB（Apple Musicの日本語表記）と一致しなくなる
      const resp = await fetch(url, {
        headers: { Authorization: `Bearer ${token}`, "Accept-Language": "ja" },
      });

      if (resp.status === 429) {
        const retryAfter = Number(resp.headers.get("Retry-After") ?? "5");
        return { url: null, quotaExceededRetryAfter: retryAfter };
      }
      if (!resp.ok) continue;

      const data = await resp.json();
      const items: SpotifyTrackItem[] = data?.tracks?.items ?? [];
      if (items.length === 0) continue;

      const match = items.find(
        (item) => item.external_urls?.spotify && isSameTrack(item, title, artist, releaseDate)
      );
      if (match) return { url: match.external_urls!.spotify! };
    } catch {
      continue;
    }
  }
  return { url: null };
}
