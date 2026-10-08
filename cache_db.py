import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("music_cache.db")


class MusicCache:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self._create_tables()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS collections (
                    kind TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS tracks (
                    video_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def save_collection(self, kind, items):
        data = json.dumps(items, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO collections (kind, data_json, cached_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(kind) DO UPDATE SET
                    data_json = excluded.data_json,
                    cached_at = CURRENT_TIMESTAMP
            """, (kind, data))

    def get_collection(self, kind):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM collections WHERE kind = ?",
                (kind,),
            ).fetchone()
        return json.loads(row["data_json"]) if row else None

    def save_tracks(self, tracks):
        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO tracks (video_id, data_json, cached_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(video_id) DO UPDATE SET
                    data_json = excluded.data_json,
                    cached_at = CURRENT_TIMESTAMP
            """, [
                (track["videoId"], json.dumps(track, ensure_ascii=False))
                for track in tracks
                if track and track.get("videoId")
            ])

    def get_track(self, video_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM tracks WHERE video_id = ?",
                (video_id,),
            ).fetchone()
        return json.loads(row["data_json"]) if row else None
