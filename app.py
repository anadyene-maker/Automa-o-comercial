import datetime
import json
import re
import time
import pandas as pd
import pdfplumber
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Torre de Controle Comercial", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    </style>
""",
    unsafe_allow_html=True,
)

# URL corrigida com 'l' minúsculo em OUlNV exatamente como no seu Apps Script:
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyOUlNVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf/exec"
ID_PLANILHA = "1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw"
URL_PLANILHA = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/edit"

if "refresh_key" not in st.session_state:
  st.session_state.refresh_key = int(time.time())


# --- FUNÇÃO DE LEITURA AUTOMÁTICA E LIMPA DO PDF ---
def extrair_dados_pdf(arquivo):
  texto = ""
  try:
    with pdfplumber.open(arquivo) as pdf:
      for pagina in pdf.pages:
        texto += pagina.extract_text() or ""
  except Exception:
    return None

  texto_up = texto.upper()

  # 1. Detecta a Filial sozinho
  filial = "Filial PR"
  if "FILIAL SC" in texto_up or " UF SC" in texto_up or "/SC" in texto_up:
    filial = "Filial SC"
  elif "FILIAL RS" in texto_up or " UF RS" in texto_up or "/RS" in texto_up:
    filial = "Filial RS"
  elif "FILIAL PR" in texto_up or " UF PR" in texto_up or "/PR" in texto_up:
    filial = "Filial PR"

  # 2. Detecta Representante / Gerente (e remove o texto de Cidade/UF que vinha grudado)
  match_rep = re.search(
      r"(?:Supervisor\s*/\s*RCA|Representante|Vendedor|GER\.)\s*[:|\n]?\s*([^\n]+)",
      texto,
      re.IGNORECASE,
  )
  if match_rep:
    rep = match_rep.group(0).strip()
    rep = re.split(r"\s+Cidade\s+", rep, flags=re.IGNORECASE)[0].strip()
    rep = re.sub(
        r"^(?:Supervisor\s*/\s*RCA|Representante|Vendedor)\s*[:|-]?\s*",
        "",
        rep,
        flags=re.IGNORECASE,
    ).strip()
  else:
    rep = "Não identificado"

  # 3. Detecta Cliente (e limpa o texto 'ORDEM DE COMPRA' do final)
  match_cli = re.search(r"Cliente\s*[:|\n]?\s*([^\n]+)", texto, re.IGNORECASE)
  if match_cli:
    cliente = match_cli.group(1).strip()
    cliente = re.split(r"\s+ORDEM\s+DE\s+COMPRA", cliente, flags=re.IGNORECASE)[
        0
    ].strip()
  else:
    cliente = "Não identificado"

  # 4. Detecta Nº do Simulador
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
    "Selecione um ou vários arquivos PDF na sua pasta (segure Ctrl ou Shift"
    " para selecionar vários)",
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
        f"🚀 Confirmar e Enviar {len(dados_lidos)} Simulador(es) para a"
        " Planilha",
        type="primary",
        use_container_width=True,
    ):
      progresso = st.progress(0)
      enviados = 0
      ultimo_erro = ""

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
          # Envio em formato text/plain para evitar bloqueio de redirecionamento do Google
          r = requests.post(
              URL_APPS_SCRIPT,
              data=json.dumps(payload),
              headers={"Content-Type": "text/plain; charset=utf-8"},
              timeout=20,
              allow_redirects=True,
          )
          if r.status_code == 200 and "error" not in r.text.lower():
            enviados += 1
          else:
            ultimo_erro = f"Status {r.status_code} - Resposta: {r.text[:150]}"
        except Exception as e:
          ultimo_erro = str(e)

        progresso.progress((idx + 1) / len(dados_lidos))

      # Aguarda 1 segundo para o Google gravar e força a atualização da tabela lá embaixo
      time.sleep(1)
      st.session_state.refresh_key = int(time.time())

      if enviados > 0:
        st.success(
            f"✅ Pronto! {enviados} de {len(dados_lidos)} simulador(es)"
            " gravado(s) com sucesso na planilha!"
        )
      else:
        st.error(
            f"❌ O Google recusou a gravação. Detalhe técnico: {ultimo_erro}"
        )

st.divider()

# --- PASSO 2: PLANILHA SEMPRE VISÍVEL EMBAIXO ---
col_p1, col_p2 = st.columns([4, 1])
with col_p1:
  st.subheader("2. Planilha em Tempo Real")
with col_p2:
  if st.button("🔄 Atualizar Visualização", use_container_width=True):
    st.session_state.refresh_key = int(time.time())
    st.rerun()

# Carrega a planilha com carimbo de tempo único para obrigar o navegador a mostrar os dados novos
url_planilha_ao_vivo = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/htmlembed?single=true&widget=false&headers=false&v={st.session_state.refresh_key}"
components.iframe(url_planilha_ao_vivo, height=600, scrolling=True)
