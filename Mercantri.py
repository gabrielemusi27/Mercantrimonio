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
    """Legge se l'asta è aperta o chiusa dal file locale"""
    if not os.path.exists(STATUS_FILE):
        # Default: Aperta se il file non esiste
        return True
    df = pd.read_parquet(STATUS_FILE)
    return bool(df.loc[0, "aperta"])

def set_asta_status(stato: bool):
    """Salva lo stato dell'asta su file locale"""
    df = pd.DataFrame([{"aperta": stato}])
    df.to_parquet(STATUS_FILE, index=False)

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
    """WRITE API – aggiunge una riga al foglio specificato"""
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
    # Leggiamo lo stato dell'asta dal file Parquet (non più session_state)
    asta_aperta = get_asta_status()
    asta_bloccata = not asta_aperta

    # -----------------------------------------------------
    # PANNELLO ADMIN
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
    # REPORT FINALE (ADMIN)
    # -----------------------------------------------------
    if st.session_state.get('show_report', False):
        st.header("🏆 Risultati Ufficiali")
        with st.spinner("Calcolo assegnazioni definitive..."):
            df_fresche = forza_scaricamento_offerte()

        df_lavoro = df_fresche.merge(
            df_carte[['Nome Carta']],
            left_on='Carta',
            right_on='Nome Carta'
        )
        df_lavoro = df_lavoro.sort_values(by=['Offerta'], ascending=False)
        assegnazioni, c_presse, t_presi = [], set(), set()

        for _, r in df_lavoro.iterrows():
            if r['Carta'] not in c_presse and r['Tavolo'] not in t_presi:
                assegnazioni.append({
                    "Carta": r['Carta'],
                    "Tavolo": r['Tavolo'],
                    "Offerta": r['Offerta'],
                    "Vincitore": r['Nome Utente']
                })
                c_presse.add(r['Carta'])
                t_presi.add(r['Tavolo'])

        df_f = pd.DataFrame(assegnazioni)
        tutti_i_tavoli = set(df_tavoli["Nome Tavolo"].unique())
        tavoli_esclusi = tutti_i_tavoli - t_presi

        if tavoli_esclusi:
            st.error(f"😟 **Tavoli senza premi ({len(tavoli_esclusi)}):**\n" + ", ".join(tavoli_esclusi))
        else:
            st.success("🎉 Tutti i tavoli hanno vinto qualcosa!")

        if not df_f.empty:
            df_f = df_f.sort_values(by="Offerta", ascending=False)
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

    # -----------------------------------------------------
    # CARTE (FRAGMENT – AGGIORNAMENTO AUTOMATICO OGNI 13 SEC)
    # -----------------------------------------------------
    @st.fragment(run_every=13)
    def render_carte():
        time.sleep(2)
        # Rileggiamo lo stato dentro il fragment per bloccare/sbloccare i tasti al refresh
        current_asta_bloccata = not get_asta_status()
        df_db = get_offerte_snapshot()
        
        for i, row in df_carte.iterrows():
            nc = row["Nome Carta"]
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
                    else:
                        st.write("🖼️")
        
                with col_txt:
                    st.write(f"### {nc}")
                    st.write(f"💰 Prezzo attuale: **{prezzo_mostrato} €**")
                    st.caption(f"In testa: {tavolo_mostrato}")
        
                with col_btn:
                    chiave = f"{nc}_{i}"
                    if current_asta_bloccata:
                        st.button("🔒 Chiusa", disabled=True, use_container_width=True, key=f"btn_lock_{chiave}")
                    else:
                        with st.expander("🚀 Punta"):
                            st.write(f"Offerta per {nc}")
                            nuova = st.number_input(
                                "Importo (€)",
                                min_value=int(prezzo_mostrato) + 1,
                                step=1,
                                key=f"in_{chiave}"
                            )
                            if st.button("Conferma", key=f"go_{chiave}", use_container_width=True):
                                append_row("Offerte", {
                                    "Tavolo": st.session_state.tavolo,
                                    "Carta": nc,
                                    "Offerta": nuova,
                                    "Nome Utente": st.session_state.username
                                })
                                st.session_state.offerte_locali[nc] = {
                                    "Offerta": nuova,
                                    "Tavolo": st.session_state.tavolo
                                }
                                st.success("Offerta inviata!")
                                time.sleep(0.5)
                                st.rerun()

    if asta_bloccata:
        st.error("🚫 L'asta è attualmente chiusa. Attendi il via dell'amministratore!")
    else:
        st.success("✅ Asta in corso! Fai la tua offerta.")

    render_carte()
                            
    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()
