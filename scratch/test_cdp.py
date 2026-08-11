import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import time
import socket

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def get_chrome_executable_path() -> str:
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

async def main():
    dl_dir = os.path.abspath("downloads_test")
    os.makedirs(dl_dir, exist_ok=True)
    
    port = get_free_port()
    chrome_path = get_chrome_executable_path()
    
    # Launch real Chrome with remote debugging
    process = subprocess.Popen([
        chrome_path,
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir=" + os.path.abspath("chrome_profile_test")
    ])
    
    time.sleep(2)
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Override download behavior on the browser CDP session
        browser_cdp = await browser.new_browser_cdp_session()
        await browser_cdp.send("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": dl_dir,
            "eventsEnabled": True
        })
        
        def on_dl_begin(event):
            print("DL BEGIN:", event)
            
        def on_dl_progress(event):
            print("DL PROGRESS:", event)
            
        browser_cdp.on("Browser.downloadWillBegin", on_dl_begin)
        browser_cdp.on("Browser.downloadProgress", on_dl_progress)
        
        async def handle_route(route, request):
            print("Intercepted:", request.url)
            response = await route.fetch()
            headers = dict(response.headers)
            headers["content-disposition"] = 'attachment; filename="custom_name.mp4"'
            print("Fulfilling with custom headers...")
            await route.fulfill(response=response, headers=headers)
        
        await context.route("**/*", handle_route)
        
        print("Clicking a native download link...")
        await page.set_content('<a href="https://proof.ovh.net/files/1Mb.dat" id="dl">Download</a>')
        await page.click("#dl")
        
        await asyncio.sleep(5)
        print("Done sleeping.")
        print(os.listdir(dl_dir))
        await browser.close()
        process.terminate()

asyncio.run(main())
