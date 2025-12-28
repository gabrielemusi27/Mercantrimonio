import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# 1. Configurazione Pagina
st.set_page_config(page_title="Asta Matrimonio", layout="wide")

# Nascondi menu Streamlit per estetica mobile
st.markdown("""<style> .stActionButton { display: none; } #MainMenu {visibility: hidden;} </style>""", unsafe_allow_html=True)

# --- AUTH GOOGLE ---
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

# --- FUNZIONI DI LETTURA/SCRITTURA ---

@st.cache_data(ttl=10)
def read_sheet(name):
    ws = sh.worksheet(name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

@st.cache_data(ttl=15)
def get_status_centrale():
    try:
        ws = sh.worksheet("Stato")
        return ws.cell(2, 1).value
    except:
        return "APERTA"

def set_status_centrale(nuovo_stato):
    ws = sh.worksheet("Stato")
    ws.update_cell(2, 1, nuovo_stato)
    st.cache_data.clear()

def append_row(name, row_dict):
    ws = sh.worksheet(name)
    ws.append_row(list(row_dict.values()))

def load_static_data():
    return read_sheet("Tavoli"), read_sheet("Carte")

@st.cache_data(ttl=5)
def load_offerte():
    return read_sheet("Offerte")

# --- CARICAMENTO DATI ---
df_tavoli, df_carte = load_static_data()
df_offerte = load_offerte()
stato_asta = get_status_centrale()
asta_bloccata = (stato_asta == "CHIUSA")

# --- GESTIONE LOGIN ---
if 'user_logged' not in st.session_state:
    st.session_state.user_logged = False

if not st.session_state.user_logged:
    st.title("🎫 Accesso all'Asta")
    with st.form("login_form"):
        nome = st.text_input("Il tuo Nome")
        tavolo = st.selectbox("Il tuo Tavolo", df_tavoli["Nome Tavolo"].unique())
        submit_login = st.form_submit_button("Entra nell'Asta")
        
        if submit_login and nome:
            st.session_state.user_logged = True
            st.session_state.username = nome.strip()
            st.session_state.tavolo = tavolo
            st.rerun()
        elif submit_login and not nome:
            st.error("Inserisci il tuo nome per favore.")
else:
    # --- INTERFACCIA ADMIN (Solo per Gabriele Musicò) ---
    if st.session_state.username == "Gabriele Musicò":
        with st.sidebar.expander("🛠 Pannello Admin", expanded=True):
            st.write(f"Stato: **{stato_asta}**")
            
            # Pulsanti di controllo stato
            if not asta_bloccata:
                if st.button("🔴 CHIUDI ASTA PER TUTTI", use_container_width=True):
                    set_status_centrale("CHIUSA")
                    st.rerun()
            else:
                if st.button("🟢 RIAPRI ASTA", use_container_width=True):
                    set_status_centrale("APERTA")
                    st.rerun()
            
            st.markdown("---")
            
            # NUOVO PULSANTE REPORT FINALE
            if st.button("📊 GENERA REPORT VINCITORI", use_container_width=True):
                st.session_state.show_report = True

    # --- VISUALIZZAZIONE REPORT FINALE (Sopra la lista carte se attivo) ---
    if st.session_state.get('show_report', False):
        st.divider()
        st.header("🏆 Riepilogo Vincitori Asta")
        
        # Uniamo i dati delle offerte migliori con i premi della tabella Carte
        df_vincitori = df_riepilogo.merge(df_carte[['Nome Carta', 'Premio']], left_on='Carta', right_on='Nome Carta')
        
        # Pulizia e ordinamento per Premio Decrescente
        df_finale = df_vincitori[['Carta', 'Tavolo', 'Prezzo', 'Premio']].copy()
        df_finale = df_finale.sort_values(by='Premio', ascending=False)
        
        # Visualizzazione Tabella Admin
        st.table(df_finale.style.format({"Prezzo": "{} €", "Premio": "{} €"}))
        
        # Bottone per chiudere il report
        if st.button("Chiudi Report"):
            st.session_state.show_report = False
            st.rerun()
        st.divider()

    # --- INTESTAZIONE ---
    st.title(f"🎁 Grande Asta - {st.session_state.username}")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")
    if st.sidebar.button("Esci"):
        st.session_state.user_logged = False
        st.rerun()

    if asta_bloccata:
        st.error("🚫 L'ASTA È CHIUSA. Non è possibile fare nuove offerte.")
    else:
        st.success("✅ ASTA APERTA! Fai la tua offerta.")

    # --- LOGICA OFFERTE ---
    def get_best_offers(df_o, df_c):
        best = []
        for _, c in df_c.iterrows():
            nome_carta = c["Nome Carta"]
            offerte_c = df_o[df_o["Carta"] == nome_carta]
            if not offerte_c.empty:
                max_off = offerte_c.sort_values(by="Offerta", ascending=False).iloc[0]
                best.append({
                    "Carta": nome_carta,
                    "Prezzo": max_off["Offerta"],
                    "Tavolo": max_off["Tavolo"]
                })
            else:
                best.append({"Carta": nome_carta, "Prezzo": 0, "Tavolo": "Nessuno"})
        return pd.DataFrame(best)

    df_riepilogo = get_best_offers(df_offerte, df_carte)

    st.subheader("Situazione Carte")

    # --- CICLO VISUALIZZAZIONE CARTE ---
    for i, row in df_riepilogo.iterrows():
        nome_c = row['Carta']
        prezzo_attuale = int(row['Prezzo'])
        chiave_unica = f"{nome_c}_{i}" # Chiave univoca anti-errore

        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])
            
            with col1:
                st.write(f"### {nome_c}")
            with col2:
                st.write(f"💰 **{prezzo_attuale} €**")
                st.caption(f"In testa: Tavolo {row['Tavolo']}")
            
            with col3:
                if asta_bloccata:
                    st.button("Chiusa 🔒", key=f"lock_{chiave_unica}", disabled=True, use_container_width=True)
                else:
                    with st.popover("Punta 🚀", use_container_width=True):
                        st.write(f"Offerta per: **{nome_c}**")
                        nuova = st.number_input(
                            "Importo (€)", 
                            min_value=prezzo_attuale + 5, 
                            step=5, 
                            key=f"in_{chiave_unica}"
                        )
                        if st.button("Conferma", key=f"go_{chiave_unica}", use_container_width=True):
                            # Scrittura su Google Sheets
                            append_row("Offerte", {
                                "Tavolo": st.session_state.tavolo,
                                "Carta": nome_c,
                                "Offerta": nuova,
                                "Nome Utente": st.session_state.username
                            })
                            st.cache_data.clear()
                            st.success("Registrata!")
                            time.sleep(0.6)
                            st.rerun()
