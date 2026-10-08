from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, ListItem, ListView, Static
from ytmusicapi import YTMusic
from cache_db import MusicCache
import psutil
import time
import subprocess
import sys
import socket
import threading
import os


class YouTubeMusicTUI(App):
    TITLE = "YouTube Music"
    SUB_TITLE = "Library"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #sidebar {
        width: 42;
        border: solid #ff4fa3;
    }

    #content {
        width: 1fr;
        border: solid #00bfff;
        padding: 1 2;
    }

    #title {
        color: #ff4fa3;
        text-style: bold;
        margin-bottom: 1;
    }

    #library {
        border: solid #ff9f1c;
    }

    #network {
        height: 7;
        border: solid #9b5de5;
        padding: 0 2;
        color: #c77dff;
    }

    #now-playing {
        height: 6;
        border: solid #ff4fa3;
        padding: 1 2;
        margin-top: 1;
        color: #ff85c8;
    }

    #tracks > ListItem {
        border-left: solid #00f5d4;
    }

    #tracks > ListItem.--highlight {
        background: #5a189a;
        color: #ffffff;
    }

    #tracks ListItem.playing-track {
        background: #9b5de5;
        color: #ffffff;
        border-left: thick solid #ff4fa3;
    }

    #tracks ListItem.playing-track.--highlight {
        background: #9b5de5;
        color: #ffffff;
        border-left: thick solid #ff4fa3;
    }

    ListView {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("p", "play_pause", "Play/Pause"),
        ("space", "play_pause", "Play/Pause"),
        ("s", "stop_playback", "Stop"),
        ("n", "next_track", "Next"),
        ("b", "previous_track", "Previous"),
        ("+", "volume_up", "Vol +"),
        ("-", "volume_down", "Vol -"),
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("escape", "back", "Back"),
    ]

    def __init__(self):
        super().__init__()

        self.yt = YTMusic("auth.json")
        self.cache = MusicCache()
        self.playlists = []
        self.current_tracks = []
        self.track_map = {}
        self.track_counter = 0

        self.albums = {}
        self.artists = {}
        self.ytdlp_process = None
        self.mpv_process = None
        self.current_track = None
        self.mpv_process = None
        self.mpv_socket = "/tmp/youtube-music-tui-mpv.sock"
        self.play_request_id = 0

        # Network monitoring
        self.last_net = None
        self.last_net_time = time.monotonic()

        self.session_downloaded = 0
        self.session_uploaded = 0

        self.net_interface = self.get_default_interface()

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Static("♫  LIBRARY", id="title")

                yield ListView(
                    ListItem(Static("♥  Liked Music"), id="liked"),
                    ListItem(Static("♫  Playlists"), id="playlists"),
                    ListItem(Static("💿  Albums"), id="albums"),
                    ListItem(Static("👤  Artists"), id="artists"),
                    id="library",
                )

                yield Static(
                    "♫  NOW PLAYING\n\n"
                    "Nothing playing",
                    id="now-playing",
                )

            with Vertical(id="content"):
                yield Static(
                    "Loading YouTube Music…",
                    id="content_text"
                )

                yield ListView(id="tracks")

                yield Static(
                    "🌐 NETWORK\n"
                    "↓ Download     --\n"
                    "↑ Upload       --\n"
                    "↓ Session      0 B\n"
                    "↑ Session      0 B\n"
                    "Interface      --",
                    id="network",
                )

        yield Footer()

    def on_mount(self):
        self.query_one("#tracks").display = False

        self.refresh_library()

        self.update_network()
        self.set_interval(1, self.update_network)

    # ---------------------------------------------------------
    # Network
    # ---------------------------------------------------------

    def get_default_interface(self):
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:
                    fields = line.split()

                    if len(fields) >= 2 and fields[1] == "00000000":
                        return fields[0]

        except Exception:
            pass

        return None

    def update_network(self):
        network = self.query_one("#network", Static)

        try:
            counters = psutil.net_io_counters(pernic=True)
            interface = self.net_interface

            if interface not in counters:
                network.update(
                    "🌐 NETWORK\n"
                    "↓ Download     --\n"
                    "↑ Upload       --\n"
                    "↓ Session      0 B\n"
                    "↑ Session      0 B\n"
                    "Interface      --"
                )
                return

            current = counters[interface]
            now = time.monotonic()

            if self.last_net is None:
                self.last_net = current
                self.last_net_time = now

                network.update(
                    "🌐 NETWORK\n"
                    "↓ Download     --\n"
                    "↑ Upload       --\n"
                    "↓ Session      0 B\n"
                    "↑ Session      0 B\n"
                    f"Interface      {interface}"
                )

                return

            elapsed = now - self.last_net_time

            if elapsed <= 0:
                return

            downloaded = (
                current.bytes_recv -
                self.last_net.bytes_recv
            )

            uploaded = (
                current.bytes_sent -
                self.last_net.bytes_sent
            )

            download_rate = downloaded / elapsed
            upload_rate = uploaded / elapsed

            self.session_downloaded += max(0, downloaded)
            self.session_uploaded += max(0, uploaded)

            network.update(
                "🌐 NETWORK\n"
                f"↓ Download     {self.format_bytes(download_rate)}/s\n"
                f"↑ Upload       {self.format_bytes(upload_rate)}/s\n"
                f"↓ Session      {self.format_bytes(self.session_downloaded)}\n"
                f"↑ Session      {self.format_bytes(self.session_uploaded)}\n"
                f"Interface      {interface}"
            )

            self.last_net = current
            self.last_net_time = now

        except Exception as e:
            network.update(
                "🌐 NETWORK\n"
                f"Unable to read network statistics:\n{e}"
            )

    @staticmethod
    def format_bytes(value):
        value = float(value)

        units = ["B", "KB", "MB", "GB", "TB"]

        for unit in units:
            if value < 1024:
                return f"{value:.1f} {unit}"

            value /= 1024

        return f"{value:.1f} PB"

    # ---------------------------------------------------------
    # Library
    # ---------------------------------------------------------

    def refresh_library(self):
        content = self.query_one("#content_text", Static)

        cached = self.cache.get_collection("playlists")
        if cached is not None:
            self.playlists = cached
            content.update(
                "♫  YOUR PLAYLISTS (cached)\n\n"
                f"{len(self.playlists)} playlists available.\n\n"
                "Refreshing from YouTube Music…"
            )

        try:
            fresh = self.yt.get_library_playlists(limit=100)
            self.playlists = fresh
            self.cache.save_collection("playlists", fresh)

            content.update(
                "♫  YOUR PLAYLISTS\n\n"
                f"{len(self.playlists)} playlists loaded.\n\n"
                "Click Playlists, Albums or Artists to browse."
            )

        except Exception as e:
            if cached is not None:
                content.update(
                    "♫  YOUR PLAYLISTS (offline cache)\n\n"
                    f"{len(self.playlists)} cached playlists available.\n\n"
                    f"Refresh failed: {e}"
                )
            else:
                content.update(
                    f"Unable to load library:\n\n{e}"
                )

    def on_list_view_selected(self, event: ListView.Selected):
        self.call_after_refresh(
            self._handle_selected_item,
            event.item.id,
        )

    def _handle_selected_item(self, item_id):

        if item_id == "liked":
            self.show_liked()

        elif item_id == "playlists":
            self.show_playlists()

        elif item_id == "albums":
            self.show_albums()

        elif item_id == "artists":
            self.show_artists()

        elif item_id and item_id.startswith("playlist-"):
            index = int(item_id.split("-")[1])
            self.show_playlist(index)

        elif item_id and item_id.startswith("album-"):
            parts = item_id.split("-")
            index = int(parts[-1])

            if 0 <= index < len(self.library_albums):
                album = self.library_albums[index]

                try:
                    data = self.yt.get_album(
                        album["browseId"]
                    )

                    self.show_media_tracks(
                        data.get("title", "Unknown Album"),
                        data.get("tracks", []),
                        "💿"
                    )

                except Exception as e:
                    self.query_one("#content_text", Static).update(
                        f"Unable to load album:\n\n{e}"
                    )

        elif item_id and item_id.startswith("artist-"):
            parts = item_id.split("-")
            index = int(parts[-1])

            if 0 <= index < len(self.library_artists):
                artist = self.library_artists[index]

                try:
                    data = self.yt.get_artist(
                        artist["browseId"]
                    )

                    songs = data.get("songs", {})
                    artist_tracks = songs.get("results", [])

                    self.show_media_tracks(
                        artist.get("artist", "Unknown Artist"),
                        artist_tracks,
                        "👤"
                    )

                except Exception as e:
                    self.query_one("#content_text", Static).update(
                        f"Unable to load artist:\n\n{e}"
                    )


        elif item_id and item_id.startswith("track-"):
            track = self.track_map.get(item_id)
            if track:
                self.play_track(track)

    def play_track(self, track):
        video_id = track.get("videoId")

        if not video_id:
            self.query_one("#content_text", Static).update(
                "Unable to play track: no video ID."
            )
            return

        self.play_request_id += 1
        request_id = self.play_request_id

        for track_id, mapped_track in self.track_map.items():
            try:
                item = self.query_one(f"#{track_id}")
                item.remove_class("playing-track")
                if mapped_track.get("videoId") == video_id:
                    item.add_class("playing-track")
            except Exception:
                pass

        title = track.get("title", "Unknown")
        artists = ", ".join(
            a.get("name", "Unknown")
            for a in track.get("artists", [])
        )

        self.query_one("#content_text", Static).update(
            f"♫  NOW PLAYING\n\n"
            f"{title}\n"
            f"{artists}\n\n"
            "Resolving audio…"
        )

        self.query_one("#now-playing", Static).update(
            f"♫  NOW PLAYING\n\n"
            f"{title}\n"
            f"{artists}"
        )

        threading.Thread(
            target=self._resolve_and_play,
            args=(track, request_id),
            daemon=True,
        ).start()

    def _resolve_and_play(self, track, request_id):
        video_id = track.get("videoId")
        url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "yt_dlp",
                    "-f",
                    "140",
                    "--get-url",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.strip() or "yt-dlp failed"
                )

            urls = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]

            if not urls:
                raise RuntimeError("yt-dlp returned no audio URL")

            audio_url = urls[0]

            if request_id != self.play_request_id:
                return

            self._ensure_mpv()
            self._send_mpv_command(
                ["loadfile", audio_url, "replace"]
            )

            self.current_track = track

            self.call_from_thread(
                self._show_playing,
                title=track.get("title", "Unknown"),
                artists=", ".join(
                    a.get("name", "Unknown")
                    for a in track.get("artists", [])
                ),
            )

        except Exception as e:
            if request_id == self.play_request_id:
                self.call_from_thread(
                    self._show_playback_error,
                    str(e),
                )

    def _ensure_mpv(self):
        if (
            self.mpv_process
            and self.mpv_process.poll() is None
            and os.path.exists(self.mpv_socket)
        ):
            return

        try:
            os.unlink(self.mpv_socket)
        except FileNotFoundError:
            pass

        self.mpv_process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--idle=yes",
                "--really-quiet",
                f"--input-ipc-server={self.mpv_socket}",
                "--audio-client-name=YouTube Music TUI",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        for _ in range(50):
            if os.path.exists(self.mpv_socket):
                return
            time.sleep(0.1)

        raise RuntimeError(
            "mpv IPC socket did not become available"
        )

    def _send_mpv_command(self, command):
        import json

        message = json.dumps(
            {"command": command}
        ) + "\n"

        with socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        ) as sock:
            sock.settimeout(5)
            sock.connect(self.mpv_socket)
            sock.sendall(message.encode())

    def _show_playing(self, title, artists):
        self.query_one("#content_text", Static).update(
            f"♫  NOW PLAYING\n\n"
            f"{title}\n"
            f"{artists}\n\n"
            "▶ Playing"
        )
        self.query_one("#now-playing", Static).update(
            f"♫  NOW PLAYING\n\n"
            f"{title}\n"
            f"{artists}"
        )

    def _show_playback_error(self, error):
        self.query_one("#content_text", Static).update(
            f"Unable to play track:\n\n{error}"
        )

    def index_tracks(self, tracks):
        for track in tracks:
            if not track:
                continue

            album = track.get("album")
            if album:
                album_name = album.get("name") if isinstance(album, dict) else str(album)

                if album_name:
                    self.albums.setdefault(
                        album_name,
                        []
                    ).append(track)

            for artist in track.get("artists", []):
                artist_name = artist.get("name")

                if artist_name:
                    self.artists.setdefault(
                        artist_name,
                        []
                    ).append(track)

    def show_albums(self):
        content = self.query_one("#content_text", Static)
        tracks = self.query_one("#tracks")

        content.display = False
        tracks.display = True
        tracks.clear()

        try:
            self.library_albums = self.yt.get_library_albums(
                limit=500
            )

            self.library_albums.sort(
                key=lambda album: album.get("title", "").casefold()
            )

            items = []

            for index, album in enumerate(self.library_albums):
                title = album.get("title", "Unknown Album")

                artist_names = ", ".join(
                    artist.get("name", "Unknown")
                    for artist in album.get("artists", [])
                )

                items.append(
                    ListItem(
                        Static(f"{title} — {artist_names}"),
                        id=f"album-{time.time_ns()}-{index}",
                    )
                )

            tracks.mount(*items)

        except Exception as e:
            tracks.clear()
            content.display = True
            content.update(
                f"Unable to load albums:\n\n{e}"
            )


    def show_artists(self):
        content = self.query_one("#content_text", Static)
        tracks = self.query_one("#tracks")

        tracks.clear()
        tracks.display = True
        content.display = True

        try:
            self.library_artists = self.yt.get_library_artists(
                limit=500
            )

            self.library_artists.sort(
                key=lambda artist: artist.get("artist", "").casefold()
            )

            content.update(
                "👤  ARTISTS\n\n"
                f"{len(self.library_artists)} artists loaded.\n"
            )

            for index, artist in enumerate(self.library_artists):
                name = artist.get("artist", "Unknown Artist")

                tracks.append(
                    ListItem(
                        Static(name),
                        id=f"artist-{index}",
                    )
                )

        except Exception as e:
            tracks.clear()
            content.update(
                f"Unable to load artists:\n\n{e}"
            )


    def show_media_tracks(self, name, media_tracks, icon):
        content = self.query_one("#content_text", Static)
        tracks = self.query_one("#tracks")

        content.display = True
        tracks.display = True
        tracks.clear()

        self.current_tracks = list(media_tracks)

        content.update(
            f"{icon}  {name}\n\n"
            f"{len(self.current_tracks)} tracks"
        )

        for track in self.current_tracks:
            title = track.get("title", "Unknown")

            artists = ", ".join(
                a.get("name", "Unknown")
                for a in track.get("artists", [])
            )

            track_id = f"track-{self.track_counter}"
            self.track_counter += 1
            self.track_map[track_id] = track

            tracks.append(
                ListItem(
                    Static(
                        f"{title} — {artists}"
                    ),
                    id=track_id,
                )
            )

    def show_playlists(self):
        content = self.query_one("#content_text", Static)
        tracks = self.query_one("#tracks")

        content.display = True
        tracks.display = True
        tracks.clear()

        content.update(
            "♫  YOUR PLAYLISTS\n\n"
            f"{len(self.playlists)} playlists loaded.\n"
        )

        for index, playlist in enumerate(self.playlists):
            title = playlist.get("title", "Untitled")
            count = playlist.get("count", "?")

            tracks.append(
                ListItem(
                    Static(f"{title}  [{count}]"),
                    id=f"playlist-{index}",
                )
            )

    def show_playlist(self, index):
        playlist = self.playlists[index]
        playlist_id = playlist["playlistId"]
        title = playlist.get("title", "Untitled")

        content = self.query_one("#content_text", Static)
        tracks = self.query_one("#tracks")

        content.display = True
        tracks.display = True
        tracks.clear()

        content.update(
            f"♫  {title}\n\n"
            "Loading tracks…"
        )

        try:
            data = self.yt.get_playlist(
                playlist_id,
                limit=5000
            )

            content.update(
                f"♫  {title}\n\n"
                f"{len(data.get('tracks', []))} tracks"
            )

            self.index_tracks(data.get("tracks", []))
            self.current_tracks = []

            for track in data.get("tracks", []):
                if not track:
                    continue

                self.current_tracks.append(track)

                track_id = f"track-{self.track_counter}"
                self.track_counter += 1
                self.track_map[track_id] = track

                track_title = track.get(
                    "title",
                    "Unknown"
                )

                artists = ", ".join(
                    a.get("name", "Unknown")
                    for a in track.get("artists", [])
                )

                tracks.append(
                    ListItem(
                        Static(
                            f"{track_title} — {artists}"
                        ),
                        id=track_id,
                    )
                )

        except Exception as e:
            content.update(
                f"♫  {title}\n\n"
                f"Unable to load playlist:\n\n{e}"
            )

    def show_liked(self):
        content = self.query_one(
            "#content_text",
            Static
        )

        tracks = self.query_one("#tracks")

        content.display = True
        tracks.display = True
        tracks.clear()

        try:
            liked = self.yt.get_liked_songs(
                limit=5000
            )

            content.update(
                "♥  LIKED MUSIC\n\n"
                f"Total reported: "
                f"{liked.get('trackCount', '?')}"
            )

            for item in liked.get("tracks", []):
                track = item.get("track")

                if not track:
                    continue

                title = track.get(
                    "title",
                    "Unknown"
                )

                artists = ", ".join(
                    a.get("name", "Unknown")
                    for a in track.get("artists", [])
                )

                tracks.append(
                    ListItem(
                        Static(
                            f"{title} — {artists}"
                        )
                    )
                )

        except Exception as e:
            content.update(
                "♥  LIKED MUSIC\n\n"
                f"Unable to load liked music:\n\n{e}"
            )

    def _safe_mpv_command(self, command):
        try:
            self._send_mpv_command(command)
            return True
        except Exception:
            return False

    def action_play_pause(self):
        if self._safe_mpv_command(
            ["cycle", "pause"]
        ):
            self.query_one("#content_text", Static).update(
                "♫  PLAYBACK\n\n"
                "▶ / ⏸  Play / Pause"
            )

    def action_stop_playback(self):
        if self._safe_mpv_command(
            ["stop"]
        ):
            self.query_one("#content_text", Static).update(
                "♫  PLAYBACK\n\n"
                "⏹ Stopped"
            )

    def action_next_track(self):
        if not self.current_tracks:
            return

        try:
            current_index = self.current_tracks.index(
                self.current_track
            )
        except ValueError:
            current_index = -1

        next_index = current_index + 1

        if next_index >= len(self.current_tracks):
            next_index = 0

        self.play_track(
            self.current_tracks[next_index]
        )

    def action_previous_track(self):
        if not self.current_tracks:
            return

        try:
            current_index = self.current_tracks.index(
                self.current_track
            )
        except ValueError:
            current_index = 0

        previous_index = current_index - 1

        if previous_index < 0:
            previous_index = len(self.current_tracks) - 1

        self.play_track(
            self.current_tracks[previous_index]
        )

    def action_volume_up(self):
        self._safe_mpv_command(
            ["add", "volume", 5]
        )

    def action_volume_down(self):
        self._safe_mpv_command(
            ["add", "volume", -5]
        )

    def action_refresh(self):
        self.refresh_library()

    def action_back(self):
        self.show_playlists()


    def on_unmount(self):
        self.play_request_id += 1

        if (
            self.mpv_process
            and self.mpv_process.poll() is None
        ):
            self.mpv_process.terminate()

            try:
                self.mpv_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.mpv_process.kill()

        try:
            os.unlink(self.mpv_socket)
        except FileNotFoundError:
            pass

if __name__ == "__main__":
    YouTubeMusicTUI().run()
