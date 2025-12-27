#import streamlit as st
#import pandas as pd

# 1. Configurazione Pagina
#st.set_page_config(page_title="Asta Matrimonio", layout="wide")

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

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

# Funzione per caricare i dati (senza cache per avere i prezzi sempre aggiornati)
@st.cache_data(ttl=5)
def load_offerte():
    return read_sheet("Offerte")

df_tavoli, df_carte = load_static_data()
df_offerte = load_offerte()

# --- GESTIONE LOGIN (Session State) ---
if 'user_logged' not in st.session_state:
    st.session_state.user_logged = False

if not st.session_state.user_logged:
    st.title("🎫 Accesso all'Asta")
    with st.form("login_form"):
        nome = st.text_input("Il tuo Nome")
        tavolo = st.selectbox("Il tuo Tavolo", df_tavoli["Nome Tavolo"].unique())
        submit_login = st.form_submit_button("Entra nel Mercante in Fiera")
        
        if submit_login and nome:
            st.session_state.user_logged = True
            st.session_state.username = nome
            st.session_state.tavolo = tavolo
            st.rerun()
        elif submit_login and not nome:
            st.error("Per favore, inserisci il tuo nome.")
else:
    # --- PAGINA PRINCIPALE ASTA ---
    st.title(f"🎁 Grande Asta - Benvenuto {st.session_state.username}")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")
    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()

    st.subheader("Situazione Carte")

    # Creiamo la tabella delle offerte più alte per ogni carta
    # Se non ci sono offerte, mettiamo 0
    def get_best_offers(df_offerte, df_carte):
        best_offers = []
        for _, c in df_carte.iterrows():
            nome_carta = c["Nome Carta"]
            # Filtriamo le offerte per questa carta
            offerte_carta = df_offerte[df_offerte["Carta"] == nome_carta]
            if not offerte_carta.empty:
                miglior_offerta = offerte_carta.sort_values(by="Offerta", ascending=False).iloc[0]
                best_offers.append({
                    "Carta": nome_carta,
                    "Prezzo Attuale (€)": miglior_offerta["Offerta"],
                    "In testa il Tavolo": miglior_offerta["Tavolo"]
                })
            else:
                best_offers.append({
                    "Carta": nome_carta,
                    "Prezzo Attuale (€)": 0,
                    "In testa il Tavolo": "Nessuno"
                })
        return pd.DataFrame(best_offers)

    df_riepilogo = get_best_offers(df_offerte, df_carte)
    
    # --- ELENCO DELLE CARTE ---
    st.subheader("Situazione Carte")

    df_riepilogo = get_best_offers(df_offerte, df_carte)
    
    for index, row in df_riepilogo.iterrows():
        # Creiamo un contenitore per ogni carta
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"### {row['Carta']}")
            with col2:
                st.write(f"💰 {row['Prezzo Attuale (€)']} €")
                st.caption(f"In testa: Tavolo {row['In testa il Tavolo']}")
            with col3:
                # Il bottone ora serve solo a "marcare" quale carta vogliamo aprire
                if st.button(f"Punta", key=f"btn_{index}", use_container_width=True):
                    st.session_state.scelta_carta = row['Carta']
                    st.session_state.prezzo_minimo = row['Prezzo Attuale (€)']
                    # NON mettiamo st.rerun() qui, così l'utente resta nel punto in cui si trova

            # --- BOX OFFERTA "IN LINEA" ---
            # Se la carta corrente è quella selezionata, mostriamo il form qui sotto
            if st.session_state.get('scelta_carta') == row['Carta']:
                st.info(f"Fai la tua offerta per {row['Carta']}")
                
                # Usiamo le colonne per rendere il form compatto
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    nuova_offerta = st.number_input(
                        "Importo (€)", 
                        min_value=int(row['Prezzo Attuale (€)']) + 1, 
                        step=5,
                        key=f"input_{index}"
                    )
                with c2:
                    if st.button("Invia 🚀", key=f"send_{index}", use_container_width=True):
                        append_row("Offerte", {
                            "Tavolo": st.session_state.tavolo,
                            "Carta": row['Carta'],
                            "Offerta": nuova_offerta,
                            "Nome Utente": st.session_state.username
                        })
                        st.success("Fatto!")
                        time.sleep(1)
                        del st.session_state.scelta_carta
                        st.cache_data.clear()
                        st.rerun()
                with c3:
                    if st.button("Annulla", key=f"canc_{index}", use_container_width=True):
                        del st.session_state.scelta_carta
                        st.rerun()

    """# --- POPUP OFFERTA ---
    if 'scelta_carta' in st.session_state:
        st.divider()
        st.subheader(f"Fai la tua offerta per: {st.session_state.scelta_carta}")
        nuova_offerta = st.number_input("Tua Offerta (€)", 
                                        min_value=int(st.session_state.prezzo_minimo) + 1, 
                                        step=5)
        
        col_invio, col_annulla = st.columns(2)
        with col_invio:
            if st.button("Conferma Offerta 🚀"):
                # Prepariamo la nuova riga
                nuova_riga = pd.DataFrame([{
                    "Tavolo": st.session_state.tavolo,
                    "Carta": st.session_state.scelta_carta,
                    "Offerta": nuova_offerta,
                    "Nome Utente": st.session_state.username
                }])
                
                # Aggiorniamo il foglio
                append_row("Offerte", {
                "Tavolo": st.session_state.tavolo,
                "Carta": st.session_state.scelta_carta,
                "Offerta": nuova_offerta,
                "Nome Utente": st.session_state.username})
                
                st.success("Offerta inviata!")
                del st.session_state.scelta_carta # Chiude il form di offerta
                st.cache_data.clear() # Svuota la cache per ricaricare i dati
                st.rerun()
        
        with col_annulla:
            if st.button("Annulla"):
                del st.session_state.scelta_carta
                st.rerun()"""





