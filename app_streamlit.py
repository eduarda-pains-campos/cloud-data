import streamlit as st
import pandas as pd
import requests

FLASK_URL = "http://localhost:8080/run"

st.title("🏅 Ranking dos Municípios - AHP")

if st.button("Gerar Ranking"):
    st.write("Processando... aguarde (pode levar alguns segundos).")

    try:
        response = requests.get(FLASK_URL)
        st.success("Ranking gerado com sucesso!")
    except Exception as e:
        st.error("Erro ao chamar o backend Flask:")
        st.error(str(e))

# Exibir o ranking gerado
try:
    df = pd.read_excel("ranking.xlsx")
    st.subheader("📊 Ranking Final")
    st.dataframe(df)
except:
    st.info("Gere o ranking para visualizar aqui.")
