import datetime
import re
import pandas as pd
import pdfplumber
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Controle - Simulações Comerciais", layout="wide"
)

st.title("📊Controle - Simulações Comerciais")
st.markdown(
    "Arraste **vários PDFs** de uma só vez. O robô extrai tudo sozinho e envia"
    " para a planilha!"
)

# URL EXATA corrigida conforme o seu print original:
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyOU1NVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf/exec"
ID_PLANILHA = "1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw"
URL_PLANILHA = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/edit"

# Memória interna para forçar a atualização da planilha sem precisar de F5
if "versao_tabela" not in st.session_state:
  st.session_state.versao_tabela = 0

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
        erros_detalhe = []

        for i, arquivo_pdf in enumerate(arquivos_pdf):
          texto_extraido = ""
          try:
            with pdfplumber.open(arquivo_pdf) as pdf:
              for pagina in pdf.pages:
                texto_extraido += pagina.extract_text() or ""
          except Exception as e:
            erros_detalhe.append(f"Erro ao ler {arquivo_pdf.name}: {e}")
            continue

          # 1. Filial automática
          filial_extraida = "Filial PR"
          texto_maiusculo = texto_extraido.upper()
          if "FILIAL SC" in texto_maiusculo or " UF SC" in texto_maiusculo:
            filial_extraida = "Filial SC"
          elif "FILIAL RS" in texto_maiusculo or " UF RS" in texto_maiusculo:
            filial_extraida = "Filial RS"
          elif "FILIAL PR" in texto_maiusculo or " UF PR" in texto_maiusculo:
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
          cliente_extraido = match_cli.group(1).strip() if match_cli else "N/D"

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
            # Envia como texto simples para evitar bloqueios de segurança do Google
            resposta = requests.post(
                URL_APPS_SCRIPT,
                data=json.dumps(payload)
                if "json" in globals()
                else str(payload),
                headers={"Content-Type": "text/plain; charset=utf-8"},
                timeout=15,
            )
            if resposta.status_code == 200:
              sucessos += 1
            else:
              erros_detalhe.append(
                  f"{arquivo_pdf.name}: Status {resposta.status_code}"
              )
          except Exception as e:
            erros_detalhe.append(f"{arquivo_pdf.name}: {e}")

          barra_progresso.progress((i + 1) / len(arquivos_pdf))

        # Atualiza o contador para recarregar a planilha automaticamente na Aba 2
        st.session_state.versao_tabela += 1

        if sucessos > 0:
          st.success(
              f"✨ Concluído! {sucessos} de {len(arquivos_pdf)} simuladores"
              " foram enviados para a planilha!"
          )
        if erros_detalhe:
          with st.expander("Ver detalhes técnicos de avisos"):
            for err in erros_detalhe:
              st.write(err)

with aba2:
  col_a, col_b = st.columns([3, 1])
  with col_a:
    st.markdown(
        f"### 📋 Visualização da Planilha ([🔗 Abrir no Google Sheets]({URL_PLANILHA}))"
    )
  with col_b:
    if st.button("🔄 Forçar Atualização da Planilha", use_container_width=True):
      st.session_state.versao_tabela += 1

  # Truque definitivo: adiciona um parâmetro único (?v=...) que obriga o navegador a atualizar a planilha sem apertar F5!
  url_iframe_sem_cache = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/preview?v={st.session_state.versao_tabela}"
  components.iframe(url_iframe_sem_cache, height=650, scrolling=True)
