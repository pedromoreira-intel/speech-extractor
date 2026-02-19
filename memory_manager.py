#!/usr/bin/env python3
"""
TherapyTrack Memory Manager with ChromaDB
Extracts conversations from session transcripts and builds searchable vector memory.
"""

import json
import chromadb
from datetime import datetime
from pathlib import Path
import re

class MemoryManager:
    def __init__(self, workspace_dir="~/.openclaw/workspace", sessions_dir="~/.openclaw/agents/main/sessions"):
        self.workspace = Path(workspace_dir).expanduser()
        self.sessions = Path(sessions_dir).expanduser()
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.workspace / "chromadb"))
        self.collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"description": "All agent conversations with embeddings"}
        )
    
    def extract_therapytrack_conversations(self):
        """Extract all TherapyTrack-related conversations from session transcripts."""
        therapytrack_sessions = []
        
        # Find all sessions mentioning TherapyTrack
        for session_file in self.sessions.glob("*.jsonl"):
            if "deleted" in session_file.name:
                continue
                
            print(f"Scanning {session_file.name}...")
            
            with open(session_file, 'r') as f:
                messages = []
                for line in f:
                    try:
                        msg = json.loads(line)
                        if msg.get('type') == 'message':
                            messages.append(msg)
                    except json.JSONDecodeError:
                        continue
                
                # Check if TherapyTrack is mentioned
                for msg in messages:
                    content = json.dumps(msg.get('message', {}))
                    if re.search(r'therapytrack|TherapyTrack', content, re.IGNORECASE):
                        therapytrack_sessions.append({
                            'session_file': session_file.name,
                            'timestamp': msg.get('timestamp'),
                            'message': msg
                        })
                        break  # Found TT in this session, move to next file
        
        return therapytrack_sessions
    
    def build_daily_log(self, date_str, conversations):
        """Build a daily memory log from conversations."""
        log_path = self.memory_dir / f"{date_str}.md"
        
        if log_path.exists():
            print(f"⚠️  {date_str}.md already exists, skipping...")
            return
        
        # Group conversations by topic
        content = f"# {date_str} - Daily Log\n\n"
        content += "## Conversations\n\n"
        
        for conv in conversations:
            timestamp = conv.get('timestamp', 'Unknown time')
            msg = conv.get('message', {}).get('message', {})
            role = msg.get('role', 'unknown')
            
            # Extract text content
            text_parts = []
            for item in msg.get('content', []):
                if item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
            
            if text_parts:
                content += f"### {timestamp} ({role})\n\n"
                content += "\n\n".join(text_parts)
                content += "\n\n---\n\n"
        
        # Write log
        with open(log_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Created {log_path}")
        
        # Add to ChromaDB
        self.index_daily_log(date_str, content)
    
    def index_daily_log(self, date_str, content):
        """Add daily log to ChromaDB for vector search."""
        self.collection.add(
            documents=[content],
            metadatas=[{"date": date_str, "type": "daily_log"}],
            ids=[f"daily_{date_str}"]
        )
        print(f"📊 Indexed {date_str} in ChromaDB")
    
    def search_memory(self, query, n_results=5):
        """Search memory using vector similarity."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results
    
    def backfill_missing_logs(self):
        """Scan all sessions and create missing daily logs."""
        print("🔍 Scanning all session transcripts...")
        
        # Map sessions to dates
        session_dates = {}
        for session_file in self.sessions.glob("*.jsonl"):
            if "deleted" in session_file.name:
                continue
            
            with open(session_file, 'r') as f:
                for line in f:
                    try:
                        msg = json.loads(line)
                        if msg.get('type') == 'message' and msg.get('timestamp'):
                            # Parse timestamp
                            ts = msg['timestamp']
                            date = datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                            
                            if date not in session_dates:
                                session_dates[date] = []
                            
                            session_dates[date].append(msg)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
        
        # Build logs for each date
        print(f"\n📅 Found conversations across {len(session_dates)} dates\n")
        
        for date, conversations in sorted(session_dates.items()):
            self.build_daily_log(date, [{'timestamp': date, 'message': c} for c in conversations])
        
        print("\n✅ Backfill complete!")

if __name__ == "__main__":
    manager = MemoryManager()
    
    print("=" * 60)
    print("🧠 MEMORY MANAGER - TherapyTrack Edition")
    print("=" * 60)
    
    # Extract TherapyTrack conversations
    print("\n1️⃣  Extracting TherapyTrack conversations...")
    tt_convs = manager.extract_therapytrack_conversations()
    print(f"   Found {len(tt_convs)} TherapyTrack-related sessions\n")
    
    # Backfill missing daily logs
    print("2️⃣  Backfilling missing daily logs...")
    manager.backfill_missing_logs()
    
    # Test search
    print("\n3️⃣  Testing memory search...")
    results = manager.search_memory("TherapyTrack session notes API", n_results=3)
    print(f"   Search returned {len(results['ids'][0])} results")
    
    print("\n" + "=" * 60)
    print("✨ MEMORY SYSTEM LEGENDARY!")
    print("=" * 60)
