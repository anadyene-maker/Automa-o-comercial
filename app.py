import datetime
import json
import re
import pandas as pd
import pdfplumber
import requests
import streamlit as st

st.set_page_config(
    page_title="Controle - Simulações Comerciais", layout="wide"
)

st.title("📊 Torre de Controle - Simulações Comerciais")
st.markdown(
    "Arraste o PDF do simulador, o sistema extrai os dados (incluindo o"
    " simulador) e envia para a planilha!"
)

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyOUlNVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf/exec"
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/edit"

aba1, aba2 = st.tabs(["➕ Enviar PDF para a Planilha", "📋 Ver Planilha Oficial"])

with aba1:
  st.subheader("Upload do PDF do Simulador")
  arquivo_pdf = st.file_uploader(
      "Arraste o ficheiro PDF enviado pelo WhatsApp", type=["pdf"]
  )

  texto_extraido = ""
  filial_extraida = "Filial PR"
  rep_extraido = ""
  cliente_extraido = ""
  simulador_extraido = ""

  if arquivo_pdf is not None:
    with pdfplumber.open(arquivo_pdf) as pdf:
      for pagina in pdf.pages:
        texto_extraido += pagina.extract_text() or ""

    # Extrair Filial
    if "FILIAL SC" in texto_extraido.upper():
      filial_extraida = "Filial SC"
    elif "FILIAL RS" in texto_extraido.upper():
      filial_extraida = "Filial RS"
    elif "FILIAL PR" in texto_extraido.upper():
      filial_extraida = "Filial PR"

    # Extrair Representante
    match_rep = re.search(
        r"Supervisor\s*/\s*RCA\s*[:|\n]?\s*([^\n]+)", texto_extraido
    )
    if match_rep:
      rep_extraido = match_rep.group(1).strip()

    # Extrair Cliente
    match_cli = re.search(
        r"Cliente\s*[:|\n]?\s*([^\n]+)", texto_extraido, re.IGNORECASE
    )
    if match_cli:
      cliente_extraido = match_cli.group(1).strip()

    # Extrair Número do Simulador
    match_sim = re.search(
        r"Simulador\s*[:|\n]?\s*(\d+)", texto_extraido, re.IGNORECASE
    )
    if match_sim:
      simulador_extraido = match_sim.group(1).strip()

    # Limpar texto de observações (removendo o bloco de endereço da Semalo)
    obs_limpa = re.sub(
        r"SEMALO IND E COMERCIO.*?(?=Lançamento|Usuário|Status|$)",
        "",
        texto_extraido,
        flags=re.DOTALL | re.IGNORECASE,
    )
    obs_limpa = re.sub(
        r"Av\. Guaicurus,.*?(?=Lançamento|Usuário|$)",
        "",
        obs_limpa,
        flags=re.DOTALL | re.IGNORECASE,
    )
    obs_limpa = "\n".join([line for line in obs_limpa.split("\n") if line.strip()])

    st.success("PDF lido com sucesso! Dados extraídos com inteligência.")

  with st.form("form_envio_direto"):
    col1, col2 = st.columns(2)
    with col1:
      filial = st.selectbox(
          "Filial", ["Filial PR", "Filial RS", "Filial SC", "Outras"]
      )
      representante = st.text_input(
          "Nome do Representante", value=rep_extraido
      )
      cliente = st.text_input("Nome do Cliente", value=cliente_extraido)
      num_simulador = st.text_input(
          "Nº do Simulador", value=simulador_extraido
      )
    with col2:
      logistica_ok = st.checkbox("Logística OK (Verificado)")
      verbas_ok = st.checkbox("Verbas OK (Verificado)")
      status_atual = st.selectbox(
          "Status Atual do Processo",
          [
              "1 - Em Triagem (Ana)",
              "2 - Com Gerente / Niko (IA)",
              "3 - Pendente Verba Manual (Kauê)",
              "4 - Pronto para Gerar no Sankhya",
              "5 - Gerado com Sucesso no Sankhya",
              "❌ Travado - Limite Financeiro",
              "❌ Travado - Divergência",
          ],
      )

    obs = st.text_area(
        "Observações / Resumo limpo",
        value=obs_limpa[:300] if "obs_limpa" in locals() else "",
    )

    botao_enviar = st.form_submit_button(
        "🚀 Enviar Direto para a Planilha do Google"
    )

    if botao_enviar:
      if representante and cliente and URL_APPS_SCRIPT.startswith("https://"):
        payload = {
            "dataHora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "filial": filial,
            "representante": representante,
            "cliente": cliente,
            "simulador": num_simulador,
            "logistica": "Sim" if logistica_ok else "Não",
            "verbas": "Sim" if verbas_ok else "Não",
            "status": status_atual,
            "obs": obs,
        }
        try:
          resposta = requests.post(URL_APPS_SCRIPT, json=payload)
          if resposta.status_code == 200:
            st.success(
                "✨ Sucesso! Simulador e dados gravados na Planilha Google!"
            )
          else:
            st.error("Erro ao comunicar com o Google Sheets.")
        except Exception as e:
          st.error(f"Erro de conexão: {e}")
      else:
        st.warning(
            "Por favor, verifique se preencheu o Representante, Cliente e a"
            " URL do Apps Script."
        )

with aba2:
  st.subheader("Visualizar Planilha Oficial")
  st.markdown(
      "[🔗 Abrir Torre de Controle - Simulações Comerciais no Google"
      f" Sheets]({URL_PLANILHA})"
  )
  st.components.v1.iframe(URL_PLANILHA.replace("/edit", "/preview"), height=600)
