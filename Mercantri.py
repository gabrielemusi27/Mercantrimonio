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

# CSS ANTI-JUMP: Stabilizza l'altezza e blocca lo scroll jitter
st.markdown("""
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 220px;
    }
    html {
        scroll-behavior: auto !important;
    }
    div[data-testid="stPopoverBody"] {
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# AUTH GOOGLE
# =========================================================
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["connections"]["gsheets"]["service_account"], scopes=scope)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1g_FXSodJoWocTc8Ni12sBSDYviQ7oAQBDipVsLzfw5w"
sh = gc.open_by_key(SPREADSHEET_ID)

# =========================================================
# FUNZIONI GOOGLE SHEETS
# =========================================================
def forza_scaricamento_offerte():
    ws = sh.worksheet("Offerte")
    df = pd.DataFrame(ws.get_all_records())
    df.to_parquet(SNAPSHOT_FILE, index=False)
    return df

@st.cache_data(ttl=5)
def get_offerte_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return pd.DataFrame(columns=["Tavolo", "Carta", "Offerta", "Nome Utente"])
    return pd.read_parquet(SNAPSHOT_FILE)

def append_row(name, row_dict):
    ws = sh.worksheet(name)
    ws.append_row(list(row_dict.values()))

# =========================================================
# CARICAMENTO DATI STATICI
# =========================================================
if 'df_tavoli' not in st.session_state or 'df_carte' not in st.session_state:
    with st.spinner("Sincronizzazione..."):
        st.session_state.df_tavoli = pd.DataFrame(sh.worksheet("Tavoli").get_all_records())
        st.session_state.df_carte = pd.DataFrame(sh.worksheet("Carte").get_all_records())
        if 'offerte_locali' not in st.session_state:
            st.session_state.offerte_locali = {}

df_tavoli = st.session_state.df_tavoli
df_carte = st.session_state.df_carte

# =========================================================
# LOGIN
# =========================================================
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
    if "asta_aperta" not in st.session_state:
        st.session_state.asta_aperta = True
    
    asta_bloccata = not st.session_state.asta_aperta

    # Pannello Admin
    if st.session_state.username == "Federica Giunta":
        with st.sidebar.expander("🛠 PANNELLO DI CONTROLLO", expanded=True):
            st.write(f"L'asta è: **{'APERTA 🟢' if not asta_bloccata else 'CHIUSA 🔴'}**")
            if st.button("🔄 AGGIORNA OFFERTE PER TUTTI", use_container_width=True, type="primary"):
                forza_scaricamento_offerte()
                st.cache_data.clear()
                st.success("Sincronizzato!")
            if not asta_bloccata:
                if st.button("🔴 CHIUDI ASTA", use_container_width=True):
                    st.session_state.asta_aperta = False
                    st.rerun()
            else:
                if st.button("🟢 AVVIA ASTA", use_container_width=True):
                    st.session_state.asta_aperta = True
                    st.rerun()
            if st.button("📊 REPORT", use_container_width=True):
                st.session_state.show_report = True

    # Report (Stessa logica di prima)
    if st.session_state.get('show_report', False):
        st.header("🏆 Risultati")
        # ... (Logica report omessa per brevità, resta uguale)
        if st.button("Chiudi Report"):
            st.session_state.show_report = False
            st.rerun()

    st.title(f"🎁 Benvuto, {st.session_state.username}!")
    if asta_bloccata:
        st.error("🚫 L'asta è attualmente chiusa.")
    else:
        st.success("✅ Asta in corso!")

    # --- CARTE (FRAGMENT – NO SCROLL JUMP) ---
    @st.fragment(run_every=10)
    def render_carte():
        st.empty()
        df_db = get_offerte_snapshot()
        
        for i, row in df_carte.iterrows():
            nc = row["Nome Carta"]
            safe_key = nc.replace(" ", "_")
        
            # Calcolo prezzo
            prezzo_mostrato = 0
            tavolo_mostrato = "Nessuno"
            off_db = df_db[df_db["Carta"] == nc]
            if not off_db.empty:
                m = off_db.sort_values(by="Offerta", ascending=False).iloc[0]
                prezzo_mostrato = m["Offerta"]
                tavolo_mostrato = m["Tavolo"]
        
            if nc in st.session_state.offerte_locali:
                local = st.session_state.offerte_locali[nc]
                if local["Offerta"] > prezzo_mostrato:
                    prezzo_mostrato = local["Offerta"]
                    tavolo_mostrato = local["Tavolo"]
        
            with st.container(border=True):
                col_img, col_txt, col_btn = st.columns([1, 2, 1])
                with col_img:
                    if row["Immagine"]:
                        st.image(row["Immagine"], use_container_width=True)
                    else: st.write("🖼️")
                with col_txt:
                    st.write(f"### {nc}")
                    st.write(f"💰 Prezzo attuale: **{prezzo_mostrato} €**")
                    st.caption(f"In testa: {tavolo_mostrato}")
                with col_btn:
                    if asta_bloccata:
                        st.button("🔒 Chiusa", key=f"lock_{safe_key}_{i}", disabled=True, use_container_width=True)
                    else:
                        # RIMOSSO 'key' da st.popover per evitare TypeError
                        with st.popover("🚀 Punta", use_container_width=True):
                            st.write(f"Offerta per {nc}")
                            nuova = st.number_input("Importo (€)", min_value=int(prezzo_mostrato) + 1, step=1, key=f"in_{safe_key}_{i}")
                            if st.button("Conferma", key=f"go_{safe_key}_{i}", use_container_width=True):
                                append_row("Offerte", {"Tavolo": st.session_state.tavolo, "Carta": nc, "Offerta": nuova, "Nome Utente": st.session_state.username})
                                st.session_state.offerte_locali[nc] = {"Offerta": nuova, "Tavolo": st.session_state.tavolo}
                                st.success("Inviata!")

    render_carte()
                            
    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()
