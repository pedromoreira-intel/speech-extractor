#!/usr/bin/env python3
"""
Speech Extractor - Extracts speech from public figures via YouTube
Simple and works - just run: python speech_extractor.py "Person Name"

Usage:
  python speech_extractor.py "Barack Obama"
  python speech_extractor.py "Barack Obama" --max 10
  python speech_extractor.py "Barack Obama" --auto  # Auto-download first 3
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
    search_query = f"ytsearch{max_results}:{query} speech OR interview OR talk OR address"
    
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
        "-o", output_path,
        video_url
    ]
    
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error downloading audio: {e}")
        return False


def download_multiple(videos: list, output_dir: str, speaker_name: str) -> list:
    """Download audio from multiple videos."""
    downloaded = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] Downloading: {video['title'][:50]}...")
        
        safe_title = sanitize_filename(video['title'])[:40]
        output_file = output_dir / f"{speaker_name}_{safe_title}.wav"
        
        if download_audio(video['url'], str(output_file)):
            downloaded.append(str(output_file))
            print(f"  ✅ Saved: {output_file}")
        else:
            print(f"  ❌ Failed")
    
    return downloaded


def main():
    parser = argparse.ArgumentParser(description="Extract speech from public figures via YouTube")
    parser.add_argument("name", nargs="?", help="Name of the public figure")
    parser.add_argument("--max", type=int, default=5, help="Maximum number of results")
    parser.add_argument("--output", default="./speeches", help="Output directory for WAV files")
    parser.add_argument("--auto", action="store_true", help="Auto-download all found videos")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.name:
        # Interactive mode
        args.name = input("🔍 Search for (person name): ").strip()
        if not args.name:
            print("No name provided.")
            return 1
    
    print(f"\n🔍 Searching for: {args.name}")
    print("-" * 50)
    
    videos = search_youtube(args.name, args.max)
    
    if not videos:
        print("No videos found.")
        return 1
    
    print(f"\nFound {len(videos)} video(s):\n")
    for i, video in enumerate(videos, 1):
        print(f"  [{i}] {video['title']}")
        print(f"      Duration: {video['duration']} | {video['url']}")
        print()
    
    if args.auto:
        print(f"\n📥 Auto-downloading all {len(videos)} videos...")
        downloaded = download_multiple(videos, str(output_dir), args.name)
        print(f"\n✅ Downloaded {len(downloaded)} files to {output_dir}/")
        return 0
    
    # Ask user what to do
    print("Options:")
    print("  [1] Download a single video")
    print("  [2] Download ALL videos")
    print("  [0] Cancel")
    
    try:
        choice = input("\nEnter option: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    
    if choice == "1":
        try:
            num = int(input("Enter video number: "))
            if 1 <= num <= len(videos):
                video = videos[num - 1]
                safe_title = sanitize_filename(video['title'])[:40]
                output_file = output_dir / f"{args.name}_{safe_title}.wav"
                print(f"\n📥 Downloading: {video['title'][:50]}")
                if download_audio(video['url'], str(output_file)):
                    print(f"\n✅ Saved: {output_file}")
                else:
                    print("\n❌ Failed")
        except ValueError:
            print("Invalid number.")
    elif choice == "2":
        print(f"\n📥 Downloading all {len(videos)} videos...")
        downloaded = download_multiple(videos, str(output_dir), args.name)
        print(f"\n✅ Downloaded {len(downloaded)} files to {output_dir}/")
    elif choice == "0":
        print("Cancelled.")
    else:
        print("Invalid option.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
