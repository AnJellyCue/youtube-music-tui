from ytmusicapi import YTMusic

yt = YTMusic("auth.json")

print("\n=== PLAYLISTS ===\n")

playlists = yt.get_library_playlists(limit=100)

for playlist in playlists:
    print(f"{playlist['title']}  ({playlist.get('count', '?')} songs)")

print("\n=== LIKED SONGS ===\n")

liked = yt.get_liked_songs(limit=25)

print(f"Total reported: {liked.get('trackCount', '?')}\n")

shown = 0

for item in liked.get("tracks", []):
    track = item.get("track")

    if not track:
        continue

    title = track.get("title", "Unknown")
    artists = ", ".join(
        artist.get("name", "Unknown")
        for artist in track.get("artists", [])
    )

    print(f"{title} — {artists}")
    shown += 1

print(f"\nDisplayed: {shown}")
