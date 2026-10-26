import datetime
import json
import re
import pandas as pd
import pdfplumber
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="Controle - Simulações Comerciais", layout="wide"
)

st.title("📊 Torre de Controle - Simulações Comerciais")
st.markdown(
    "Arraste **vários PDFs** de uma só vez, o sistema processa todos e atualiza"
    " a planilha automaticamente!"
)

# Cole aqui a sua URL do Web App do Google Apps Script:
URL_APPS_SCRIPT = "COLE_A_SUA_URL_DO_WEB_APP_AQUI"
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/edit"

# Atualização automática da tabela a cada 15 segundos (sem precisar de F5)
st_autorefresh(interval=15000, key="datarefresh")

aba1, aba2 = st.tabs(
    ["➕ Enviar Múltiplos PDFs", "📋 Tabela Atualizada em Tempo Real"]
)

with aba1:
  st.subheader("Upload em Lote de PDFs")
  # accept_multiple_files=True permite selecionar vários ficheiros de uma vez
  arquivos_pdf = st.file_uploader(
      "Selecione ou arraste vários ficheiros PDF",
      type=["pdf"],
      accept_multiple_files=True,
  )

  if arquivos_pdf:
    st.info(f"📁 {len(arquivos_pdf)} ficheiro(s) selecionado(s) para envio.")

  with st.form("form_envio_lote"):
    col1, col2 = st.columns(2)
    with col1:
      filial_padrao = st.selectbox(
          "Filial Padrão para o Lote",
          ["Filial PR", "Filial RS", "Filial SC", "Outras"],
      )
    with col2:
      status_atual = st.selectbox(
          "Status Atual do Processo (para todos)",
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

    logistica_ok = st.checkbox("Logística OK (Verificado para todos)")
    verbas_ok = st.checkbox("Verbas OK (Verificado para todos)")

    botao_enviar_lote = st.form_submit_button(
        "🚀 Enviar Todos os PDFs para a Planilha"
    )

    if botao_enviar_lote:
      if not arquivos_pdf:
        st.warning(
            "Por favor, selecione pelo menos um ficheiro PDF antes de enviar."
        )
      elif not URL_APPS_SCRIPT.startswith("https://"):
        st.warning("Por favor, configure a URL do Apps Script no código.")
      else:
        barra_progresso = st.progress(0)
        sucessos = 0

        for i, arquivo_pdf in enumerate(arquivos_pdf):
          texto_extraido = ""
          with pdfplumber.open(arquivo_pdf) as pdf:
            for pagina in pdf.pages:
              texto_extraido += pagina.extract_text() or ""

          # Extrações automáticas por PDF
          filial_extraida = filial_padrao
          if "FILIAL SC" in texto_extraido.upper():
            filial_extraida = "Filial SC"
          elif "FILIAL RS" in texto_extraido.upper():
            filial_extraida = "Filial RS"
          elif "FILIAL PR" in texto_extraido.upper():
            filial_extraida = "Filial PR"

          match_rep = re.search(
              r"Supervisor\s*/\s*RCA\s*[:|\n]?\s*([^\n]+)", texto_extraido
          )
          rep_extraido = match_rep.group(1).strip() if match_rep else "N/D"

          match_cli = re.search(
              r"Cliente\s*[:|\n]?\s*([^\n]+)", texto_extraido, re.IGNORECASE
          )
          cliente_extraido = (
              match_cli.group(1).strip() if match_cli else "N/D"
          )

          match_sim = re.search(
              r"Simulador\s*[:|\n]?\s*(\d+)", texto_extraido, re.IGNORECASE
          )
          simulador_extraido = match_sim.group(1).strip() if match_sim else ""

          payload = {
              "dataHora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
              "filial": filial_extraida,
              "representante": rep_extraido,
              "cliente": cliente_extraido,
              "simulador": simulador_extraido,
              "logistica": "Sim" if logistica_ok else "Não",
              "verbas": "Sim" if verbas_ok else "Não",
              "status": status_atual,
              "obs": "",
          }

          try:
            resposta = requests.post(URL_APPS_SCRIPT, json=payload)
            if resposta.status_code == 200:
              sucessos += 1
          except Exception:
            pass

          barra_progresso.progress((i + 1) / len(arquivos_pdf))

        st.success(
            f"✨ Concluído! {sucessos} de {len(arquivos_pdf)} simuladores foram"
            " enviados com sucesso para a planilha!"
        )

with aba2:
  st.subheader("📋 Tabela Atualizada Automaticamente")
  st.markdown(
      f"[🔗 Abrir Planilha Completa no Google Drive]({URL_PLANILHA})"
  )

  try:
    csv_url = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/export?format=csv"
    df = pd.read_csv(csv_url)
    st.dataframe(df, use_container_width=True, height=500)
  except Exception:
    st.info(
        "Certifique-se de que a planilha está partilhada com permissão de"
        " leitura."
    )
