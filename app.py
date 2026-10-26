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

st.title("📊 Controle - Simulações Comerciais")
st.markdown(
    "Arraste **vários PDFs** de uma só vez. O robô extrai tudo sozinho e envia"
    " para a planilha!"
)

# ⚠️ COLE A SUA URL DO APPS SCRIPT AQUI ENTRE AS ASPAS:
URL_APPS_SCRIPT = "AKfycbyOUlNVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf"
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/edit"

aba1, aba2 = st.tabs(
    ["➕ Enviar Múltiplos PDFs (Automático)", "📋 Tabela em Tempo Real"]
)

with aba1:
  st.subheader("Upload em Lote de PDFs")
  arquivos_pdf = st.file_uploader(
      "Arraste os ficheiros PDF dos simuladores aqui",
      type=["pdf"],
      accept_multiple_files=True,
  )

  if arquivos_pdf:
    st.info(
        f"📁 {len(arquivos_pdf)} ficheiro(s) pronto(s) para processamento"
        " automático."
    )

  with st.form("form_envio_automatico"):
    st.markdown(
        "**Configurações padrão para os PDFs enviados:**"
    )
    col1, col2 = st.columns(2)
    with col1:
      status_atual = st.selectbox(
          "Status Inicial do Processo",
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
    with col2:
      logistica_ok = st.checkbox(
          "Logística OK (Verificado)", value=False
      )
      verbas_ok = st.checkbox("Verbas OK (Verificado)", value=False)

    botao_enviar = st.form_submit_button(
        "🚀 Processar e Enviar Tudo Automaticamente"
    )

    if botao_enviar:
      if not arquivos_pdf:
        st.warning("Por favor, selecione pelo menos um ficheiro PDF.")
      elif not URL_APPS_SCRIPT.startswith("https://"):
        st.warning(
            "Por favor, configure a sua URL real do Apps Script no código"
            " (substitua o texto 'COLE_A_SUA_URL_DO_WEB_APP_AQUI')."
        )
      else:
        barra_progresso = st.progress(0)
        sucessos = 0

        for i, arquivo_pdf in enumerate(arquivos_pdf):
          texto_extraido = ""
          with pdfplumber.open(arquivo_pdf) as pdf:
            for pagina in pdf.pages:
              texto_extraido += pagina.extract_text() or ""

          # 1. Filial automática
          filial_extraida = "Filial PR"
          if "FILIAL SC" in texto_extraido.upper():
            filial_extraida = "Filial SC"
          elif "FILIAL RS" in texto_extraido.upper():
            filial_extraida = "Filial RS"
          elif "FILIAL PR" in texto_extraido.upper():
            filial_extraida = "Filial PR"

          # 2. Representante automático
          match_rep = re.search(
              r"Supervisor\s*/\s*RCA\s*[:|\n]?\s*([^\n]+)", texto_extraido
          )
          rep_extraido = match_rep.group(1).strip() if match_rep else "N/D"

          # 3. Cliente automático
          match_cli = re.search(
              r"Cliente\s*[:|\n]?\s*([^\n]+)", texto_extraido, re.IGNORECASE
          )
          cliente_extraido = (
              match_cli.group(1).strip() if match_cli else "N/D"
          )

          # 4. Número do Simulador automático
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
            " extraídos e enviados automaticamente para a planilha!"
        )

with aba2:
  st.subheader("📋 Tabela em Tempo Real")
  col_a, col_b = st.columns([3, 1])
  with col_a:
    st.markdown(
        f"[🔗 Abrir Planilha Completa no Google Drive]({URL_PLANILHA})"
    )
  with col_b:
    if st.button("🔄 Atualizar Tabela"):
      st.rerun()

  try:
    csv_url = "https://docs.google.com/spreadsheets/d/1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw/export?format=csv"
    df = pd.read_csv(csv_url)
    st.dataframe(df, use_container_width=True, height=500)
  except Exception:
    st.info(
        "Certifique-se de que a planilha está partilhada para leitura pública"
        " ou via Web App."
    )
