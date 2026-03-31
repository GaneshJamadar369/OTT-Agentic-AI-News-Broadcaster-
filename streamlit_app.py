import streamlit as st
import os
import json

# --- HACK: Install Playwright Chromium on the Cloud Server ---
@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")
install_playwright()
# -------------------------------------------------------------

# Assuming you have a function called run_industry_pipeline(url) in main.py
from main import run_industry_pipeline 

st.set_page_config(page_title="LOQO AI Newsroom", page_icon="📺", layout="centered")

st.title("📺 LOQO AI: Dynamic News Screenplay Generator")
st.markdown("Enter a public news URL below to autonomously generate a TV broadcast screenplay.")

url_input = st.text_input("News Article URL:", placeholder="https://www.bbc.com/news/...")

if st.button("Generate Broadcast Package"):
    if not url_input:
        st.warning("Please enter a URL first.")
    else:
        with st.spinner("Scraping, Writing, and Visualizing (This takes 10-15 seconds)..."):
            try:
                # Run the God-Tier pipeline
                result_json = run_industry_pipeline(url_input)
                
                if result_json:
                    st.success("Screenplay Generated Successfully!")
                    
                    # Show the JSON output nicely
                    st.subheader("Final Broadcast Plan (JSON)")
                    st.json(result_json)
                else:
                    st.error("Pipeline failed: Content was blocked or invalid.")
                
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
