import pandas as pd
import gspread
import streamlit as st
import time
import os
from google.oauth2.service_account import Credentials

# =========================================================
# CONFIGURAZIONE
# =========================================================
SNAPSHOT_FILE = "offerte_snapshot.parquet"
STATUS_FILE = "asta_status.parquet"

st.set_page_config(page_title="Mercante in Fiera - Matrimonio", layout="wide")

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
# FUNZIONI STATO ASTA (PERSISTENTE)
# =========================================================

def get_asta_status():
    if not os.path.exists(STATUS_FILE):
        return True
    df = pd.read_parquet(STATUS_FILE)
    return bool(df.loc[0, "aperta"])

def set_asta_status(stato: bool):
    df = pd.DataFrame([{"aperta": stato}])
    df.to_parquet(STATUS_FILE, index=False)

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
    with st.spinner("Sincronizzazione tavoli e carte..."):
        ws_t = sh.worksheet("Tavoli")
        st.session_state.df_tavoli = pd.DataFrame(ws_t.get_all_records())
        ws_c = sh.worksheet("Carte")
        st.session_state.df_carte = pd.DataFrame(ws_c.get_all_records())
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
                st.error("Inserisci il tuo nome per partecipare.")

# =========================================================
# APP PRINCIPALE
# =========================================================
else:
    asta_aperta = get_asta_status()

    # -----------------------------------------------------
    # PANNELLO ADMIN (Resta fuori dai fragment per controllo globale)
    # -----------------------------------------------------
    if st.session_state.username == "Federica Giunta":
        with st.sidebar.expander("🛠 PANNELLO DI CONTROLLO", expanded=True):
            st.write(f"L'asta è: **{'APERTA 🟢' if asta_aperta else 'CHIUSA 🔴'}**")
            if st.button("🔄 AGGIORNA OFFERTE PER TUTTI", use_container_width=True, type="primary"):
                forza_scaricamento_offerte()
                st.cache_data.clear()
                st.success("Dati sincronizzati!")
            
            if asta_aperta:
                if st.button("🔴 CHIUDI ASTA PER TUTTI"):
                    set_asta_status(False)
                    st.cache_data.clear()
                    st.rerun()
            else:
                if st.button("🟢 AVVIA ASTA PER TUTTI"):
                    set_asta_status(True)
                    st.cache_data.clear()
                    st.rerun()

            st.divider()
            if st.button("📊 GENERA REPORT FINALE"):
                st.session_state.show_report = True

            if st.button("🐷 Premi per elevare la vita di un povero maialino indifeso!"):
                del st.session_state.df_tavoli
                del st.session_state.df_carte
                st.rerun()

    # -----------------------------------------------------
    # REPORT FINALE
    # -----------------------------------------------------
    if st.session_state.get('show_report', False):
        st.header("🏆 Risultati Ufficiali")
        df_fresche = forza_scaricamento_offerte()
        df_lavoro = df_fresche.merge(df_carte[['Nome Carta']], left_on='Carta', right_on='Nome Carta')
        df_lavoro = df_lavoro.sort_values(by=['Offerta'], ascending=False)
        assegnazioni, c_presse, t_presi = [], set(), set()
        for _, r in df_lavoro.iterrows():
            if r['Carta'] not in c_presse and r['Tavolo'] not in t_presi:
                assegnazioni.append({"Carta": r['Carta'], "Tavolo": r['Tavolo'], "Offerta": r['Offerta'], "Vincitore": r['Nome Utente']})
                c_presse.add(r['Carta'])
                t_presi.add(r['Tavolo'])
        df_f = pd.DataFrame(assegnazioni)
        if not df_f.empty:
            st.table(df_f.style.format({"Offerta": "{} €"}))
            st.metric("💰 Totale Raccolto", f"{df_f['Offerta'].sum()} €")
        if st.button("Chiudi Report"):
            st.session_state.show_report = False
            st.rerun()
        st.divider()

    # -----------------------------------------------------
    # INTERFACCIA UTENTE
    # -----------------------------------------------------
    st.title(f"🎁 Benvenuto al Mercantrimonio, {st.session_state.username}!")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")

    if not asta_aperta:
        st.error("🚫 L'asta è attualmente chiusa. Attendi il via dell'amministratore!")
    else:
        st.success("✅ Asta in corso! Fai la tua offerta.")

    # Definizione del Fragment DINAMICO per ogni singola carta
    @st.fragment(run_every=10)
    def ui_dinamica_carta(nome_carta, index_carta):
        # 1. Recupero dati aggiornati
        current_asta_bloccata = not get_asta_status()
        df_db = get_offerte_snapshot()
        
        prezzo_mostrato = 0
        tavolo_mostrato = "Nessuno"
        
        off_db = df_db[df_db["Carta"] == nome_carta]
        if not off_db.empty:
            m = off_db.sort_values(by="Offerta", ascending=False).iloc[0]
            prezzo_mostrato = m["Offerta"]
            tavolo_mostrato = m["Tavolo"]
        
        if nome_carta in st.session_state.offerte_locali:
            local = st.session_state.offerte_locali[nome_carta]
            if local["Offerta"] > prezzo_mostrato:
                prezzo_mostrato = local["Offerta"]
                tavolo_mostrato = local["Tavolo"]

        # 2. Render delle sole parti che cambiano
        col_txt, col_btn = st.columns([2, 1])
        
        with col_txt:
            st.write(f"💰 Prezzo attuale: **{prezzo_mostrato} €**")
            st.caption(f"In testa: {tavolo_mostrato}")
        
        with col_btn:
            chiave = f"{nome_carta}_{index_carta}"
            if current_asta_bloccata:
                st.button("🔒 Chiusa", disabled=True, use_container_width=True, key=f"btn_lock_{chiave}")
            else:
                with st.expander("🚀 Punta"):
                    nuova = st.number_input(
                        "Importo (€)", 
                        min_value=int(prezzo_mostrato) + 1, 
                        step=1, 
                        key=f"in_{chiave}"
                    )
                    if st.button("Conferma", key=f"go_{chiave}", use_container_width=True):
                        append_row("Offerte", {
                            "Tavolo": st.session_state.tavolo,
                            "Carta": nome_carta,
                            "Offerta": nuova,
                            "Nome Utente": st.session_state.username
                        })
                        st.session_state.offerte_locali[nome_carta] = {
                            "Offerta": nuova,
                            "Tavolo": st.session_state.tavolo
                        }
                        st.success("Inviata!")
                        time.sleep(0.5)
                        st.rerun()

    # Creazione della griglia STATICA
    for i, row in df_carte.iterrows():
        nc = row["Nome Carta"]
        with st.container(border=True):
            col_img, col_content = st.columns([1, 3])
            
            # Parte Statica: Immagine e Nome
            with col_img:
                if row["Immagine"]:
                    st.image(row["Immagine"], use_container_width=True)
                else:
                    st.write("🖼️")
            
            with col_content:
                st.write(f"### {nc}")
                # Richiamo il Fragment per la parte dinamica
                ui_dinamica_carta(nc, i)

    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()
