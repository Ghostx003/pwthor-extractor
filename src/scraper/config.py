"""
Configuration and DOM selectors for PWTHOR Auto Downloader.
"""
import re
from typing import List, Tuple, Optional

# File Paths
LOG_FILE_PATH = "logs/download_log.json"
COOKIE_STORE_PATH = "logs/cookie_store.json"
DOWNLOADS_DIR = "downloads"

# Cookie Configuration
DEFAULT_COOKIE_NAME = "download_access"
ALT_COOKIE_NAME = "download_acess"
DEFAULT_COOKIE_DOMAIN = "download.pwthor.live"

# Website Selectors & Text Markers
LOAD_MORE_BUTTON_XPATH = "//button[contains(normalize-space(), 'Load More')]"
LOAD_MORE_BUTTON_SELECTOR = "button:has-text('Load More')"

VIDEO_ARTICLE_SELECTOR = "article"
VIDEO_TITLE_SELECTOR = "p.line-clamp-2.text-left.text-sm.font-semibold.text-foreground.px-2"
VIDEO_DATE_SELECTOR = "time.font-normal"
VIDEO_DURATION_SELECTOR = "div.p-2.text-xs.text-muted-foreground.flex.justify-between.items-center span.flex.items-center.gap-1"

PLAYBACK_DEVICE_MODAL_TEXT = "Select Playback Device"
ANDROID_WINDOWS_OPTION_XPATH = "//p[contains(normalize-space(), 'Android / Windows')]"

OPTIONS_MENU_BUTTON_SELECTOR = "button:has(svg.lucide-ellipsis-vertical), svg.lucide-ellipsis-vertical"
OPTIONS_MENU_XPATH = "//*[local-name()='svg' and contains(@class, 'lucide-ellipsis-vertical')]/ancestor::button | //*[local-name()='svg' and contains(@class, 'lucide-ellipsis-vertical')]"

DOWNLOAD_OPTION_XPATH = "//span[contains(normalize-space(), 'Download')] | //button[contains(normalize-space(), 'Download')]"

QUALITY_MODAL_SELECTOR = "#quality-modal-content"
QUALITIES_LIST_SELECTOR = "#qualities-list"
QUALITIES_BUTTON_SELECTOR = "#qualities-list button, #quality-modal-content button"

EXECUTE_DOWNLOAD_BUTTON_SELECTOR = "#download-btn"
EXECUTE_DOWNLOAD_BUTTON_XPATH = "//button[@id='download-btn'] | //button[contains(normalize-space(), 'Execute Download')]"

PREFERRED_QUALITY = "1280x720"


def parse_resolution(quality_text: str) -> Tuple[int, int]:
    """
    Extract width and height from quality string (e.g. '1280x720' -> (1280, 720)).
    If no numeric pattern match, return (0, 0).
    """
    match = re.search(r'(\d+)\s*x\s*(\d+)', quality_text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    match_single = re.search(r'(\d+)\s*p', quality_text, re.IGNORECASE)
    if match_single:
        h = int(match_single.group(1))
        w = int(h * 16 / 9)
        return w, h
    return 0, 0


def select_highest_quality(available_qualities: List[str]) -> Optional[str]:
    """
    Given a list of available quality string labels, pick the highest available resolution.
    Prefers 1280x720 when present.
    """
    if not available_qualities:
        return None

    for q in available_qualities:
        if PREFERRED_QUALITY in q:
            return q

    scored = []
    for q in available_qualities:
        w, h = parse_resolution(q)
        scored.append((w * h, q))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else available_qualities[0]
