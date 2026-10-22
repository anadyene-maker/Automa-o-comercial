import datetime
import re
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(
    page_title="Torre de Controle - Simulações Comerciais", layout="wide"
)

st.title("📊 Torre de Controle - Simulações Comerciais")
st.markdown(
    "Arraste o PDF do simulador e o sistema preenche os campos e gera a linha"
    " para a planilha automaticamente!"
)

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/edit"

aba1, aba2 = st.tabs(["➕ Ler PDF do Simulador", "📋 Aceder à Planilha Oficial"])

with aba1:
  st.subheader("Upload do PDF do Simulador")
  arquivo_pdf = st.file_uploader(
      "Arraste o ficheiro PDF enviado pelo WhatsApp", type=["pdf"]
  )

  texto_extraido = ""
  filial_extraida = "Filial PR"
  rep_extraido = ""
  cliente_extraido = ""

  if arquivo_pdf is not None:
    with pdfplumber.open(arquivo_pdf) as pdf:
      for pagina in pdf.pages:
        texto_extraido += pagina.extract_text() or ""

    # Extração inteligente dos dados do PDF da Semalo
    # 1. Filial
    if "FILIAL SC" in texto_extraido.upper():
      filial_extraida = "Filial SC"
    elif "FILIAL RS" in texto_extraido.upper():
      filial_extraida = "Filial RS"
    elif "FILIAL PR" in texto_extraido.upper():
      filial_extraida = "Filial PR"

    # 2. Representante / Supervisor
    match_rep = re.search(
        r"Supervisor\s*/\s*RCA\s*[:|\n]?\s*([^\n]+)", texto_extraido
    )
    if match_rep:
      rep_extraido = match_rep.group(1).strip()

    # 3. Cliente
    match_cli = re.search(
        r"Cliente\s*[:|\n]?\s*([^\n]+)", texto_extraido, re.IGNORECASE
    )
    if match_cli:
      cliente_extraido = match_cli.group(1).strip()

    st.success(
        "PDF lido e campos preenchidos automaticamente pela inteligência do"
        " sistema!"
    )

  with st.form("form_simulacao"):
    col1, col2 = st.columns(2)
    with col1:
      filial = st.selectbox(
          "Filial",
          [
              "Filial PR",
              "Filial RS",
              "Filial SC",
              "Filial SP",
              "Filial MS",
              "Outras",
          ],
          index=(
              0
              if filial_extraida == "Filial PR"
              else (
                  1
                  if filial_extraida == "Filial RS"
                  else 2 if filial_extraida == "Filial SC" else 0
              )
          ),
      )
      representante = st.text_input(
          "Nome do Representante", value=rep_extraido
      )
      cliente = st.text_input("Nome do Cliente", value=cliente_extraido)
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
              "5 - Gerado com Successo no Sankhya",
              "❌ Travado - Limite Financeiro",
              "❌ Travado - Divergência",
          ],
      )

    obs = st.text_area(
        "Resumo do Pedido / Dados do PDF",
        value=texto_extraido[:400] if texto_extraido else "",
    )

    botao_gerar = st.form_submit_button("Gerar Linha para a Planilha")

    if botao_gerar:
      if representante and cliente:
        st.success(
            "Pronto! Copie a linha abaixo e cole diretamente na sua planilha:"
        )
        data_hoje = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        linha_texto = (
            f"{data_hoje} \t {filial} \t {representante} \t {cliente} \t"
            f" {'Sim' if logistica_ok else 'Não'} \t"
            f" {'Sim' if verbas_ok else 'Não'} \t {status_atual} \t {obs}"
        )
        st.code(linha_texto, language="text")
      else:
        st.warning("Aguardando o upload do PDF para preencher os dados.")

with aba2:
  st.subheader("Planilha de Controle")
  st.markdown(
      "[🔗 Abrir Torre de Controle - Simulações Comerciais no Google"
      f" Sheets]({URL_PLANILHA})"
  )
  st.components.v1.iframe(URL_PLANILHA.replace("/edit", "/preview"), height=600)
