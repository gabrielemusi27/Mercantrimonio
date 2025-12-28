import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time

# 1. Configurazione Pagina
st.set_page_config(page_title="Mercante in Fiera - Asta", layout="wide")

# --- AUTH GOOGLE ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["connections"]["gsheets"]["service_account"], scopes=scope)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1g_FXSodJoWocTc8Ni12sBSDYviQ7oAQBDipVsLzfw5w"
sh = gc.open_by_key(SPREADSHEET_ID)

# --- FUNZIONI DI SCRITTURA E LETTURA DINAMICA ---

@st.cache_data(ttl=5)
def load_offerte(force=False):
    """Carica le offerte. Se force=True, ignora la cache per il report finale."""
    if force:
        ws = sh.worksheet("Offerte")
        return pd.DataFrame(ws.get_all_records())
    ws = sh.worksheet("Offerte")
    return pd.DataFrame(ws.get_all_records())

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

# --- CARICAMENTO DATI STATICI (SOLO UNA VOLTA) ---
if 'df_tavoli' not in st.session_state or 'df_carte' not in st.session_state:
    with st.spinner("Sincronizzazione tavoli e carte in corso..."):
        ws_t = sh.worksheet("Tavoli")
        st.session_state.df_tavoli = pd.DataFrame(ws_t.get_all_records())
        ws_c = sh.worksheet("Carte")
        st.session_state.df_carte = pd.DataFrame(ws_c.get_all_records())

# Shortcut per i dati in sessione
df_tavoli = st.session_state.df_tavoli
df_carte = st.session_state.df_carte

# --- GESTIONE LOGIN ---
if 'user_logged' not in st.session_state:
    st.session_state.user_logged = False

if not st.session_state.user_logged:
    st.title("🎫 Accesso all'Asta")
    with st.form("login_form"):
        nome = st.text_input("Il tuo Nome")
        tavolo = st.selectbox("Il tuo Tavolo", df_tavoli["Nome Tavolo"].unique())
        if st.form_submit_button("Entra nell'Asta"):
            if nome:
                st.session_state.user_logged = True
                st.session_state.username = nome.strip()
                st.session_state.tavolo = tavolo
                st.rerun()
            else:
                st.error("Inserisci il tuo nome.")
else:
    # --- STATO ASTA ---
    stato_asta = get_status_centrale()
    asta_bloccata = (stato_asta == "CHIUSA")

    # --- PANNELLO ADMIN ---
    if st.session_state.username == "Gabriele Musicò":
        with st.sidebar.expander("🛠 Pannello Admin", expanded=True):
            st.write(f"Stato: **{stato_asta}**")
            if not asta_bloccata:
                if st.button("🔴 CHIUDI ASTA"):
                    set_status_centrale("CHIUSA")
                    st.rerun()
            else:
                if st.button("🟢 RIAPRI ASTA"):
                    set_status_centrale("APERTA")
                    st.rerun()
            
            if st.button("📊 GENERA REPORT FINALE"):
                st.session_state.show_report = True
            
            if st.button("🔄 Forza ricarica Carte/Tavoli"):
                del st.session_state.df_tavoli
                del st.session_state.df_carte
                st.rerun()

    # --- LOGICA REPORT FINALE (CASCATA) ---
    if st.session_state.get('show_report', False):
        st.header("🏆 Assegnazione Finale Univoca")
        df_fresche = load_offerte(force=True)
        
        # Algoritmo Greedy
        df_lavoro = df_fresche.merge(df_carte[['Nome Carta', 'Premio']], left_on='Carta', right_on='Nome Carta')
        df_lavoro = df_lavoro.sort_values(by=['Offerta', 'Premio'], ascending=False)
        
        assegnazioni, c_presse, t_presi = [], set(), set()
        for _, r in df_lavoro.iterrows():
            if r['Carta'] not in c_presse and r['Tavolo'] not in t_presi:
                assegnazioni.append({"Carta": r['Carta'], "Tavolo": r['Tavolo'], "Offerta": r['Offerta'], "Premio": r['Premio']})
                c_presse.add(r['Carta']), t_presi.add(r['Tavolo'])
        
        df_f = pd.DataFrame(assegnazioni)
        
        # Tavoli e Carte rimasti fuori
        t_out = set(df_tavoli["Nome Tavolo"].unique()) - t_presi
        c_out = set(df_carte["Nome Carta"].unique()) - c_presse
        
        if t_out: st.error(f"Tavoli senza premi: {', '.join(t_out)}")
        if c_out: st.warning(f"Carte non assegnate: {', '.join(c_out)}")
        
        if not df_f.empty:
            st.table(df_f.sort_values(by="Premio", ascending=False))
            st.metric("Totale Raccolto", f"{df_f['Offerta'].sum()} €")
        
        if st.button("Chiudi Report"):
            st.session_state.show_report = False
            st.rerun()
        st.divider()

    # --- INTERFACCIA UTENTE ---
    st.title(f"🎁 Benvenuto all'Asta, {st.session_state.username}!")
    st.sidebar.write(f"📍 Tavolo: {st.session_state.tavolo}")
    if st.sidebar.button("Logout"):
        st.session_state.user_logged = False
        st.rerun()

    if asta_bloccata:
        st.error("🚫 L'asta è terminata!")
    else:
        st.success("✅ Asta aperta: fai la tua puntata!")

    # --- LISTA CARTE ---
    df_offerte = load_offerte()
    
    # Calcolo prezzi attuali
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
                if row['Img']: st.image(row['Img'], use_container_width=True)
                else: st.write("🃏")
            with col_txt:
                st.write(f"### {row['Carta']}")
                st.write(f"💰 **{row['Prezzo']} €**")
                st.caption(f"Tavolo in testa: {row['Tavolo']}")
            with col_btn:
                chiave = f"btn_{row['Carta']}_{i}"
                if asta_bloccata:
                    st.button("Chiusa", key=chiave, disabled=True, use_container_width=True)
                else:
                    with st.popover("Punta", use_container_width=True):
                        nuova = st.number_input("Tua offerta", min_value=int(row['Prezzo'])+5, step=5, key=f"in_{chiave}")
                        if st.button("Conferma", key=f"go_{chiave}"):
                            append_row("Offerte", {"T": st.session_state.tavolo, "C": row['Carta'], "O": nuova, "U": st.session_state.username})
                            st.cache_data.clear()
                            st.success("Puntata fatta!")
                            time.sleep(0.5)
                            st.rerun()
