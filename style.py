import streamlit as st

BR6_BLUE = "#214c6e"

def inject_css(st_obj=st, dark: bool = False):
    bg = "#0b1220" if dark else "#ffffff"
    fg = "#e5e7eb" if dark else "#0f172a"
    card = "rgba(255,255,255,.06)" if dark else "#fff"
    border = "rgba(255,255,255,.10)" if dark else "rgba(0,0,0,.08)"
    muted = "rgba(229,231,235,.70)" if dark else "rgba(15,23,42,.65)"
    rowbg = "rgba(255,255,255,.08)" if dark else "rgba(0,0,0,.06)"

    st_obj.markdown(f"""
<style>
:root {{
  --kbm-bg: {bg};
  --kbm-fg: {fg};
  --kbm-card: {card};
  --kbm-border: {border};
  --kbm-muted: {muted};
  --kbm-row: {rowbg};
  --kbm-blue: {BR6_BLUE};
}}

html, body, [data-testid="stAppViewContainer"] {{
  background: var(--kbm-bg) !important;
  color: var(--kbm-fg) !important;
}}
a {{ color: var(--kbm-blue); text-decoration: none; }}
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
{".kbm-topbar{background: rgba(15,23,42,.72); border-bottom: 1px solid rgba(255,255,255,.10);}" if dark else ""}

.kbm-brand {{
  display: flex;
  gap: 12px;
  align-items: center;
}}
.kbm-brand img {{
  width: 64px;
  height: auto;
  border-radius: 10px;
  background: #fff;
}}
.kbm-title {{
  font-weight: 900;
  font-size: 22px;
  line-height: 1.1;
  color: var(--kbm-fg);
}}
.kbm-sub {{
  color: var(--kbm-muted);
  font-size: 13px;
  margin-top: 2px;
}}

.kbm-card {{
  border: 1px solid var(--kbm-border);
  background: var(--kbm-card);
  border-radius: 18px;
  padding: 14px 14px;
  box-shadow: 0 10px 26px rgba(0,0,0,.10);
}}
.kbm-meta {{
  color: var(--kbm-muted);
  font-size: 12px;
  margin-top: 6px;
}}

.kbm-new {{
  display:inline-block;
  font-size: 11px;
  font-weight: 900;
  padding: 3px 8px;
  border-radius: 999px;
  margin-right: 8px;
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 8px 18px rgba(0,0,0,.18);
}}
{".kbm-new{background:#f59e0b;color:#111827;}" if dark else ""}

/* Thumbnail rows */
.kbm-thumbs {{ margin-top: 10px; display: flex; flex-direction: column; gap: 10px; }}
.kbm-thumbrow{{
  display:flex; gap:12px; align-items:flex-start;
  padding:10px; border-radius:14px;
  background: var(--kbm-row);
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
  color: var(--kbm-fg);
}}
.kbm-thumbtitle a {{ color: var(--kbm-fg) !important; }}
.kbm-thumbmeta{{ opacity:.75; font-size:12px; margin-top:6px; color: var(--kbm-muted); }}

.kbm-exp-title {{
  font-weight: 900;
  font-size: 16px;
  margin-bottom: 6px;
}}
</style>
""", unsafe_allow_html=True)
