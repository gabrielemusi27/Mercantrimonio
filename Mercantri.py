import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# 1. Configurazione Pagina
st.set_page_config(page_title="Mercante in Fiera - Matrimonio", layout="wide")

# --- STATO GLOBALE CONDIVISO (Sincronizza tutti gli utenti) ---
@st.cache_resource
def get_global_state():
    # Questo dizionario è unico per l'intero server Streamlit
    return {"asta_aperta": True}

global_state = get_global_state()

# --- AUTH GOOGLE ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["connections"]["gsheets"]["service_account"], scopes=scope)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1g_FXSodJoWocTc8Ni12sBSDYviQ7oAQBDipVsLzfw5w"
sh = gc.open_by_key(SPREADSHEET_ID)

# --- FUNZIONI DI SCRITTURA E LETTURA ---

@st.cache_data(ttl=5)
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
    st.title("🎫 Benvenuti all'Asta del Mercante!")
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

    # --- PANNELLO ADMIN (Solo per te) ---
    if st.session_state.username == "Gabriele Musicò":
        with st.sidebar.expander("🛠 PANNELLO DI CONTROLLO", expanded=True):
            st.write(f"L'asta è: **{'APERTA 🟢' if not asta_bloccata else 'CHIUSA 🔴'}**")
            
            if not asta_bloccata:
                if st.button("🔴 CHIUDI ASTA PER TUTTI"):
                    global_state["asta_aperta"] = False
                    st.cache_data.clear()
                    st.rerun()
            else:
                if st.button("🟢 RIAPRI ASTA PER TUTTI"):
                    global_state["asta_aperta"] = True
                    st.cache_data.clear()
                    st.rerun()
            
            st.divider()
            if st.button("📊 GENERA REPORT FINALE"):
                st.session_state.show_report = True
            
            if st.button("🔄 Ricarica Carte/Tavoli da Google"):
                del st.session_state.df_tavoli
                del st.session_state.df_carte
                st.rerun()

    # --- LOGICA REPORT FINALE (Greedy/Cascata) ---
    if st.session_state.get('show_report', False):
        st.header("🏆 Risultati Ufficiali")
        df_fresche = load_offerte(force=True)
        
        # Merge con le carte per sapere il premio
        df_lavoro = df_fresche.merge(df_carte[['Nome Carta', 'Premio']], left_on='Carta', right_on='Nome Carta')
        # Ordine: Offerta più alta, poi Premio più alto
        df_lavoro = df_lavoro.sort_values(by=['Offerta', 'Premio'], ascending=False)
        
        assegnazioni, c_presse, t_presi = [], set(), set()
        for _, r in df_lavoro.iterrows():
            if r['Carta'] not in c_presse and r['Tavolo'] not in t_presi:
                assegnazioni.append({
                    "Carta": r['Carta'], 
                    "Tavolo": r['Tavolo'], 
                    "Offerta": r['Offerta'], 
                    "Premio": r['Premio'],
                    "Vincitore": r['Nome Utente']
                })
                c_presse.add(r['Carta'])
                t_presi.add(r['Tavolo'])
        
        df_f = pd.DataFrame(assegnazioni)
        if not df_f.empty:
            st.dataframe(df_f, use_container_width=True)
            st.metric("Totale Raccolto", f"{df_f['Offerta'].sum()} €")
        
        if st.button("Chiudi Report"):
            st.session_state.show_report = False
            st.rerun()
        st.divider()

    # --- INTERFACCIA UTENTE ---
    st.title(f"🎁 Benvuto all'Asta, {st.session_state.username}!")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")
    
    if asta_bloccata:
        st.error("🚫 L'asta è stata chiusa dall'amministratore.")
    else:
        st.success("✅ Asta in corso! Fai la tua offerta.")

    # --- ELENCO CARTE (CON IMMAGINI) ---
    df_offerte = load_offerte()
    
    # Prepariamo la lista con le offerte più alte per ogni carta
    best_list = []
    for _, c in df_carte.iterrows():
        nc = c["Nome Carta"]
        off = df_offerte[df_offerte["Carta"] == nc]
        if not off.empty:
            m = off.sort_values(by="Offerta", ascending=False).iloc[0]
            best_list.append({"Carta": nc, "Prezzo": m["Offerta"], "Tavolo": m["Tavolo"], "Img": c["Immagine"]})
        else:
            best_list.append({"Carta": nc, "Prezzo": 0, "Tavolo": "Nessuno", "Img": c["Immagine"]})
    
    # Mostriamo le carte in container
    for i, row in enumerate(best_list):
        with st.container(border=True):
            col_img, col_txt, col_btn = st.columns([1, 2, 1])
            
            with col_img:
                if row['Img']:
                    st.image(row['Img'], use_container_width=True)
                else:
                    st.write("🖼️")
            
            with col_txt:
                st.write(f"### {row['Carta']}")
                st.write(f"💰 Prezzo attuale: **{row['Prezzo']} €**")
                st.caption(f"In testa: {row['Tavolo']}")
            
            with col_btn:
                chiave = f"btn_{row['Carta']}_{i}"
                if asta_bloccata:
                    st.button("🔒 Chiusa", key=chiave, disabled=True, use_container_width=True)
                else:
                    with st.popover("🚀 Punta", use_container_width=True):
                        st.write(f"Offerta per {row['Carta']}")
                        nuova = st.number_input(
                            "Importo (€)", 
                            min_value=int(row['Prezzo']) + 5, 
                            step=5, 
                            key=f"in_{chiave}"
                        )
                        if st.button("Conferma", key=f"go_{chiave}", use_container_width=True):
                            append_row("Offerte", {
                                "Tavolo": st.session_state.tavolo,
                                "Carta": row['Carta'],
                                "Offerta": nuova,
                                "Nome Utente": st.session_state.username
                            })
                            st.cache_data.clear()
                            st.success("Offerta inviata!")
                            time.sleep(0.5)
                            st.rerun()

    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()
