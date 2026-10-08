from ytmusicapi import YTMusic
import json

yt = YTMusic("auth.json")

playlist = yt.get_playlist(
    yt.get_library_playlists(limit=100)[2]["playlistId"],
    limit=1
)

track = playlist["tracks"][0]

print("Track:", track["title"])
print("Video ID:", track["videoId"])

song = yt.get_song(
    track["videoId"],
    yt.get_signatureTimestamp()
)

print("\nPlayability:")
print(json.dumps(song.get("playabilityStatus"), indent=2))

print("\nAudio formats:")

for fmt in song.get("streamingData", {}).get("adaptiveFormats", []):
    print(
        "itag:", fmt.get("itag"),
        "| mime:", fmt.get("mimeType"),
        "| bitrate:", fmt.get("bitrate"),
        "| url:", "YES" if fmt.get("url") else "NO",
        "| cipher:", "YES" if fmt.get("signatureCipher") or fmt.get("cipher") else "NO",
    )
