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

function normalize(s: string): string {
  return s.normalize("NFKC").toLowerCase().trim();
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
  external_urls?: { spotify?: string };
}

export interface SpotifySearchResult {
  url: string | null;
  // 429（QUOTA_EXCEEDED）を検出した場合、Retry-After秒数が入る。
  // 呼び出し側が「これ以上呼んでも無駄」と判断して早期に打ち切るためのシグナル。
  quotaExceededRetryAfter?: number;
}

export async function searchSpotify(
  token: string,
  title: string,
  artist: string
): Promise<SpotifySearchResult> {
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

      const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });

      if (resp.status === 429) {
        const retryAfter = Number(resp.headers.get("Retry-After") ?? "5");
        return { url: null, quotaExceededRetryAfter: retryAfter };
      }
      if (!resp.ok) continue;

      const data = await resp.json();
      const items: SpotifyTrackItem[] = data?.tracks?.items ?? [];
      if (items.length === 0) continue;

      const titleNorm = normalize(title);
      for (const item of items) {
        const spTitle = normalize(item.name ?? "");
        const spUrl = item.external_urls?.spotify;
        if (
          spUrl &&
          (titleNorm.includes(spTitle) || spTitle.includes(titleNorm)) &&
          artistMatch(item.artists ?? [], artist)
        ) {
          return { url: spUrl };
        }
      }
      const firstUrl = items[0]?.external_urls?.spotify;
      if (firstUrl) return { url: firstUrl };
    } catch {
      continue;
    }
  }
  return { url: null };
}
