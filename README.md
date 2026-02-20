# Speech Extractor

Extract speech audio from YouTube videos.

## Two Ways to Use

### 1. CLI (Simplest)
```bash
python speech_extractor.py "Barack Obama"
python speech_extractor.py "Barack Obama" --auto  # Auto-download all
```

### 2. Web Interface (Local Server)
```bash
# Install requirements
pip install flask yt-dlp

# Start server
python server.py

# Open browser to
http://localhost:5000
```

## Requirements
- Python 3.8+
- yt-dlp (`pip install yt-dlp`)
- ffmpeg (for audio conversion)

## Output
WAV files saved to `./speeches/` directory
