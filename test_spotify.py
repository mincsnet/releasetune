"""
test_spotify.py — Spotify APIでリリース日が取れるか確認
"""
import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
))

# 欅坂46をアーティスト検索
results = sp.search(q="欅坂46", type="artist", market="JP", limit=3)
artists = results["artists"]["items"]
for a in artists:
    print(f"アーティスト: {a['name']} (id={a['id']})")

if not artists:
    print("見つかりませんでした")
    exit()

# 先頭アーティストのシングル一覧を取得
artist_id = artists[0]["id"]
albums = sp.artist_albums(
    artist_id,
    album_type="single",
    country="JP",
    limit=10,
)
print(f"\nシングル一覧（先頭10件）:")
for a in albums["items"]:
    print(f"  {a['release_date']}  {a['name']}")