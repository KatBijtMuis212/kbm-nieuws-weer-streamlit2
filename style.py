import streamlit as st

BR6_BLUE = "#214c6e"


def inject_css(st_obj=st):
    st_obj.markdown(
        f"""
<style>
/* Base */
html, body, [class*="css"] {{
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}}
a {{ color: {BR6_BLUE}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.kbm-topbar {{
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(244,247,251,.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(0,0,0,.06);
  padding: 12px 8px;
  margin-bottom: 10px;
}}
.kbm-brand {{
  display: flex;
  gap: 12px;
  align-items: center;
}}
.kbm-brand img {{
  width: 64px;
  height: auto;
  border-radius: 10px;
}}
.kbm-title {{
  font-weight: 900;
  font-size: 22px;
  line-height: 1.1;
}}
.kbm-sub {{
  color: rgba(15,23,42,.70);
  font-size: 13px;
  margin-top: 2px;
}}

.kbm-card {{
  border: 1px solid rgba(0,0,0,.08);
  background: #fff;
  border-radius: 18px;
  padding: 14px 14px;
  box-shadow: 0 8px 22px rgba(0,0,0,.06);
}}
.kbm-meta {{
  color: rgba(15,23,42,.65);
  font-size: 12px;
  margin-top: 6px;
}}

/* Thumbnail rows (mobile friendly) */
.kbm-thumbs {{ margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }}
.kbm-thumbrow{{
  display:flex; gap:12px; align-items:flex-start;
  padding:10px; border-radius:14px;
  background:rgba(0,0,0,.06);
}}
.kbm-thumbimg{{
  width:86px; height:86px; border-radius:12px;
  object-fit:cover;
  flex:0 0 86px;
  background:#e5e7eb;
  box-shadow:0 6px 16px rgba(0,0,0,.18);
}}
.kbm-thumbtext{{ flex:1 1 auto; min-width:0; }}
.kbm-thumbtitle{{
  font-weight:800; line-height:1.15;
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  overflow:hidden;
  margin:0;
}}
.kbm-thumbmeta{{ opacity:.75; font-size:12px; margin-top:6px; }}

@media (max-width: 768px){{
  .kbm-brand img {{ width: 56px; }}
  .kbm-thumbimg{{ width:78px; height:78px; flex-basis:78px; }}
  .kbm-thumbrow{{ padding:9px; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


/* --- Contrast fix (mobile/preview lists) --- */
.kbm-thumbrow { background: #ffffff !important; }
.kbm-thumbtitle, .kbm-thumbtitle a { color: #0b1b2b !important; opacity: 1 !important; }
.kbm-thumbmeta, .kbm-meta { color: #516072 !important; opacity: 1 !important; }
.kbm-card { background: #ffffff !important; }
