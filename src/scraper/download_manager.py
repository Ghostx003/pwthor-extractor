"""
Duration-Based Download Mapping Manager for PWTHOR Auto Downloader.

Stores a simple title <-> duration mapping for every triggered download.
This JSON file is later consumed by the post-processing renamer.
"""
import os
import json
import re
from datetime import datetime
from typing import Optional


def sanitize_filename(title: str) -> str:
    """Sanitize title string for safe filesystem usage on Windows."""
    clean = re.sub(r'[\\/:*?"<>|]', '-', title)
    clean = clean.strip().strip('.')
    return clean if clean else "video_download"


class DownloadManager:
    """
    Maintains a real-time JSON mapping of:
        video title  ←→  video duration (H:MM:SS)

    This is the ONLY information the downloader needs to record.
    The renamer script uses FFprobe to find the duration of each
    downloaded file and looks up the matching title from this JSON.
    """

    def __init__(self, log_path: str = "download_mapping.json", downloads_dir: str = "downloads"):
        self.log_path = os.path.abspath(log_path)
        self.downloads_dir = os.path.abspath(downloads_dir)
        self.data = {"videos": []}

        self._ensure_dirs()
        self.load()

    def _ensure_dirs(self):
        os.makedirs(self.downloads_dir, exist_ok=True)
        dir_name = os.path.dirname(self.log_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

    def load(self):
        """Load JSON from disk if it exists."""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict) and "videos" in content:
                        self.data = content
            except Exception as e:
                print(f"[DownloadManager] Warning: Failed to load mapping file ({e}). Starting fresh.")

    def save(self):
        """Atomic write to disk."""
        self._ensure_dirs()
        temp_path = f"{self.log_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.log_path):
                os.remove(self.log_path)
            os.rename(temp_path, self.log_path)
        except Exception as e:
            print(f"[DownloadManager] Error saving mapping file: {e}")

    def register_mapping(self, title: str, duration: str, url: str = None):
        """
        Record a title <-> duration mapping and immediately persist to disk.

        Args:
            title:    Original video title from the grid, e.g. "Time and Work"
            duration: Duration string from the vjs-duration element, e.g. "2:00:26"
            url:      Direct video URL
        """
        # Update if exists, otherwise append
        for entry in self.data["videos"]:
            if entry.get("title") == title:
                entry["duration"] = duration
                if url:
                    entry["url"] = url
                entry["captured_at"] = datetime.now().isoformat()
                self.save()
                return

        new_entry = {
            "title": title,
            "duration": duration,
            "captured_at": datetime.now().isoformat()
        }
        if url:
            new_entry["url"] = url
            
        self.data["videos"].append(new_entry)
        self.save()

    def get_title_by_duration(self, duration: str) -> Optional[str]:
        """Look up the title for a given duration string."""
        for entry in self.data["videos"]:
            if entry.get("duration") == duration:
                return entry.get("title")
        return None
