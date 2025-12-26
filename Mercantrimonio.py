import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. Configurazione obbligatoria
st.set_page_config(page_title="Asta Matrimonio", icon="🏆")

st.title("🎁 Verifica Database")

# 2. Tentativo di connessione protetto
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    st.success("1. Connessione stabilita!")
    
    # Prova a leggere il foglio Carte
    df_carte = conn.read(worksheet="Carte")
    st.success("2. Foglio 'Carte' trovato e letto!")
    st.dataframe(df_carte.head()) # Ti mostra le prime righe per conferma
    
except Exception as e:
    st.error("Si è verificato un errore durante la lettura dei dati:")
    st.code(e)
    st.info("Verifica che il nome della tab sia esattamente 'Carte' e che il foglio sia condiviso come 'Editor' con chiunque abbia il link.")
"""
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
