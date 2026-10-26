import datetime
import json
import re
import pandas as pd
import pdfplumber
import requests
import streamlit as st

st.set_page_config(
    page_title="Torre de Controle - Simulações Comerciais", layout="wide"
)

st.title("📊 Torre de Controle - Simulações Comerciais")
st.markdown(
    "Arraste **vários PDFs** de uma só vez. O robô extrai tudo sozinho e envia"
    " para a planilha!"
)

URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyOU1NVz3lEXiFr3qPymosYno2ulA080jK8QPTL2eq1sLYwFhZh1-oFSAwzcuE3hZf/exec"
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
    st.markdown("**Configurações padrão para os PDFs enviados:**")
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
      logistica_ok = st.checkbox("Logística OK (Verificado)", value=False)
      verbas_ok = st.checkbox("Verbas OK (Verificado)", value=False)

    botao_enviar = st.form_submit_button(
        "🚀 Processar e Enviar Tudo Automaticamente"
    )

    if botao_enviar:
      if not arquivos_pdf:
        st.warning("Por favor, selecione pelo menos um ficheiro PDF.")
      else:
        barra_progresso = st.progress(0)
        sucessos = 0

        for i, arquivo_pdf in enumerate(arquivos_pdf):
          texto_extraido = ""
          try:
            with pdfplumber.open(arquivo_pdf) as pdf:
              for pagina in pdf.pages:
                texto_extraido += pagina.extract_text() or ""
          except Exception:
            pass

          filial_extraida = "Filial PR"
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
            resposta = requests.post(URL_APPS_SCRIPT, json=payload, timeout=10)
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
  st.markdown(
      f"[🔗 Abrir Planilha Completa no Google Drive]({URL_PLANILHA})"
  )

  if st.button("🔄 Carregar / Atualizar Dados da Tabela"):
    try:
      # Puxa os dados direto pelo canal seguro do Apps Script (sem erro 401)
      resposta = requests.get(URL_APPS_SCRIPT, timeout=10)
      if resposta.status_code == 200:
        dados = resposta.json()
        if len(dados) > 1:
          df = pd.DataFrame(dados[1:], columns=dados[0])
          st.dataframe(df, use_container_width=True, height=500)
        else:
          st.info("A planilha ainda está vazia.")
      else:
        st.error("Erro ao comunicar com o Google Sheets.")
    except Exception as e:
      st.error(f"Erro ao carregar dados: {e}")
  else:
    st.info("Clique no botão acima para carregar os dados atualizados.")
