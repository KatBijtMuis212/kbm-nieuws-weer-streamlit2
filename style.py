import streamlit as st

def inject_css():
    st.markdown(
        '''
        <style>
          :root{
            --kbm-blue:#214c6e;
            --kbm-bg:#0b1220;
            --kbm-card:#0f1b33;
            --kbm-card2:#101d3a;
            --kbm-border:rgba(255,255,255,.10);
            --kbm-text:#e9f0ff;
            --kbm-muted:rgba(233,240,255,.70);
          }

          .kbm-shell{max-width:1180px;margin:0 auto;padding:6px 6px 20px;}
          .kbm-topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0 12px;}
          .kbm-brand{display:flex;align-items:center;gap:10px;}
          .kbm-brand img{height:34px;width:auto;display:block;}
          .kbm-pill{display:inline-flex;align-items:center;gap:8px;padding:8px 10px;border:1px solid var(--kbm-border);border-radius:999px;background:rgba(255,255,255,.04);}
          .kbm-btnlike{display:inline-flex;align-items:center;gap:8px;padding:8px 10px;border-radius:10px;border:1px solid var(--kbm-border);background:rgba(255,255,255,.04);}

          .kbm-card{border:1px solid var(--kbm-border);border-radius:18px;background:rgba(255,255,255,.03);padding:14px 14px 12px;}
          .kbm-card h3{margin:0 0 10px;}
          .kbm-meta{color:var(--kbm-muted);font-size:.92rem;}
          .kbm-hero-title a{color:var(--kbm-text);text-decoration:none;}
          .kbm-hero-title a:hover{text-decoration:underline;}

          .kbm-thumbs{display:flex;flex-direction:column;gap:10px;margin-top:6px;}
          .kbm-thumbrow{display:grid;grid-template-columns:84px 1fr;gap:10px;align-items:start;padding:10px;border:1px solid var(--kbm-border);border-radius:14px;background:rgba(255,255,255,.02);}
          .kbm-thumbimg{width:84px;height:64px;object-fit:cover;border-radius:10px;display:block;background:rgba(255,255,255,.06);}
          .kbm-thumbtitle{margin:0;font-weight:700;line-height:1.15;}
          .kbm-thumbtitle a{color:var(--kbm-text);text-decoration:none;}
          .kbm-thumbtitle a:hover{text-decoration:underline;}
          .kbm-thumbmeta{margin-top:4px;color:var(--kbm-muted);font-size:.90rem;}

          /* Mobile: thumbs should stay compact under the hero */
          @media (max-width: 780px){
            .kbm-shell{padding:2px 2px 14px;}
            .kbm-thumbrow{grid-template-columns:76px 1fr;padding:9px;}
            .kbm-thumbimg{width:76px;height:58px;}
          }
        </style>
        ''',
        unsafe_allow_html=True,
    )
