"""
Video Grid Discovery & Right-to-Left Traversal Manager for PWTHOR Auto Downloader.
"""
import asyncio
from typing import List, Dict, Any, Optional
from playwright.async_api import Page
from scraper.config import (
    LOAD_MORE_BUTTON_XPATH,
    VIDEO_ARTICLE_SELECTOR,
    VIDEO_TITLE_SELECTOR,
    VIDEO_DATE_SELECTOR,
    VIDEO_DURATION_SELECTOR
)


class VideoFinder:
    """
    Handles website scrolling, 'Load More' button expansion, DOM parsing of video grid,
    and right-to-left order determination.
    """

    def __init__(self, page: Page):
        self.page = page

    async def load_complete_grid(self, max_scroll_attempts: int = 50) -> int:
        """
        Scrolls down repeatedly and clicks the 'Load More' button until all videos are exposed.
        Returns total number of 'Load More' clicks performed.
        """
        clicks = 0
        previous_article_count = 0
        stuck_counter = 0

        while clicks < max_scroll_attempts:
            # Scroll to bottom to trigger any dynamic lazy loading
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)

            # Check current article count
            articles = await self.page.query_selector_all(VIDEO_ARTICLE_SELECTOR)
            current_count = len(articles)

            # Look for Load More button
            load_more_btn = None
            try:
                # Try XPath first, fallback to text match
                load_more_btn = await self.page.query_selector(f"xpath={LOAD_MORE_BUTTON_XPATH}")
                if not load_more_btn:
                    load_more_btn = await self.page.query_selector("button:has-text('Load More')")
            except Exception:
                pass

            if load_more_btn:
                try:
                    is_visible = await load_more_btn.is_visible()
                    is_enabled = await load_more_btn.is_enabled()
                    if is_visible and is_enabled:
                        # Scroll element into view and click
                        await load_more_btn.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        await load_more_btn.click()
                        clicks += 1
                        await asyncio.sleep(1.5)
                        continue
                except Exception:
                    pass

            # Check if article count stopped changing
            if current_count == previous_article_count and current_count > 0:
                stuck_counter += 1
                if stuck_counter >= 2:
                    # No new articles after 2 attempts and no clickable button
                    break
            else:
                stuck_counter = 0

            previous_article_count = current_count

        return clicks

    async def extract_all_videos(self) -> List[Dict[str, Any]]:
        """
        Extracts video articles from the DOM.
        Returns a list of video objects ordered left-to-right (0 to N-1).
        """
        articles = await self.page.query_selector_all(VIDEO_ARTICLE_SELECTOR)
        videos: List[Dict[str, Any]] = []

        for idx, article in enumerate(articles):
            title = ""
            date_str = ""
            duration_str = ""

            # Extract Title
            title_el = await article.query_selector(VIDEO_TITLE_SELECTOR)
            if not title_el:
                # Fallback to paragraph or img alt
                title_el = await article.query_selector("p")
            if title_el:
                title = (await title_el.inner_text()).strip()
            else:
                img_el = await article.query_selector("img")
                if img_el:
                    alt = await img_el.get_attribute("alt")
                    if alt:
                        title = alt.strip()

            if not title:
                title = f"Untitled Video {idx + 1}"

            # Extract Date
            date_el = await article.query_selector(VIDEO_DATE_SELECTOR)
            if date_el:
                date_str = (await date_el.inner_text()).strip()

            # Extract Duration
            duration_el = await article.query_selector(VIDEO_DURATION_SELECTOR)
            if duration_el:
                duration_str = (await duration_el.inner_text()).strip()

            videos.append({
                "dom_index": idx,
                "title": title,
                "date": date_str,
                "duration": duration_str
            })

        return videos

    def prepare_right_to_left_sequence(
        self,
        videos: List[Dict[str, Any]],
        start_video_title: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Orders videos for right-to-left processing.
        Default: Starts from the right-most video (index N-1) down to index 0.
        If start_video_title is specified: Finds the matching title, starts from there,
        and proceeds right-to-left (towards index 0).
        """
        if not videos:
            return []

        # Standard DOM layout: left-to-right means index 0 is left-most, index N-1 is right-most.
        # Right-to-left sequence is index N-1, N-2, ..., 0 (reversed list).
        reversed_videos = list(reversed(videos))

        if not start_video_title:
            return reversed_videos

        start_video_title = start_video_title.strip()
        
        # If user passed a number (e.g. "16"), treat it as 1-based index from the bottom
        if start_video_title.isdigit():
            target_index = int(start_video_title) - 1
            if 0 <= target_index < len(reversed_videos):
                return reversed_videos[target_index:]
            else:
                return reversed_videos

        # Search for exact or substring match for start_video_title
        start_index = -1
        target_lower = start_video_title.lower()

        for idx, v in enumerate(reversed_videos):
            v_title_lower = v["title"].strip().lower()
            if target_lower == v_title_lower or target_lower in v_title_lower:
                start_index = idx
                break

        if start_index != -1:
            # Slice sequence starting from the requested video onwards in right-to-left order
            return reversed_videos[start_index:]

        # Fallback if title not found
        return reversed_videos

    async def extract_all_notes(self) -> List[Dict[str, Any]]:
        """
        Extracts notes articles from the DOM.
        """
        articles = await self.page.query_selector_all("article, div.bg-background.flex.flex-col")
        notes: List[Dict[str, Any]] = []

        for idx, article in enumerate(articles):
            title = ""
            title_selector = "div.p-4.pb-0.text-sm.font-semibold.text-foreground.mb-2.line-clamp-2"
            title_el = await article.query_selector(title_selector)
            
            if not title_el:
                # Some variations might exist
                title_el = await article.query_selector("div.font-semibold")

            if title_el:
                title = (await title_el.inner_text()).strip()

            if not title:
                title = f"Untitled Note {idx + 1}"

            notes.append({
                "dom_index": idx,
                "title": title,
                "element": article # Storing the element handle to click it later
            })

        return notes

    async def extract_all_dpps(self) -> List[Dict[str, Any]]:
        """
        Extracts DPP articles from the DOM.
        """
        articles = await self.page.query_selector_all("article")
        dpps: List[Dict[str, Any]] = []

        for idx, article in enumerate(articles):
            title = ""
            title_selector = "div.p-4.pb-0.text-sm.font-semibold.text-foreground.mb-2.line-clamp-2"
            title_el = await article.query_selector(title_selector)
            
            if not title_el:
                title_el = await article.query_selector("div.font-semibold")

            if title_el:
                title = (await title_el.inner_text()).strip()

            if not title:
                title = f"Untitled DPP {idx + 1}"

            # Locate the download control inside this article
            download_btn = await article.query_selector("div.cursor-pointer:has(svg.lucide-download)")
            
            dpps.append({
                "dom_index": idx,
                "title": title,
                "element": article,
                "download_btn": download_btn
            })

        return dpps

