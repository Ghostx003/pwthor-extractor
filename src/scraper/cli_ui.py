"""
Rich Terminal User Interface, Live Progress Monitor, and Interactive Prompts for PWTHOR Auto Downloader.
"""
import sys
import os
import signal
import tkinter as tk
from tkinter import filedialog
from typing import Dict, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.prompt import Prompt


class TerminalUI:
    """
    Manages interactive CLI prompts, dynamic status updates, live statistics panel,
    cookie input prompts, and graceful Ctrl+C interruption.
    """

    def __init__(self):
        self.console = Console()
        self.live: Optional[Live] = None
        self.interrupted = False

    def setup_interrupt_handler(self, on_interrupt_callback=None):
        """Register Ctrl+C signal handler."""
        def handle_signal(sig, frame):
            if self.interrupted:
                return
            self.interrupted = True
            self.console.print("\n[bold red]Ctrl+C detected.[/bold red]")
            self.console.print("[yellow]Saving current state...[/yellow]")
            self.console.print("[yellow]Saving download log...[/yellow]")
            self.console.print("[yellow]Preserving resume information...[/yellow]\n")
            if on_interrupt_callback:
                on_interrupt_callback()
            self.console.print("[bold green]Session safely stopped.[/bold green]")
            self.console.print("[cyan]Run the program again to resume.[/cyan]\n")
            raise KeyboardInterrupt()

        signal.signal(signal.SIGINT, handle_signal)

    def print_banner(self):
        self.console.clear()
        banner = (
            "[bold cyan]========================================[/bold cyan]\n"
            "[bold white]       VIDEO DOWNLOAD AUTOMATION       [/bold white]\n"
            "[bold cyan]========================================[/bold cyan]"
        )
        self.console.print(Panel(banner, border_style="cyan", expand=False))

    @staticmethod
    def prompt_download_folder() -> str:
        """Prompt user for the download folder using Windows dialog."""
        console = Console()
        console.print("\n[bold yellow]========================================[/bold yellow]")
        console.print("[bold yellow]DOWNLOAD FOLDER SELECTION[/bold yellow]")
        console.print("[bold yellow]========================================[/bold yellow]")
        console.print("Select the folder where you want all downloaded videos to be saved.\n")
        
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Select Download Folder")
        root.destroy()
        
        while not folder:
            console.print("[bold red]No folder selected. Please select a valid folder.[/bold red]")
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(title="Select Download Folder")
            root.destroy()
            
        console.print(f"[bold green][OK] Download folder:[/bold green]")
        console.print(f"[bold white]{folder}[/bold white]")
        return folder

    @staticmethod
    def prompt_url() -> str:
        """Prompt user for exact target website URL."""
        console = Console()
        console.print("\n[bold yellow]STEP 1 — COMMAND-LINE URL INPUT[/bold yellow]")
        url = Prompt.ask("[bold green]Enter website URL[/bold green]")
        url = url.strip()
        while not url:
            url = Prompt.ask("[bold red]URL cannot be empty. Please enter website URL[/bold red]").strip()

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        return url

    @staticmethod
    def prompt_download_mode() -> str:
        """Prompt user to select what to download (Lecture, Notes, DPP)."""
        console = Console()
        console.print("\n[bold yellow]========================================[/bold yellow]")
        console.print("[bold yellow]          WHAT DO YOU WANT TO DOWNLOAD?         [/bold yellow]")
        console.print("[bold yellow]========================================[/bold yellow]")
        console.print("1. Lecture")
        console.print("2. Notes")
        console.print("3. DPP\n")
        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3"])
        return choice

    @staticmethod
    def prompt_lecture_mode() -> str:
        """
        Prompt user to select Lecture execution mode.
        """
        console = Console()
        console.print("\n[bold yellow]========================================[/bold yellow]")
        console.print("[bold yellow]              LECTURE MODE              [/bold yellow]")
        console.print("[bold yellow]========================================[/bold yellow]")
        console.print("1. Execute Downloads")
        console.print("2. Capture Links\n")
        choice = Prompt.ask("Enter your choice", choices=["1", "2"])
        return "execute" if choice == "1" else "capture"

    @staticmethod
    def prompt_cookie_reuse_choice(saved_datetime_str: str) -> str:
        """
        Prompt user when an unexpired cookie is found:
        'Do you want to use the cookie you saved on [date and time]?'
        1. YES
        2. NO
        """
        console = Console()
        console.print(f"\n[bold yellow]Do you want to use the cookie you saved on {saved_datetime_str}?[/bold yellow]")
        console.print("1. YES")
        console.print("2. NO")
        choice = Prompt.ask("Select", choices=["1", "2"], default="1")
        return choice

    @staticmethod
    def prompt_cookie_value_input(cookie_name: str = "download_access") -> str:
        """Prompt user to enter cookie value."""
        console = Console()
        console.print(f"\n[bold yellow]Enter value for cookie '{cookie_name}':[/bold yellow]")
        value = Prompt.ask("[bold green]Value[/bold green]")
        while not value.strip():
            value = Prompt.ask("[bold red]Cookie value cannot be empty. Enter value[/bold red]")
        return value.strip()

    def prompt_start_video_option(self, last_lecture_name: Optional[str] = None) -> Tuple[Optional[str], bool]:
        """
        Ask user if they want to start downloading from a specific video.
        Returns tuple: (start_video_title, start_from_scratch_bool)
        """
        console = Console()
        console.print("\n[bold yellow]Do you want to start downloading from a specific video?[/bold yellow]")
        console.print("1. YES")
        console.print("2. NO")
        choice = Prompt.ask("Select", choices=["1", "2"], default="2")

        if choice == "1":
            title = Prompt.ask("[bold green]Enter video name or number (e.g. 16 for 16th video from bottom)[/bold green]")
            return (title.strip() if title else None), False
        else:
            return None, True  # start_from_scratch = True

    @staticmethod
    def prompt_video_count() -> Optional[int]:
        """
        Prompt user for the number of videos to download.
        Returns int if a valid number is provided, or None if ENTER is pressed (meaning ALL).
        """
        console = Console()
        while True:
            console.print("\n[bold yellow]How many videos do you want to download?[/bold yellow]")
            console.print("[bold white]Enter a number:\n(or press ENTER to download ALL videos)[/bold white]")
            val = Prompt.ask(">")
            
            if not val.strip():
                return None
            
            try:
                num = int(val)
                if num > 0:
                    return num
                else:
                    console.print("[bold red][ERROR] Number of videos must be greater than 0.[/bold red]")
            except ValueError:
                console.print("[bold red][ERROR] Please enter a valid positive number or press ENTER for ALL.[/bold red]")

    def prompt_end_action(self) -> str:
        """
        Prompt user at completion:
        1. Run the program again
        2. Exit
        """
        console = Console()
        console.print("\n[bold yellow]What would you like to do?[/bold yellow]")
        console.print("1. Run the program again")
        console.print("2. Exit")
        choice = Prompt.ask("Select", choices=["1", "2"], default="2")
        return choice

    def prompt_download_next(self, next_video_title: str) -> bool:
        """
        After finishing a single-video download, ask if the user wants to
        download the next video in the queue. Chrome stays open either way.

        Returns True  → download the next video
        Returns False → exit the program (Chrome stays open)
        """
        console = Console()
        console.print("\n[bold cyan]========================================[/bold cyan]")
        console.print("[bold green]  DOWNLOAD TRIGGERED SUCCESSFULLY  [/bold green]")
        console.print("[bold cyan]========================================[/bold cyan]")
        console.print(f"\n[bold yellow]Next video in queue:[/bold yellow]")
        console.print(f"[bold white]  {next_video_title}[/bold white]\n")
        console.print("[bold yellow]Hey! Do you want to download the next file?[/bold yellow]")
        console.print("1. YES — download next video")
        console.print("2. NO  — exit program (Chrome stays open)\n")
        choice = Prompt.ask("Select", choices=["1", "2"], default="1")
        return choice == "1"

    def build_dashboard_table(self, stats: Dict[str, Any], current_video: str = "N/A", current_quality: str = "1280x720", status: str = "Initializing...") -> Table:
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="bold white")

        table.add_row("URL", stats.get("session_url", "N/A"))
        table.add_row("Total Videos Found", str(stats.get("total", 0)))
        table.add_row("Videos Processed", str(stats.get("processed", 0)))
        table.add_row("Downloads Active", str(stats.get("active", 0)))
        table.add_row("Downloads Finished", str(stats.get("completed", 0)))
        table.add_row("Downloads Failed", str(stats.get("failed", 0)))
        table.add_row("", "")
        table.add_row("Current Video", current_video)
        table.add_row("Current Quality", current_quality)
        table.add_row("Processing Order", "Right -> Left")
        table.add_row("Status", f"[bold green]{status}[/bold green]")

        return table

    def display_live_status(self, stats: Dict[str, Any], current_video: str = "N/A", current_quality: str = "1280x720", status: str = "Processing..."):
        table = self.build_dashboard_table(stats, current_video, current_quality, status)
        panel = Panel(table, title="[bold white]LIVE MONITORING[/bold white]", border_style="cyan")
        self.console.print(panel)

    def display_final_summary(self, stats: Dict[str, Any], failed_videos: list = None):
        self.console.print("\n[bold cyan]========================================[/bold cyan]")
        self.console.print("[bold green]           DOWNLOAD COMPLETE           [/bold green]")
        self.console.print("[bold cyan]========================================[/bold cyan]")

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold yellow")
        table.add_column("Value", style="bold white")

        table.add_row("Total Videos Found", str(stats.get("total", 0)))
        table.add_row("Processed", str(stats.get("processed", 0)))
        table.add_row("Completed", str(stats.get("completed", 0)))
        table.add_row("Failed", str(stats.get("failed", 0)))
        table.add_row("Quality Mode", "Highest Available (Prefer 1280x720)")

        self.console.print(table)

        if failed_videos:
            self.console.print("\n[bold red]Failed Downloads:[/bold red]")
            for idx, item in enumerate(failed_videos, 1):
                self.console.print(f"  {idx}. {item}")
        self.console.print("[bold cyan]========================================[/bold cyan]\n")
