"""
Unit test suite for PWTHOR Auto Downloader components (including CookieManager).
"""
import os
import sys
import unittest
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scraper.config import parse_resolution, select_highest_quality
from scraper.log_manager import LogManager
from scraper.download_manager import DownloadManager, sanitize_filename
from scraper.cookie_manager import CookieManager
from scraper.video_finder import VideoFinder


class TestPWTHORPipeline(unittest.TestCase):

    def test_resolution_parser(self):
        w, h = parse_resolution("1280x720")
        self.assertEqual((w, h), (1280, 720))

        w, h = parse_resolution("854x480")
        self.assertEqual((w, h), (854, 480))

        w, h = parse_resolution("640x360")
        self.assertEqual((w, h), (640, 360))

        w, h = parse_resolution("426x240")
        self.assertEqual((w, h), (426, 240))

    def test_highest_quality_selection(self):
        qualities = ["426x240", "640x360", "854x480", "1280x720"]
        chosen = select_highest_quality(qualities)
        self.assertEqual(chosen, "1280x720")

        qualities_no_720 = ["426x240", "640x360", "854x480", "1920x1080"]
        chosen_no_720 = select_highest_quality(qualities_no_720)
        self.assertEqual(chosen_no_720, "1920x1080")

    def test_log_manager_and_resume(self):
        test_log_path = "logs/test_download_log.json"
        if os.path.exists(test_log_path):
            os.remove(test_log_path)

        lm = LogManager(log_path=test_log_path)
        lm.set_session_url("https://example.com/test")
        lm.register_video("Video 01", 0)
        lm.register_video("Video 02", 1)

        self.assertFalse(lm.is_processed_or_started("Video 01"))

        lm.update_status("Video 01", LogManager.STATUS_DOWNLOAD_STARTED, quality="1280x720")
        self.assertTrue(lm.is_processed_or_started("Video 01"))

        summary = lm.get_summary()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["processed"], 1)

        if os.path.exists(test_log_path):
            os.remove(test_log_path)

    def test_filename_sanitization(self):
        title = 'Quantitative Aptitude 09 : Counting Theory / <Part 1>?'
        clean = sanitize_filename(title)
        self.assertNotIn(":", clean)
        self.assertNotIn("/", clean)
        self.assertNotIn("<", clean)
        self.assertNotIn(">", clean)

    def test_right_to_left_sequence(self):
        mock_finder = VideoFinder(page=None)
        videos = [
            {"dom_index": 0, "title": "Video A"},
            {"dom_index": 1, "title": "Video B"},
            {"dom_index": 2, "title": "Video C"},
            {"dom_index": 3, "title": "Video D"}
        ]

        seq = mock_finder.prepare_right_to_left_sequence(videos, start_video_title=None)
        titles = [v["title"] for v in seq]
        self.assertEqual(titles, ["Video D", "Video C", "Video B", "Video A"])

        seq_c = mock_finder.prepare_right_to_left_sequence(videos, start_video_title="Video C")
        titles_c = [v["title"] for v in seq_c]
        self.assertEqual(titles_c, ["Video C", "Video B", "Video A"])

    def test_cookie_manager_persistence_and_expiry(self):
        test_cookie_file = "logs/test_cookie_store.json"
        if os.path.exists(test_cookie_file):
            os.remove(test_cookie_file)

        cm = CookieManager(store_path=test_cookie_file)
        saved = cm.save_cookie("secret_token_123", cookie_name="download_acess", domain="download.pwthor.live")
        self.assertEqual(saved["cookie_value"], "secret_token_123")
        self.assertEqual(saved["cookie_name"], "download_acess")

        # Test loading valid cookie
        loaded = cm.load_cookie_info()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["cookie_value"], "secret_token_123")

        # Test domain extractor
        extracted = cm.extract_domain_from_url("https://download.pwthor.live/lectures")
        self.assertEqual(extracted, "download.pwthor.live")

        # Test 24-hour expiration simulation
        import json
        with open(test_cookie_file, "r") as f:
            data = json.load(f)
        # Set created_at to 25 hours ago
        old_time = datetime.now() - timedelta(hours=25)
        data["created_at"] = old_time.isoformat()
        with open(test_cookie_file, "w") as f:
            json.dump(data, f)

        # Loading expired cookie should return None and delete file
        expired_result = cm.load_cookie_info()
        self.assertIsNone(expired_result)
        self.assertFalse(os.path.exists(test_cookie_file))


if __name__ == "__main__":
    unittest.main()
