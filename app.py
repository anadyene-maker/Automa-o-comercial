import datetime
import json
import re
import pandas as pd
import pdfplumber
import requests
import streamlit as st
import streamlit.components.v1 as components

# Configuração da página
st.set_page_config(page_title="Torre de Controle Comercial", layout="wide")

# Estilo visual limpo e moderno
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    </style>
""",
    unsafe_allow_html=True,
)

# Conexões já configuradas (não precisa mexer)
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyOU1NVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf/exec"
ID_PLANILHA = "1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw"
URL_PLANILHA = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/edit"

if "refresh_key" not in st.session_state:
  st.session_state.refresh_key = 0


# --- FUNÇÃO DE LEITURA AUTOMÁTICA DO PDF ---
def extrair_dados_pdf(arquivo):
  texto = ""
  try:
    with pdfplumber.open(arquivo) as pdf:
      for pagina in pdf.pages:
        texto += pagina.extract_text() or ""
  except Exception:
    return None

  texto_up = texto.upper()

  # 1. Detecta a Filial sozinho (procura por Filial ou pela UF da cidade do RCA/Cliente)
  filial = "Filial PR"
  if "FILIAL SC" in texto_up or " UF SC" in texto_up or "/SC" in texto_up:
    filial = "Filial SC"
  elif "FILIAL RS" in texto_up or " UF RS" in texto_up or "/RS" in texto_up:
    filial = "Filial RS"
  elif "FILIAL PR" in texto_up or " UF PR" in texto_up or "/PR" in texto_up:
    filial = "Filial PR"

  # 2. Detecta Representante / Gerente
  match_rep = re.search(
      r"(?:Supervisor\s*/\s*RCA|Representante|Vendedor|GER\.)\s*[:|\n]?\s*([^\n]+)",
      texto,
      re.IGNORECASE,
  )
  rep = match_rep.group(1).strip() if match_rep else "Não identificado"

  # 3. Detecta Cliente
  match_cli = re.search(r"Cliente\s*[:|\n]?\s*([^\n]+)", texto, re.IGNORECASE)
  cliente = match_cli.group(1).strip() if match_cli else "Não identificado"

  # 4. Detecta Nº do Simulador (no texto ou no próprio nome do arquivo PDF)
  match_sim = re.search(r"Simulador\s*[:|\n]?\s*(\d+)", texto, re.IGNORECASE)
  if match_sim:
    simulador = match_sim.group(1).strip()
  else:
    match_nome = re.search(r"(\d{5,7})", arquivo.name)
    simulador = match_nome.group(1) if match_nome else "S/N"

  return {
      "Arquivo": arquivo.name,
      "Filial": filial,
      "Representante": rep,
      "Cliente": cliente,
      "Simulador": simulador,
  }


# --- CABEÇALHO ---
col_titulo, col_link = st.columns([3, 1])
with col_titulo:
  st.title("📊 Torre de Controle — Simulações Comerciais")
with col_link:
  st.write("")
  st.link_button(
      "📂 Abrir Planilha no Google Sheets",
      URL_PLANILHA,
      use_container_width=True,
  )

st.divider()

# --- PASSO 1: UPLOAD E CONFERÊNCIA AUTOMÁTICA ---
st.subheader("1. Selecionar e Conferir PDFs")
arquivos = st.file_uploader(
    "Selecione um ou vários arquivos PDF na sua pasta (segure Ctrl ou Shift para selecionar vários)",
    type=["pdf"],
    accept_multiple_files=True,
)

if arquivos:
  dados_lidos = []
  for arq in arquivos:
    info = extrair_dados_pdf(arq)
    if info:
      dados_lidos.append(info)

  if dados_lidos:
    st.markdown(
        "**Confira abaixo o que o sistema leu automaticamente dos seus PDFs:**"
    )
    df_preview = pd.DataFrame(dados_lidos)
    st.dataframe(df_preview, use_container_width=True, hide_index=True)

    # Opções rápidas em uma única linha limpa
    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    with c1:
      status_lote = st.selectbox(
          "Status Inicial",
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
    with c2:
      st.write("")
      log_ok = st.checkbox("Logística OK", value=True)
    with c3:
      st.write("")
      verba_ok = st.checkbox("Verbas OK", value=True)
    with c4:
      obs_lote = st.text_input(
          "Observação (Opcional)", placeholder="Ex: Verificando com RCA..."
      )

    if st.button(
        f"🚀 Confirmar e Enviar {len(dados_lidos)} Simulador(es) para a Planilha",
        type="primary",
        use_container_width=True,
    ):
      progresso = st.progress(0)
      enviados = 0

      for idx, item in enumerate(dados_lidos):
        payload = {
            "dataHora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "filial": item["Filial"],
            "representante": item["Representante"],
            "cliente": item["Cliente"],
            "simulador": item["Simulador"],
            "logistica": "Sim" if log_ok else "Não",
            "verbas": "Sim" if verba_ok else "Não",
            "status": status_lote,
            "obs": obs_lote,
        }
        try:
          r = requests.post(URL_APPS_SCRIPT, json=payload, timeout=15)
          if r.status_code == 200:
            enviados += 1
        except Exception:
          pass
        progresso.progress((idx + 1) / len(dados_lidos))

      # Força a planilha de baixo a recarregar sozinha na mesma hora
      st.session_state.refresh_key += 1
      st.success(f"✅ Pronto! {enviados} simulador(es) gravado(s) com sucesso!")

st.divider()

# --- PASSO 2: PLANILHA SEMPRE VISÍVEL EMBAIXO ---
col_p1, col_p2 = st.columns([4, 1])
with col_p1:
  st.subheader("2. Planilha em Tempo Real")
with col_p2:
  if st.button("🔄 Atualizar Visualização", use_container_width=True):
    st.session_state.refresh_key += 1

url_planilha_ao_vivo = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/preview?rm=minimal&v={st.session_state.refresh_key}"
components.iframe(url_planilha_ao_vivo, height=600, scrolling=True)
