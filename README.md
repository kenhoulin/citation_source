# 🎓 Citation Analyzer: OpenAlex vs Semantic Scholar

A Streamlit application that analyzes citation patterns for researchers using data from **OpenAlex** and **Semantic Scholar**. It helps identify **Collaborators** vs. **Independent Citations** and visualizes the results side-by-side.

## Features

*   **Dual-Source Comparison**: Search for a researcher on both OpenAlex and Semantic Scholar simultaneously.
*   **Collaboration Detection**: Automatically identifies co-authors to distinguish independent citations from collaborative circles.
*   **Self-Citation Analysis**: Flags self-citations.
*   **Visualizations**: interactive bar charts and color-coded data tables (Red=Self, Orange=Co-author, Blue=Others).
*   **Direct Links**: One-click access to researcher profiles.

## How to Run Locally

1.  **Clone the repository** (or download files).
2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the app**:
    ```bash
    streamlit run app.py
    ```

## Deployment (Free)

This app is ready for **Streamlit Community Cloud**:

1.  Push this code to a **GitHub** repository.
2.  Go to [share.streamlit.io](https://share.streamlit.io/).
3.  Log in (with GitHub) and click **"New app"**.
4.  Select your repository and the `app.py` file.
5.  Click **"Deploy"**!
