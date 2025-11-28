# Imagem base
FROM python:3.11-slim

# Evita prompts interativos
ENV DEBIAN_FRONTEND=noninteractive

# Define diretório da aplicação
WORKDIR /app

# Copia requirements primeiro (melhor para cache)
COPY requirements.txt .

# Instala dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante da aplicação
COPY . .

# Dá permissão de execução ao script de inicialização
RUN chmod +x startup.sh

# Expõe a porta padrão do Streamlit
EXPOSE 8501

# Comando padrão ao iniciar o container
CMD ["./startup.sh"]




