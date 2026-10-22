import datetime
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(
    page_title="Torre de Controle - Simulações Comerciais", layout="wide"
)

st.title("📊 Torre de Controle - Simulações Comerciais")
st.markdown(
    "Arraste o PDF do simulador para preencher os dados e gravá-los"
    " automaticamente na Planilha Google."
)

# URL da sua Planilha Google oficial
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/edit"

# Ligação à Planilha Google
try:
  conn = st.connection("gsheets", type="GsheetsConnection")
  df_existente = conn.read(spreadsheet=URL_PLANILHA, ttl="0")
except Exception as e:
  df_existente = pd.DataFrame(
      columns=[
          "Data/Hora",
          "Filial",
          "Representante",
          "Cliente",
          "Logística OK",
          "Verbas OK",
          "Status Atual",
          "Observações",
      ]
  )

aba1, aba2 = st.tabs(["➕ Nova Simulação (Via PDF)", "📋 Painel de Acompanhamento"])

with aba1:
  st.subheader("Upload do PDF do Simulador")
  arquivo_pdf = st.file_uploader(
      "Arraste o ficheiro PDF enviado pelo WhatsApp", type=["pdf"]
  )

  texto_pdf = ""
  if arquivo_pdf is not None:
    with pdfplumber.open(arquivo_pdf) as pdf:
      for pagina in pdf.pages:
        texto_pdf += pagina.extract_text() or ""
    st.success(
        "PDF lido com sucesso! Verifique e ajuste os campos abaixo se necessário:"
    )

  with st.form("form_simulacao"):
    col1, col2 = st.columns(2)
    with col1:
      filial = st.selectbox(
          "Filial", ["Filial RS", "Filial SC", "Filial PR", "Outras"]
      )
      representante = st.text_input("Nome do Representante")
      cliente = st.text_input("Nome do Cliente")
    with col2:
      logistica_ok = st.checkbox(
          "Logística OK (Frete Automático / RS Metropolitano verificado)"
      )
      verbas_ok = st.checkbox("Verbas OK (Verba promotor / saldo conferido)")
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
        "Observações / Resumo extraído do PDF",
        value=texto_pdf[:400] if texto_pdf else "",
    )

    botao_enviar = st.form_submit_button("Salvar na Planilha Google")

    if botao_enviar:
      if representante and cliente:
        nova_linha = pd.DataFrame(
            [{
                "Data/Hora": datetime.datetime.now().strftime(
                    "%d/%m/%Y %H:%M"
                ),
                "Filial": filial,
                "Representante": representante,
                "Cliente": cliente,
                "Logística OK": "Sim" if logistica_ok else "Não",
                "Verbas OK": "Sim" if verbas_ok else "Não",
                "Status Atual": status_atual,
                "Observações": obs,
            }]
        )

        try:
          df_atualizado = pd.concat(
              [df_existente, nova_linha], ignore_index=True
          )
          conn.update(spreadsheet=URL_PLANILHA, data=df_atualizado)
          st.success("Simulação guardada na Planilha Google com sucesso!")
        except Exception as e:
          st.error(
              "Erro ao atualizar a planilha. Certifique-se de que a partilha"
              " da planilha permite edição: "
              f"{e}"
          )
      else:
        st.warning("Por favor, preencha pelo menos o Representante e o Cliente.")

with aba2:
  st.subheader("Painel Geral de Acompanhamento")
  try:
    df_dados = conn.read(spreadsheet=URL_PLANILHA, ttl="0")
    if not df_dados.empty:
      st.dataframe(df_dados, use_container_width=True)
    else:
      st.info("Ainda não há simulações registadas.")
  except Exception as e:
    st.info("A carregar dados da planilha...")