import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
from streamlit_autorefresh import st_autorefresh # Aggiungere a requirements.txt

# 1. Configurazione Pagina
st.set_page_config(page_title="Mercante in Fiera - Matrimonio", layout="wide")

# --- AUTOREFRESH (Ogni 10 secondi) ---
st_autorefresh(interval=10000, limit=None, key="mercantrimonio_refresh")

# --- STATO GLOBALE CONDIVISO (Sincronizza tutti gli utenti) ---
@st.cache_resource
def get_global_state():
    # MODIFICA: L'asta ora nasce APERTA di default
    return {"asta_aperta": True}

global_state = get_global_state()

# --- AUTH GOOGLE ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["connections"]["gsheets"]["service_account"], scopes=scope)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1g_FXSodJoWocTc8Ni12sBSDYviQ7oAQBDipVsLzfw5w"
sh = gc.open_by_key(SPREADSHEET_ID)

# --- FUNZIONI DI SCRITTURA E LETTURA ---

@st.cache_data(ttl=60)
def load_offerte(force=False):
    """Carica le offerte. Se force=True, ignora la cache."""
    ws = sh.worksheet("Offerte")
    return pd.DataFrame(ws.get_all_records())

def append_row(name, row_dict):
    ws = sh.worksheet(name)
    ws.append_row(list(row_dict.values()))

# --- CARICAMENTO DATI STATICI (SOLO UNA VOLTA NELLA SESSIONE) ---
if 'df_tavoli' not in st.session_state or 'df_carte' not in st.session_state:
    with st.spinner("Sincronizzazione tavoli e carte..."):
        ws_t = sh.worksheet("Tavoli")
        st.session_state.df_tavoli = pd.DataFrame(ws_t.get_all_records())
        ws_c = sh.worksheet("Carte")
        st.session_state.df_carte = pd.DataFrame(ws_c.get_all_records())

df_tavoli = st.session_state.df_tavoli
df_carte = st.session_state.df_carte

# --- GESTIONE LOGIN ---
if 'user_logged' not in st.session_state:
    st.session_state.user_logged = False

if not st.session_state.user_logged:
    st.title("🎫 Benvenuti al Mercantrimonio!")
    with st.form("login_form"):
        nome = st.text_input("Inserisci il tuo Nome")
        tavolo = st.selectbox("Seleziona il tuo Tavolo", df_tavoli["Nome Tavolo"].unique())
        if st.form_submit_button("Entra nell'Asta"):
            if nome:
                st.session_state.user_logged = True
                st.session_state.username = nome.strip()
                st.session_state.tavolo = tavolo
                st.rerun()
            else:
                st.error("Inserisci il tuo nome per partecipare.")
else:
    # --- LOGICA ASTA BLOCCATA ---
    asta_bloccata = not global_state["asta_aperta"]

    # --- PANNELLO ADMIN (Solo per Federica Giunta) ---
    if st.session_state.username == "Federica Giunta":
        with st.sidebar.expander("🛠 PANNELLO DI CONTROLLO", expanded=True):
            st.write(f"L'asta è: **{'APERTA 🟢' if not asta_bloccata else 'CHIUSA 🔴'}**")
            
            # Logica pulsanti: se aperta mostra "Chiudi", se chiusa mostra "Avvia"
            if not asta_bloccata:
                if st.button("🔴 CHIUDI ASTA PER TUTTI"):
                    global_state["asta_aperta"] = False
                    st.cache_data.clear()
                    st.rerun()
            else:
                if st.button("🟢 AVVIA ASTA PER TUTTI"):
                    global_state["asta_aperta"] = True
                    st.cache_data.clear()
                    st.rerun()
            
            st.divider()
            if st.button("📊 GENERA REPORT FINALE"):
                st.session_state.show_report = True
            
            if st.button("🐷 Premi per elevare la vita di un povero maialino indifeso!"):
                del st.session_state.df_tavoli
                del st.session_state.df_carte
                st.rerun()

    # --- LOGICA REPORT FINALE (Greedy/Cascata con Esclusi) ---
    if st.session_state.get('show_report', False):
        st.header("🏆 Risultati Ufficiali")
        
        with
