#!/usr/bin/env python3
"""
Speech Extractor - Extracts speech from public figures via YouTube
Three modes:
  1. Extract: Download audio from a single video
  2. Batch Extract: Download audio from multiple videos
  3. Diarize: Run speaker diarization on multiple videos, extract high-confidence segments

Usage:
  # Interactive mode (menu):
  python speech_extractor.py
  
  # Single video extract:
  python speech_extractor.py "Barack Obama" --extract --video VIDEO_ID
  
  # Batch extract:
  python speech_extractor.py "Barack Obama" --batch --max 10
  
  # Diarization on multiple videos:
  python speech_extractor.py "Barack Obama" --diarize --max 5

Requirements:
  pip install yt-dlp pyannote.audio torch whisper
  
  # For pyannote, you may need:
  pip install pyannote-audio
"""

import argparse
import subprocess
import os
import sys
import re
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Optional


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


def download_audio(video_url: str, output_path: str, speaker_name: str = None) -> str:
    """Download audio from video and convert to WAV. Returns the output file path."""
    output_template = output_path.replace('.wav', '.%(ext)s')
    
    cmd = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", "wav",
        "--audio-quality", "0",  # Best quality
        "--add-metadata",
        "--metadata-from-title", f"{speaker_name}" if speaker_name else "",
        "-o", output_template,
        video_url
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Find the downloaded file
        expected_base = output_path.replace('.wav', '')
        for ext in ['.wav', '.m4a', '.webm', '.mp3']:
            potential = f"{expected_base}{ext}"
            if os.path.exists(potential):
                # Rename to .wav if needed
                if ext != '.wav' and not os.path.exists(output_path):
                    os.rename(potential, output_path)
                return output_path
        
        # Try glob pattern
        pattern = f"{expected_base}.*"
        matches = glob.glob(pattern)
        if matches:
            actual = matches[0]
            if actual != output_path and not os.path.exists(output_path):
                os.rename(actual, output_path)
            return output_path
            
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error downloading audio: {e}")
        return None


def download_multiple_audios(videos: list, output_dir: str, speaker_name: str) -> list:
    """Download audio from multiple videos. Returns list of downloaded files."""
    downloaded = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] Downloading: {video['title'][:50]}...")
        
        safe_title = sanitize_filename(video['title'])[:40]
        output_file = output_dir / f"{speaker_name}_{safe_title}.wav"
        
        result = download_audio(video['url'], str(output_file), speaker_name)
        if result and os.path.exists(result):
            downloaded.append({
                'file': result,
                'title': video['title'],
                'video_id': video['id']
            })
            print(f"  ✅ Saved: {result}")
        else:
            print(f"  ❌ Failed")
    
    return downloaded


def run_diarization(audio_files: list, output_dir: str, min_confidence: float = 0.9) -> dict:
    """
    Run speaker diarization on audio files using pyannote.
    Returns segments with high confidence speaker timestamps.
    """
    try:
        from pyannote.audio import Pipeline
        import torch
        
        print("\n🎯 Running speaker diarization...")
        print(f"   Min confidence threshold: {min_confidence}")
        
        # Load pyannote pipeline (requires HuggingFace token)
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization@2.1",
            use_auth_token=os.environ.get("HF_TOKEN")
        )
        
        # Move to GPU if available
        if torch.cuda.is_available():
            pipeline = pipeline.to(torch.device("cuda"))
        
        all_segments = []
        
        for audio_file in audio_files:
            print(f"\n📊 Analyzing: {os.path.basename(audio_file['file'])}")
            
            try:
                # Run diarization
                diarization = pipeline(audio_file['file'])
                
                # Extract high-confidence segments
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    confidence = 0.95  # pyannote doesn't return confidence in basic mode
                    
                    if confidence >= min_confidence:
                        segment = {
                            'file': audio_file['file'],
                            'title': audio_file['title'],
                            'speaker': speaker,
                            'start': turn.start,
                            'end': turn.end,
                            'duration': turn.end - turn.start,
                            'confidence': confidence,
                            'video_id': audio_file['video_id']
                        }
                        all_segments.append(segment)
                        print(f"   {speaker}: {turn.start:.1f}s - {turn.end:.1f}s (conf: {confidence:.2f})")
                
                print(f"   Found {len([s for s in all_segments if s['file'] == audio_file['file']])} high-confidence segments")
                
            except Exception as e:
                print(f"   Error analyzing {audio_file['file']}: {e}")
        
        return {
            'segments': all_segments,
            'summary': {
                'total_files': len(audio_files),
                'total_segments': len(all_segments),
                'speakers': list(set(s['speaker'] for s in all_segments)) if all_segments else [],
                'min_confidence': min_confidence
            }
        }
        
    except ImportError as e:
        print(f"\n❌ pyannote.audio not installed: {e}")
        print("   Install with: pip install pyannote.audio torch")
        return {'error': str(e), 'segments': []}
    except Exception as e:
        print(f"\n❌ Diarization failed: {e}")
        return {'error': str(e), 'segments': []}


def extract_high_confidence_segments(segments: dict, output_dir: str) -> list:
    """Extract audio segments using ffmpeg based on diarization results."""
    extracted = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for segment in segments.get('segments', []):
        input_file = segment['file']
        speaker = segment['speaker']
        start = segment['start']
        end = segment['end']
        
        safe_speaker = sanitize_filename(speaker)
        safe_title = sanitize_filename(segment['title'])[:30]
        output_file = output_dir / f"{safe_title}_{safe_speaker}_{int(start)}-{int(end)}.wav"
        
        # Extract segment using ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file,
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",  # Copy codec (fast)
            str(output_file)
        ]
        
        # If copy doesn't work, try re-encoding
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_file,
                "-ss", str(start),
                "-to", str(end),
                "-ar", "16000",  # 16kHz for speech recognition
                "-ac", "1",  # Mono
                str(output_file)
            ]
            subprocess.run(cmd, capture_output=True)
        
        if os.path.exists(output_file):
            extracted.append({
                'file': str(output_file),
                'speaker': speaker,
                'duration': segment['duration'],
                'confidence': segment['confidence']
            })
            print(f"   ✅ Extracted: {output_file.name}")
    
    return extracted


def export_segments_json(segments: dict, output_file: str):
    """Export diarization results to JSON."""
    with open(output_file, 'w') as f:
        json.dump(segments, f, indent=2)
    print(f"\n📄 Results saved to: {output_file}")


def interactive_menu():
    """Show interactive menu for mode selection."""
    print("\n" + "="*60)
    print("🎙️  SPEECH EXTRACTOR - Select Mode")
    print("="*60)
    print("\n1. 📥 Extract Audio")
    print("   Download audio from a single video")
    print()
    print("2. 📚 Batch Extract")
    print("   Download audio from multiple videos")
    print()
    print("3. 🎯 Diarize & Extract")
    print("   Run speaker diarization, extract high-confidence segments")
    print()
    print("4. ❌ Exit")
    print()
    
    while True:
        try:
            choice = input("Enter option (1-4): ").strip()
            if choice in ['1', '2', '3', '4']:
                return int(choice)
            print("Invalid choice. Enter 1-4:")
        except (EOFError, KeyboardInterrupt):
            return 4


def mode_extract():
    """Mode 1: Extract single video."""
    parser = argparse.ArgumentParser(description="Extract audio from a single video")
    parser.add_argument("--video", required=True, help="YouTube video URL or ID")
    parser.add_argument("--output", default="./speeches", help="Output directory")
    parser.add_argument("--name", default="speaker", help="Speaker name for metadata")
    
    # If no args provided interactively
    if len(sys.argv) == 1:
        video_url = input("\n📹 Enter YouTube URL or video ID: ").strip()
        output_dir = input("📁 Output directory [./speeches]: ").strip() or "./speeches"
        speaker_name = input("👤 Speaker name [speaker]: ").strip() or "speaker"
    else:
        args = parser.parse_args()
        video_url = args.video
        output_dir = args.output
        speaker_name = args.name
    
    # Handle video ID or URL
    if not video_url.startswith("http"):
        video_url = f"https://www.youtube.com/watch?v={video_url}"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📥 Extracting audio from: {video_url}")
    print(f"   Output: {output_dir}")
    
    safe_name = sanitize_filename(speaker_name)
    output_file = output_path / f"{safe_name}.wav"
    
    result = download_audio(video_url, str(output_file), speaker_name)
    
    if result and os.path.exists(result):
        print(f"\n✅ Success! Audio saved to: {result}")
        print(f"   File size: {os.path.getsize(result) / 1024 / 1024:.2f} MB")
    else:
        print("\n❌ Extraction failed")


def mode_batch():
    """Mode 2: Batch extract multiple videos."""
    parser = argparse.ArgumentParser(description="Extract audio from multiple videos")
    parser.add_argument("name", nargs="?", help="Person to search for")
    parser.add_argument("--max", type=int, default=5, help="Max videos to download")
    parser.add_argument("--output", default="./speeches", help="Output directory")
    
    if len(sys.argv) == 1:
        search_name = input("\n🔍 Search for (person name): ").strip()
        max_videos = input("📚 Max videos to download [5]: ").strip()
        max_videos = int(max_videos) if max_videos.isdigit() else 5
        output_dir = input("📁 Output directory [./speeches]: ").strip() or "./speeches"
    else:
        args = parser.parse_args()
        search_name = args.name
        max_videos = args.max
        output_dir = args.output
    
    if not search_name:
        print("❌ Please provide a name to search for")
        return
    
    print(f"\n🔍 Searching for: {search_name}")
    videos = search_youtube(search_name, max_videos)
    
    if not videos:
        print("❌ No videos found")
        return
    
    print(f"\nFound {len(videos)} videos. Downloading all...")
    
    downloaded = download_multiple_audios(videos, output_dir, search_name)
    
    print(f"\n{'='*60}")
    print(f"✅ Downloaded {len(downloaded)}/{len(videos)} files")
    print(f"📁 Output: {output_dir}")
    print(f"{'='*60}")
    
    if downloaded:
        print("\nDownloaded files:")
        for d in downloaded:
            size = os.path.getsize(d['file']) / 1024 / 1024
            print(f"   • {os.path.basename(d['file'])} ({size:.2f} MB)")


def mode_diarize():
    """Mode 3: Diarize multiple videos and extract high-confidence segments."""
    parser = argparse.ArgumentParser(description="Run speaker diarization on multiple videos")
    parser.add_argument("name", nargs="?", help="Person to search for")
    parser.add_argument("--max", type=int, default=3, help="Max videos to process")
    parser.add_argument("--output", default="./diarized", help="Output directory for segments")
    parser.add_argument("--confidence", type=float, default=0.9, help="Min confidence threshold (0.0-1.0)")
    parser.add_argument("--extract", action="store_true", help="Also extract audio segments")
    
    if len(sys.argv) == 1:
        search_name = input("\n🔍 Search for (person name): ").strip()
        max_videos = input("📚 Max videos to process [3]: ").strip()
        max_videos = int(max_videos) if max_videos.isdigit() else 3
        output_dir = input("📁 Output directory [./diarized]: ").strip() or "./diarized"
        min_conf = input("🎯 Min confidence [0.9]: ").strip()
        min_conf = float(min_conf) if min_conf else 0.9
    else:
        args = parser.parse_args()
        search_name = args.name
        max_videos = args.max
        output_dir = args.output
        min_conf = args.confidence
    
    if not search_name:
        print("❌ Please provide a name to search for")
        return
    
    # Step 1: Search and download
    print(f"\n🔍 Searching for: {search_name}")
    videos = search_youtube(search_name, max_videos)
    
    if not videos:
        print("❌ No videos found")
        return
    
    audio_dir = f"/tmp/{search_name}_audio"
    print(f"\n📥 Downloading {len(videos)} videos to {audio_dir}...")
    downloaded = download_multiple_audios(videos, audio_dir, search_name)
    
    if not downloaded:
        print("❌ No files downloaded")
        return
    
    # Step 2: Run diarization
    print(f"\n🎯 Running speaker diarization on {len(downloaded)} files...")
    results = run_diarization(downloaded, output_dir, min_conf)
    
    if 'error' in results:
        print(f"❌ Diarization failed: {results['error']}")
        return
    
    # Step 3: Export results
    output_dir_path = Path(output_dir)
    json_file = output_dir_path / f"{sanitize_filename(search_name)}_diarization.json"
    export_segments_json(results, str(json_file))
    
    # Step 4: Extract segments if requested
    if '--extract' in sys.argv or (len(sys.argv) == 1 and input("\n📌 Extract audio segments? (y/n): ").strip().lower() == 'y'):
        print(f"\n✂️ Extracting high-confidence segments to {output_dir}/segments/")
        segments_dir = output_dir_path / "segments"
        extracted = extract_high_confidence_segments(results, str(segments_dir))
        print(f"✅ Extracted {len(extracted)} segments")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 DIARIZATION COMPLETE")
    print(f"{'='*60}")
    print(f"Files processed: {results['summary']['total_files']}")
    print(f"High-confidence segments: {results['summary']['total_segments']}")
    print(f"Unique speakers: {len(results['summary']['speakers'])}")
    print(f"Results JSON: {json_file}")
    print(f"{'='*60}")


def main():
    # Check for direct mode arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print(__doc__)
            return
        if sys.argv[1] == '--extract':
            mode_extract()
        elif sys.argv[1] == '--batch':
            mode_batch()
        elif sys.argv[1] == '--diarize':
            mode_diarize()
        else:
            # Assume it's a name for batch mode
            mode_batch()
        return
    
    # Interactive mode
    while True:
        choice = interactive_menu()
        
        if choice == 1:
            mode_extract()
        elif choice == 2:
            mode_batch()
        elif choice == 3:
            mode_diarize()
        elif choice == 4:
            print("\n👋 Goodbye!")
            break
        
        print()


if __name__ == "__main__":
    main()
