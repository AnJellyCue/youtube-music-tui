from ytmusicapi import YTMusic
import subprocess

yt = YTMusic("auth.json")

print("Loading first track from Good Vibes...")

playlist = yt.get_playlist(
    yt.get_library_playlists(limit=100)[2]["playlistId"],
    limit=1
)

track = playlist["tracks"][0]

print(f"Playing: {track['title']}")

timestamp = yt.get_signatureTimestamp()
song = yt.get_song(track["videoId"], timestamp)

formats = song["streamingData"]["adaptiveFormats"]

audio = next(
    f for f in formats
    if f.get("mimeType", "").startswith("audio/")
    and f.get("url")
)

subprocess.Popen([
    "mpv",
    "--no-video",
    "--really-quiet",
    audio["url"]
])
