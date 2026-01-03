def inject_css(st):
    BR6_BLUE = "#214c6e"
    st.markdown(f"""
<style>
:root {{
  --kbm-blue: {BR6_BLUE};
  --kbm-bg: #f4f7fb;
  --kbm-card: #ffffff;
  --kbm-muted: #6b7280;
  --kbm-border: rgba(0,0,0,.08);
}}
.stApp {{
  background: radial-gradient(1200px 600px at 10% 0%, #cfe7ff 0%, var(--kbm-bg) 55%, #eef4ff 100%);
}}
.kbm-topbar {{
  border: 1px solid var(--kbm-border);
  background: rgba(255,255,255,.75);
  backdrop-filter: blur(10px);
  border-radius: 18px;
  padding: 14px 16px;
  margin-bottom: 12px;
}}
.kbm-brand {{
  display:flex;
  gap:12px;
  align-items:center;
}}
.kbm-brand img {{ height: 44px; width:auto; }}
.kbm-title {{ font-size: 22px; font-weight: 900; margin:0; }}
.kbm-sub {{ color: var(--kbm-muted); margin-top: 2px; }}
.kbm-chip {{
  display:inline-flex;
  align-items:center;
  gap:8px;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(33,76,110,.10);
  color: var(--kbm-blue);
  font-weight: 900;
  border: 1px solid rgba(33,76,110,.15);
}}
.kbm-card {{
  border: 1px solid var(--kbm-border);
  background: var(--kbm-card);
  border-radius: 18px;
  padding: 14px;
}}
.kbm-meta {{ color: var(--kbm-muted); font-size: 12px; }}
/* input rounding */
div[data-baseweb="input"] input, div[data-baseweb="select"] > div {{
  border-radius: 12px !important;
}}
#MainMenu {{visibility:hidden;}}
footer {{visibility:hidden;}}
</style>
""", unsafe_allow_html=True)
