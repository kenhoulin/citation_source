import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time

# --- Big Bend Palette ---
PALETTE = {
    "DeepBlue": "#1E3F5F",
    "BlueGrey": "#597C8B",
    "Sage": "#A8C6C3",
    "Sand": "#F2D8B2",
    "Terracotta": "#B38F5F"
}

# --- Constants & Config ---
HEADERS = {
    "User-Agent": "mailto:test@example.com"
}

# --- Custom CSS for "Sharp" UI ---
def apply_theme():
    st.markdown(f"""
    <style>
    /* Sharp Headers */
    h1, h2, h3 {{
        font-family: 'Segoe UI', sans-serif;
        color: {PALETTE['DeepBlue']};
        border-bottom: 2px solid {PALETTE['Terracotta']};
        padding-bottom: 10px;
        margin-bottom: 20px;
    }}
    
    /* Global Background Accent */
    .stApp {{
        background-color: #FAFAFA;
    }}
    
    /* Card-like Containers */
    div[data-testid="stVerticalBlock"] > div:has(div[data-testid="stMarkdownContainer"]) {{
        /* Adding subtle distinction if needed, but keeping it clean */
    }}
    
    /* Button Styling */
    div.stButton > button {{
        background-color: {PALETTE['DeepBlue']};
        color: white;
        border: none;
        border-radius: 0px; /* SHARP edges */
        padding: 10px 24px;
        font-weight: bold;
    }}
    div.stButton > button:hover {{
        background-color: {PALETTE['BlueGrey']};
        color: white;
        border: 2px solid {PALETTE['DeepBlue']};
    }}
    
    /* Metrics */
    div[data-testid="stMetricValue"] {{
        color: {PALETTE['Terracotta']};
    }}
    
    /* Info/Warning Boxes */
    div[data-testid="stStatusWidget"] {{
        border: 1px solid {PALETTE['BlueGrey']};
        border-radius: 0px;
    }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. OPENALEX FUNCTIONS
# ==========================================

@st.cache_data
def oa_search_authors(query):
    if not query: return []
    url = f"https://api.openalex.org/authors?search={query}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        
        structured_results = []
        for author in results:
            name = author.get("display_name", "Unknown")
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
    if author_id.startswith("https://openalex.org/"):
        author_id = author_id.replace("https://openalex.org/", "")
    url = "https://api.openalex.org/works"
    params = {"filter": f"author.id:{author_id}", "per-page": 200, "cursor": "*"}
    all_works = []
    try:
        while True:
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if not results: break
            all_works.extend(results)
            meta = data.get("meta", {})
            next_cursor = meta.get("next_cursor")
            if not next_cursor: break
            params["cursor"] = next_cursor
            if len(all_works) > 5000: break
    except Exception as e:
        st.error(f"OA Works Error: {e}")
        return []
    return all_works

def oa_extract_collaborators(author_works, target_author_id):
    if target_author_id.startswith("https://openalex.org/"):
        target_author_id = target_author_id.replace("https://openalex.org/", "")
    collaborators = set()
    for work in author_works:
        for authorship in work.get("authorships", []):
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
        for authorship in work.get("authorships", []):
            author = authorship.get("author", {})
            a_id = author.get("id")
            a_name = author.get("display_name")
            if not a_id: continue
            clean_id = a_id.replace("https://openalex.org/", "") if a_id.startswith("https://openalex.org/") else a_id
            
            if exclude_self and clean_id == target_author_id: continue
            
            if clean_id in author_counts:
                author_counts[clean_id]["count"] += 1
            else:
                author_counts[clean_id] = {"name": a_name, "count": 1, "id": clean_id}
                
    data = []
    for a_id, info in author_counts.items():
        is_collab = "Yes" if a_id in collaborator_ids else "No"
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
    if category == "Self-Citation": return PALETTE['Terracotta']
    elif category == "Co-author": return PALETTE['BlueGrey']
    else: return PALETTE['Sage'] # For Others (more distinct than Sage? Maybe DeepBlue? No, too similar to header)
    # Using Sage for 'Others' is subtle. Let's try DeepBlue for 'Others' if Sage is too light?
    # No, keep distinct.

def style_dataframe(df):
    def color_name(row):
        color = get_author_color(row["Category"])
        # If color is 'Sage' (#A8C6C3), it works on white.
        return [f'color: {color}; font-weight: bold' if col == 'Author Name' else '' for col in row.index]
    return df.style.apply(color_name, axis=1)

def display_results(source_name, target_author, df_top, num_analyzed, exclude_self=False):
    # Sharp visual separation
    st.markdown(f"### {source_name}")
    st.markdown("---") # Sharp divider
    
    if not df_top.empty:
        total = df_top["Citations"].sum()
        self_cites = df_top[df_top["Category"] == "Self-Citation"]["Citations"].sum()
        co_cites = df_top[df_top["Category"] == "Co-author"]["Citations"].sum()
        self_pct = (self_cites / total * 100) if total else 0
        collab_pct = (co_cites / total * 100) if total else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Analyzed Works", num_analyzed)
        c2.metric("Total Citations", total)
        c3.metric("Citation Density", f"{(total/num_analyzed):.1f}" if num_analyzed else "0")
        
        # Chart with Big Bend Colors
        fig = px.bar(
            df_top, 
            x="Author Name", 
            y="Citations", 
            color='Category',
            color_discrete_map={
                "Self-Citation": PALETTE['Terracotta'],
                "Co-author": PALETTE['BlueGrey'],
                "Other": PALETTE['Sage'], # or DeepBlue?
                "(?)": "#D3D3D3"
            },
            title="Citation Distribution by Relationship",
            height=400
        )
        # Update layout for sharp look
        fig.update_layout(
            font_family="Segoe UI",
            title_font_family="Segoe UI",
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            xaxis={'categoryorder':'total descending', 'showgrid': False},
            yaxis={'showgrid': True, 'gridcolor': '#EFEFEF'},
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.caption("Top 50 Citing Authors")
        column_config = {
            "Author Name": st.column_config.TextColumn("Author Name"),
            "Profile URL": st.column_config.LinkColumn("Profile", display_text="🔗 View"),
            "Citations": st.column_config.NumberColumn("Citations", format="%d"),
            "Category": st.column_config.TextColumn("Rel.")
        }
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
    st.set_page_config(page_title="Citation Explorer", layout="wide", page_icon="🏜️")
    apply_theme()
    
    st.title("🏜️ Citation Explorer")
    st.markdown(f"**OpenAlex** and **Semantic Scholar** working together to map research impact.")

    with st.sidebar:
        st.header("Settings")
        fetch_limit = st.slider("Analyze Top N Papers", 10, 200, 100, step=10)
        exclude_self = st.checkbox("Exclude Self-Citations", value=False)
        st.info("Uses **Big Bend** Palette: Deep Blue, Terracotta, Sage, Sand.")
    
    st.header("1. Identify Researcher")
    search_query = st.text_input("Enter Researcher Name", "")
    
    c1, c2 = st.columns(2)
    oa_target, s2_target = None, None
    
    if search_query:
        with c1:
            st.markdown(f"#### OpenAlex Profile")
            oa_res = oa_search_authors(search_query)
            if oa_res:
                sel = st.selectbox("Select OA Match:", [c["display"] for c in oa_res], key="oa")
                for c in oa_res:
                    if c["display"] == sel: oa_target = c; break
        with c2:
            st.markdown(f"#### Semantic Scholar Profile")
            s2_res = s2_search_authors(search_query)
            if s2_res:
                sel = st.selectbox("Select S2 Match:", [c["display"] for c in s2_res], key="s2")
                for c in s2_res:
                    if c["display"] == sel: s2_target = c; break

    if oa_target and s2_target:
        st.divider()
        if st.button("Generate Explorer View", type="primary"):
            
            c_oa, c_s2 = st.columns(2)
            
            with c_oa:
                with st.status("Querying OpenAlex...", expanded=True) as status:
                    status.write(f"Analyzing top {fetch_limit} papers...")
                    try:
                        oa_works_full = oa_get_author_works(oa_target["id"])
                        oa_works_full.sort(key=lambda x: x.get("cited_by_count", 0), reverse=True)
                        oa_works_analyzed = oa_works_full[:fetch_limit]
                        
                        oa_collabs = oa_extract_collaborators(oa_works_full, oa_target["id"])
                        target_ids = [w["id"] for w in oa_works_analyzed]
                        
                        oa_citing = []
                        if target_ids:
                            chunked = [target_ids[i:i+25] for i in range(0, len(target_ids), 25)]
                            url = "https://api.openalex.org/works"
                            for i, chunk in enumerate(chunked):
                                status.write(f"Fetching citations batch {i+1}...")
                                ids_clean = [x.replace("https://openalex.org/", "") for x in chunk]
                                params = {"filter": f"cites:{'|'.join(ids_clean)}", "per-page": 200, "cursor": "*"}
                                while True:
                                    try:
                                        r = requests.get(url, headers=HEADERS, params=params); r.raise_for_status()
                                        d = r.json(); res = d.get("results", []); oa_citing.extend(res) 
                                        if not d.get("meta", {}).get("next_cursor"): break
                                        params["cursor"] = d.get("meta", {}).get("next_cursor")
                                    except: break

                        df_oa = oa_process_data(oa_citing, oa_target["id"], oa_collabs, exclude_self)
                        status.update(label="OpenAlex Ready", state="complete", expanded=False)
                        display_results("OpenAlex", oa_target, df_oa, len(oa_works_analyzed), exclude_self)
                    except Exception as e: st.error(str(e))

            with c_s2:
                with st.status("Querying Semantic Scholar...", expanded=True) as status:
                    status.write(f"Analyzing top {fetch_limit} papers...")
                    try:
                        limit = min(500, fetch_limit * 5)
                        s2_raw = s2_get_data(s2_target["id"], limit=limit)
                        s2_raw.sort(key=lambda x: x.get("citationCount", 0), reverse=True)
                        s2_papers = s2_raw[:fetch_limit]
                        
                        df_s2, num = s2_process_data(s2_papers, s2_target["id"], exclude_self)
                        status.update(label="Semantic Scholar Ready", state="complete", expanded=False)
                        display_results("Semantic Scholar", s2_target, df_s2, len(s2_papers), exclude_self)
                    except Exception as e: st.error(str(e))

if __name__ == "__main__":
    main()
