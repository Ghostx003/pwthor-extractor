<div align="center">
  <h1>⚡ PWTHOR Extractor ⚡</h1>
  <p><strong>The Ultimate Automated Video Downloader & Scraper</strong></p>
  
  [![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![Playwright](https://img.shields.io/badge/Playwright-Automated-green?style=for-the-badge&logo=playwright)](https://playwright.dev/)
  [![License](https://img.shields.io/badge/License-MIT-red?style=for-the-badge)](#)
</div>

---

## 🌟 What is it?

**PWTHOR Extractor** is a state-of-the-art automation suite built to seamlessly download videos, capture direct links, and intelligently rename video files—all from a beautifully streamlined terminal interface.

Powered by `Playwright`, this script drives a headless (or dark-mode visible) Chromium browser that mimics human interaction, intelligently extracting video links, titles, and durations directly from DOM articles, ensuring lightning-fast metadata capture!

---

## 🚀 Installation & Setup

Getting started is insanely simple. 

1. **Clone the Repository**
   ```bash
   git clone https://github.com/Ghostx003/pwthor-extractor.git
   cd pwthor-extractor
   ```

2. **Ensure Python is Installed**
   - Make sure you have [Python 3.9+](https://www.python.org/downloads/) installed.
   - When installing on Windows, check the box **"Add Python to PATH"**.

3. **Run the Installer (Magic Button!)**
   - Simply double-click `run.bat`! 🪄
   - It will automatically install all required pip dependencies (`playwright`, `rich`, etc.) and download the Chromium browser engine for you.

---

## 🛠️ The Toolkit (Batch Files)

We’ve split the core functionalities into **four powerful, one-click batch scripts**. You never have to touch the terminal if you don't want to!

### 1️⃣ `run.bat` (The Core Engine ⚙️)
This is the heart of the Extractor. It launches the main scraping and downloading pipeline.
- Prompts for the target URL and download folder.
- Captures cookies securely.
- Navigates through video grids and grabs metadata (title & duration) natively from the DOM.
- Triggers background downloads instantly without annoying 30-second delays.

### 2️⃣ `run_renamer.bat` (The Organizer 📂)
Downloaded videos usually end up with messy or random filenames.
- This script scans your `downloads` folder and cross-references it with your captured metadata (`download_mapping.json`).
- Automatically renames all messy video files into beautifully formatted titles! 🎬

### 3️⃣ `Run_Open_Links.bat` (The Injector 🔗)
Did you run the scraper in **Capture Mode** to save direct 720p `.m3u8` or `.mp4` links instead of downloading them right away?
- This script reads your `link_saver.json`.
- Rapidly injects and opens all captured video links directly into your primary Chrome browser for manual review or third-party extension downloads! 🌐

### 4️⃣ `flush.bat` (The Cleaner 🧹)
Ready to start a fresh project? 
- Instantly flushes your local database (`download_mapping.json` and `link_saver.json`).
- Clears the slate for your next scraping mission without deleting your physical video files.

---

## 🏗️ Folder Structure

Everything is neatly organized to keep your workspace completely clutter-free:
* 📁 **`src/`** - Contains all the Python logic (`main.py`, `scraper/`, etc.)
* 📁 **`downloads/`** - Where your scraped videos land.
* 📁 **`logs/`** - Stores the session resumption states and logs.
* 📄 **`.json` files** - Local data storage kept at the root.

---

## ⚠️ Disclaimer
This tool is for educational purposes and personal archival only. Do not use this tool to pirate or distribute copyrighted content.

---
<div align="center">
  <i>Made with 🖤 from the shadows of Bhubaneswar (2026)</i>
</div>
