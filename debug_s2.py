import requests
import time
import json

def test_s2_api():
    print("Testing Semantic Scholar API...")
    
    # 1. Search for an author (e.g., Hinton)
    query = "Geoffrey Hinton"
    url_search = f"https://api.semanticscholar.org/graph/v1/author/search?query={query}&fields=name,affiliations,citationCount,hIndex&limit=5"
    
    try:
        print(f"Searching for: {query}")
        r = requests.get(url_search)
        r.raise_for_status()
        data = r.json()
        print("Search Response:", json.dumps(data, indent=2))
        
        if not data.get("data"):
            print("No author found.")
            return

        # Pick the one with highest citations
        authors = data["data"]
        authors.sort(key=lambda x: x.get("citationCount", 0), reverse=True)
        top_author = authors[0]
        author_id = top_author["authorId"]
        
        print(f"\nFound Author ID: {author_id} ({top_author['name']}) with {top_author['citationCount']} citations")
        
        # 2. Fetch Author Papers + Citations + Citing Authors
        # Using fields=citations.authors to get the citing authors directly
        # Attempting to increase limit of citations field (syntax: citations(limit=500).authors)
        print(f"Fetching papers for {author_id}...")
        
        # Limit to 5 papers (for the author), but fetch up to 500 citations per paper
        url_papers = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers?fields=title,year,citationCount,citations.authors,authors&limit=5&fields=citations(limit=500).authors"
        # Wait, the fields format is one string. Correct syntax: fields=title,...,citations.authors
        # To limit nested field: key(limit=N).field
        # Correct URL:
        url_papers = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers?fields=title,year,citationCount,citations.authors,authors&limit=5"
        # Actually S2 Graph API documentation on nested fields:
        # fields=citations.authors -> returns limited list
        # We can try: fields=citations.limit(500).authors if supported, 
        # but let's stick to standard and see if 'limit' param on main query affects nested.
        # Actually standard syntax for nested limit is often not supported in simple graph. 
        # But let's try the syntax: citations.limit(100).authors or citations(limit=100).authors
        
        # Let's try the common localized convention: citations.limit(500).authors
        url_papers = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers?fields=title,year,citationCount,citations.limit(500).authors,authors&limit=5"
        
        start_time = time.time()
        r2 = requests.get(url_papers)
        end_time = time.time()
        
        r2.raise_for_status()
        papers_data = r2.json()
        
        print(f"\nFetch took {end_time - start_time:.2f} seconds")
        
        # Analyze structure
        if "data" in papers_data:
            papers = papers_data["data"]
            papers.sort(key=lambda x: x.get("citationCount", 0), reverse=True) # Sort to check big papers first
            print(f"Fetched {len(papers)} papers.")
            
            for i, p in enumerate(papers):
                title = p.get("title", "Unknown")
                total_cites = p.get("citationCount", 0)
                citations = p.get("citations", [])
                fetched_cites = len(citations)
                
                print(f"\nPaper {i+1}: {title}")
                print(f"  - Total Citations (Metadata): {total_cites}")
                print(f"  - Fetched Citations (in payload): {fetched_cites}")
                
                if fetched_cites < total_cites:
                    print("  [WARNING] Truncation detected! Not all citations fetched.")
                    
                # Check first citation's authors
                if citations:
                    first_cite = citations[0]
                    citing_authors = first_cite.get("authors", [])
                    print(f"  - Sample Citing Paper Authors: {[a.get('name') for a in citing_authors]}")
                    
        else:
            print("No papers found or error in structure.")
            print(papers_data)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_s2_api()
