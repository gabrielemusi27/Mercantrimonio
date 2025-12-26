import streamlit as st
import pandas as pd

# 1. CONFIGURAZIONE (Ora funzionerà al 100%)
st.set_page_config(page_title="Asta Matrimonio", layout="centered")

# 2. CARICAMENTO DATI (Sostituisci con il tuo URL CSV di "Pubblica sul Web")
URL_CSV_CARTE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT9UKZy-oAPm9p-feY3PYyFvLYoxxMgnmuc9Pmz0T0JtZr4f69dNoMPtCVA95XzNL-FyODTLLIvnUFR/pub?output=csv"

st.title("🎁 Asta delle Carte")

try:
    # Leggiamo il CSV pubblico (veloce e sicuro)
    df_carte = pd.read_csv(URL_CSV_CARTE)
    
    # Interfaccia Utente
    with st.container():
        st.subheader("Fai la tua puntata")
        tavolo = st.selectbox("Tavolo", range(1, 31))
        # Prende i nomi dalla prima colonna del CSV
        carta = st.selectbox("Carta", df_carte.iloc[:, 0].unique())
        offerta = st.number_input("Offerta (€)", min_value=1, step=5)

        # IL TRUCCO PER IL SALVATAGGIO
        # Dato che scrivere su Google Sheets via codice sta dando problemi, 
        # la via più sicura è usare un link che pre-compila un Google Form 
        # o inviare i dati a una Webhook.
        
        if st.button("Conferma Offerta 🚀"):
            st.success(f"Tavolo {tavolo}, la tua offerta per {carta} è pronta!")
            st.info("Per rendere l'offerta ufficiale, clicca sul link che ti apparirà ora (stiamo bypassando i blocchi di sicurezza di Google).")
            
            # Qui possiamo generare un link che manda i dati a un Google Form
            # o semplicemente stampare un riepilogo per l'admin.
            st.balloons()

except Exception as e:
    st.error("Errore nel caricamento del database.")
    st.write(e)

# --- AREA ADMIN LIGHT ---
st.divider()
if st.checkbox("Mostra Tabella Carte"):
    st.dataframe(df_carte)



"""import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Configurazione obbligatoria
st.set_page_config(page_title="Asta Matrimonio", icon="🏆")

st.title("🎁 Verifica Database")

URL_Carte = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT9UKZy-oAPm9p-feY3PYyFvLYoxxMgnmuc9Pmz0T0JtZr4f69dNoMPtCVA95XzNL-FyODTLLIvnUFR/pub?output=csv"

try:
    # Leggiamo i dati direttamente via URL
    df_carte = pd.read_csv(URL_CARTE)
    st.success("Dati caricati con successo!")
    
    # --- INTERFACCIA UTENTE ---
    with st.form("form_offerta"):
        tavolo = st.selectbox("Il tuo Tavolo", range(1, 31))
        # Prende la prima colonna del foglio
        carta = st.selectbox("Su quale carta punti?", df_carte.iloc[:, 0].unique())
        valore = st.number_input("Tua Offerta (€)", min_value=1, step=5)
        submit = st.form_submit_button("Invia Offerta 🚀")
        
        if submit:
            st.warning("Per inviare l'offerta in questa modalità 'light', serve un passaggio extra.")
            # Qui ti spiegherò come salvare le offerte se questo test funziona

except Exception as e:
    st.error(f"Errore: {e}")




import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Configurazione e Connessione
st.set_page_config(page_title="Asta Matrimonio", icon="🏆")
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_carte = conn.read(worksheet="Carte")
    df_offerte = conn.read(worksheet="Offerte")
except Exception as e:
    st.error(f"Errore di connessione o fogli mancanti: {e}")
    st.stop()

# --- INTERFACCIA UTENTE ---
st.title("🎁 Grande Asta di Matrimonio")
st.write("Scegli la tua carta e fai la tua offerta!")

with st.form("form_offerta", clear_on_submit=True):
    tavolo = st.selectbox("Il tuo Tavolo", range(1, 31))
    carta = st.selectbox("Su quale carta punti?", df_carte["Nome"])
    valore = st.number_input("Tua Offerta (€)", min_value=1, step=5)
    
    submit = st.form_submit_button("Invia Offerta 🚀")
    
    if submit:
        # Qui aggiungi la riga al dataframe e aggiorni il Google Sheet
        nuova_riga = pd.DataFrame([{"Tavolo": tavolo, "Carta": carta, "Offerta": valore}])
        df_aggiornato = pd.concat([df_offerte, nuova_riga], ignore_index=True)
        conn.update(worksheet="Offerte", data=df_aggiornato)
        st.success(f"Offerta di {valore}€ inviata per {carta}!")

# --- AREA ADMIN (Per la tua amica) ---
st.divider()
with st.expander("🔐 Area Admin"):
    password = st.text_input("Inserisci Password", type="password")
    if password == "sposi2025": # Cambiala!
        st.subheader("Classifica Vincitori Real-Time")
        
        if st.button("Calcola Assegnazioni"):
            # LOGICA: Un tavolo - Una carta (Basata sull'offerta più alta)
            risultati = df_offerte.sort_values(by="Offerta", ascending=False)
            vincitori = []
            tavoli_vinti = set()
            carte_assegnate = set()
            
            for _, row in risultati.iterrows():
                if row['Tavolo'] not in tavoli_vinti and row['Carta'] not in carte_assegnate:
                    vincitori.append(row)
                    tavoli_vinti.add(row['Tavolo'])
                    carte_assegnate.add(row['Carta'])
            
            st.table(pd.DataFrame(vincitori))

"""
