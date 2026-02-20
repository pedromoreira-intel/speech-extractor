// Demo search API for Speech Extractor
// Note: Full yt-dlp integration requires server with system dependencies

export default function handler(req, res) {
    const { q, limit = 10 } = req.query;

    if (!q) {
        return res.status(400).json({ error: 'Query parameter "q" is required' });
    }

    // Demo data - in production, this would call yt-dlp
    const videos = [
        { id: 'demo1', title: `${q} - Official Speech`, duration: '5:30', durationSec: 330 },
        { id: 'demo2', title: `${q} - Interview Highlights`, duration: '12:45', durationSec: 765 },
        { id: 'demo3', title: `${q} - Commencement Address`, duration: '18:20', durationSec: 1100 },
        { id: 'demo4', title: `${q} - TED Talk`, duration: '15:00', durationSec: 900 },
        { id: 'demo5', title: `${q} - Public Appearance`, duration: '8:15', durationSec: 495 },
    ].slice(0, parseInt(limit));

    res.json({
        query: q,
        count: videos.length,
        videos: videos
    });
}
