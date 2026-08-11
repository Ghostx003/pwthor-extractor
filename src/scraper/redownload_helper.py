import os
import sys
import json
import asyncio

def run_comparison_and_download(folder: str, mapping_path: str):
    # Load mapping
    if not os.path.exists(mapping_path):
        print(f"[ERROR] Mapping file not found: {mapping_path}")
        return
        
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read {mapping_path}: {e}")
        return
        
    videos = data.get("videos", [])
    
    # Check folder for present titles (assuming they are renamed)
    all_files = os.listdir(folder)
    present_titles = set()
    
    # We must import sanitize_filename from rename_downloads
    import rename_downloads
    
    for f in all_files:
        if f.lower().endswith(".mp4") or f.lower().endswith(".ts"):
            name, _ = os.path.splitext(f)
            present_titles.add(name.lower())
            
    missing_videos = []
    for v in videos:
        title = v.get("title", "")
        safe_title = rename_downloads.sanitize_filename(title).lower()
        if safe_title not in present_titles:
            missing_videos.append(v)
            
    # Print comparison report
    print("\n========================================")
    print("VIDEO DOWNLOAD COMPARISON")
    print("========================================")
    print(f"Mapping entries:\n{len(videos)}\n")
    print(f"Videos found:\n{len(videos) - len(missing_videos)}\n")
    print(f"Videos missing:\n{len(missing_videos)}\n")
    print("========================================")
    
    if not missing_videos:
        print("\n========================================")
        print("COMPARISON COMPLETE")
        print("========================================")
        print("\nAll mapped videos are present")
        print("in the selected folder.\n")
        print("Missing videos:\n0\n")
        print("Nothing needs to be downloaded.")
        print("========================================\n")
        return
        
    print("\nMISSING VIDEOS:")
    print("========================================")
    for i, mv in enumerate(missing_videos, start=1):
        print(f"[{i}] {mv.get('title', 'Unknown')}")
        print(f"    Duration: {mv.get('duration', 'Unknown')}")
        print(f"    URL: {mv.get('url', 'NOT AVAILABLE')}\n")
    print("========================================\n")
    
    print("Enter the number to redownload or type 'all' to download all missing vids.")
    print("Press ENTER to skip downloading.")
    
    choice = input("> ").strip().lower()
    
    if not choice:
        return
        
    # parse selection
    selected_indices = []
    if choice == "all":
        selected_indices = list(range(1, len(missing_videos) + 1))
    else:
        for p in choice.split(","):
            p = p.strip()
            if not p:
                continue
            if p.isdigit():
                idx = int(p)
                if 1 <= idx <= len(missing_videos):
                    selected_indices.append(idx)
                else:
                    print(f"[ERROR] Video {idx} does not exist in the missing-video list.")
            else:
                print("[ERROR] Invalid selection.\nPlease enter video numbers or 'all'")
                return
            
    if not selected_indices:
        return
        
    # De-duplicate while preserving order
    selected_indices = list(dict.fromkeys(selected_indices))
    
    print(f"\n========================================")
    print("MISSING VIDEO DOWNLOADS")
    print("========================================")
    print(f"\nSelected:\n{len(selected_indices)}\n")
    
    to_download = [missing_videos[i-1] for i in selected_indices]
    
    # Check if they have URLs
    valid_downloads = []
    for mv in to_download:
        if not mv.get("url"):
            print(f"[WARNING]")
            print(f"{mv.get('title')} is missing from the folder,")
            print("but no URL is stored in download_mapping.json.")
            print("This video cannot be automatically re-downloaded.\n")
        else:
            valid_downloads.append(mv)
            
    if not valid_downloads:
        return
        
    print(f"Downloads triggered:\n{len(valid_downloads)}\n")
    print("Chrome/browser downloads are continuing")
    print("in the background.\n")
    print("The program does not wait for completion.")
    print("========================================\n")
    
    asyncio.run(run_missing_downloads(folder, valid_downloads))

async def run_missing_downloads(folder: str, valid_downloads: list):
    # Import main.py stuff and trigger downloads
    # Add root folder to sys path to import main
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    from main import process_single_video
    from scraper.browser import BrowserEngine
    from scraper.cli_ui import TerminalUI
    from scraper.cookie_manager import CookieManager, DEFAULT_COOKIE_NAME
    from scraper.download_manager import DownloadManager
    from scraper.log_manager import LogManager
    
    ui = TerminalUI()
    log_mgr = LogManager()
    dl_mgr = DownloadManager()
    cookie_mgr = CookieManager()
    saved_cookie = cookie_mgr.load_cookie_info()
    cookie_value = None

    if saved_cookie and "cookie_value" in saved_cookie:
        saved_date_str = saved_cookie.get("created_at_formatted", "unknown date/time")
        choice = ui.prompt_cookie_reuse_choice(saved_date_str)
        if choice == "1":
            cookie_value = saved_cookie["cookie_value"]
            ui.console.print(f"[bold green]Using saved cookie '{DEFAULT_COOKIE_NAME}' from {saved_date_str}.[/bold green]")
        else:
            cookie_value = ui.prompt_cookie_value_input(DEFAULT_COOKIE_NAME)
            # Just default domain for saving if no URL is available yet
            target_domain = CookieManager.extract_domain_from_url(valid_downloads[0].get("url", ""))
            cookie_mgr.save_cookie(cookie_value, cookie_name=DEFAULT_COOKIE_NAME, domain=target_domain)
            ui.console.print("[bold green]New cookie saved for 24 hours.[/bold green]")
    else:
        cookie_value = ui.prompt_cookie_value_input(DEFAULT_COOKIE_NAME)
        target_domain = CookieManager.extract_domain_from_url(valid_downloads[0].get("url", ""))
        cookie_mgr.save_cookie(cookie_value, cookie_name=DEFAULT_COOKIE_NAME, domain=target_domain)
        ui.console.print("[bold green]Cookie saved for 24 hours.[/bold green]")
        
    browser = BrowserEngine(headless=False)
    browser.cookie_value = cookie_value
    await browser.start(download_dir=folder)
    
    if cookie_value and valid_downloads:
        first_url = valid_downloads[0].get("url")
        target_domain = CookieManager.extract_domain_from_url(first_url)
        await browser.inject_cookie(
            value=cookie_value,
            name=DEFAULT_COOKIE_NAME,
            domain=target_domain,
            target_url=first_url
        )
    
    for i, mv in enumerate(valid_downloads, start=1):
        title = mv.get("title")
        url = mv.get("url")
        print(f"\n[{i}/{len(valid_downloads)}] Starting:\n{title}")
        print(f"\nOpening:\n{url}\n")
        print("Running existing download workflow...\n")
        
        # create new tab
        new_tab = await browser.open_new_tab(url="about:blank")
        
        success = await process_single_video(
            title=title,
            tab=new_tab,
            log_mgr=log_mgr,
            dl_mgr=dl_mgr,
            ui=ui,
            browser=browser,
            video_index=i,
            total_videos=len(valid_downloads),
            direct_url=url
        )
        if success:
            print(f"[OK] Execute Download clicked.")
            print(f"[INFO] Moving to next missing video.")
            # Update status to DOWNLOAD_TRIGGERED (user request explicitly asked for this string)
            # Actually, LogManager might not have STATUS_DOWNLOAD_TRIGGERED, let's just use the closest or a raw string
            log_mgr.update_status(title, "DOWNLOAD_TRIGGERED")
        else:
            print(f"[ERROR] Failed to trigger download for {title}")
            
        # Clean up tabs
        try:
            await browser.close_non_download_tabs(keep_url_fragment="download.pwthor.live")
        except Exception:
            pass
        await asyncio.sleep(2.0)
        
    print("\n[INFO] All selected missing downloads triggered.")
    
    # Keep the script running to allow background downloads to finish
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass # Will drop down to finally block
    finally:
        await browser.close()
