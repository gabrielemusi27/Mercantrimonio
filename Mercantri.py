import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import os

# =========================================================
# CONFIG
# =========================================================
SNAPSHOT_FILE = "offerte_snapshot.parquet"

# =========================================================
# CONFIGURAZIONE PAGINA
# =========================================================
st.set_page_config(page_title="Mercante in Fiera - Matrimonio", layout="wide")

# CSS ANTI-JUMP: Blocca l'altezza dei container e stabilizza lo scroll
st.markdown("""
    <style>
    /* Mantiene i container stabili durante il refresh */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 220px;
    }
    /* Disabilita animazioni di scroll che causano jitter nei refresh automatici */
    html {
        scroll-behavior: auto !important;
    }
    /* Estetica dei popover per mobile */
    div[data-testid="stPopoverBody"] {
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# AUTH GOOGLE
# =========================================================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"]["service_account"],
    scopes=scope
)
gc = gspread.authorize(creds)

SPREADSHEET_ID = "1g_FXSodJoWocTc8Ni12sBSDYviQ7oAQBDipVsLzfw5w"
sh = gc.open_by_key(SPREADSHEET_ID)

# =========================================================
# FUNZIONI GOOGLE SHEETS
# =========================================================

def forza_scaricamento_offerte():
    """SOLO ADMIN – legge da Google Sheets e salva snapshot locale"""
    ws = sh.worksheet("Offerte")
    df = pd.DataFrame(ws.get_all_records())
    df.to_parquet(SNAPSHOT_FILE, index=False)
    return df

@st.cache_data(ttl=5)
def get_offerte_snapshot():
    """TUTTI – legge SOLO da file locale, ZERO API"""
    if not os.path.exists(SNAPSHOT_FILE):
        return pd.DataFrame(
            columns=["Tavolo", "Carta", "Offerta", "Nome Utente"]
        )
    return pd.read_parquet(SNAPSHOT_FILE)

def append_row(name, row_dict):
    """WRITE API – ok"""
    ws = sh.worksheet(name)
    ws.append_row(list(row_dict.values()))

# =========================================================
# CARICAMENTO DATI STATICI
# =========================================================
if 'df_tavoli' not in st.session_state or 'df_carte' not in st.session_state:
    with st.spinner("Sincronizzazione tavoli e carte..."):
        ws_t = sh.worksheet("Tavoli")
