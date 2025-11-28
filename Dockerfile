# Imagem base
FROM python:3.10-slim

# Diretório de trabalho
WORKDIR /app

# Copia requirements 
COPY requirements.txt .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o projeto
COPY . .

# Expõe porta do Flask
EXPOSE 8080

# Comando de inicialização
CMD ["python", "app.py"]

