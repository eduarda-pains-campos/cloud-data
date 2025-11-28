#!/bin/bash

# Inicia o Flask em background (porta 8080)
python app.py &

# Inicia o Streamlit como aplicação principal (porta 8501)
streamlit run app_streamlit.py --server.address 0.0.0.0 --server.port 8501
