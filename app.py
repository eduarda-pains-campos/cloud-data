from flask import Flask
import pandas as pd
import numpy as np
import itertools
from unidecode import unidecode
from azure.storage.blob import BlobServiceClient
import ahpy
from unittest.mock import patch
import os

app = Flask(__name__)

# -----------------------------------------------------------
# CONFIGURAÇÕES 
# -----------------------------------------------------------

AZURE_CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = "excel"
INPUT_FILE = "preferencias_final.xlsx"
OUTPUT_FILE = "ranking_gerado.xlsx"

# -----------------------------------------------------------
# SUAS FUNÇÕES (não alterei nada)
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
    return {k: (v - minv) / (maxv - minv) for k in d.items()}

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
# FUNÇÃO PRINCIPAL (roda quando acessar /run)
# -----------------------------------------------------------

def executar_processamento():

    blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container = blob_service.get_container_client(CONTAINER_NAME)
    blob_client = container.get_blob_client(INPUT_FILE)

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
    df_rank.to_excel("ranking.xlsx")

    blob_out = container.get_blob_client(OUTPUT_FILE)
    with open("ranking.xlsx", "rb") as f:
        blob_out.upload_blob(f, overwrite=True)

# -----------------------------------------------------------
# ROTAS FLASK
# -----------------------------------------------------------

@app.route("/")
def health():
    return "Running", 200

@app.route("/run")
def run():
    try:
        executar_processamento()
        return "Processamento concluído com sucesso!", 200
    except Exception as e:
        return f"Erro: {str(e)}", 500

# -----------------------------------------------------------
# INICIAR SERVIDOR
# -----------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
