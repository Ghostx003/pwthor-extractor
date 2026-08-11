"""
Cookie Persistence and 24-Hour Expiration Manager for PWTHOR Auto Downloader.
"""
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from scraper.config import COOKIE_STORE_PATH, DEFAULT_COOKIE_NAME, DEFAULT_COOKIE_DOMAIN


class CookieManager:
    """
    Manages loading, saving, auto-deleting 24-hour expired cookies,
    and formatting cookies for Playwright browser context injection.
    """

    def __init__(self, store_path: str = COOKIE_STORE_PATH):
        self.store_path = store_path
        self._ensure_dir()
        self.clean_expired_cookies()

    def _ensure_dir(self):
        dir_name = os.path.dirname(self.store_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

    def load_cookie_info(self) -> Optional[Dict[str, Any]]:
        """
        Loads saved cookie dictionary if valid and less than 24 hours old.
        Auto-deletes the cookie file if it has expired (>= 24 hours).
        """
        if not os.path.exists(self.store_path):
            return None

        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            created_at_str = data.get("created_at")
            if not created_at_str:
                self.delete_cookie_store()
                return None

            created_at = datetime.fromisoformat(created_at_str)
            now = datetime.now()

            # Check if cookie is 24 hours old or more
            if now - created_at >= timedelta(hours=24):
                print("[CookieManager] Cookie is older than 24 hours. Auto-deleting stored cookie file.")
                self.delete_cookie_store()
                return None

            return data

        except Exception as e:
            print(f"[CookieManager] Error loading cookie file: {e}")
            self.delete_cookie_store()
            return None

    def clean_expired_cookies(self):
        """Auto-delete cookie file if expired (> 24 hrs)."""
        self.load_cookie_info()

    def save_cookie(self, value: str, cookie_name: str = DEFAULT_COOKIE_NAME, domain: str = DEFAULT_COOKIE_DOMAIN) -> Dict[str, Any]:
        """
        Saves cookie value with current timestamp and 24-hour expiration details.
        """
        now = datetime.now()
        expires = now + timedelta(hours=24)
        data = {
            "cookie_name": cookie_name,
            "cookie_value": value.strip(),
            "domain": domain,
            "created_at": now.isoformat(),
            "created_at_formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at": expires.isoformat()
        }

        self._ensure_dir()
        temp_path = f"{self.store_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if os.path.exists(self.store_path):
            os.remove(self.store_path)
        os.rename(temp_path, self.store_path)
        return data

    def delete_cookie_store(self):
        """Deletes the stored cookie file from disk."""
        if os.path.exists(self.store_path):
            try:
                os.remove(self.store_path)
            except Exception:
                pass

    @staticmethod
    def extract_domain_from_url(url: str, default: str = DEFAULT_COOKIE_DOMAIN) -> str:
        """Extract domain from URL for cookie injection."""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc or parsed.path
            domain = netloc.split(":")[0]  # Strip port if any
            return domain if domain else default
        except Exception:
            return default
