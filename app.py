import streamlit as st
import pandas as pd
import numpy as np
import itertools
from unidecode import unidecode
from azure.storage.blob import BlobServiceClient
import ahpy
from unittest.mock import patch
import os
from io import BytesIO

# -----------------------------------------------------------
# CONFIGURAÇÕES
# -----------------------------------------------------------
AZURE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER_NAME = "excel"
INPUT_FILE = "preferencias_final.xlsx"
OUTPUT_FILE = "ranking_gerado.xlsx"
LOCAL_RANKING = "ranking.xlsx"  # nome do arquivo gerado localmente

# -----------------------------------------------------------
# SUAS FUNÇÕES (mantidas do original)
# -----------------------------------------------------------

def tratamento_zeros1(df):
    epsilon = 0.0001
    for column in df.columns:
        if df[column].dtype != object:
            zeros_mask = (df[column] == 0)
            if zeros_mask.any():
                df.loc[zeros_mask, column] += epsilon

def normalize(values):
    min_val = min(values)
    max_val = max(values)
    # evitar divisão por zero
    if max_val == min_val:
        return [1.0 for _ in values]
    return [((v - min_val) / (max_val - min_val)) * 8 + 1 for v in values]

def julgamentos_alternativa(normalized_values, inverse):
    combos = []
    for i, j in itertools.combinations(range(len(normalized_values)), 2):
        if inverse:
            combos.append(normalized_values[j] / normalized_values[i])
        else:
            combos.append(normalized_values[i] / normalized_values[j])
    return combos

def arredonda_lista(lista, referencia):
    lista_arred = []
    for val in lista:
        if val >= 1:
            lista_arred.append(round(val))
        else:
            divisor = min(referencia, key=lambda x: abs(x - val))
            lista_arred.append(divisor)
    return lista_arred

def gera_dicionario_julgamentos(chave, julg):
    pares = list(itertools.combinations(chave, 2))
    return dict(zip(pares, julg))

def replace_zero_values(dic):
    for k, v in dic.items():
        if v == 0:
            dic[k] = 1

@patch('ahpy.ahpy.Compare._build_matrix')
def patched__build_matrix(self, original__build_matrix):
    self._matrix = np.zeros((len(self._elements), len(self._elements)))
    for pair, value in self._pairs.items():
        loc = tuple(self._elements.index(e) for e in pair)
        self._matrix[loc] = value

def julgamentos_coluna(df, coluna, precision, municipios, referencia):
    valores = normalize(df[coluna].values)
    nome = coluna.split('-')[0]
    inverter = coluna.split('-')[1]

    if inverter == 'bom':
        julg = julgamentos_alternativa(valores, inverse=False)
    else:
        julg = julgamentos_alternativa(valores, inverse=True)

    julg = arredonda_lista(julg, referencia)
    dicionario = gera_dicionario_julgamentos(municipios, julg)
    replace_zero_values(dicionario)

    with patch('ahpy.ahpy.Compare._build_matrix', patched__build_matrix):
        return ahpy.Compare(nome, dicionario, precision=precision, random_index='dd')

def normalize_dict(d):
    minv = min(d.values())
    maxv = max(d.values())
    if maxv == minv:
        return {k: 1.0 for k in d.keys()}
    return {k: (v - minv) / (maxv - minv) for k, v in d.items()}

def ordena_prioridades_alternativas(lista):
    prioridades = []
    for comp in lista:
        local = {str(k): v for k, v in comp.local_weights.items()}
        prioridades.append(dict(sorted(local.items())))
    return prioridades

def calculo_prioridade_global(variaveis, pesos_criterio, alternativas):
    ranking = []
    for cidade in alternativas[0]:
        total = sum(alternativas[i][cidade] * pesos_criterio[variaveis[i]] for i in range(len(variaveis)))
        ranking.append(total)
    return ranking

# -----------------------------------------------------------
# PROCESSAMENTO PRINCIPAL
# -----------------------------------------------------------

def executar_processamento():
    if not AZURE_CONNECTION_STRING:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING não configurado.")
    blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container = blob_service.get_container_client(CONTAINER_NAME)
    blob_client = container.get_blob_client(INPUT_FILE)

    # baixa o arquivo de entrada
    with open("entrada.xlsx", "wb") as f:
        f.write(blob_client.download_blob().readall())

    crit = pd.read_excel("entrada.xlsx", sheet_name="criterios")
    crit = crit.drop(crit.columns[0], axis=1)

    julg_crit = tuple(crit.values[np.triu_indices_from(crit.values, k=1)])
    dic_crit = gera_dicionario_julgamentos(crit.columns, julg_crit)

    with patch('ahpy.ahpy.Compare._build_matrix', patched__build_matrix):
        CRITERIA = ahpy.Compare("Criteria", dic_crit, precision=10, random_index='dd')

    df = pd.read_excel("entrada.xlsx", sheet_name="dados2022_geral")
    df_original = df.copy()

    df["Município"] = df["Município"].apply(lambda x: unidecode(x))
    tratamento_zeros1(df)

    MUNICIPIOS = tuple(df["Município"].values)
    MUNICIPIOS_ACENT = tuple(df_original["Município"].values)

    REFERENCIA = [1/i for i in range(1, 10)]

    objetos_comp = []
    for col in df.columns[9:]:
        if "-" in col:
            objetos_comp.append(julgamentos_coluna(df, col, 10, MUNICIPIOS, REFERENCIA))

    VARIAVEIS = list(crit.columns)

    prior_alt = ordena_prioridades_alternativas(objetos_comp)
    ranking_vals = calculo_prioridade_global(VARIAVEIS, CRITERIA.global_weights, prior_alt)

    ranking_final = dict(zip(MUNICIPIOS_ACENT, ranking_vals))
    ranking_final = dict(sorted(ranking_final.items(), key=lambda x: x[1], reverse=True))

    norm = normalize_dict(ranking_final)

    df_rank = pd.DataFrame.from_dict(norm, orient="index", columns=["Valor"])
    df_rank.index.name = "Município"
    df_rank.reset_index(inplace=True)

    # salva localmente e faz upload do resultado
    df_rank.to_excel(LOCAL_RANKING, index=False)

    blob_out = container.get_blob_client(OUTPUT_FILE)
    with open(LOCAL_RANKING, "rb") as f:
        blob_out.upload_blob(f, overwrite=True)

    return df_rank

# -----------------------------------------------------------
# FUNÇÕES AUXILIARES DE I/O (carregar ranking pra visualização)
# -----------------------------------------------------------

def carregar_ranking_local():
    if os.path.exists(LOCAL_RANKING):
        try:
            df = pd.read_excel(LOCAL_RANKING)
            # garantir colunas esperadas
            if "Município" in df.columns and "Valor" in df.columns:
                return df
            # aceitar variações
            if "Município" in df.columns and "Valor" not in df.columns:
                # tentativa de encontrar outra coluna numérica
                numcols = df.select_dtypes(include=[np.number]).columns
                if len(numcols) >= 1:
                    df = df.rename(columns={numcols[0]: "Valor"})
                    return df[["Município", "Valor"]]
        except Exception:
            pass
    return None

def baixar_ranking_blob_para_df():
    if not AZURE_CONNECTION_STRING:
        return None
    try:
        blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container = blob_service.get_container_client(CONTAINER_NAME)
        blob_client = container.get_blob_client(OUTPUT_FILE)
        stream = blob_client.download_blob().readall()
        df = pd.read_excel(BytesIO(stream))
        # padronizar colunas
        if "Município" not in df.columns:
            # tenta inferir primeira coluna como município
            cols = list(df.columns)
            if len(cols) >= 2:
                df = df.rename(columns={cols[0]: "Município", cols[1]: "Valor"})
        return df[["Município", "Valor"]]
    except Exception:
        return None

# -----------------------------------------------------------
# INTERFACE STREAMLIT (visual)
# -----------------------------------------------------------

st.set_page_config(page_title="Ranking AHP • Bacias PCJ", layout="wide")

st.title("Ranking das Bacias PCJ — Perdas Hídricas")
st.markdown(
    "Este dashboard exibe o ranking dos municípios das bacias PCJ em relação às perdas hídricas.\n\n"
    "Você pode **executar o processamento** (ler o arquivo do Blob, gerar o ranking e subir o resultado) ou **carregar** o ranking já gerado para visualizar gráficos."
)

# Área lateral: controles
with st.sidebar:
    st.header("Ações")
    run_button = st.button("Executar processamento (gerar ranking)")
    refresh_button = st.button("Recarregar ranking")
    st.markdown("---")
    top_n = st.slider("Mostrar top N municípios", min_value=5, max_value=50, value=15, step=1)
    sort_order = st.selectbox("Ordenação", options=["Descendente (maior primeiro)", "Ascendente (menor primeiro)"])
    st.markdown("---")
    st.write("Download")
    download_csv_btn = st.checkbox("Mostrar botão de download após carregar")
    st.markdown("---")
    st.write("Debug")
    show_raw = st.checkbox("Mostrar tabela completa")

# Execução do processamento
if run_button:
    st.info("Executando processamento... isto pode levar alguns instantes.")
    try:
        df_rank = executar_processamento()
        st.success("Processamento concluído com sucesso! Ranking gerado e enviado ao Blob.")
    except Exception as e:
        st.error(f"Erro durante o processamento: {e}")
        df_rank = None
else:
    df_rank = carregar_ranking_local()
    if df_rank is None:
        # tentar baixar do blob (caso o arquivo exista no Blob mas não localmente)
        df_rank = baixar_ranking_blob_para_df()

# Se não temos ranking ainda
if df_rank is None or df_rank.shape[0] == 0:
    st.warning("Nenhum ranking encontrado localmente. Rode o processamento ou verifique o Blob/arquivo.")
else:
    # Preparar dados
    df_rank = df_rank.copy()
    # garantir tipos
    df_rank["Valor"] = pd.to_numeric(df_rank["Valor"], errors="coerce").fillna(0)
    # ordenar
    ascending = (sort_order == "Ascendente (menor primeiro)")
    df_rank = df_rank.sort_values("Valor", ascending=ascending).reset_index(drop=True)

    # Visual: duas colunas
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Gráfico — Ranking por Município")
        # mostrar top N
        top_df = df_rank.head(top_n).copy() if not ascending else df_rank.tail(top_n).copy()
        # para visual horizontal (município no eixo y), vamos inverter a ordem para visual agradável
        top_df_plot = top_df.copy()
        top_df_plot = top_df_plot.set_index("Município")
        # exibir bar chart (streamlit usa altair internamente)
        st.bar_chart(top_df_plot["Valor"])

        st.markdown("**Observações:**\n- Valores normalizados entre 0 e 1 (conforme implementação).")
        # permitir download
        if download_csv_btn:
            csv = df_rank.to_csv(index=False).encode("utf-8")
            st.download_button("Baixar ranking (CSV)", data=csv, file_name="ranking.csv", mime="text/csv")
            # excel
            towrite = BytesIO()
            df_rank.to_excel(towrite, index=False, engine="openpyxl")
            towrite.seek(0)
            st.download_button("Baixar ranking (XLSX)", data=towrite, file_name="ranking.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with col2:
        st.subheader("Resumo e Estatísticas")
        st.metric("Municípios", len(df_rank))
        st.metric("Máximo (valor)", f"{df_rank['Valor'].max():.4f}")
        st.metric("Mínimo (valor)", f"{df_rank['Valor'].min():.4f}")
        st.markdown("### Top 5")
        top5 = df_rank.head(5)
        st.table(top5.reset_index(drop=True))

    # tabela completa
    if show_raw:
        st.subheader("Tabela completa")
        st.dataframe(df_rank)

st.markdown("---")
st.caption("Feito com Streamlit — se precisar de outros gráficos (mapa, séries temporais ou comparações entre bacias), eu adapto o dashboard.")
