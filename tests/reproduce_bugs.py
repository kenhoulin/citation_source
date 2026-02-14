import requests
import pandas as pd

# Mocking the comparison logic from app.py to see if it fails

def test_id_comparison():
    print("Testing ID Comparison Logic...")
    
    # Simulate target_author from search_authors
    target_author = {
        "id": "https://openalex.org/A123456789", # Search returns full URL
        "name": "Test Author"
    }
    
    # Simulate row from process_citing_authors
    # In process_citing_authors:
    # clean_id = a_id.replace("https://openalex.org/", "") ...
    # author_counts[clean_id] = { ... "id": clean_id }
    
    row = {
        "Author ID": "A123456789", # Cleaned ID
        "Collaborator?": "Self" # This is set in process_citing_authors, but let's check the category logic
    }
    
    # The problematic code in main():
    # def get_category(row):
    #    if row["Author ID"] == target_author["id"]:
    #        return "Self-Citation"
    
    is_match = row["Author ID"] == target_author["id"]
    print(f"Direct Match: {row['Author ID']} == {target_author['id']} -> {is_match}")
    
    clean_target = target_author["id"].replace("https://openalex.org/", "")
    is_match_clean = row["Author ID"] == clean_target
    print(f"Cleaned Match: {row['Author ID']} == {clean_target} -> {is_match_clean}")

    if not is_match and is_match_clean:
        print("BUG CONFIRMED: ID comparison mismatch due to URL prefix.")
    else:
        print("No bug found in ID comparison.")

if __name__ == "__main__":
    test_id_comparison()
