from cherry.cherry_dashboard import render_dashboard
import streamlit as st

st.markdown("""
<style>
    div[data-testid="stAppDeployButton"] {
        display: none !important;
    }
    div[data-testid="stDecoration"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)
st.logo('https://ahaslides.com/wp-content/uploads/2025/05/logo-full.png')
render_dashboard()
