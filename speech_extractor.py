#!/usr/bin/env python3
"""
Speech Extractor - Extracts speech from public figures via YouTube
Usage: python speech_extractor.py "Person Name" [--max-results 5] [--output-dir ./speeches]
"""

import argparse
import subprocess
import os
import sys
import re
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def search_youtube(query: str, max_results: int = 5) -> list:
    """Search YouTube and return video URLs."""
    search_query = f"ytsearch{max_results}:{query} speech OR interview OR talk"
    
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s\t%(duration)s",
        search_query
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    video_id = parts[0]
                    title = parts[1]
                    duration = parts[2] if len(parts) > 2 else "unknown"
                    videos.append({
                        'id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'title': title,
                        'duration': duration
                    })
        return videos
    except subprocess.CalledProcessError as e:
        print(f"Error searching YouTube: {e.stderr}")
        return []


def download_audio(video_url: str, output_path: str) -> bool:
    """Download audio from video and convert to WAV."""
    cmd = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", "wav",
        "--audio-quality", "0",  # Best quality
        "-o", output_path.replace('.wav', '.%(ext)s'),
        video_url
    ]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error downloading audio: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Extract speech from public figures via YouTube")
    parser.add_argument("name", help="Name of the public figure")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum number of results to show")
    parser.add_argument("--output-dir", default="./speeches", help="Output directory for WAV files")
    parser.add_argument("--auto", action="store_true", help="Automatically download first result")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🔍 Searching for speeches by: {args.name}")
    print("-" * 50)
    
    videos = search_youtube(args.name, args.max_results)
    
    if not videos:
        print("No videos found.")
        return 1
    
    print(f"\nFound {len(videos)} video(s):\n")
    for i, video in enumerate(videos, 1):
        print(f"  [{i}] {video['title']}")
        print(f"      Duration: {video['duration']} | URL: {video['url']}")
        print()
    
    if args.auto:
        choice = 1
    else:
        try:
            choice = int(input("Enter number to download (0 to cancel): "))
        except ValueError:
            print("Invalid input.")
            return 1
    
    if choice == 0:
        print("Cancelled.")
        return 0
    
    if choice < 1 or choice > len(videos):
        print("Invalid selection.")
        return 1
    
    selected = videos[choice - 1]
    safe_name = sanitize_filename(args.name)
    safe_title = sanitize_filename(selected['title'])[:50]
    output_file = output_dir / f"{safe_name}_{safe_title}.wav"
    
    print(f"\n📥 Downloading: {selected['title']}")
    print(f"   Saving to: {output_file}")
    print()
    
    if download_audio(selected['url'], str(output_file)):
        print(f"\n✅ Successfully saved to: {output_file}")
        return 0
    else:
        print("\n❌ Download failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
