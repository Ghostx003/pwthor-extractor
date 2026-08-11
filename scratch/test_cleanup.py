import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    dl_dir = os.path.abspath("downloads_test")
    os.makedirs(dl_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, downloads_path=dl_dir)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        
        await page.set_content('<a href="https://proof.ovh.net/files/1Mb.dat" download id="dl">Download</a>')
        
        print("Clicking...")
        async with page.expect_download(timeout=10000) as download_info:
            await page.click("#dl")
            
        download = await download_info.value
        print("Suggested filename:", download.suggested_filename)
        guid = getattr(download, '_guid', None)
        print("Download GUID:", guid)
        
        print("Files in dl_dir before sleep:", os.listdir(dl_dir))
        await asyncio.sleep(1)
        print("Files in dl_dir after sleep:", os.listdir(dl_dir))
        
        await browser.close()
        
    await asyncio.sleep(1)
    print("Files in dl_dir after close:", os.listdir(dl_dir))

asyncio.run(main())
