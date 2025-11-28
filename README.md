# Sistema de Análise de Dados  
Repositório para o projeto final da disciplina de **Computação em Nuvem**.

---

## Equipe
- **Eduarda Pains Campos** — 23882004 — eduarda.pc1@puccampinas.edu.br  
- **Tayana Araujo de Assis** — 23880883 — tayana.aa@puccampinas.edu.br  

---

## 📄 Descrição Geral
Este projeto consiste no desenvolvimento de um **painel de análise de dados de perdas hídricas** na região das **Bacias PCJ (Piracicaba, Capivari e Jundiaí)**.

O sistema tem como objetivo:

- Facilitar a visualização dos indicadores municipais de perdas hídricas;  
- Gerar rankings comparativos entre os municípios;  
- Permitir uma exploração visual interativa (dashboard);  
- Apoiar decisões em gestão hídrica e saneamento.  

A aplicação foi implementada em **Streamlit**, containerizada com **Docker** e implantada no **Azure Container Apps** via **CI/CD** automatizado com **GitHub Actions**.

---

## 📊 Dataset

- **Fonte dos dados:**  
  https://datacloud2025.blob.core.windows.net/excel/preferencias_final.xlsx  

- **Volume de dados esperado:**  
  Arquivo Excel contendo indicadores municipais das Bacias PCJ.

- **Licenciamento:**  
  Dados públicos.

---

## 🏗 Arquitetura da Solução

```mermaid
flowchart TD
A[GitHub Repository] --> B[GitHub Actions - CI/CD Pipeline]
B --> C[Docker Build]
C --> D[Azure Container Registry]
D --> E[Azure Container Apps - Deploy]
E --> F[Dashboard em Streamlit]
F --> G[Usuário]
