# style.py — centrale CSS injectie voor KbM Streamlit

import streamlit as st

def inject_css():
    css = """
    <style>
    /* Algemene layout */
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #f5f7fa;
        color: #0b1b2b;
    }

    /* Cards */
    .kbm-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 24px;
        box-shadow: 0 6px 24px rgba(0,0,0,0.06);
    }

    /* Meta */
    .kbm-meta {
        font-size: 0.85rem;
        color: #516072;
        margin-top: 4px;
    }

    /* Hero */
    .kbm-hero-title a {
        color: #0b1b2b;
        text-decoration: none;
    }
    .kbm-hero-title a:hover {
        text-decoration: underline;
    }

    /* Thumbnails lijst */
    .kbm-thumbs {
        display: flex;
        flex-direction: column;
        gap: 12px;
    }

    .kbm-thumbrow {
        display: grid;
        grid-template-columns: 96px 1fr;
        gap: 12px;
        align-items: center;
        background: #ffffff;
        border-radius: 10px;
        padding: 8px;
    }

    .kbm-thumbimg {
        width: 96px;
        height: 64px;
        object-fit: cover;
        border-radius: 8px;
        background: #e5e9f0;
    }

    .kbm-thumbtitle {
        font-size: 0.95rem;
        font-weight: 600;
        margin: 0;
    }

    .kbm-thumbtitle a {
        color: #0b1b2b;
        text-decoration: none;
    }

    .kbm-thumbtitle a:hover {
        text-decoration: underline;
    }

    .kbm-thumbmeta {
        font-size: 0.8rem;
        color: #6b7a8c;
        margin-top: 2px;
    }

    /* Buttons */
    button {
        border-radius: 8px !important;
    }

    /* Expander */
    details > summary {
        font-weight: 600;
    }

    /* Mobiel */
    @media (max-width: 768px) {
        .kbm-thumbrow {
            grid-template-columns: 72px 1fr;
        }
        .kbm-thumbimg {
            width: 72px;
            height: 56px;
        }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
