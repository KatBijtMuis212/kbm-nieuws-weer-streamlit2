# KbM Nieuws (Streamlit v2)

## Online zetten (Streamlit Community Cloud)
1) Upload alles naar GitHub (incl. `pages/` en `.streamlit/`).
2) Streamlit Cloud → New app → selecteer repo → Main file: `app.py`.
3) Optioneel privé (wachtwoord):
   In Streamlit Secrets:
   APP_PASSWORD="jouw-wachtwoord"

## Lokaal
pip install -r requirements.txt
streamlit run app.py
