import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# 1. Configurazione Pagina (DEVE ESSERE LA PRIMA COSA)
st.set_page_config(page_title="Asta Matrimonio", layout="wide")

# --- AUTH GOOGLE ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["connections"]["gsheets"]["service_account"], scopes=scope)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1g_FXSodJoWocTc8Ni12sBSDYviQ7oAQBDipVsLzfw5w"
sh = gc.open_by_key(SPREADSHEET_ID)

# --- FUNZIONI ---
@st.cache_data(ttl=10)
def read_sheet(name):
    ws = sh.worksheet(name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def append_row(name, row_dict):
    ws = sh.worksheet(name)
    ws.append_row(list(row_dict.values()))

def load_static_data():
    return read_sheet("Tavoli"), read_sheet("Carte")

@st.cache_data(ttl=5)
def load_offerte():
    return read_sheet("Offerte")

# --- CARICAMENTO DATI INIZIALI ---
df_tavoli, df_carte = load_static_data()
df_offerte = load_offerte()

# --- GESTIONE LOGIN ---
if 'user_logged' not in st.session_state:
    st.session_state.user_logged = False

if not st.session_state.user_logged:
    st.title("🎫 Accesso all'Asta")
    with st.form("login_form"):
        nome = st.text_input("Il tuo Nome (Admin: Gabriele Musicò)")
        tavolo = st.selectbox("Il tuo Tavolo", df_tavoli["Nome Tavolo"].unique())
        submit_login = st.form_submit_button("Entra nel Mercante in Fiera")
        
        if submit_login and nome:
            st.session_state.user_logged = True
            st.session_state.username = nome.strip() # .strip() toglie spazi extra
            st.session_state.tavolo = tavolo
            st.rerun()
else:
    # --- LOGICA STATO ASTA (LOCALE) ---
    if 'asta_attiva' not in st.session_state:
        st.session_state.asta_attiva = False
    if 'fine_asta' not in st.session_state:
        st.session_state.fine_asta = None

    # --- CONTROLLO ADMIN ---
    if st.session_state.username == "Gabriele Musicò":
        with st.sidebar.expander("🛠 Area Riservata Admin", expanded=True):
            status = "ATTIVA" if st.session_state.asta_attiva else "NON ATTIVA"
            st.write(f"Stato: **{status}**")
            durata = st.number_input("Durata (minuti)", min_value=1, value=30)
            
            if not st.session_state.asta_attiva:
                if st.button("Fai partire l'asta! 🚀"):
                    st.session_state.asta_attiva = True
                    st.session_state.fine_asta = time.time() + (durata * 60)
                    st.rerun()
            else:
                if st.button("STOP ASTA 🛑"):
                    st.session_state.asta_attiva = False
                    st.session_state.fine_asta = None
                    st.rerun()

    # --- CALCOLO TIMER ---
    asta_bloccata = not st.session_state.asta_attiva
    if st.session_state.asta_attiva and st.session_state.fine_asta:
        rimanenti = int(st.session_state.fine_asta - time.time())
        if rimanenti <= 0:
            st.session_state.asta_attiva = False
            asta_bloccata = True
            st.error("⌛ TEMPO SCADUTO!")
        else:
            m, s = divmod(rimanenti, 60)
            st.warning(f"⏳ Tempo rimasto: {m:02d}:{s:02d}")

    # --- INTERFACCIA PRINCIPALE ---
    st.title(f"🎁 Benvenuto {st.session_state.username}")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")
    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()

    def get_best_offers(df_o, df_c):
        res = []
        for _, c in df_c.iterrows():
            nc = c["Nome Carta"]
            off = df_o[df_o["Carta"] == nc]
            if not off.empty:
                migliore = off.sort_values(by="Offerta", ascending=False).iloc[0]
                res.append({"Carta": nc, "Prezzo": migliore["Offerta"], "Tavolo": migliore["Tavolo"]})
            else:
                res.append({"Carta": nc, "Prezzo": 0, "Tavolo": "Nessuno"})
        return pd.DataFrame(res)

    df_riepilogo = get_best_offers(df_offerte, df_carte)
    
    st.subheader("Situazione Carte")
    for i, row in df_riepilogo.iterrows():
        nome_c = row['Carta']
        prezzo_attuale = int(row['Prezzo'])
        chiave_unica = f"{nome_c}_{i}"
        
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])
            with col1:
                st.write(f"### {nome_c}")
            with col2:
                st.write(f"💰 {prezzo_attuale} €")
                st.caption(f"In testa: {row['Tavolo']}")
            with col3:
                if asta_bloccata:
                    st.button("Chiusa 🔒", key=f"lock_{chiave_unica}", disabled=True, use_container_width=True)
                else:
                    # USIAMO SOLO IL POPOVER (Rimosso expander interno che creava bug)
                    with st.popover("Punta 🚀", use_container_width=True):
                        st.write(f"Offerta per {nome_c}")
                        nuova = st.number_input("Quanto offri?", min_value=prezzo_attuale + 5, step=5, key=f"in_{chiave_unica}")
                        if st.button("Conferma", key=f"go_{chiave_unica}", use_container_width=True):
                            append_row("Offerte", {
                                "Tavolo": st.session_state.tavolo,
                                "Carta": nome_c,
                                "Offerta": nuova,
                                "Nome Utente": st.session_state.username
                            })
                            st.cache_data.clear()
                            st.success("Presa!")
                            time.sleep(0.5)
                            st.rerun()
