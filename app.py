import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time

# --- Constants & Config ---
HEADERS = {
    "User-Agent": "mailto:test@example.com" # Politeness
}

# ==========================================
# 1. OPENALEX FUNCTIONS
# ==========================================

@st.cache_data
def oa_search_authors(query):
    """
    Search for authors via OpenAlex API.
    """
    if not query:
        return []
    
    url = f"https://api.openalex.org/authors?search={query}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        # Format for display
        structured_results = []
        for author in results:
            name = author.get("display_name", "Unknown")
            
            # Priority: last_known_institution > affiliations[0] > Unknown
            last_known = author.get("last_known_institution")
            if last_known:
                affiliation = last_known.get("display_name", "Unknown")
            else:
                aff_list = author.get("affiliations", [])
                affiliation = aff_list[0].get("institution", {}).get("display_name", "Unknown") if aff_list else "Unknown"
                
            citation_count = author.get("cited_by_count", 0)
            id_val = author.get("id")
            
            structured_results.append({
                "display": f"{name} ({affiliation}) - {citation_count} citations",
                "id": id_val,
                "name": name,
                "citation_count": citation_count
            })
        return structured_results
    except Exception as e:
        st.error(f"OA Search Error: {e}")
        return []

@st.cache_data
def oa_get_author_works(author_id):
    """
    Fetch ALL works by the author (paginated) for OA collaboration check.
    """
    if author_id.startswith("https://openalex.org/"):
        author_id = author_id.replace("https://openalex.org/", "")
        
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"author.id:{author_id}",
        "per-page": 200,
        "cursor": "*"
    }
    
    all_works = []
    try:
        while True:
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                break
            all_works.extend(results)
            
            meta = data.get("meta", {})
            next_cursor = meta.get("next_cursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor
            
            if len(all_works) > 5000: # Safety cap
                break
    except Exception as e:
        st.error(f"OA Works Error: {e}")
        return []
    return all_works

@st.cache_data
def oa_get_citing_works(target_author_id, max_works=100):
    """
    Fetch citing works from OpenAlex.
    """
    author_works = oa_get_author_works(target_author_id)
    if not author_works:
        return []
    
    work_ids = [w["id"].replace("https://openalex.org/", "") for w in author_works if w.get("id")]
    if not work_ids:
        return []

    collected_works = []
    batch_size = 25
    chunked_ids = [work_ids[i:i + batch_size] for i in range(0, len(work_ids), batch_size)]
    
    url = "https://api.openalex.org/works"
    
    for chunk in chunked_ids:
        if len(collected_works) >= max_works:
            break
        
        work_id_string = "|".join(chunk)
        params = {
            "filter": f"cites:{work_id_string}",
            "per-page": 200,
            "cursor": "*"
        }
        
        while len(collected_works) < max_works:
            try:
                response = requests.get(url, headers=HEADERS, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                
                if not results:
                    break
                collected_works.extend(results)
                
                meta = data.get("meta", {})
                next_cursor = meta.get("next_cursor")
                if not next_cursor:
                    break
                params["cursor"] = next_cursor
            except Exception:
                break
                
    return collected_works[:max_works]

def oa_extract_collaborators(author_works, target_author_id):
    if target_author_id.startswith("https://openalex.org/"):
        target_author_id = target_author_id.replace("https://openalex.org/", "")

    collaborators = set()
    for work in author_works:
        authorships = work.get("authorships", [])
        for authorship in authorships:
            author = authorship.get("author", {})
            a_id = author.get("id")
            if a_id:
                if a_id.startswith("https://openalex.org/"):
                    a_id = a_id.replace("https://openalex.org/", "")
                if a_id != target_author_id:
                    collaborators.add(a_id)
    return collaborators

def oa_process_data(works, target_author_id, collaborator_ids=None, exclude_self=False):
    if target_author_id.startswith("https://openalex.org/"):
        target_author_id = target_author_id.replace("https://openalex.org/", "")

    if collaborator_ids is None:
        collaborator_ids = set()
        
    author_counts = {} 
    
    for work in works:
        authorships = work.get("authorships", [])
        for authorship in authorships:
            author = authorship.get("author", {})
            a_id = author.get("id")
            a_name = author.get("display_name")
            
            if not a_id: continue
            
            clean_id = a_id.replace("https://openalex.org/", "") if a_id.startswith("https://openalex.org/") else a_id

            if exclude_self and clean_id == target_author_id:
                continue
                
            if clean_id in author_counts:
                author_counts[clean_id]["count"] += 1
            else:
                author_counts[clean_id] = {"name": a_name, "count": 1, "id": clean_id}
                
    data = []
    for a_id, info in author_counts.items():
        is_collab = "Yes" if a_id in collaborator_ids else "No"
        if a_id == target_author_id:
            is_collab = "Self"
            
        data.append({
            "Author Name": info["name"], 
            "Citations": info["count"], 
            "Collaborator?": is_collab,
            "Author ID": a_id
        })
        
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by="Citations", ascending=False).head(50)
        
        def get_category(row):
            if row["Author ID"] == target_author_id: return "Self-Citation"
            elif row["Collaborator?"] == "Yes": return "Co-author"
            else: return "Other"

        df["Category"] = df.apply(get_category, axis=1)
        df["Profile URL"] = df["Author ID"].apply(lambda x: f"https://openalex.org/{x}" if x else "")
        
    return df

# ==========================================
# 2. SEMANTIC SCHOLAR FUNCTIONS
# ==========================================

@st.cache_data
def s2_search_authors(query):
    if not query: return []
    url = f"https://api.semanticscholar.org/graph/v1/author/search?query={query}&fields=name,affiliations,citationCount,hIndex&limit=10"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 429:
            time.sleep(2)
            response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        results = data.get("data", [])
        
        structured_results = []
        for author in results:
            name = author.get("name", "Unknown")
            aff_list = author.get("affiliations", [])
            affiliation = aff_list[0] if aff_list else "Unknown"
            citation_count = author.get("citationCount", 0)
            structured_results.append({
                "display": f"{name} ({affiliation}) - {citation_count} citations",
                "id": author.get("authorId"),
                "name": name,
                "citation_count": citation_count
            })
        structured_results.sort(key=lambda x: x["citation_count"], reverse=True)
        return structured_results
    except Exception as e:
        st.error(f"S2 Search Error: {e}")
        return []

@st.cache_data
def s2_get_data(author_id, limit=100):
    url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
    params = {"fields": "title,year,citationCount,authors,citations.authors", "limit": limit}
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 429:
            time.sleep(5)
            response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json().get("data", [])
    except Exception as e:
        st.error(f"S2 Fetch Error: {e}")
        return []

def s2_process_data(papers, target_author_id, exclude_self=False):
    collaborators = set()
    citing_authors = {} 
    target_author_id = str(target_author_id)
    
    for paper in papers:
        for author in paper.get("authors", []):
            a_id = author.get("authorId")
            if a_id and str(a_id) != target_author_id:
                collaborators.add(str(a_id))
        
        for citation in paper.get("citations", []):
            for author in citation.get("authors", []):
                a_id = author.get("authorId")
                name = author.get("name")
                if not a_id: continue
                a_id = str(a_id)
                
                if exclude_self and a_id == target_author_id: continue
                
                if a_id in citing_authors:
                    citing_authors[a_id]["count"] += 1
                else:
                    citing_authors[a_id] = {"name": name, "count": 1, "id": a_id}
                    
    data = []
    for a_id, info in citing_authors.items():
        is_collab = "Yes" if a_id in collaborators else "No"
        if a_id == target_author_id: is_collab = "Self"
        
        data.append({
            "Author Name": info["name"],
            "Citations": info["count"],
            "Collaborator?": is_collab,
            "Author ID": a_id
        })
        
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.sort_values(by="Citations", ascending=False).head(50)
        
        def get_category(row):
            if row["Author ID"] == target_author_id: return "Self-Citation"
            elif row["Collaborator?"] == "Yes": return "Co-author"
            else: return "Other"

        df["Category"] = df.apply(get_category, axis=1)
        df["Profile URL"] = df["Author ID"].apply(lambda x: f"https://www.semanticscholar.org/author/{x}" if x else "")
        
    return df, len(papers)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def get_author_color(category):
    if category == "Self-Citation": return "#EF553B" # Red
    elif category == "Co-author": return "#FFA15A"    # Orange
    else: return "#636EFA"                            # Blue

def style_dataframe(df):
    """
    Apply color styling to Author Name based on Category.
    """
    def color_name(row):
        color = get_author_color(row["Category"])
        return [f'color: {color}; font-weight: bold' if col == 'Author Name' else '' for col in row.index]

    return df.style.apply(color_name, axis=1)

def display_results(source_name, target_author, df_top, num_analyzed, exclude_self=False):
    st.markdown(f"### {source_name}")
    
    # 1. Metrics
    if not df_top.empty:
        total = df_top["Citations"].sum()
        self_cites = df_top[df_top["Category"] == "Self-Citation"]["Citations"].sum()
        co_cites = df_top[df_top["Category"] == "Co-author"]["Citations"].sum()
        
        self_pct = (self_cites / total * 100) if total else 0
        collab_pct = (co_cites / total * 100) if total else 0
        
        c1, c2 = st.columns(2)
        c1.metric("Analyzed", num_analyzed, help="Number of papers/works fetched")
        c2.metric("Total Citations (in sample)", total)
        
        c3, c4 = st.columns(2)
        c3.metric("% Self", f"{self_pct:.1f}%")
        c4.metric("% Co-Author", f"{collab_pct:.1f}%")
        
    # 2. Chart
    if not df_top.empty:
        fig = px.bar(
            df_top, 
            x="Author Name", 
            y="Citations", 
            color='Category',
            color_discrete_map={
                "Self-Citation": "#EF553B",
                "Co-author": "#FFA15A",
                "Other": "#636EFA",
                "(?)": "#D3D3D3"
            },
            title=f"Top Citing Authors ({source_name})",
            height=400
        )
        fig.update_layout(xaxis={'categoryorder':'total descending'}, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # 3. Table
        st.caption("Top 50 Citing Authors (Colored by Relationship)")
        
        # Apply Logic for columns
        # We need to display the Link separately
        
        # Configure Columns
        column_config = {
            "Author Name": st.column_config.TextColumn("Author Name"),
            "Profile URL": st.column_config.LinkColumn("Profile", display_text="🔗 View"),
            "Citations": st.column_config.NumberColumn("Citations", format="%d"),
            "Category": st.column_config.TextColumn("Rel.")
        }
        
        # Apply Styling
        # Note: st.dataframe supports 'style' object if passed directly? 
        # Actually st.dataframe supports pandas Styler object.
        
        styled_df = style_dataframe(df_top)
        
        st.dataframe(
            styled_df,
            column_config=column_config,
            column_order=["Author Name", "Citations", "Category", "Profile URL"],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No data found.")

# ==========================================
# 4. MAIN APP
# ==========================================

def main():
    st.set_page_config(page_title="Citation Analyzer (Dual Source)", layout="wide", page_icon="⚖️")
    st.title("⚖️ Citation Analyzer: OpenAlex vs Semantic Scholar")
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("Configuration")
        fetch_limit = st.slider("Analyze Top N Papers", 10, 200, 100, step=10)
        exclude_self = st.checkbox("Exclude Self-Citations", value=False)
    
    # --- Search Section ---
    st.subheader("1. Find Researcher")
    search_query = st.text_input("Enter Researcher Name", "Geoffrey Hinton")
    
    col_oa_search, col_s2_search = st.columns(2)
    
    oa_target = None
    s2_target = None
    
    if search_query:
        # OpenAlex Search
        with col_oa_search:
            st.info("OpenAlex Search")
            oa_candidates = oa_search_authors(search_query)
            if oa_candidates:
                oa_opts = [c["display"] for c in oa_candidates]
                oa_sel = st.selectbox("Select OA Profile:", oa_opts, key="oa_sel")
                for c in oa_candidates:
                    if c["display"] == oa_sel:
                        oa_target = c
                        break
            else:
                st.warning("No OA results.")
                
        # Semantic Scholar Search
        with col_s2_search:
            st.success("Semantic Scholar Search")
            s2_candidates = s2_search_authors(search_query)
            if s2_candidates:
                s2_opts = [c["display"] for c in s2_candidates]
                s2_sel = st.selectbox("Select S2 Profile:", s2_opts, key="s2_sel")
                for c in s2_candidates:
                    if c["display"] == s2_sel:
                        s2_target = c
                        break
            else:
                st.warning("No S2 results.")

    # --- Analysis Section ---
    if oa_target and s2_target:
        st.divider()
        if st.button("🚀 Run Comparative Analysis", type="primary"):
            st.header("Comparative Analysis")
            
            # --- OpenAlex Analysis ---
            st.subheader("1. OpenAlex Results")
            with st.status("Fetching OpenAlex Data...", expanded=True) as status:
                status.write(f"Fetching top {fetch_limit} works...")
                try:
                    # 1. Fetch Author Works (Top N)
                    oa_works_full = oa_get_author_works(oa_target["id"])
                    
                    # Sort locally to ensure Top Cited
                    oa_works_full.sort(key=lambda x: x.get("cited_by_count", 0), reverse=True)
                    
                    # Slice to "Same number of papers"
                    oa_works_analyzed = oa_works_full[:fetch_limit]
                    status.write(f"Analyzing Top {len(oa_works_analyzed)} papers (by citation count)...")
                    
                    # Collaborators from full history? Or just top?
                    # Using full history for detection is generally safer for "Is Collab?" check.
                    oa_collaborators = oa_extract_collaborators(oa_works_full, oa_target["id"])
                    
                    # 2. Fetch Citing Works FOR THESE PAPERS
                    target_work_ids = [w["id"] for w in oa_works_analyzed]
                    
                    oa_citing_works = []
                    if target_work_ids:
                        chunked_ids = [target_work_ids[i:i + 25] for i in range(0, len(target_work_ids), 25)]
                        url = "https://api.openalex.org/works"
                        
                        status.write("Fetching citations...")
                        for i, chunk in enumerate(chunked_ids):
                            ids_clean = [item.replace("https://openalex.org/", "") for item in chunk]
                            filter_str = "|".join(ids_clean)
                            params = {
                                "filter": f"cites:{filter_str}",
                                "per-page": 200,
                                "cursor": "*" 
                            }
                            
                            status.write(f"Fetching citations for batch {i//25 + 1}...")
                            
                            while True:
                                try:
                                    r = requests.get(url, headers=HEADERS, params=params)
                                    r.raise_for_status()
                                    d = r.json()
                                    res = d.get("results", [])
                                    if not res: break
                                    oa_citing_works.extend(res)
                                    meta = d.get("meta", {})
                                    next_c = meta.get("next_cursor")
                                    if not next_c: break
                                    params["cursor"] = next_c
                                except Exception as e:
                                    st.warning(f"Error fetching batch: {e}")
                                    break
                    
                    # 3. Process
                    df_oa = oa_process_data(oa_citing_works, oa_target["id"], oa_collaborators, exclude_self)
                    
                    status.update(label="OpenAlex Analysis Complete", state="complete", expanded=False)
                    
                    display_results("OpenAlex Results", oa_target, df_oa, len(oa_works_analyzed), exclude_self)
                    
                except Exception as e:
                    st.error(f"OA Analysis Failed: {e}")

            st.divider()

            # --- Semantic Scholar Analysis ---
            st.subheader("2. Semantic Scholar Results")
            with st.status("Fetching Semantic Scholar Data...", expanded=True) as status:
                status.write("Fetching papers...")
                try:
                    # 1. Fetch Papers
                    # Fetch MORE than limit to ensure we can sort by citation count and pick the best
                    # S2 doesn't sort by citation count by default
                    safe_fetch = min(500, fetch_limit * 5) 
                    s2_papers_raw = s2_get_data(s2_target["id"], limit=safe_fetch)
                    
                    # Sort by citationCount descending
                    s2_papers_raw.sort(key=lambda x: x.get("citationCount", 0), reverse=True)
                    
                    # Slice to match the requested limit
                    s2_papers = s2_papers_raw[:fetch_limit]
                    
                    status.write(f"Analyzing Top {len(s2_papers)} papers (by citation count)...")
                    
                    # 2. Process
                    df_s2, num_papers = s2_process_data(s2_papers, s2_target["id"], exclude_self)
                    
                    status.update(label="Semantic Scholar Analysis Complete", state="complete", expanded=False)
                    
                    display_results("Semantic Scholar Results", s2_target, df_s2, len(s2_papers), exclude_self)
                    
                except Exception as e:
                    st.error(f"S2 Analysis Failed: {e}")

if __name__ == "__main__":
    main()
