import json
import os
import time
import webbrowser
from rich.console import Console

console = Console()

def main():
    link_file = "link_saver.json"
    
    console.print("\n[bold yellow]========================================[/bold yellow]")
    console.print("[bold yellow]          OPEN SAVED LINKS             [/bold yellow]")
    console.print("[bold yellow]========================================[/bold yellow]\n")
    
    if not os.path.exists(link_file):
        console.print("[red]link_saver.json not found! You need to capture some links first.[/red]")
        return
        
    try:
        with open(link_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[red]Failed to read link_saver.json: {e}[/red]")
        return
        
    videos = data.get("videos", [])
    if not videos:
        console.print("[yellow]No captured links found in the JSON file.[/yellow]")
        return
        
    console.print(f"[green]Found {len(videos)} links. Opening in your default Chrome browser...[/green]\n")
    
    for i, v in enumerate(videos, 1):
        url = v.get("download_url_720p")
        title = v.get("title", f"Video {i}")
        
        if url:
            console.print(f"[{i}/{len(videos)}] Opening: {title}")
            # webbrowser opens it in the user's actual default browser instance
            webbrowser.open_new_tab(url)
            time.sleep(1)  # Brief pause to let Chrome handle the new tab gracefully
            
    console.print("\n[bold green]========================================[/bold green]")
    console.print("[bold green]All links have been injected into your Chrome browser![/bold green]")
    console.print("[bold green]========================================[/bold green]\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
