import datetime
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(
    page_title="Torre de Controle - Simulações Comerciais", layout="wide"
)

st.title("📊 Torre de Controle - Simulações Comerciais")
st.markdown(
    "Arraste o PDF do simulador para extrair os dados e copiá-los facilmente"
    " para a sua Planilha Google."
)

# Link da Planilha Google da Torre de Controle
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/edit"

aba1, aba2 = st.tabs(["➕ Ler PDF do Simulador", "📋 Aceder à Planilha Oficial"])

with aba1:
  st.subheader("Upload do PDF do Simulador")
  arquivo_pdf = st.file_uploader(
      "Arraste o ficheiro PDF enviado pelo WhatsApp", type=["pdf"]
  )

  texto_extraido = ""
  if arquivo_pdf is not None:
    with pdfplumber.open(arquivo_pdf) as pdf:
      for pagina in pdf.pages:
        texto_extraido += pagina.extract_text() or ""
    st.success("PDF lido com sucesso pela nuvem!")

  with st.form("form_simulacao"):
    col1, col2 = st.columns(2)
    with col1:
      filial = st.selectbox(
          "Filial", ["Filial RS", "Filial SC", "Filial PR", "Outras"]
      )
      representante = st.text_input("Nome do Representante")
      cliente = st.text_input("Nome do Cliente")
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
        "Detalhes / Texto extraído do PDF",
        value=texto_extraido[:400] if texto_extraido else "",
    )

    botao_gerar = st.form_submit_button("Gerar Linha para a Planilha")

    if botao_gerar:
      if representante and cliente:
        st.success(
            "Dados prontos! Copie os dados abaixo ou abra a planilha para colar"
            " na sua linha:"
        )
        data_hoje = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        linha_texto = (
            f"{data_hoje} \t {filial} \t {representante} \t {cliente} \t"
            f" {'Sim' if logistica_ok else 'Não'} \t"
            f" {'Sim' if verbas_ok else 'Não'} \t {status_atual} \t {obs}"
        )
        st.code(linha_texto, language="text")
        st.info(
            "💡 Dica: Basta copiar o texto acima e colar diretamente na sua"
            " primeira linha vazia da planilha!"
        )
      else:
        st.warning("Por favor, preencha pelo menos o Representante e o Cliente.")

with aba2:
  st.subheader("Planilha de Controle")
  st.markdown(
      "Pode abrir a sua Planilha Google oficial diretamente no botão abaixo para"
      " consultar ou colar os dados:"
  )
  st.markdown(
      "[🔗 Abrir Torre de Controle - Simulações Comerciais no Google"
      f" Sheets]({URL_PLANILHA})"
  )

  # Incorpora a planilha diretamente na página se o navegador permitir
  st.components.v1.iframe(URL_PLANILHA.replace("/edit", "/preview"), height=600)
