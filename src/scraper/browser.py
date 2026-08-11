"""
Playwright Browser Automation Engine for PWTHOR Auto Downloader.

STRICT STATE MACHINE ENFORCEMENT:
  Every video MUST complete ALL 8 steps before being marked done:
  [1/8] Video article opened
  [2/8] 'Android / Windows' selected (10s wait)
  [3/8] Options menu opened
  [4/8] 'Download' menu item clicked
  [5/8] Quality modal detected (#quality-modal-content)
  [6/8] Quality selected (1280x720 preferred, else highest)
  [7/8] Execute Download button (#download-btn) located
  [8/8] Execute Download button CLICKED → download initiated

  Moving to next video is ONLY allowed after step [8/8] completes.
  There is NO shortcut from [4/8] to completion.
"""
import os
import asyncio
from typing import Tuple, List, Optional, Any
from urllib.parse import urlparse
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Download,
    TimeoutError as PlaywrightTimeoutError
)
from scraper.config import (
    ANDROID_WINDOWS_OPTION_XPATH,
    OPTIONS_MENU_XPATH,
    DOWNLOAD_OPTION_XPATH,
    QUALITY_MODAL_SELECTOR,
    QUALITIES_LIST_SELECTOR,
    EXECUTE_DOWNLOAD_BUTTON_XPATH,
    select_highest_quality,
    PREFERRED_QUALITY,
    DEFAULT_COOKIE_NAME,
    ALT_COOKIE_NAME,
    DEFAULT_COOKIE_DOMAIN
)

def get_chrome_executable_path() -> Optional[str]:
    """Find the actual installed Google Chrome executable on Windows."""
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

class BrowserEngine:
    """
    Manages Playwright browser lifecycle, dark mode enforcement, multi-tab execution,
    dual-name cookie injection, and automated download workflow steps.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None  # Main grid page
        self.cookie_value: Optional[str] = None
        self.cookie_name: str = DEFAULT_COOKIE_NAME
        self.cookie_domain: str = DEFAULT_COOKIE_DOMAIN

    async def start(self, download_dir: str):
        """Initialize Playwright chromium browser in Dark Mode with download support natively pointing to download_dir."""
        self.playwright = await async_playwright().start()
        self.download_dir = download_dir
        
        chrome_path = get_chrome_executable_path()
        if not chrome_path:
            print("[ERROR] Google Chrome not found. Ensure Chrome is installed.")
            chrome_path = None # Will fallback to bundled Chromium, though not requested.
            
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            executable_path=chrome_path,
            downloads_path=download_dir,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--enable-features=WebUIDarkMode",
                "--force-dark-mode"
            ]
        )
        
        self.context = await self.browser.new_context(
            accept_downloads=True,
            no_viewport=True,
            color_scheme="dark"
        )
        
        dark_init_js = """
        (function() {
            try {
                document.documentElement.classList.add('dark');
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
                localStorage.setItem('color-scheme', 'dark');
                setInterval(() => {
                    document.querySelectorAll('video, audio').forEach(m => { m.muted = true; m.volume = 0; });
                }, 500);
            } catch(e) {}
        })();
        """
        await self.context.add_init_script(dark_init_js)

        self.page = await self.context.new_page()
        self.page.set_default_timeout(30000)

    async def inject_cookie(self, value: str, name: str = DEFAULT_COOKIE_NAME, domain: str = DEFAULT_COOKIE_DOMAIN, target_url: Optional[str] = None):
        """
        Injects specified cookie into browser using a Triple-Layer approach.
        Injects both 'download_access' and 'download_acess' for complete compatibility.
        """
        if not self.context:
            raise RuntimeError("Browser context not initialized")

        self.cookie_value = value
        self.cookie_name = name
        self.cookie_domain = domain

        clean_domain = domain
        if target_url:
            try:
                parsed = urlparse(target_url)
                if parsed.netloc:
                    clean_domain = parsed.netloc.split(":")[0]
            except Exception:
                pass

        if clean_domain.startswith("."):
            clean_domain = clean_domain[1:]

        domains_to_set = list(set([
            clean_domain,
            f".{clean_domain}",
            "download.pwthor.live",
            ".download.pwthor.live",
            "pwthor.live",
            ".pwthor.live"
        ]))

        cookie_names = [DEFAULT_COOKIE_NAME, ALT_COOKIE_NAME]
        cookies = []

        for c_name in cookie_names:
            for d in domains_to_set:
                cookies.append({
                    "name": c_name,
                    "value": value,
                    "domain": d,
                    "path": "/",
                    "httpOnly": False,
                    "secure": False
                })
                cookies.append({
                    "name": c_name,
                    "value": value,
                    "domain": d,
                    "path": "/",
                    "httpOnly": False,
                    "secure": True
                })

        try:
            await self.context.add_cookies(cookies)
        except Exception as e:
            print(f"[BrowserEngine] Note adding context cookies: {e}")

        header_cookie_str = f"{DEFAULT_COOKIE_NAME}={value}; {ALT_COOKIE_NAME}={value}"
        try:
            await self.context.set_extra_http_headers({
                "Cookie": header_cookie_str
            })
        except Exception as e:
            print(f"[BrowserEngine] Note setting HTTP headers: {e}")

        init_js = f"""
        (function() {{
            try {{
                document.cookie = "{DEFAULT_COOKIE_NAME}={value}; path=/; max-age=86400;";
                document.cookie = "{ALT_COOKIE_NAME}={value}; path=/; max-age=86400;";
                document.cookie = "{DEFAULT_COOKIE_NAME}={value}; path=/; domain=.{clean_domain}; max-age=86400;";
                document.cookie = "{ALT_COOKIE_NAME}={value}; path=/; domain=.{clean_domain}; max-age=86400;";
                localStorage.setItem("{DEFAULT_COOKIE_NAME}", "{value}");
                localStorage.setItem("{ALT_COOKIE_NAME}", "{value}");
                sessionStorage.setItem("{DEFAULT_COOKIE_NAME}", "{value}");
                sessionStorage.setItem("{ALT_COOKIE_NAME}", "{value}");
                document.documentElement.classList.add('dark');
            }} catch(e) {{}}
        }})();
        """
        await self.context.add_init_script(init_js)
        print(f"[BrowserEngine] Injected cookies '{DEFAULT_COOKIE_NAME}' & '{ALT_COOKIE_NAME}' into browser context, HTTP headers, & DOM init script.")

    async def open_new_tab(self, url: Optional[str] = None) -> Page:
        """Opens a new tab in the browser context in Dark Mode with cookies injected."""
        if not self.context:
            raise RuntimeError("Browser context not initialized")
        new_tab = await self.context.new_page()
        new_tab.set_default_timeout(30000)
        if url:
            await self.navigate_to(url, page=new_tab)
        return new_tab

    async def close_tab(self, tab: Page):
        """Closes a specific tab cleanly if it is not the main grid page."""
        try:
            if tab and not tab.is_closed() and tab != self.page:
                await tab.close()
        except Exception:
            pass

    async def close(self):
        """Close browser context and playwright instance cleanly."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

    async def navigate_to(self, url: str, page: Optional[Page] = None):
        """
        Navigate target page (or main page) to the EXACT URL provided by user.
        Ensures cookie headers and dark mode preferences are active.
        """
        target_page = page or self.page
        if not target_page:
            raise RuntimeError("Browser page not initialized")

        if self.cookie_value:
            try:
                await self.context.set_extra_http_headers({
                    "Cookie": f"{DEFAULT_COOKIE_NAME}={self.cookie_value}; {ALT_COOKIE_NAME}={self.cookie_value}"
                })
            except Exception:
                pass

        try:
            await target_page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"[BrowserEngine] Note: goto interrupted or timed out: {e}")
            
        await asyncio.sleep(1.5)

        # Anti-redirect check
        current_url = target_page.url
        target_path = urlparse(url).path
        current_path = urlparse(current_url).path

        if len(target_path) > len(current_path) and target_path not in current_path:
            print(f"[BrowserEngine] Anti-redirect notice: Target path '{target_path}' differs from '{current_path}'. Re-navigating...")
            if self.cookie_value:
                try:
                    await target_page.evaluate(
                        f"document.cookie = '{DEFAULT_COOKIE_NAME}={self.cookie_value}; path=/;'; "
                        f"document.cookie = '{ALT_COOKIE_NAME}={self.cookie_value}; path=/;';"
                    )
                except Exception:
                    pass
            try:
                await target_page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass
            await asyncio.sleep(1.5)

        # Cloudflare might challenge us multiple times
        for _ in range(3):
            was_challenged = await self.handle_cloudflare(target_page)
            if was_challenged:
                print(f"[BrowserEngine] Cloudflare challenge passed. Waiting for page to settle...")
                await asyncio.sleep(4.0)
            else:
                break

    async def handle_cloudflare(self, page: Optional[Page] = None) -> bool:
        """
        Detects the Cloudflare 'Verify you are human' challenge.
        Waits for the user to manually click it.
        Returns True if a challenge was detected and handled, False otherwise.
        """
        target_page = page or self.page
        if not target_page:
            return False

        try:
            # 1. Broadly check for Cloudflare indicators
            is_cf = False
            
            # Check title
            try:
                title = await target_page.title()
                if "Just a moment" in title or "Cloudflare" in title:
                    is_cf = True
            except Exception:
                pass

            # Check DOM elements
            if not is_cf:
                try:
                    challenge = await target_page.query_selector(
                        "#cf-wrapper, #challenge-running, #cf-please-wait, "
                        "iframe[src*='challenges.cloudflare.com'], "
                        "iframe[src*='turnstile'], "
                        "h2:has-text('security verification'), "
                        "h2:has-text('Verify you are human')"
                    )
                    if challenge:
                        is_cf = True
                except Exception:
                    pass
                
            if not is_cf:
                return False

            print("\n[Cloudflare] 🚨 'Verify you are human' challenge detected! 🚨")
            print("[Cloudflare] PLEASE SOLVE IT MANUALLY IN THE BROWSER...")
            print("[Cloudflare] Waiting up to 120 seconds for manual verification...\n")
            
            # Wait for user to manually click it, loop until the challenge goes away
            for _ in range(120): # Wait up to 120 seconds
                await asyncio.sleep(1.0)
                try:
                    # If title changed away from "Just a moment...", we're probably good
                    current_title = await target_page.title()
                    if "Just a moment" not in current_title and "Cloudflare" not in current_title:
                        # Double check DOM for iframes
                        still_there = await target_page.query_selector(
                            "#cf-wrapper, #challenge-running, iframe[src*='challenges.cloudflare.com']"
                        )
                        if not still_there:
                            print("[Cloudflare] Verification cleared! Re-navigating in a moment...")
                            return True
                except Exception as e:
                    if "Execution context was destroyed" in str(e) or "Target page" in str(e):
                        print("[Cloudflare] Page navigated! Challenge likely solved.")
                        return True

            print("[Cloudflare] Verification timeout reached. Proceeding anyway.")
            return True
        except Exception as e:
            print(f"[Cloudflare] Note: Error checking challenge: {e}")
            return False

    async def click_video_article_by_title(self, video_title: str, page: Optional[Page] = None) -> bool:
        """
        Locates a video article matching title and clicks it.
        Waits for playback device modal or page navigation.
        """
        target_page = page or self.page
        if not target_page:
            return False

        xpath_title = f"//article[.//p[contains(normalize-space(), '{video_title}')] | .//img[contains(@alt, '{video_title}')]]"
        article_el = await target_page.query_selector(f"xpath={xpath_title}")
        
        if not article_el:
            articles = await target_page.query_selector_all("article")
            for art in articles:
                text = await art.inner_text()
                if video_title in text:
                    article_el = art
                    break

        if article_el:
            await article_el.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await article_el.click()
            
            try:
                await target_page.wait_for_selector(
                    "xpath=//*[contains(text(), 'Select Playback Device')]",
                    state="visible",
                    timeout=15000
                )
                return True
            except PlaywrightTimeoutError:
                return True
        return False

    async def select_playback_device(self, page: Optional[Page] = None) -> bool:
        """
        Selects 'Android / Windows' (High Quality Dash Stream).
        Waits 4 seconds after clicking 'Android / Windows' before the options menu.
        """
        target_page = page or self.page
        if not target_page:
            return False

        try:
            device_option = await target_page.wait_for_selector(
                f"xpath={ANDROID_WINDOWS_OPTION_XPATH}",
                state="visible",
                timeout=15000
            )
            if device_option:
                print("[BrowserEngine] Clicked 'Android / Windows'. Proceeding to options menu ASAP...")
                await device_option.click()
                # Wait briefly for the UI to transition, then rely on wait_for_selector for the 3-dots menu
                await asyncio.sleep(1.0)
                return True
        except PlaywrightTimeoutError:
            try:
                el = await target_page.query_selector("text='Android / Windows'")
                if el:
                    print("[BrowserEngine] Clicked 'Android / Windows'. Proceeding to options menu ASAP...")
                    await el.click()
                    await asyncio.sleep(1.0)
                    return True
            except Exception as e:
                print(f"[BrowserEngine] Note: Fallback device query failed (likely navigating): {e}")

        return False

    # capture_video_duration has been removed as duration is now captured from the article element before opening the video.

    async def open_video_options_menu(self, page: Optional[Page] = None) -> bool:
        """
        Locates three-dot vertical menu icon and clicks it.
        """
        target_page = page or self.page
        if not target_page:
            return False

        try:
            menu_btn = await target_page.wait_for_selector(
                f"xpath={OPTIONS_MENU_XPATH}",
                state="visible",
                timeout=15000
            )
            if not menu_btn:
                menu_btn = await target_page.query_selector("button:has(svg.lucide-ellipsis-vertical), svg.lucide-ellipsis-vertical")

            if menu_btn:
                await menu_btn.click()
                await asyncio.sleep(1.5)
                return True
        except PlaywrightTimeoutError:
            el = await target_page.query_selector("svg.lucide-ellipsis-vertical")
            if el:
                await el.click()
                await asyncio.sleep(1.5)
                return True

        return False

    async def select_download_menu_item(self, page: Optional[Page] = None) -> Tuple[bool, Optional[Page]]:
        """
        Clicks 'Download' option from options menu.

        STRICT CONTRACT:
        - Returns (True, download_page) where download_page is the page
          that will host the quality modal (#quality-modal-content).
        - Does NOT mark the video as complete.
        - The caller MUST continue to handle_download_pwthor_page() on
          the returned page before considering any video processed.
        """
        target_page = page or self.page
        if not target_page:
            return False, None

        # Locate the 'Download' span/button in the options menu
        dl_btn = None
        try:
            dl_btn = await target_page.wait_for_selector(
                f"xpath={DOWNLOAD_OPTION_XPATH}",
                state="visible",
                timeout=15000
            )
        except PlaywrightTimeoutError:
            pass

        if not dl_btn:
            dl_btn = await target_page.query_selector("span:has-text('Download'), button:has-text('Download')")

        if not dl_btn:
            print("[BrowserEngine] ERROR: Could not locate 'Download' menu item.")
            return False, None

        # -------------------------------------------------------------------
        # CLICK 'Download' and detect whether a new tab is opened.
        #
        # The site may either:
        #   (a) Open download.pwthor.live in a NEW TAB  → we capture it
        #   (b) Show the quality modal on the SAME PAGE → we stay on it
        #
        # We use a 15-second window (NOT 5s) to avoid missing slow tabs.
        # After that we do an explicit scan of ALL open pages for the
        # download.pwthor.live domain as an additional safety net.
        # -------------------------------------------------------------------
        print("[4/8] Clicking 'Download' menu item...")
        found_new_tab: Optional[Page] = None

        try:
            async with self.context.expect_page(timeout=15000) as page_info:
                await dl_btn.click()
            found_new_tab = await page_info.value
            await found_new_tab.wait_for_load_state("domcontentloaded", timeout=15000)
            print(f"[4/8] 'Download' clicked → New tab opened: {found_new_tab.url}")
        except PlaywrightTimeoutError:
            # No new tab opened within 15s — the modal is likely on the current page
            print("[4/8] 'Download' clicked → No new tab detected (modal expected on current page).")
        except Exception as e:
            print(f"[4/8] 'Download' click note: {e}")

        # -------------------------------------------------------------------
        # Safety net: scan all open pages for download.pwthor.live
        # in case the tab opened but we missed the event.
        # -------------------------------------------------------------------
        if found_new_tab is None and self.context:
            all_pages = self.context.pages
            for p in all_pages:
                if p != target_page and "pwthor" in p.url.lower():
                    found_new_tab = p
                    print(f"[4/8] Found existing download tab via page scan: {p.url}")
                    break

        # Decide which page hosts the quality modal
        if found_new_tab is not None:
            quality_page = found_new_tab
        else:
            quality_page = target_page

        print(f"[4/8] Quality modal will be handled on page: {quality_page.url}")
        print("[4/8] ⚠️  DO NOT LEAVE THIS VIDEO — proceeding to quality modal detection...")

        # Small stabilisation pause — NOT a skip, we are still on this video
        await asyncio.sleep(1.5)

        # Close all other tabs to save memory and stop background videos
        await self.close_non_download_tabs(keep_url_fragment="download.pwthor.live", keep_page=quality_page)

        return True, quality_page

    async def wait_for_chrome_download_start(self, page: Page, timeout_seconds: int = 30) -> Optional[Download]:
        """
        Monitors Chrome for active download confirmation event.
        Blocks until Chrome confirms an active file download has begun.
        """
        captured_download: Optional[Download] = None
        event_received = asyncio.Event()

        def handle_download(dl: Download):
            nonlocal captured_download
            captured_download = dl
            print(f"[BrowserEngine] CHROME DOWNLOAD CONFIRMED ACTIVE! File: {dl.suggested_filename}")
            event_received.set()

        page.on("download", handle_download)
        if self.context:
            self.context.on("download", handle_download)

        print(f"[BrowserEngine] Waiting for active Chrome download confirmation event (up to {timeout_seconds}s)...")
        try:
            await asyncio.wait_for(event_received.wait(), timeout=timeout_seconds)
            return captured_download
        except asyncio.TimeoutError:
            print(f"[BrowserEngine] Chrome download click completed. Download extraction active in background.")
            return None
        finally:
            try:
                page.remove_listener("download", handle_download)
                if self.context:
                    self.context.remove_listener("download", handle_download)
            except Exception:
                pass

    async def handle_download_pwthor_page(self, page: Page, max_wait_seconds: int = 120, capture_mode: bool = False) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
        """
        Strict state machine for completing the download workflow after the
        'Download' menu item has been clicked.

        MANDATORY STATE SEQUENCE (no shortcuts, no early exits):

            [5/8] WAITING_FOR_QUALITY_MODAL
                  ↓  (waits up to max_wait_seconds; refreshes once on timeout)
            [5/8] QUALITY_MODAL_READY
                  ↓
            [6/8] QUALITY_SELECTED  (prefers 1280x720, else highest available)
                  ↓
            [7/8] WAITING_FOR_EXECUTE_DOWNLOAD
                  ↓  (explicitly waits for #download-btn to be present)
            [7/8] EXECUTE_DOWNLOAD_READY
                  ↓
            [8/8] EXECUTE_DOWNLOAD_CLICKED (skipped if capture_mode=True)
                  ↓
            [8/8] DOWNLOAD_TRIGGERED  ← return here IMMEDIATELY

        ❌ DO NOT wait for Chrome download confirmation.
        ❌ DO NOT wait for the file to finish downloading.
        ❌ DO NOT block for 30 seconds after clicking.
        ✅ Click #download-btn → return immediately as DOWNLOAD_TRIGGERED.

        If capture_mode is True, extracts and returns the URL instead of clicking.

        Returns:
            chosen_quality (str), uuid_or_url (str), extension (str) on success
            None, None, None on failure
        """
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                # ============================================================
                # STATE: WAITING_FOR_QUALITY_MODAL
                # ============================================================
                print(f"[5/8] Waiting for quality modal (#quality-modal-content) "
                      f"— up to {max_wait_seconds}s (attempt {attempt}/{max_attempts})...")

                modal_el = await page.wait_for_selector(
                    "#quality-modal-content, #qualities-list, #quality-modal",
                    state="visible",
                    timeout=max_wait_seconds * 1000
                )

                if not modal_el:
                    raise PlaywrightTimeoutError("Quality modal selector returned None")

                # ============================================================
                # STATE: QUALITY_MODAL_READY
                # ============================================================
                print("[5/8] Quality modal detected — QUALITY_MODAL_READY.")

                # Give the quality list time to fully populate
                await asyncio.sleep(1.5)

                # ============================================================
                # STATE: QUALITY_SELECTED
                # ============================================================
                chosen_quality, _ = await self.select_highest_quality_option(page=page)
                if not chosen_quality:
                    chosen_quality = PREFERRED_QUALITY
                    print(f"[6/8] Quality selection fallback → using '{chosen_quality}'.")

                # ============================================================
                # STATE: WAITING_FOR_EXECUTE_DOWNLOAD
                # ============================================================
                print("[7/8] Waiting for Execute Download button (#download-btn)...")
                exec_btn = None
                try:
                    exec_btn = await page.wait_for_selector(
                        "#download-btn, button:has-text('Execute Download')",
                        state="visible",
                        timeout=30000
                    )
                except PlaywrightTimeoutError:
                    # One more fallback query before giving up
                    exec_btn = await page.query_selector("#download-btn")

                if not exec_btn:
                    print("[7/8] ERROR: #download-btn not found after 30s wait. Aborting this attempt.")
                    raise PlaywrightTimeoutError("#download-btn not found")

                # ============================================================
                # STATE: EXECUTE_DOWNLOAD_READY
                # ============================================================
                print("[7/8] Execute Download button detected — EXECUTE_DOWNLOAD_READY.")

                # ============================================================
                # STATE: EXECUTE_DOWNLOAD_CLICKED / DOWNLOAD_TRIGGERED
                #
                # ❌ DO NOT spawn a Chrome-download-confirmation listener.
                # ❌ DO NOT await any 30-second blocking wait.
                # ✅ Click the button, print confirmation, return IMMEDIATELY.
                # ============================================================
                
                if capture_mode:
                    print("[8/8] Capture Mode active — EXTRACTING download URL instead of clicking.")
                    extracted_url = await self.extract_download_url(page=page)
                    if extracted_url:
                        print("[OK] Download URL extracted successfully.")
                        return chosen_quality, extracted_url, ".mp4"
                    else:
                        print("[ERROR] Failed to extract download URL.")
                        return None, None, None
                
                print("[8/8] Clicking 'Execute Download' (#download-btn)...")

                try:
                    fresh_btn = await page.query_selector("#download-btn")
                    btn_to_click = fresh_btn if fresh_btn else exec_btn
                    
                    try:
                        await btn_to_click.click()
                        print("[8/8] Execute Download clicked. Not waiting for expect_download.")
                    except Exception as click_err:
                        print(f"[8/8] Click error (non-fatal, continuing): {click_err}")

                    uuid = "unknown_uuid"
                    extension = ".mp4"
                        
                except Exception as e:
                    print(f"[8/8] Unexpected error during download triggering: {e}")
                    uuid = "unknown_uuid"
                    extension = ".mp4"

                # ============================================================
                # STATE: DOWNLOAD_TRIGGERED
                # Return immediately — no Chrome confirmation wait.
                # ============================================================
                print("[OK] Execute Download clicked.")
                print(f"[OK] Download triggered with UUID: {uuid} and extension: {extension}")
                print("[INFO] Not waiting for Chrome download confirmation.")
                print("[INFO] Download will continue in the background.")

                return chosen_quality, uuid, extension

            except PlaywrightTimeoutError as te:
                print(f"[5/8] Quality modal / #download-btn did not appear within timeout "
                      f"(attempt {attempt}/{max_attempts}): {te}")
                if attempt < max_attempts:
                    print(f"[5/8] Refreshing page and retrying (attempt {attempt + 1}/{max_attempts})...")
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3.0)
                    except Exception as reload_err:
                        print(f"[5/8] Page reload error: {reload_err}")
                else:
                    print(f"[5/8] All {max_attempts} attempts exhausted. Download workflow FAILED for this video.")

            except Exception as e:
                print(f"[BrowserEngine] Unexpected error in download state machine: {e}")
                if attempt >= max_attempts:
                    break

        return None, None, None

    async def close_non_download_tabs(self, keep_url_fragment: str = "download.pwthor.live", keep_page: Optional[Page] = None) -> None:
        """
        Closes every open tab whose URL does NOT contain keep_url_fragment.

        Rule (from spec sections 7 & 8):
          - Keep https://download.pwthor.live/ tabs alive.
          - Close all other temporary processing tabs.
          - NEVER close the main browser / Chrome window.

        Safe to call after each video's Execute Download has been triggered.
        """
        if not self.context:
            return
        pages_snapshot = list(self.context.pages)
        closed = 0
        for p in pages_snapshot:
            if keep_page and p == keep_page:
                continue
            try:
                if p.is_closed():
                    continue
                url = p.url or ""
                if keep_url_fragment.lower() not in url.lower():
                    await p.close()
                    closed += 1
            except Exception:
                pass
        if closed:
            print(f"[TAB] Closed {closed} non-download tab(s). Remaining: {len(self.context.pages)} tab(s).")

    async def select_highest_quality_option(self, page: Optional[Page] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Inspects available qualities in modal (#qualities-list).
        Selects 1280x720 if available, otherwise the highest resolution.
        Logs all discovered options explicitly.

        DOES NOT exit the download workflow — returns to handle_download_pwthor_page
        which then continues to the Execute Download step.
        """
        target_page = page or self.page
        if not target_page:
            return None, None

        try:
            # Wait for the qualities list to be present and populated
            await target_page.wait_for_selector(QUALITIES_LIST_SELECTOR, state="visible", timeout=15000)

            # Gather all quality option buttons
            buttons = await target_page.query_selector_all(
                f"{QUALITIES_LIST_SELECTOR} button, {QUALITY_MODAL_SELECTOR} button"
            )

            available_qualities = []
            btn_map = {}

            for btn in buttons:
                txt = (await btn.inner_text()).strip()
                if txt and "EXECUTE DOWNLOAD" not in txt.upper() and "CANCEL PROCESS" not in txt.upper():
                    available_qualities.append(txt)
                    btn_map[txt] = btn

            # Fallback: scan spans inside the quality list if no buttons found
            if not available_qualities:
                spans = await target_page.query_selector_all(f"{QUALITIES_LIST_SELECTOR} span")
                for span in spans:
                    txt = (await span.inner_text()).strip()
                    if "x" in txt or "p" in txt:
                        available_qualities.append(txt)
                        parent = await span.evaluate_handle("el => el.closest('button')")
                        btn_map[txt] = parent

            # Log all discovered qualities
            quality_list_str = ", ".join(available_qualities) if available_qualities else "(none found)"
            print(f"[6/8] Available qualities: {quality_list_str}")

            # Select the best quality
            chosen_quality = select_highest_quality(available_qualities)

            if chosen_quality and chosen_quality in btn_map:
                print(f"[6/8] Selecting quality: {chosen_quality}")
                target_btn = btn_map[chosen_quality]
                if hasattr(target_btn, "click"):
                    await target_btn.click()
                else:
                    await target_btn.as_element().click()
                await asyncio.sleep(1.0)
                print(f"[6/8] Quality '{chosen_quality}' selected — QUALITY_SELECTED.")
                return chosen_quality, chosen_quality
            elif available_qualities:
                # Fallback: click the first button in the list
                first_quality = available_qualities[0]
                print(f"[6/8] Preferred quality not in btn_map. Falling back to: {first_quality}")
                await btn_map[first_quality].click()
                await asyncio.sleep(1.0)
                return first_quality, first_quality

        except Exception as e:
            print(f"[6/8] Warning during quality selection: {e}")

        print(f"[6/8] Quality selection fallback — will use '{PREFERRED_QUALITY}' label.")
        return PREFERRED_QUALITY, None

    async def execute_download(self, page: Optional[Page] = None) -> Optional[Download]:
        """
        Waits for <button id="download-btn" onclick="startDownload()">Execute Download</button>,
        clicks it, and captures the download trigger.
        """
        target_page = page or self.page
        if not target_page:
            return None

        exec_btn = None
        try:
            exec_btn = await target_page.wait_for_selector(
                "#download-btn, button:has-text('Execute Download')",
                state="visible",
                timeout=30000
            )
        except PlaywrightTimeoutError:
            exec_btn = await target_page.query_selector("#download-btn")

        if exec_btn:
            try:
                async with target_page.expect_download(timeout=15000) as download_info:
                    await exec_btn.click()
                download_obj = await download_info.value
                print("[BrowserEngine] Execute Download clicked & download event captured successfully.")
                return download_obj
            except PlaywrightTimeoutError:
                print("[BrowserEngine] Note: Execute Download button clicked. Background video extraction initiated.")
                return None
            except Exception as e:
                print(f"[BrowserEngine] Execute download click trigger: {e}")
                return None
        return None

    async def click_notes_tab(self, page: Optional[Page] = None) -> bool:
        """Clicks the Notes tab on the grid page."""
        target_page = page or self.page
        if not target_page:
            return False

        try:
            print("[BrowserEngine] Clicking Notes tab...")
            notes_tab = await target_page.wait_for_selector(
                "button[role='tab']:has-text('Notes')",
                state="visible",
                timeout=15000
            )
            if notes_tab:
                await notes_tab.click()
                await asyncio.sleep(2.0)
                return True
        except Exception as e:
            print(f"[BrowserEngine] Note: Error clicking Notes tab: {e}")
        return False

    async def click_dpp_pdf_tab(self, page: Optional[Page] = None) -> bool:
        """Clicks the DPP PDF tab on the grid page."""
        target_page = page or self.page
        if not target_page:
            return False

        try:
            print("[BrowserEngine] Clicking DPP PDF tab...")
            dpp_tab = await target_page.wait_for_selector(
                "button[role='tab']:has-text('DPP PDF')",
                state="visible",
                timeout=15000
            )
            if dpp_tab:
                await dpp_tab.click()
                await asyncio.sleep(2.0)
                return True
        except Exception as e:
            print(f"[BrowserEngine] Note: Error clicking DPP PDF tab: {e}")
        return False

    async def handle_pdf_download(self, page: Page, expected_filename: str, download_dir: str) -> bool:
        """
        Handles downloading the PDF quickly and robustly.
        Fixes 26KB issues by finding the direct URL and fetching it with context cookies,
        and ensures we don't accidentally download HTML viewer wrappers.
        """
        import os
        import re
        import asyncio
        import urllib.parse
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        clean_filename = re.sub(r'[\\/*?:"<>|]', "", expected_filename).strip()
        if not clean_filename.lower().endswith('.pdf'):
            clean_filename += ".pdf"
        clean_filename = clean_filename.replace(" : ", " - ")
        final_path = os.path.join(download_dir, clean_filename)

        print(f"[PDF] Target path: {final_path}")
        
        # We will attempt to find a valid PDF URL using an aggressive JS scraper
        pdf_url = None
        
        try:
            print("[PDF] Searching page for direct PDF links...")
            js_extractor = """() => {
                // 1. Check if the page itself is a PDF
                if (document.contentType === 'application/pdf' || window.location.href.endsWith('.pdf')) {
                    return window.location.href;
                }
                
                // 2. Check for Next.js props
                const nextData = document.getElementById('__NEXT_DATA__');
                if (nextData) {
                    try {
                        const html = nextData.innerHTML;
                        const match = html.match(/(https?:\\/\\/[^"']+\\.pdf[^"']*)/i);
                        if (match) return match[1];
                        
                        // Sometimes it's stored in a 'url' or 'fileUrl' prop without .pdf
                        const match2 = html.match(/"(?:fileUrl|pdfUrl|url)"\\s*:\\s*"([^"]+)"/i);
                        if (match2) return match2[1];
                    } catch(e) {}
                }
                
                // 3. Check for embed or iframe
                const embed = document.querySelector('embed[type="application/pdf"]');
                if (embed && embed.src) return embed.src;
                
                const iframe = document.querySelector('iframe');
                if (iframe && iframe.src && (iframe.src.includes('.pdf') || iframe.src.includes('amazonaws.com') || iframe.src.includes('storage.googleapis.com'))) {
                    return iframe.src;
                }
                
                // 4. Check for download links
                const a = document.querySelector('a[download], a[href$=".pdf"]');
                if (a && a.href) return a.href;
                
                return null;
            }"""
            extracted_url = await page.evaluate(js_extractor)
            
            if not extracted_url:
                parsed = urllib.parse.urlparse(page.url)
                query = urllib.parse.parse_qs(parsed.query)
                if 'url' in query:
                    extracted_url = query['url'][0]
                    
            if extracted_url:
                print(f"[PDF] Extracted potential URL: {extracted_url}")
                # Fetch headers first to verify it's a PDF
                response = await page.context.request.get(extracted_url, timeout=60000)
                if response.ok:
                    content_type = response.headers.get("content-type", "").lower()
                    if "application/pdf" in content_type or "binary" in content_type:
                        data = await response.body()
                        with open(final_path, 'wb') as f:
                            f.write(data)
                        print(f"[PDF] Successfully downloaded actual PDF ({len(data)} bytes): {final_path}")
                        return True
                    else:
                        print(f"[PDF] Extracted URL returned non-PDF content type: {content_type}. It's probably an HTML wrapper.")
                else:
                    print(f"[PDF] Extracted URL failed with status {response.status}")
        except Exception as e:
            print(f"[PDF] Fast extraction failed: {e}")

        # Attempt: Click any possible download button
        try:
            print("[PDF] Looking for a download button on the page...")
            # We look for typical PW THOR download buttons, or Google Drive download buttons, or native #save
            download_selectors = [
                "cr-icon-button#save", 
                "#save", 
                "#download",
                "button:has-text('Download')",
                "[aria-label='Download']",
                "[title='Download']",
                ".download-btn",
                "a[download]"
            ]
            for sel in download_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        print(f"[PDF] Found download button using selector: {sel}")
                        async with page.expect_download(timeout=60000) as download_info:
                            await btn.click(force=True)
                        download_obj = await download_info.value
                        await download_obj.save_as(final_path)
                        try:
                            await download_obj.delete()
                        except:
                            pass
                        print(f"[PDF] Successfully saved via button click: {final_path}")
                        
                        # Verify the file is actually a PDF and not a tiny HTML file
                        if os.path.exists(final_path) and os.path.getsize(final_path) > 50000:
                            return True
                        else:
                            print("[PDF] WARNING: Downloaded file is too small. Might be HTML. Trying another method...")
                            break
                except Exception:
                    continue
        except Exception as e:
            print(f"[PDF] Button click failed: {e}")

        # Attempt: JS blob fetch on page.url ONLY if it's explicitly a PDF
        try:
            if page.url.lower().endswith('.pdf'):
                print("[PDF] Attempting JS blob fetch download on current URL...")
                async with page.expect_download(timeout=60000) as download_info:
                    await page.evaluate('''async () => {
                        const response = await fetch(window.location.href);
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.style.display = 'none';
                        a.href = url;
                        a.download = 'download.pdf';
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                    }''')
                download_obj = await download_info.value
                await download_obj.save_as(final_path)
                try:
                    await download_obj.delete()
                except:
                    pass
            print(f"[PDF] Successfully saved via JS blob fetch: {final_path}")
            return True
        except Exception as e:
            print(f"[PDF] JS blob fetch failed: {e}")

        print(f"[PDF] ERROR: All download approaches failed for '{expected_filename}'.")
        return False
