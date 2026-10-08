from ytmusicapi import YTMusic

yt = YTMusic("auth.json")

playlist = yt.get_playlist(
    yt.get_library_playlists(limit=100)[2]["playlistId"],
    limit=1
)

track = playlist["tracks"][0]

song = yt.get_song(
    track["videoId"],
    yt.get_signatureTimestamp()
)

for fmt in song.get("streamingData", {}).get("adaptiveFormats", []):
    if fmt.get("mimeType", "").startswith("audio/"):
        print("itag:", fmt.get("itag"))
        print("mime:", fmt.get("mimeType"))
        print("has url:", bool(fmt.get("url")))
        print("has signatureCipher:", bool(fmt.get("signatureCipher")))
        print("cipher keys:", list(fmt.get("signatureCipher", "").split("&")))
        print()
