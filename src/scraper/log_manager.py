"""
Persistent JSON Logging and State Resume Manager for PWTHOR Auto Downloader.
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from scraper.config import LOG_FILE_PATH


class LogManager:
    """
    Manages persistent state in logs/download_log.json.
    Survives program termination and handles seamless session resume.
    """

    # Video Status Constants
    STATUS_DISCOVERED = "DISCOVERED"
    STATUS_QUEUED = "QUEUED"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_DOWNLOAD_STARTED = "DOWNLOAD_STARTED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    def __init__(self, log_path: str = LOG_FILE_PATH):
        self.log_path = log_path
        self.data: Dict[str, Any] = {
            "session_url": "",
            "last_updated": "",
            "videos": {}  # title -> metadata dict
        }
        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        dir_name = os.path.dirname(self.log_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

    def load(self):
        """Load JSON log from disk if it exists, otherwise initialize empty structure."""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict) and "videos" in content:
                        self.data = content
            except Exception as e:
                print(f"[LogManager] Warning: Failed to load log file ({e}). Starting fresh.")

    def save(self):
        """Save current in-memory log data to disk atomically."""
        self._ensure_dir()
        self.data["last_updated"] = datetime.now().isoformat()
        temp_path = f"{self.log_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            if os.path.exists(self.log_path):
                os.remove(self.log_path)
            os.rename(temp_path, self.log_path)
        except Exception as e:
            print(f"[LogManager] Error saving log file: {e}")

    def clear(self):
        """Clears saved video states to allow starting from scratch."""
        self.data["videos"] = {}
        self.save()

    def set_session_url(self, url: str):
        self.data["session_url"] = url
        self.save()

    def register_video(self, title: str, order_index: int) -> Dict[str, Any]:
        """Record a discovered video if not already present."""
        if title not in self.data["videos"]:
            self.data["videos"][title] = {
                "title": title,
                "status": self.STATUS_DISCOVERED,
                "quality": "",
                "order_index": order_index,
                "timestamp": datetime.now().isoformat(),
                "file_path": "",
                "attempts": 0,
                "error": ""
            }
            self.save()
        return self.data["videos"][title]

    def update_status(self, title: str, status: str, quality: str = "", file_path: str = "", error: str = ""):
        """Update video state, quality, file path, or error message."""
        if title not in self.data["videos"]:
            self.data["videos"][title] = {
                "title": title,
                "status": status,
                "quality": quality,
                "order_index": -1,
                "timestamp": datetime.now().isoformat(),
                "file_path": file_path,
                "attempts": 1,
                "error": error
            }
        else:
            v = self.data["videos"][title]
            v["status"] = status
            if quality:
                v["quality"] = quality
            if file_path:
                v["file_path"] = file_path
            if error:
                v["error"] = error
            if status in (self.STATUS_PROCESSING, self.STATUS_FAILED):
                v["attempts"] = v.get("attempts", 0) + 1
            v["timestamp"] = datetime.now().isoformat()

        self.save()

    def is_processed_or_started(self, title: str) -> bool:
        """Return True if download has already started or completed successfully."""
        if title in self.data["videos"]:
            status = self.data["videos"][title].get("status")
            return status in (self.STATUS_DOWNLOAD_STARTED, self.STATUS_COMPLETED)
        return False

    def get_last_processed_video_title(self) -> Optional[str]:
        """Returns the title of the last recorded/processed lecture, if any."""
        videos = self.data.get("videos", {})
        processed = [
            v for v in videos.values()
            if v.get("status") in (self.STATUS_DOWNLOAD_STARTED, self.STATUS_COMPLETED)
        ]
        if not processed:
            return None
        # Sort by timestamp
        processed.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return processed[0].get("title")

    def get_status(self, title: str) -> Optional[str]:
        if title in self.data["videos"]:
            return self.data["videos"][title].get("status")
        return None

    def get_summary(self) -> Dict[str, Any]:
        videos = self.data.get("videos", {})
        total = len(videos)
        completed = sum(1 for v in videos.values() if v.get("status") == self.STATUS_COMPLETED)
        started = sum(1 for v in videos.values() if v.get("status") == self.STATUS_DOWNLOAD_STARTED)
        failed = sum(1 for v in videos.values() if v.get("status") == self.STATUS_FAILED)
        processing = sum(1 for v in videos.values() if v.get("status") == self.STATUS_PROCESSING)
        
        processed = started + completed

        return {
            "total": total,
            "processed": processed,
            "active": started + processing,
            "completed": completed,
            "started": started,
            "failed": failed,
            "session_url": self.data.get("session_url", "")
        }

    def save_captured_link(self, title: str, video_url: str, duration: str, download_url_720p: str):
        """Appends a captured link to link_saver.json"""
        import json
        import os
        
        saver_path = os.path.join(os.path.dirname(self.log_path), "..", "link_saver.json")
        saver_path = os.path.normpath(saver_path)
        
        data = {"videos": []}
        if os.path.exists(saver_path):
            try:
                with open(saver_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict) and "videos" in content:
                        data = content
            except Exception:
                pass
                
        # Update or append
        found = False
        for v in data["videos"]:
            if v.get("title") == title:
                v["video_url"] = video_url
                v["duration"] = duration
                v["download_url_720p"] = download_url_720p
                found = True
                break
                
        if not found:
            data["videos"].append({
                "title": title,
                "video_url": video_url,
                "duration": duration,
                "download_url_720p": download_url_720p
            })
            
        try:
            with open(saver_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[LogManager] Error saving to link_saver.json: {e}")
