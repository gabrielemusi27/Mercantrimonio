import pandas as pd
import gspread
import streamlit as st
import time
import os
from google.oauth2.service_account import Credentials

# =========================================================
# CONFIGURAZIONE
# =========================================================
SNAPSHOT_FILE = "offerte_live.parquet"
STATUS_FILE = "asta_status.parquet"

SHEET_HEADERS = ["Tavolo", "Carta", "Offerta", "Utente"]

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
# STATO ASTA
# =========================================================
def get_asta_status():
    if not os.path.exists(STATUS_FILE):
        return True
    return bool(pd.read_parquet(STATUS_FILE).loc[0, "aperta"])

def set_asta_status(stato: bool):
    pd.DataFrame([{"aperta": stato}]).to_parquet(STATUS_FILE, index=False)

# =========================================================
# OFFERTEDB LOCALE (PARQUET)
# =========================================================
def get_offerte_live():
    if not os.path.exists(SNAPSHOT_FILE):
        return pd.DataFrame(columns=SHEET_HEADERS)
    return pd.read_parquet(SNAPSHOT_FILE)

def append_offerta_locale(row):
    df = get_offerte_live()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_parquet(SNAPSHOT_FILE, index=False)

# =========================================================
# SYNC GOOGLE <-> PARQUET
# =========================================================
def sync_google_to_parquet():
    ws = sh.worksheet("Offerte")
    df = pd.DataFrame(ws.get_all_records())
    if not df.empty:
        # Assicuriamoci che le colonne siano quelle corrette
        df = df[[c for c in SHEET_HEADERS if c in df.columns]]
        df.to_parquet(SNAPSHOT_FILE, index=False)
    return df

def sync_parquet_to_google():
    ws = sh.worksheet("Offerte")
    df = get_offerte_live()
    ws.clear()
    ws.append_row(SHEET_HEADERS)
    if not df.empty:
        ws.append_rows(df[SHEET_HEADERS].values.tolist())

# =========================================================
# DATI STATICI
# =========================================================
if "df_tavoli" not in st.session_state or "df_carte" not in st.session_state:
    with st.spinner("Sincronizzazione tavoli e carte..."):
        st.session_state.df_tavoli = pd.DataFrame(
            sh.worksheet("Tavoli").get_all_records()
        )
        st.session_state.df_carte = pd.DataFrame(
            sh.worksheet("Carte").get_all_records()
        )
        st.session_state.offerte_locali = {}

df_tavoli = st.session_state.df_tavoli
df_carte = st.session_state.df_carte

# =========================================================
# LOGIN
# =========================================================
if "user_logged" not in st.session_state:
    st.session_state.user_logged = False

if not st.session_state.user_logged:
    st.title("🎫 Benvenuti al Mercantrimonio!")
    with st.form("login_form"):
        nome = st.text_input("Inserisci il tuo Nome")
        tavolo = st.selectbox(
            "Seleziona il tuo Tavolo",
            df_tavoli["Nome Tavolo"].unique()
        )
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
    # PANNELLO ADMIN
    # -----------------------------------------------------
    if st.session_state.username == "Federica Giunta":
        with st.sidebar.expander("🛠 PANNELLO DI CONTROLLO", expanded=True):
            st.write(f"L'asta è: **{'APERTA 🟢' if asta_aperta else 'CHIUSA 🔴'}**")
    
            if st.button(
                "🔄 AGGIORNA EXCEL",
                key="admin_sync_google",
                use_container_width=True,
                type="primary"
            ):
                sync_parquet_to_google()
                st.success("Dati sincronizzati su Google Sheet!")
    
            if asta_aperta:
                if st.button("🔴 CHIUDI ASTA PER TUTTI", key="admin_close_asta"):
                    set_asta_status(False)
                    st.rerun()
            else:
                if st.button("🟢 AVVIA ASTA PER TUTTI", key="admin_open_asta"):
                    set_asta_status(True)
                    st.rerun()
    
            st.divider()
    
            if st.button("📊 GENERA REPORT FINALE", key="admin_report"):
                # Forza il caricamento da Google prima di generare il report
                with st.spinner("Recupero dati da Google Sheet..."):
                    st.session_state.df_per_report = sync_google_to_parquet()
                st.session_state.show_report = True
    
            if st.button("🐷 Premi per elevare la vita di un povero maialino indifeso!", key="admin_pig"):
                st.success("Grazie, il maiale ti è grato! 🐷")

            st.divider()

            if st.button("📥 CARICA OFFERTE DA EXCEL", key="admin_load_google"):
                sync_google_to_parquet()
                st.success("Offerte inizializzate dal Google Sheet!")

    # -----------------------------------------------------
    # REPORT FINALE (ORA CON LOGICA TAVOLI/CARTE MANCANTI)
    # -----------------------------------------------------
    if st.session_state.get("show_report", False):
        st.header("🏆 Risultati Ufficiali")

        # Legge i dati appena scaricati da Google
        df_offerte = st.session_state.get("df_per_report", pd.DataFrame(columns=SHEET_HEADERS))
        df_offerte = df_offerte.sort_values(by="Offerta", ascending=False)
        
        assegnazioni = []
        carte_assegnate = set()
        tavoli_vincitori = set()

        # Calcolo vincitori (1 premio per tavolo, max offerta per carta)
        for _, r in df_offerte.iterrows():
            if r["Carta"] not in carte_assegnate and r["Tavolo"] not in tavoli_vincitori:
                assegnazioni.append(r)
                carte_assegnate.add(r["Carta"])
                tavoli_vincitori.add(r["Tavolo"])

        df_finale = pd.DataFrame(assegnazioni)

        # Logica Mancanze
        tutti_tavoli = set(df_tavoli["Nome Tavolo"].unique())
        tutte_carte = set(df_carte["Nome Carta"].unique())
        
        tavoli_senza_premio = tutti_tavoli - tavoli_vincitori
        carte_rimaste = tutte_carte - carte_assegnate

        # Visualizzazione Avvisi Mancanze
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if tavoli_senza_premio:
                st.error(f"😟 **Tavoli a mani vuote ({len(tavoli_senza_premio)}):**\n" + ", ".join(tavoli_senza_premio))
            else:
                st.success("🎉 Tutti i tavoli hanno vinto!")
        
        with col_m2:
            if carte_rimaste:
                st.warning(f"🃏 **Carte non assegnate ({len(carte_rimaste)}):**\n" + ", ".join(carte_rimaste))
            else:
                st.info("💎 Tutte le carte sono state assegnate!")

        # Tabella Risultati
        if not df_finale.empty:
            st.table(df_finale.style.format({"Offerta": "{} €"}))
            st.metric("💰 Totale Raccolto", f"{df_finale['Offerta'].sum()} €")

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

    @st.fragment(run_every=7)
    def ui_dinamica_carta(nome_carta, index):
        asta_aperta_local = get_asta_status()
        df = get_offerte_live()
        prezzo, tavolo = 0, "Nessuno"

        sub = df[df["Carta"] == nome_carta]
        if not sub.empty:
            top = sub.sort_values(by="Offerta", ascending=False).iloc[0]
            prezzo, tavolo = top["Offerta"], top["Tavolo"]

        if nome_carta in st.session_state.offerte_locali:
            loc = st.session_state.offerte_locali[nome_carta]
            if loc["Offerta"] > prezzo:
                prezzo, tavolo = loc["Offerta"], loc["Tavolo"]

        col_txt, col_btn = st.columns([2, 1])
        with col_txt:
            st.write(f"💰 Prezzo attuale: **{prezzo} €**")
            st.caption(f"In testa: {tavolo}")

        with col_btn:
            chiave = f"{nome_carta}_{index}"
            if not asta_aperta_local:
                st.button("🔒 Chiusa", disabled=True, use_container_width=True, key = f"lock_{chiave}")
            else:
                with st.expander("🚀 Punta"):
                    nuova = st.number_input("Importo (€)", min_value=int(prezzo)+1, step=1, key=f"input_{chiave}")
                    if st.button("Conferma", key=f"go_{chiave}", use_container_width=True):
                        append_offerta_locale({
                            "Tavolo": st.session_state.tavolo,
                            "Carta": nome_carta,
                            "Offerta": nuova,
                            "Utente": st.session_state.username
                        })
                        st.session_state.offerte_locali[nome_carta] = {
                            "Offerta": nuova,
                            "Tavolo": st.session_state.tavolo
                        }
                        st.success("Inviata!")
                        time.sleep(0.3)
                        st.rerun()

    for i, row in df_carte.iterrows():
        with st.container(border=True):
            col_img, col_content = st.columns([1, 3])
            with col_img:
                if row["Immagine"]:
                    st.image(row["Immagine"], use_container_width=True)
                else:
                    st.write("🖼️")
            with col_content:
                st.write(f"### {row['Nome Carta']}")
                ui_dinamica_carta(row["Nome Carta"], i)

    if st.sidebar.button("Log out"):
        st.session_state.user_logged = False
        st.rerun()
