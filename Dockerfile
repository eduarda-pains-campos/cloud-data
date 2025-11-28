FROM python:3.10-slim

# Diretório de trabalho
WORKDIR /app

# Copia requirements
COPY requirements.txt .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o projeto
COPY . .

# Torna o script de inicialização executável
RUN chmod +x startup.sh

# Expõe as portas do Flask e do Streamlit
EXPOSE 8080
EXPOSE 8501

# Usa o script de inicialização
CMD ["./startup.sh"]



