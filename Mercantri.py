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

    # --- LOGICA DI STATO LOCALE ---
    # Usiamo il session_state per gestire l'asta senza interrogare Google ogni secondo
    if 'asta_attiva' not in st.session_state:
        st.session_state.asta_attiva = False
    if 'fine_asta' not in st.session_state:
        st.session_state.fine_asta = None
    
    # --- FUNZIONE ADMIN ---
    def interfaccia_admin():
        st.sidebar.markdown("---")
        st.sidebar.subheader("🛠 Area Riservata Admin")
        
        status = "ATTIVA" if st.session_state.asta_attiva else "NON ATTIVA"
        st.sidebar.write(f"Stato: **{status}**")
        
        durata = st.sidebar.number_input("Durata asta (minuti)", min_value=1, value=30)
        
        if not st.session_state.asta_attiva:
            if st.sidebar.button("Fai partire l'asta! 🚀"):
                st.session_state.asta_attiva = True
                st.session_state.fine_asta = time.time() + (durata * 60)
                st.rerun()
        else:
            if st.sidebar.button("STOP ASTA 🛑"):
                st.session_state.asta_attiva = False
                st.session_state.fine_asta = None
                st.rerun()
    
    # --- LOGICA DI ACCESSO ---
    # Verifichiamo se l'utente è l'Admin
    is_admin = (st.session_state.get('username') == "Gabriele Musicò")
    
    if is_admin:
        interfaccia_admin()
    
    # --- CALCOLO TIMER (Solo se attiva) ---
    timer_testo = ""
    asta_bloccata = not st.session_state.asta_attiva
    
    if st.session_state.asta_attiva and st.session_state.fine_asta:
        secondi_rimanenti = int(st.session_state.fine_asta - time.time())
        if secondi_rimanenti <= 0:
            st.session_state.asta_attiva = False
            asta_bloccata = True
            st.error("⌛ TEMPO SCADUTO! L'asta è terminata.")
        else:
            mins, secs = divmod(secondi_rimanenti, 60)
            timer_testo = f"⏳ Tempo rimasto: {mins:02d}:{secs:02d}"
            st.warning(timer_testo)

    
    # --- PAGINA PRINCIPALE ASTA ---
    st.title(f"🎁 Grande Asta - Benvenuto {st.session_state.username}")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")
    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()

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
    
    # Usiamo enumerate per avere un numero unico (i) per ogni riga
    for i, row in df_riepilogo.iterrows():
        nome_c = row['Carta']
        prezzo_attuale = int(row['Prezzo Attuale (€)'])
        
        # Creiamo una chiave univoca combinando nome carta e indice
        # Questo risolve l'errore StreamlitDuplicateElementKey
        chiave_unica = f"{nome_c}_{i}"
        
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1.5])
            
            with col1:
                st.write(f"### {nome_c}")
            with col2:
                st.write(f"💰 {prezzo_attuale} €")
                st.caption(f"Tavolo: {row['In testa il Tavolo']}")
            
            with col3:
                if asta_bloccata:
                    st.button("Chiusa 🔒", key=f"disabled_{chiave_unica}", disabled=True, use_container_width=True)
                else:
                    with st.popover("Punta 🚀", use_container_width=True):
                    # L'expander è più stabile: si chiude da solo al refresh
                    with st.expander("Punta 🚀"):
                        nuova_offerta = st.number_input(
                            "Importo (€)", 
                            min_value=prezzo_attuale + 1, 
                            step=5,
                            key=f"input_{chiave_unica}"
                        )
                        
                        if st.button("Conferma!", key=f"btn_send_{chiave_unica}", use_container_width=True):
                            # 1. Scrittura sul foglio
                            append_row("Offerte", {
                                "Tavolo": st.session_state.tavolo,
                                "Carta": nome_c,
                                "Offerta": nuova_offerta,
                                "Nome Utente": st.session_state.username
                            })
                            
                            # 2. Reset e chiusura
                            st.cache_data.clear()
                            st.success("Registrata!")
                            time.sleep(0.5)
                            
                            # Il rerun ricarica la pagina e l'expander tornerà CHIUSO di default
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





