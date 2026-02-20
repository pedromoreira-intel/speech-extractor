#!/usr/bin/env python3
"""
Speech Extractor Server - Local web interface for extracting speech
Run: python server.py
Then open: http://localhost:5000
"""

from flask import Flask, request, jsonify, render_template
import subprocess
import os
import re
import json
import threading
from pathlib import Path

app = Flask(__name__)

downloads = []
search_results = []

def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def search_youtube(query: str, max_results: int = 10) -> list:
    cmd = [
        "yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(title)s\t%(duration)s",
        f"ytsearch{max_results}:{query} speech OR interview OR talk"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    videos.append({
                        'id': parts[0],
                        'title': parts[1],
                        'duration': parts[2] if len(parts) > 2 else "unknown",
                        'url': f"https://www.youtube.com/watch?v={parts[0]}"
                    })
        return videos
    except:
        return []

def download_video(video, output_dir="./speeches"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    safe_title = sanitize_filename(video['title'])[:40]
    output_file = output_dir / f"{safe_title}.wav"
    
    cmd = [
        "yt-dlp", "-x", "--audio-format", "wav", "--audio-quality", "0",
        "-o", str(output_file), video['url']
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return {'success': True, 'file': str(output_file), 'title': video['title']}
    except Exception as e:
        return {'success': False, 'error': str(e), 'title': video['title']}

def download_background(videos, output_dir):
    for video in videos:
        result = download_video(video, output_dir)
        downloads.append(result)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    max_results = int(request.args.get('max', 10))
    
    if not query:
        return jsonify({'error': 'No query'})
    
    videos = search_youtube(query, max_results)
    global search_results
    search_results = videos
    
    return jsonify({'query': query, 'count': len(videos), 'videos': videos})

@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json()
    video_ids = data.get('video_ids', [])
    output_dir = data.get('output_dir', './speeches')
    
    if not video_ids:
        return jsonify({'error': 'No videos'})
    
    selected = [v for v in search_results if v['id'] in video_ids]
    thread = threading.Thread(target=download_background, args=(selected, output_dir))
    thread.start()
    
    return jsonify({'success': True, 'message': f'Downloading {len(selected)} videos'})

@app.route('/api/downloads')
def api_downloads():
    return jsonify({'downloads': downloads})

@app.route('/api/clear', methods=['POST'])
def api_clear():
    global downloads
    downloads = []
    return jsonify({'success': True})

if __name__ == '__main__':
    print("\n🎙️  Speech Extractor Server")
    print("="*40)
    print("Open: http://localhost:5000")
    print("="*40 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
