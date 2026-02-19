#!/Users/admin/.openclaw/workspace/scripts/venv/bin/python3
"""
Memory sync script for Barney's semantic memory system.
Reads memory/*.md files, splits by headings, generates embeddings, stores in ChromaDB.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
import requests
import chromadb

# Configuration
WORKSPACE = Path("/Users/admin/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
CHROMA_URL = "http://localhost:8000"
OLLAMA_URL = "http://localhost:11434"
COLLECTION_NAME = "barney-memory"

def get_embedding(text):
    """Generate embedding using Ollama nomic-embed-text."""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={
                "model": "nomic-embed-text",
                "prompt": text
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def split_markdown_by_headings(content, filepath):
    """Split markdown content by ## headings into chunks."""
    chunks = []
    lines = content.split('\n')
    current_chunk = []
    current_heading = None
    
    for line in lines:
        if line.startswith('## '):
            # Save previous chunk if exists
            if current_chunk:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    chunks.append({
                        'text': chunk_text,
                        'heading': current_heading,
                        'filepath': str(filepath)
                    })
            # Start new chunk
            current_heading = line.replace('## ', '').strip()
            current_chunk = [line]
        else:
            current_chunk.append(line)
    
    # Save last chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk).strip()
        if chunk_text:
            chunks.append({
                'text': chunk_text,
                'heading': current_heading,
                'filepath': str(filepath)
            })
    
    return chunks

def sync_memory_files():
    """Main sync function."""
    print(f"Starting memory sync at {datetime.now()}")
    
    # Check Ollama is running
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    except:
        print("ERROR: Ollama not accessible at localhost:11434")
        sys.exit(1)
    
    # Connect to ChromaDB
    try:
        client = chromadb.HttpClient(host="localhost", port=8000)
    except Exception as e:
        print(f"ERROR: Cannot connect to ChromaDB: {e}")
        sys.exit(1)
    
    # Get or create collection
    try:
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        print(f"Collection '{COLLECTION_NAME}' ready.")
    except Exception as e:
        print(f"ERROR: Cannot create collection: {e}")
        sys.exit(1)
    
    # Process all .md files in memory directory
    if not MEMORY_DIR.exists():
        print(f"Memory directory not found: {MEMORY_DIR}")
        sys.exit(1)
    
    # Also process MEMORY.md in workspace root
    all_md_files = list(MEMORY_DIR.glob("*.md")) + [WORKSPACE / "MEMORY.md"]
    
    total_chunks = 0
    for md_file in all_md_files:
        if not md_file.exists():
            continue
            
        print(f"Processing {md_file.name}...")
        
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into chunks
        chunks = split_markdown_by_headings(content, md_file)
        print(f"  Found {len(chunks)} chunks")
        
        # Generate embeddings and upsert
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for idx, chunk in enumerate(chunks):
            # Truncate text to 4000 chars (like Jarvis does)
            text = chunk['text'][:4000]
            
            embedding = get_embedding(text)
            if not embedding:
                print(f"  Skipping chunk {idx} due to embedding error")
                continue
            
            # Create document ID
            doc_id = f"{md_file.stem}_{idx}"
            
            ids.append(doc_id)
            embeddings.append(embedding)
            documents.append(text)
            metadatas.append({
                "filepath": chunk['filepath'],
                "heading": chunk['heading'] or "untitled",
                "filename": md_file.name,
                "synced_at": datetime.now().isoformat()
            })
        
        # Batch upsert to ChromaDB
        if ids:
            try:
                collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
                total_chunks += len(ids)
                print(f"  Upserted {len(ids)} chunks")
            except Exception as e:
                print(f"  Error upserting chunks: {e}")
    
    print(f"Sync complete! Processed {total_chunks} chunks.")

if __name__ == "__main__":
    sync_memory_files()
