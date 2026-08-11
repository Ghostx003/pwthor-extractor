"""
PWTHOR Post-Processing Renamer

Workflow:
  1. User selects folder containing downloaded lecture files.
  2. Files without an extension are renamed to .ts (extension-only change, no transcoding).
  3. download_mapping.json is loaded (title <-> duration mapping).
  4. FFprobe inspects each .ts file to read its exact duration (H:MM:SS).
  5. Duration is matched exactly against the JSON.
  6. File is renamed to the original video title.
  7. FFmpeg remuxes TS -> MP4 (no re-encoding).
  8. If MP4 exists and FFmpeg succeeded, the .ts file is deleted.
  9. If anything fails, the .ts file is preserved and the error is reported.

Usage:
    python rename_downloads.py <download_folder> [--mapping path/to/download_mapping.json] [--dry-run]
"""
import os
import sys
import json
import re
import subprocess
import shutil
import argparse
import tkinter as tk
from tkinter import filedialog
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG_FILE = "renamer_settings.json"

def get_config_path() -> str:
    """Return the absolute path to the config file."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)

def load_last_directory() -> str:
    """Load the last used directory from the config file."""
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_directory", "")
        except Exception:
            pass
    return ""

def save_last_directory(directory: str):
    """Save the selected directory to the config file."""
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"last_directory": directory}, f)
    except Exception as e:
        print(f"[WARN] Could not save config to {path}: {e}")

def sanitize_filename(title: str) -> str:
    """Strip characters that are illegal in Windows filenames."""
    clean = re.sub(r'[\\/:*?"<>|]', '-', title)
    clean = clean.strip().strip('.')
    return clean if clean else "video"


def find_ffprobe() -> Optional[str]:
    """Return path to ffprobe binary, or None if not found."""
    # Try PATH first
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    # Common Windows install locations
    candidates = [
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def find_ffmpeg() -> Optional[str]:
    """Return path to ffmpeg binary, or None if not found."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_file_duration(ffprobe_path: str, filepath: str) -> Optional[str]:
    """
    Uses FFprobe to get the total duration of a video file.

    Returns the duration formatted as "H:MM:SS" (e.g. "2:00:26"),
    or None if duration cannot be determined.
    """
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        duration_sec = float(data.get("format", {}).get("duration", 0))
        if duration_sec <= 0:
            return None

        # Convert total seconds -> H:MM:SS
        total_secs = int(round(duration_sec))
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        seconds = total_secs % 60
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    except Exception:
        return None


def load_mapping(mapping_path: str) -> dict:
    """Load download_mapping.json and build a duration -> title lookup dict."""
    if not os.path.exists(mapping_path):
        print(f"[ERROR] Mapping file not found: {mapping_path}")
        return {}
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        videos = data.get("videos", [])
        lookup = {}
        for entry in videos:
            dur = entry.get("duration", "").strip()
            title = entry.get("title", "").strip()
            if dur and title:
                lookup[dur] = title
        return lookup
    except Exception as e:
        print(f"[ERROR] Failed to read mapping file: {e}")
        return {}


def convert_ts_to_mp4(ffmpeg_path: str, ts_path: str, mp4_path: str) -> bool:
    """
    Remux TS -> MP4 without re-encoding.
    Returns True on success.
    """
    result = subprocess.run(
        [
            ffmpeg_path,
            "-y",                   # overwrite output if it exists
            "-i", ts_path,
            "-c", "copy",           # stream copy — no re-encoding
            "-movflags", "+faststart",
            "-bsf:a", "aac_adtstoasc",  # required for AAC in TS -> MP4
            mp4_path,
        ],
        capture_output=True,
        text=True,
        timeout=300
    )
    return result.returncode == 0 and os.path.exists(mp4_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Rename and convert downloaded PWTHOR lecture files."
    )
    parser.add_argument(
        "download_folder", 
        nargs="?", 
        default=None, 
        help="Folder containing the downloaded lecture files (optional, opens UI if omitted)."
    )
    parser.add_argument(
        "--mapping",
        default="download_mapping.json",
        help="Path to download_mapping.json (default: download_mapping.json in current directory)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without modifying any files."
    )
    args = parser.parse_args()

    folder = args.download_folder
    
    if not folder:
        # Prompt using tkinter UI
        root = tk.Tk()
        root.withdraw() # Hide the main window
        root.attributes('-topmost', True) # Bring dialog to front
        
        last_dir = load_last_directory()
        initial_dir = last_dir if os.path.isdir(last_dir) else os.getcwd()
        
        print("Waiting for folder selection in UI...")
        selected_folder = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Select Folder Containing Downloaded Lecture Files"
        )
        
        if not selected_folder:
            print("\n[CANCELLED] No folder was selected. Exiting.")
            sys.exit(0)
            
        folder = selected_folder

    folder = os.path.abspath(folder)
    save_last_directory(folder)
    
    mapping_path = os.path.abspath(args.mapping)
    dry_run = args.dry_run

    print("========================================")
    print("  PWTHOR VIDEO RENAMER + CONVERTER")
    print("========================================")
    if dry_run:
        print("  *** DRY RUN — No files will be changed ***")
    print(f"\nFolder:\n{folder}")
    print(f"\nMapping file:\n{mapping_path}\n")
    print("========================================\n")

    # Validate folder
    if not os.path.isdir(folder):
        print(f"[ERROR] Folder does not exist: {folder}")
        sys.exit(1)

    print("========================================")
    print("VIDEO COMPARISON")
    print("========================================")
    print("Do you want to compare the download")
    print("mapping against the selected folder?\n")
    print("1. Yes")
    print("2. No")
    
    choice = input("\nEnter your choice:\n> ").strip()
    while choice not in ("1", "2"):
        choice = input("> ").strip()
        
    run_comparison = (choice == "1")

    # Check if we should skip conversion
    all_files_check = os.listdir(folder)
    has_mp4 = any(f.lower().endswith(".mp4") for f in all_files_check)
    has_ts = any(f.lower().endswith(".ts") for f in all_files_check)
    has_no_ext = any(os.path.splitext(f)[1] == "" for f in all_files_check if os.path.isfile(os.path.join(folder, f)))

    skip_conversion = has_mp4 and not has_ts and not has_no_ext
    
    if skip_conversion:
        print("\nAll relevant files are already .mp4.")
        print("Skipping TS -> MP4 conversion phase.\n")
    else:
        # Check FFprobe / FFmpeg
        ffprobe = find_ffprobe()
        ffmpeg = find_ffmpeg()
        if not ffprobe:
            print("[ERROR] ffprobe not found. Please install FFmpeg and ensure it is on PATH.")
            sys.exit(1)
        if not ffmpeg:
            print("[ERROR] ffmpeg not found. Please install FFmpeg and ensure it is on PATH.")
            sys.exit(1)

    # -----------------------------------------------------------------------
    # STEP 1 — Rename files without extensions to .ts
    # -----------------------------------------------------------------------
    print("STEP 1: Adding .ts extension to files without extensions")
    print("-" * 44)
    all_files = os.listdir(folder)
    renamed_to_ts = 0
    for fname in all_files:
        fpath = os.path.join(folder, fname)
        if not os.path.isfile(fpath):
            continue
        _, ext = os.path.splitext(fname)
        if ext == "":
            new_name = fname + ".ts"
            new_path = os.path.join(folder, new_name)
            print(f"  {fname}  →  {new_name}")
            if not dry_run:
                os.rename(fpath, new_path)
            renamed_to_ts += 1

    if renamed_to_ts == 0:
        print("  (No extension-less files found.)")
    print(f"\n  Added .ts extension to {renamed_to_ts} file(s).\n")

    # -----------------------------------------------------------------------
    # STEP 2 — Load mapping
    # -----------------------------------------------------------------------
    print("STEP 2: Loading download_mapping.json")
    print("-" * 44)
    duration_to_title = load_mapping(mapping_path)
    if not duration_to_title:
        print("[ERROR] No mappings found. Cannot rename files.")
        print("        Make sure download_mapping.json is present and contains video entries.")
        sys.exit(1)
    print(f"  {len(duration_to_title)} mapping(s) loaded.\n")

    # -----------------------------------------------------------------------
    # STEP 3 — Process each .ts file
    # -----------------------------------------------------------------------
    print("STEP 3: Processing .ts files")
    print("-" * 44)

    ts_files = [
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(".ts")
    ]

    if not ts_files:
        if not skip_conversion:
            print("  No .ts files found in the folder.")
            print("\n========================================")
            print("CONVERSION COMPLETE — Nothing to process.")
            print("========================================")
    else:
        discovered = len(ts_files)
    matched = 0
    renamed = 0
    converted = 0
    deleted = 0
    failed_ffmpeg = 0
    unmatched = 0
    duration_failed = 0

    for ts_file in ts_files:
        ts_path = os.path.join(folder, ts_file)
        print(f"\n{'=' * 44}")
        print(f"File:\n{ts_file}\n")

        # --- FFprobe duration ---
        print("FFprobe: reading duration...")
        duration = get_file_duration(ffprobe, ts_path)

        if not duration:
            print(f"[ERROR]\nCould not determine duration.")
            print(f"\n[SKIPPED]\nDuration could not be determined.\nTS file preserved.")
            duration_failed += 1
            continue

        print(f"Duration:\n{duration}\n")

        # --- Match against JSON ---
        matched_title = duration_to_title.get(duration)
        if not matched_title:
            print(f"[NO MATCH]\n\nFile:\n{ts_file}\n\nDuration:\n{duration}\n")
            print("No matching duration was found in download_mapping.json.")
            print("TS file preserved.")
            unmatched += 1
            continue

        matched += 1
        safe_title = sanitize_filename(matched_title)
        print(f"[MATCH FOUND]\n\nDuration:\n{duration}\n\nMatched title:\n{matched_title}\n")

        # --- Rename .ts to title.ts ---
        new_ts_name = f"{safe_title}.ts"
        new_ts_path = os.path.join(folder, new_ts_name)

        # Handle collision
        if os.path.exists(new_ts_path) and new_ts_path != ts_path:
            base, ext = os.path.splitext(new_ts_name)
            new_ts_name = f"{base}_{ts_file[:8]}{ext}"
            new_ts_path = os.path.join(folder, new_ts_name)

        print(f"Renaming:\n{ts_file}\n        ↓\n{new_ts_name}\n")

        if not dry_run:
            try:
                os.rename(ts_path, new_ts_path)
                renamed += 1
            except Exception as e:
                print(f"[ERROR] Rename failed: {e}\nTS file preserved.")
                continue
        else:
            print("  [DRY RUN] Would rename.")
            renamed += 1
            continue

        # --- FFmpeg: TS -> MP4 ---
        mp4_name = f"{safe_title}.mp4"
        mp4_path = os.path.join(folder, mp4_name)

        print(f"[FFMPEG]\n{new_ts_name}\n        ↓\n{mp4_name}\n")

        success = convert_ts_to_mp4(ffmpeg, new_ts_path, mp4_path)

        if success:
            converted += 1
            print("[OK] MP4 created successfully.\n")
            # Delete TS only after confirmed MP4 exists
            try:
                os.remove(new_ts_path)
                deleted += 1
                print("[OK] TS file deleted.")
            except Exception as e:
                print(f"[WARN] Could not delete TS file: {e}")
        else:
            failed_ffmpeg += 1
            print("[ERROR] FFmpeg conversion failed.\n")
            print(f"File:\n{new_ts_name}\n")
            print("The original TS file has NOT been deleted.")
            print("Please inspect the file manually.")
            # Remove partial MP4 if it exists but is corrupt/empty
            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) == 0:
                try:
                    os.remove(mp4_path)
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Final summary (if conversion ran)
    # -----------------------------------------------------------------------
    if not skip_conversion and ts_files:
        ts_preserved = duration_failed + unmatched + failed_ffmpeg
        errors = failed_ffmpeg + duration_failed

        print("\n")
        print("========================================")
        print("PROCESS COMPLETE")
        print("========================================\n")
        print(f"Files discovered:      {discovered}")
        print(f"Matched:               {matched}")
        print(f"Renamed:               {renamed}")
        print(f"Converted to MP4:      {converted}")
        print(f"TS files deleted:      {deleted}")
        print(f"Unmatched:             {unmatched}")
        print(f"Duration read errors:  {duration_failed}")
        print(f"FFmpeg errors:         {failed_ffmpeg}")
        print(f"TS files preserved:    {ts_preserved}")
        print(f"Errors:                {errors}")
        print("\n========================================\n")
        
    if run_comparison:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from scraper.redownload_helper import run_comparison_and_download
        run_comparison_and_download(folder, mapping_path)


if __name__ == "__main__":
    main()
