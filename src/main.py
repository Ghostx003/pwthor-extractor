"""
PWTHOR Automated Video Downloader — Multi-Video Batch Orchestrator

Workflow per video:
  [1/8] Open video article
  [2/8] Select 'Android / Windows'  (10-second wait)
  [3/8] Open three-dot options menu
  [4/8] Click 'Download' menu item
  [5/8] Wait for quality modal (#quality-modal-content)
  [6/8] Select 1280x720 (or highest available)
  [7/8] Wait for #download-btn (Execute Download)
  [8/8] Click #download-btn  ← DOWNLOAD TRIGGERED HERE

After [8/8]:
  ✅ Open new tab for the next video
  ✅ Downloads continue in the background
  ❌ DO NOT wait for Chrome download confirmation
  ❌ DO NOT close Chrome between videos

After ALL videos:
  ✅ Print completion message
  ✅ Leave Chrome open
  ✅ Wait for Ctrl+C from user
"""
import sys
import asyncio
from typing import List, Optional
from playwright.async_api import Page
from scraper.cli_ui import TerminalUI
from scraper.log_manager import LogManager
from scraper.download_manager import DownloadManager
from scraper.cookie_manager import CookieManager
from scraper.browser import BrowserEngine
from scraper.video_finder import VideoFinder
from scraper.config import DEFAULT_COOKIE_NAME, DEFAULT_COOKIE_DOMAIN


async def process_single_video(
    title: str, duration: str, tab: Page, log_mgr: LogManager, dl_mgr: DownloadManager, 
    ui: TerminalUI, browser: BrowserEngine, video_index: int, total_videos: int,
    direct_url: str = None, lecture_mode: str = "execute"
) -> bool:
    """
    Execute the full 8-step download workflow for a single video on the given tab.

    Returns True if Execute Download was successfully clicked (download triggered)
    or if link was successfully captured in Capture Links mode.
    Returns False on any unrecoverable step failure.

    NEVER closes Chrome. NEVER waits for download completion.
    """
    prefix = f"[{video_index}/{total_videos}]"
    print(f"\n{prefix} ─────────────────────────────────────────")
    print(f"[VIDEO] Opening: {title}")
    print(f"{prefix} ─────────────────────────────────────────")

    log_mgr.update_status(title, LogManager.STATUS_PROCESSING)
    ui.display_live_status(
        log_mgr.get_summary(),
        current_video=title,
        current_quality="1280x720 (Preferred)",
        status=f"[1/8] Opening Video Article..."
    )

    # ------------------------------------------------------------------
    # [1/8] Open video article
    # ------------------------------------------------------------------
    if direct_url:
        print(f"[1/8] Opening direct video URL...")
        try:
            await browser.navigate_to(direct_url, page=tab)
            print("[1/8] Direct video URL opened.")
        except Exception as e:
            log_mgr.update_status(title, LogManager.STATUS_FAILED, error=f"Direct URL navigation failed: {e}")
            print(f"[ERROR] Failed to navigate to direct URL: {e}")
            return False
    else:
        print(f"[1/8] Opening video article...")
        clicked = await browser.click_video_article_by_title(title, page=tab)
        if not clicked:
            log_mgr.update_status(title, LogManager.STATUS_FAILED, error="Article click failed")
            print(f"[ERROR] Failed to click video article '{title}'.")
            return False
        print("[1/8] Video article opened.")
        
    video_url = tab.url

    # Save mapping using the newly acquired video_url (and duration from the article)
    if duration:
        dl_mgr.register_mapping(title=title, duration=duration, url=video_url)

    # ------------------------------------------------------------------
    # [2/8] Select 'Android / Windows'
    # ------------------------------------------------------------------
    print("[2/8] Selecting 'Android / Windows'...")
    ui.display_live_status(
        log_mgr.get_summary(),
        current_video=title,
        status="[2/8] Selecting 'Android / Windows'..."
    )
    device_ok = await browser.select_playback_device(page=tab)
    if not device_ok:
        log_mgr.update_status(title, LogManager.STATUS_FAILED, error="Device selection failed")
        print("[ERROR] Failed to select 'Android / Windows'.")
        return False
    print("[2/8] 'Android / Windows' selected.")

    # ------------------------------------------------------------------
    # [3/8] Open three-dot options menu
    # ------------------------------------------------------------------
    print("[3/8] Opening options menu (three-dot button)...")
    ui.display_live_status(
        log_mgr.get_summary(),
        current_video=title,
        status="[3/8] Opening Options Menu..."
    )
    menu_ok = await browser.open_video_options_menu(page=tab)
    if not menu_ok:
        log_mgr.update_status(title, LogManager.STATUS_FAILED, error="Options menu failed")
        print("[ERROR] Failed to open options menu.")
        return False
    print("[3/8] Options menu opened.")

    # ------------------------------------------------------------------
    # [4/8] Click 'Download' from options menu
    #        Returns the page that will host the quality modal.
    # ------------------------------------------------------------------
    print("[4/8] Clicking 'Download' from options menu...")
    print("      (Steps [5/8]–[8/8] MUST complete before moving to next video.)")
    ui.display_live_status(
        log_mgr.get_summary(),
        current_video=title,
        status="[4/8] Clicking Download Menu Item..."
    )
    dl_ok, quality_page = await browser.select_download_menu_item(page=tab)
    if not dl_ok:
        log_mgr.update_status(title, LogManager.STATUS_FAILED, error="Download option click failed")
        print("[ERROR] Failed to click 'Download' menu item.")
        return False

    # The quality modal is on quality_page (may be a new tab or the same tab)
    dl_page = quality_page or tab

    # ------------------------------------------------------------------
    # [5/8]–[8/8] Quality modal → select 1280x720 → Execute Download
    # ------------------------------------------------------------------
    is_capture_mode = (lecture_mode == "capture")
    
    if is_capture_mode:
        print("\n🚨 CAPTURE MODE: Extracting page URL directly. 🚨")
        ui.display_live_status(
            log_mgr.get_summary(),
            current_video=title,
            status="[CAPTURE] Extracting page URL..."
        )
        
        # Wait a moment for any redirects to settle
        import asyncio
        await asyncio.sleep(2)
        captured_url = dl_page.url
        
        # Save captured link
        log_mgr.save_captured_link(
            title=title,
            video_url=video_url,
            duration=duration if duration else "NOT CAPTURED",
            download_url_720p=captured_url
        )
        print("\n========================================")
        print("LINK CAPTURED")
        print("========================================")
        print(f"\nVideo:\n{title}")
        print(f"\nVideo URL:\n{video_url}")
        print(f"\nDuration:\n{duration if duration else 'NOT CAPTURED'}")
        print(f"\nQuality:\n(URL direct extraction)")
        print(f"\nDownload URL:\n{captured_url}")
        print("\n[OK] Saved to link_saver.json")
        print("[OK] Saved to download_mapping.json")
        print("========================================\n")
        
        log_mgr.update_status(title, LogManager.STATUS_COMPLETED, quality="Captured")
        return True

    print("\n🚨 CRITICAL SECTION: Staying on current video until #download-btn is clicked. 🚨")
    ui.display_live_status(
        log_mgr.get_summary(),
        current_video=title,
        status="[5/8]–[8/8] Quality Modal → 1280x720 → Execute Download..."
    )
        
    chosen_quality, uuid_or_url, extension = await browser.handle_download_pwthor_page(
        page=dl_page,
        max_wait_seconds=120,
        capture_mode=False
    )

    if not chosen_quality or not uuid_or_url:
        log_mgr.update_status(title, LogManager.STATUS_FAILED, error="Quality modal / Download workflow failed")
        print("[ERROR] Quality modal or Execute Download workflow failed.")
        return False

    # ------------------------------------------------------------------
    # DOWNLOAD TRIGGERED — state recorded, mapping already written above.
    # ------------------------------------------------------------------
    log_mgr.update_status(title, LogManager.STATUS_DOWNLOAD_STARTED, quality=chosen_quality)

    ui.display_live_status(
        log_mgr.get_summary(),
        current_video=title,
        current_quality=chosen_quality,
        status="DOWNLOAD_TRIGGERED — moving to next video"
    )

    print(f"[OK] '{title}' — download triggered at quality {chosen_quality}.")
    return True




async def handle_auto_download(download_dir, expected_title, existing_files):
    import os, re, asyncio
    
    def get_new_files():
        try:
            return set(os.listdir(download_dir)) - existing_files
        except Exception:
            return set()
            
    # Check quickly if a new download started (within 3s)
    started = False
    for _ in range(6):
        if get_new_files():
            started = True
            break
        await asyncio.sleep(0.5)
        
    if not started:
        return False
        
    print("[PDF] Automatic download detected! Waiting for it to finish...")
    # Wait for .crdownload to finish (up to 30s)
    for _ in range(60):
        new_files = get_new_files()
        crdownloads = [f for f in new_files if f.endswith('.crdownload') or f.endswith('.tmp')]
        guids = [f for f in new_files if '.' not in f and len(f) >= 32]
        
        if guids and not crdownloads:
            # Download complete! Rename the GUID file
            file_path = os.path.join(download_dir, guids[0])
            clean_filename = re.sub(r'[\\/*?:"<>|]', "", expected_title).strip()
            if not clean_filename.lower().endswith('.pdf'):
                clean_filename += ".pdf"
            clean_filename = clean_filename.replace(" : ", " - ")
            final_path = os.path.join(download_dir, clean_filename)
            
            try:
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(file_path, final_path)
                print(f"[AUTO-DOWNLOAD] Successfully intercepted and renamed to: '{clean_filename}'")
                return True
            except Exception as e:
                print(f"[AUTO-DOWNLOAD] Failed to rename: {e}")
                return False
                
        await asyncio.sleep(0.5)
        
    print("[AUTO-DOWNLOAD] Timed out waiting for automatic download to finish.")
    return False

def fix_pdf_extensions(download_dir):
    import os
    print("\n[CLEANUP] Converting any extensionless files to .pdf...")
    try:
        count = 0
        for root, dirs, files in os.walk(download_dir):
            for file in files:
                if '.' not in file:
                    old_path = os.path.join(root, file)
                    new_path = old_path + ".pdf"
                    try:
                        os.rename(old_path, new_path)
                        count += 1
                        print(f"  -> Renamed '{file}' to '{file}.pdf'")
                    except Exception as e:
                        print(f"  -> Failed to rename '{file}': {e}")
        if count > 0:
            print(f"[CLEANUP] Converted {count} files to PDF.")
        else:
            print("[CLEANUP] No extensionless files found to convert.")
    except Exception as e:
        print(f"[CLEANUP] Error during extension fix: {e}")

async def notes_workflow(browser, target_url, log_mgr, ui, download_folder):
    from scraper.video_finder import VideoFinder
    import asyncio
    
    print("[Notes] Starting Notes workflow...")
    await browser.navigate_to(target_url)
    
    clicked = await browser.click_notes_tab()
    if not clicked:
        ui.console.print("[bold red]Could not click Notes tab.[/bold red]")
        return
        
    finder = VideoFinder(browser.page)
    await finder.load_complete_grid()
    
    notes = await finder.extract_all_notes()
    if not notes:
        ui.console.print("[bold red]No notes found on the page.[/bold red]")
        return
        
    total = len(notes)
    ui.console.print(f"[bold green]Found {total} notes. Processing from bottom-right (right to left, upwards)...[/bold green]")
    
    # Process from bottom-right -> right-to-left -> upwards means just reverse the DOM order.
    # Because DOM order is top-left to bottom-right.
    reversed_notes = list(reversed(notes))
    
    for idx, note in enumerate(reversed_notes, start=1):
        title = note["title"]
        print(f"\n[{idx}/{total}] Processing Note: '{title}'")
        
        try:
            # Click the note to open PDF
            element = note["element"]
            import os
            existing_files = set(os.listdir(download_folder)) if os.path.exists(download_folder) else set()
            
            pdf_page = None
            try:
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                async with browser.context.expect_page(timeout=10000) as page_info:
                    await element.click()
                pdf_page = await page_info.value
                await pdf_page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2.0)
            except asyncio.TimeoutError:
                print(f"[Notes] No new tab opened for note '{title}'. Checking for auto-download...")
                pdf_page = browser.page
            except Exception as e:
                print(f"[ERROR] Failed to click note '{title}': {e}")
                
            success = await handle_auto_download(download_folder, title, existing_files)
            if not success and pdf_page is not None:
                success = await browser.handle_pdf_download(pdf_page, title, download_folder)
            if success:
                print(f"[OK] Downloaded note: {title}")
            else:
                print(f"[ERROR] Failed to download note: {title}")
                
            # Cleanup: close new tabs if any opened, or navigate back
            for p in browser.context.pages:
                if p != browser.page:
                    await p.close()
                    
            # Ensure we are back on the Notes tab grid
            if browser.page.url != target_url:
                await browser.navigate_to(target_url)
                await browser.click_notes_tab()
                await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[CRITICAL ERROR] Note '{title}' completely failed: {e}. Finishing the mission...")
            continue
            
    fix_pdf_extensions(download_folder)
    print("\n[Notes] Workflow completed.")

async def dpp_workflow(browser, target_url, log_mgr, ui, download_folder):
    from scraper.video_finder import VideoFinder
    import asyncio
    
    print("[DPP] Starting DPP workflow...")
    await browser.navigate_to(target_url)
    
    clicked = await browser.click_dpp_pdf_tab()
    if not clicked:
        ui.console.print("[bold red]Could not click DPP PDF tab.[/bold red]")
        return
        
    finder = VideoFinder(browser.page)
    await finder.load_complete_grid()
    
    dpps = await finder.extract_all_dpps()
    if not dpps:
        ui.console.print("[bold red]No DPPs found on the page.[/bold red]")
        return
        
    total = len(dpps)
    ui.console.print(f"[bold green]Found {total} DPPs. Processing from bottom-right (right to left, upwards)...[/bold green]")
    
    reversed_dpps = list(reversed(dpps))
    
    for idx, dpp in enumerate(reversed_dpps, start=1):
        title = dpp["title"]
        download_btn = dpp["download_btn"]
        
        print(f"\n[{idx}/{total}] Processing DPP: '{title}'")
        
        if not download_btn:
            print(f"[ERROR] No download button found for DPP '{title}'.")
            continue
            
        try:
            import os
            existing_files = set(os.listdir(download_folder)) if os.path.exists(download_folder) else set()
            
            pdf_page = None
            try:
                await download_btn.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                # Click the download icon inside the card, which should open PDF viewer
                async with browser.context.expect_page(timeout=10000) as page_info:
                    await download_btn.click()
                pdf_page = await page_info.value
                await pdf_page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2.0)
            except asyncio.TimeoutError:
                print(f"[DPP] No new tab opened for DPP '{title}'. Checking for auto-download...")
                pdf_page = browser.page
            except Exception as e:
                print(f"[ERROR] Failed to click DPP '{title}' or wait for page: {e}")
                
            success = await handle_auto_download(download_folder, title, existing_files)
            if not success and pdf_page is not None:
                success = await browser.handle_pdf_download(pdf_page, title, download_folder)
            
            if success:
                print(f"[OK] Downloaded DPP: {title}")
            else:
                print(f"[ERROR] Failed to download DPP: {title}")
                
        except Exception as e:
            print(f"[ERROR] Failed to process DPP '{title}': {e}")
            
        # Cleanup extra tabs
        try:
            all_pages = browser.context.pages
            for p in all_pages:
                if p != browser.page:
                    await p.close()
            
            if browser.page.url != target_url:
                await browser.navigate_to(target_url)
                await browser.click_dpp_pdf_tab()
                await asyncio.sleep(2.0)
        except Exception as e:
            print(f"[CRITICAL ERROR] DPP cleanup failed: {e}. Finishing the mission...")
            
    fix_pdf_extensions(download_folder)
    print("\n[DPP] Workflow completed.")

async def lecture_workflow(browser, target_url, log_mgr, dl_mgr, ui, cookie_value, download_folder, lecture_mode="execute"):
        # ──────────────────────────────────────────────────────────────
        # Step 5: Navigate to the main grid page and load all videos
        # ──────────────────────────────────────────────────────────────
        last_lecture = log_mgr.get_last_processed_video_title()
        start_video_title, start_from_scratch = ui.prompt_start_video_option(last_lecture_name=last_lecture)
        video_count = ui.prompt_video_count()

        if start_from_scratch:
            ui.console.print("[yellow]Starting from scratch. Clearing previous session state...[/yellow]")
            log_mgr.clear()
            
        await browser.navigate_to(target_url)

        ui.display_live_status(
            log_mgr.get_summary(),
            current_video="Loading Grid...",
            status="Scrolling & Expanding Load More"
        )

        finder = VideoFinder(browser.page)
        await finder.load_complete_grid()

        raw_videos = await finder.extract_all_videos()
        if not raw_videos:
            ui.console.print("\n[bold red]No video articles found on the provided page.[/bold red]")
            return

        for idx, v in enumerate(raw_videos):
            log_mgr.register_video(v["title"], idx)

        # ──────────────────────────────────────────────────────────────
        # Step 6: Build the ordered video sequence (right-to-left,
        #         skipping already-started videos)
        # ──────────────────────────────────────────────────────────────
        sequence = finder.prepare_right_to_left_sequence(raw_videos, start_video_title)
        if not sequence:
            ui.console.print("\n[bold red]No matching video found to process.[/bold red]")
            return

        # Filter out videos that have already been triggered
        pending = [
            v for v in sequence
            if not log_mgr.is_processed_or_started(v["title"])
        ]

        if video_count is not None:
            pending = pending[:video_count]

        total = len(pending)
        if total == 0:
            ui.console.print("\n[bold green]All videos have already been processed. Nothing to do.[/bold green]")
        else:
            ui.console.print(f"\n[bold green]{total} video(s) to process. Starting batch...[/bold green]\n")

        # ──────────────────────────────────────────────────────────────
        # Step 7: Process each video — with optional one-at-a-time mode
        # ──────────────────────────────────────────────────────────────
        # When the user asked for exactly 1 video, after each successful
        # download we pause and ask: "Download next? [1/2]".
        # If YES  → advance pointer, download next video, ask again.
        # If NO   → break out, Chrome stays open, script stays alive.
        one_at_a_time = (video_count == 1)
        video_index = 0
        total = len(pending)

        while video_index < total:
            video = pending[video_index]
            title = video["title"]
            video_num = video_index + 1  # 1-based label

            try:
                # Skip already-processed (in case of concurrent log update)
                if log_mgr.is_processed_or_started(title):
                    print(f"[SKIP] '{title}' already processed. Skipping.")
                    video_index += 1
                    continue

                # Open a fresh tab for this video and navigate to the grid URL
                print(f"\n[NEXT] Opening new tab for video {video_num}/{total}: '{title}'")
                new_tab = await browser.open_new_tab(url=target_url)

                # Re-expand grid on the new tab so the article is clickable
                tab_finder = VideoFinder(new_tab)
                await tab_finder.load_complete_grid()
                
                print("========================================")
                print("VIDEO METADATA CAPTURED")
                print("========================================")
                print(f"\nTitle:\n{title}")
                print(f"\nDuration:\n{video.get('duration', 'NOT CAPTURED')}")
                print("\n========================================")

                success = await process_single_video(
                    browser=browser,
                    tab=new_tab,
                    title=title,
                    duration=video.get("duration", "NOT CAPTURED"),
                    log_mgr=log_mgr,
                    dl_mgr=dl_mgr,
                    ui=ui,
                    video_index=video_num,
                    total_videos=total,
                    lecture_mode=lecture_mode
                )

                if success:
                    print(f"\n[NEXT] Download triggered for '{title}'.")
                    print("[INFO] Download continues in the background.")
                else:
                    print(f"\n========================================")
                    print(f"[VIDEO FAILED]")
                    print(f"========================================")
                    print(f"Video:\n{title}")
                    print(f"Status:\nFAILED")
                    print(f"Chrome:\nSTILL OPEN")
                    print(f"Action:\nRecording failure and continuing.")
                    print(f"========================================")

            except Exception as loop_e:
                print(f"\n========================================")
                print(f"[RECOVERABLE ERROR]")
                print(f"========================================")
                print(f"Video:\n{title}")
                print(f"Error:\n{loop_e}")
                print(f"Chrome:\nSTILL OPEN")
                print(f"Recovery:\nRecording failure and continuing to next video...")
                print(f"========================================")
                log_mgr.update_status(title, LogManager.STATUS_FAILED, error=str(loop_e))

            # ── Tab cleanup ────────────────────────────────────────────
            video_index += 1  # advance pointer BEFORE the prompt

            if video_index < total:
                print("[NEXT] Cleaning up tabs before next video...")
                try:
                    await browser.close_non_download_tabs(keep_url_fragment="download.pwthor.live")
                except Exception as tab_e:
                    print(f"[WARN] Error during tab cleanup: {tab_e}. Chrome remains open.")
                await asyncio.sleep(1.0)

                # ── One-at-a-time mode: pause and ask ─────────────────
                if one_at_a_time:
                    next_title = pending[video_index]["title"]
                    want_next = ui.prompt_download_next(next_video_title=next_title)
                    if not want_next:
                        ui.console.print("\n[bold yellow]Exiting after your choice. Chrome stays open.[/bold yellow]")
                        ui.console.print("[bold yellow]Downloads already triggered will continue in the background.[/bold yellow]\n")
                        break  # stop processing; drop into completion block

        # ──────────────────────────────────────────────────────────────────
        # ALL VIDEOS PROCESSED (or user chose to stop)
        # ──────────────────────────────────────────────────────────────────
        print("\n========================================")
        print("SCRIPT HAS FINISHED ITS PROCESSING JOB")
        print("========================================\n")
        print("All requested download mappings have been captured.")
        print("\nDownloads may still be continuing in Chrome.")
        print("\nChrome will remain OPEN.")
        print("The script will NOT close Chrome.")
        print("\nYou may leave Chrome running until all")
        print("downloads are complete.")
        print("\nPress Ctrl+C only when you intentionally")
        print("want to terminate the script/browser session.")
        print("========================================\n")

        ui.console.print("\n[bold green]========================================[/bold green]")
        ui.console.print("[bold green]     SCRIPT HAS FINISHED ITS JOB      [/bold green]")
        ui.console.print("[bold green]========================================[/bold green]")
        ui.console.print("[bold yellow]Chrome is still open. Press Ctrl+C to exit.[/bold yellow]\n")


async def master_run_session(ui: TerminalUI):
    """
    Multi-video batch download session.

    For each video:
      1. Opens a fresh browser tab.
      2. Runs the full 8-step download workflow.
      3. Triggers the download (clicks #download-btn).
      4. Does NOT wait for Chrome download confirmation.
      5. Closes non-download-pwthor tabs.
      6. Opens a new tab for the next video.

    When all videos are done:
      - Prints a completion message.
      - Leaves Chrome open.
      - Waits for Ctrl+C.
    """
    ui.print_banner()

    # ──────────────────────────────────────────────────────────────────
    # Step 1: URL input
    # ──────────────────────────────────────────────────────────────────
    download_folder = ui.prompt_download_folder()
    target_url = ui.prompt_url()
    mode_choice = ui.prompt_download_mode()

    # ──────────────────────────────────────────────────────────────────
    # Step 2: Cookie setup
    # ──────────────────────────────────────────────────────────────────
    cookie_mgr = CookieManager()
    saved_cookie = cookie_mgr.load_cookie_info()
    cookie_value = None

    if saved_cookie and "cookie_value" in saved_cookie:
        saved_date_str = saved_cookie.get("created_at_formatted", "unknown date/time")
        if mode_choice == "1":
            choice = ui.prompt_cookie_reuse_choice(saved_date_str)
        else:
            choice = "1"
        if choice == "1":
            cookie_value = saved_cookie["cookie_value"]
            ui.console.print(f"[bold green]Using saved cookie '{DEFAULT_COOKIE_NAME}' from {saved_date_str}.[/bold green]")
        else:
            cookie_value = ui.prompt_cookie_value_input(DEFAULT_COOKIE_NAME)
            domain = CookieManager.extract_domain_from_url(target_url)
            cookie_mgr.save_cookie(cookie_value, cookie_name=DEFAULT_COOKIE_NAME, domain=domain)
            ui.console.print("[bold green]New cookie saved for 24 hours.[/bold green]")
    else:
        cookie_value = ui.prompt_cookie_value_input(DEFAULT_COOKIE_NAME)
        domain = CookieManager.extract_domain_from_url(target_url)
        cookie_mgr.save_cookie(cookie_value, cookie_name=DEFAULT_COOKIE_NAME, domain=domain)
        ui.console.print("[bold green]Cookie saved for 24 hours.[/bold green]")

    # ──────────────────────────────────────────────────────────────────
    # Step 3: Log / resume setup
    # ──────────────────────────────────────────────────────────────────
    log_mgr = LogManager()
    log_mgr.set_session_url(target_url)
    dl_mgr = DownloadManager(downloads_dir=download_folder)

    # We rely on asyncio's native Ctrl+C handling to prevent freezing on Windows.
    # The state will be saved in the finally block at the end of this function.

    # ──────────────────────────────────────────────────────────────────
    # Step 4: Browser startup
    # ──────────────────────────────────────────────────────────────────
    browser = BrowserEngine(headless=False)

    try:
        ui.display_live_status(
            log_mgr.get_summary(),
            current_video="Starting Browser & Injecting Cookie...",
            status="Opening Browser"
        )
        await browser.start(download_dir=download_folder)

        if cookie_value:
            target_domain = CookieManager.extract_domain_from_url(target_url)
            await browser.inject_cookie(
                value=cookie_value,
                name=DEFAULT_COOKIE_NAME,
                domain=target_domain,
                target_url=target_url
            )


        # Dispatch to the correct workflow
        if mode_choice == "1":
            lecture_mode = ui.prompt_lecture_mode()
            await lecture_workflow(browser, target_url, log_mgr, dl_mgr, ui, cookie_value, download_folder, lecture_mode=lecture_mode)
        elif mode_choice == "2":
            await notes_workflow(browser, target_url, log_mgr, ui, download_folder)
        elif mode_choice == "3":
            await dpp_workflow(browser, target_url, log_mgr, ui, download_folder)
        else:
            ui.console.print("[red]Invalid mode choice. Exiting.[/red]")
            return

    except (KeyboardInterrupt, asyncio.CancelledError):
        ui.console.print("\n[bold red]Ctrl+C detected. Performing final shutdown...[/bold red]")
    except Exception as general_e:
        print(f"\n========================================")
        print(f"[AUTOMATION ERROR]")
        print(f"========================================")
        print(f"Error: {general_e}")
        print(f"Chrome: STILL OPEN")
        print(f"========================================")
        
    # Keep the script running to allow background downloads to finish
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass # Will drop down to finally block
        
    finally:
        ui.console.print("\n[yellow]Saving current state...[/yellow]")
        ui.console.print("[yellow]Saving download log...[/yellow]")
        ui.console.print("[yellow]Preserving resume information...[/yellow]\n")
        log_mgr.save()
        
        # Only close the browser if we reach here (Ctrl+C / unhandled error / completion)
        await browser.close()
        
        ui.console.print("[bold green]Session safely stopped.[/bold green]")
        ui.console.print("[cyan]Run the program again to resume.[/cyan]\n")



def main():
    """Main entrypoint — runs batch download session until Ctrl+C."""
    ui = TerminalUI()
    try:
        asyncio.run(master_run_session(ui))
    except KeyboardInterrupt:
        ui.console.print("\n[bold green]Session safely stopped by user.[/bold green]")
        sys.exit(0)
    except Exception as e:
        ui.console.print(f"\n[bold red]Unhandled Session Error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
