#!/usr/bin/env python3
"""
Quick memory search using ChromaDB embeddings
Usage: python3 search_memory.py "your query here"
"""

import sys
import chromadb
from pathlib import Path

def search_memory(query, n_results=5):
    workspace = Path("~/.openclaw/workspace").expanduser()
    client = chromadb.PersistentClient(path=str(workspace / "chromadb"))
    
    try:
        collection = client.get_collection(name="conversations")
    except:
        print("❌ Memory database not initialized. Run memory_manager.py first.")
        return
    
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    
    print(f"\n🔍 Search results for: '{query}'\n")
    print("=" * 60)
    
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    ), 1):
        print(f"\n{i}. {metadata.get('date', 'Unknown date')} (relevance: {1-distance:.2%})")
        print("-" * 60)
        print(doc[:500] + "..." if len(doc) > 500 else doc)
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 search_memory.py 'your query'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    search_memory(query)
