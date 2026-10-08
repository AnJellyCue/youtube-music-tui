cat > README.md <<'EOF'
# YouTube Music TUI 🎵

A beautiful terminal-based YouTube Music client built with Python and [Textual](https://github.com/Textualize/textual).

Browse your YouTube Music library, search for music, manage playback, and listen through `mpv` — all from a fast, keyboard-friendly TUI.

![YouTube Music TUI](https://raw.githubusercontent.com/AnJellyCue/youtube-music-tui/main/screenshot.png)

## ✨ Features

- 🎵 YouTube Music library browsing
- ❤️ Liked music
- 📚 Playlists
- 💿 Albums
- 🎤 Artists
- 🔎 Music search
- ▶️ Play / pause
- ⏭️ Next / previous track
- 🔊 Volume control
- 🔀 Shuffle
- 🔁 Repeat
- 🎧 Persistent `mpv` audio playback
- 🎨 Rainbow-themed Textual interface
- 📡 Network status
- 🎵 Now Playing display
- ✨ Currently playing track highlighted in the library

## 🖥️ Requirements

- Linux
- Python 3
- `mpv`
- A YouTube Music account
- `ytmusicapi`
- Textual

Install `mpv` on Debian/Ubuntu/Zorin:

```bash
sudo apt install mpv
