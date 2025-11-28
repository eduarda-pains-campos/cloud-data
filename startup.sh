#!/bin/bash

# Ativar modo "strict" 
set -e

echo "Inicializando aplicação Streamlit..."

# Executa o app
streamlit run app.py --server.port=8501 --server.address=0.0.0.0

