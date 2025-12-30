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
        
        with st.spinner("Calcolo assegnazioni definitive..."):
            df_fresche = load_offerte(force=True)
        
        df_lavoro = df_fresche.merge(df_carte[['Nome Carta', 'Premio']], left_on='Carta', right_on='Nome Carta')
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

        tutti_i_tavoli = set(df_tavoli["Nome Tavolo"].unique())
        tutte_le_carte = set(df_carte["Nome Carta"].unique())
        
        tavoli_esclusi = tutti_i_tavoli - t_presi
        carte_escluse = tutte_le_carte - c_presse

        col_t, col_c = st.columns(2)
        with col_t:
            if tavoli_esclusi:
                st.error(f"😟 **Tavoli senza premi ({len(tavoli_esclusi)}):**\n" + ", ".join(tavoli_esclusi))
            else:
                st.success("🎉 Tutti i tavoli hanno vinto qualcosa!")
        
        with col_c:
            if carte_escluse:
                st.warning(f"📦 **Carte non assegnate ({len(carte_escluse)}):**\n" + ", ".join(carte_escluse))
            else:
                st.success("🃏 Tutte le carte sono state vendute!")

        if not df_f.empty:
            df_f = df_f.sort_values(by="Premio", ascending=False)
            st.table(df_f.style.format({"Offerta": "{} €", "Premio": "{}"}))
            st.metric("💰 Totale Raccolto", f"{df_f['Offerta'].sum()} €")
        else:
            st.info("Nessuna offerta registrata finora.")
        
        if st.button("Aggiorna Calcoli"):
            st.rerun()

        if st.button("Chiudi Report"):
            st.session_state.show_report = False
            st.rerun()
        st.divider()

    # --- INTERFACCIA UTENTE ---
    st.title(f"🎁 Benvuto al Mercantrimonio, {st.session_state.username}!")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")

    if st.button("🔄 AGGIORNA OFFERTE", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    if asta_bloccata:
        st.error("🚫 L'asta è attualmente chiusa. Attendi il via dell'amministratore!")
    else:
        st.success("✅ Asta in corso! Fai la tua offerta.")

    # --- ELENCO CARTE (CON IMMAGINI) ---
    df_offerte = load_offerte()
    
    best_list = []
    for _, c in df_carte.iterrows():
        nc = c["Nome Carta"]
        off = df_offerte[df_offerte["Carta"] == nc]
        if not off.empty:
            m = off.sort_values(by="Offerta", ascending=False).iloc[0]
            best_list.append({"Carta": nc, "Prezzo": m["Offerta"], "Tavolo": m["Tavolo"], "Img": c["Immagine"]})
        else:
            best_list.append({"Carta": nc, "Prezzo": 0, "Tavolo": "Nessuno", "Img": c["Immagine"]})
    
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
                    with st.expander("🚀 Punta", expanded=False):
                        st.write(f"Offerta per {row['Carta']}")
                        nuova = st.number_input(
                            "Importo (€)", 
                            min_value=int(row['Prezzo']) + 1, 
                            step=1, 
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
