import datetime
import json
import re
import time
import pandas as pd
import pdfplumber
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Controle Comercial", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    </style>
""",
    unsafe_allow_html=True,
)

# Conexões fixas em segundo plano (não ocupam espaço no ecrã)
URL_SCRIPT_ATIVA = "https://script.google.com/macros/s/AKfycbyOUlNVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf/exec"
ID_PLANILHA = "1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw"
URL_PLANILHA = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/edit"

if "refresh_key" not in st.session_state:
  st.session_state.refresh_key = int(time.time())


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

  # 1. Filial
  filial = "Filial PR"
  if "FILIAL SC" in texto_up or " UF SC" in texto_up or "/SC" in texto_up:
    filial = "Filial SC"
  elif "FILIAL RS" in texto_up or " UF RS" in texto_up or "/RS" in texto_up:
    filial = "Filial RS"
  elif "FILIAL PR" in texto_up or " UF PR" in texto_up or "/PR" in texto_up:
    filial = "Filial PR"

  # 2. Representante / Gerente
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

  # 3. Cliente
  match_cli = re.search(r"Cliente\s*[:|\n]?\s*([^\n]+)", texto, re.IGNORECASE)
  if match_cli:
    cliente = match_cli.group(1).strip()
    cliente = re.split(r"\s+ORDEM\s+DE\s+COMPRA", cliente, flags=re.IGNORECASE)[
        0
    ].strip()
  else:
    cliente = "Não identificado"

  # 4. Nº do Simulador
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

# --- PASSO 1: UPLOAD, CONFERÊNCIA INTELIGENTE E EDIÇÃO ---
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
    df_preview = pd.DataFrame(dados_lidos)

    # Mini-resumo rápido do lote por Filial
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📄 Total no Lote", len(df_preview))
    m2.metric(
        "🌲 Filial PR", len(df_preview[df_preview["Filial"] == "Filial PR"])
    )
    m3.metric(
        "🏖️ Filial SC", len(df_preview[df_preview["Filial"] == "Filial SC"])
    )
    m4.metric(
        "🧉 Filial RS", len(df_preview[df_preview["Filial"] == "Filial RS"])
    )

    # Detetor de duplicados no mesmo lote
    duplicados = df_preview[
        df_preview.duplicated(subset=["Simulador"], keep=False)
    ]
    if not duplicados.empty:
      sims_dup = ", ".join(duplicados["Simulador"].unique())
      st.warning(
          "⚠️ Atenção: Os seguintes simuladores estão repetidos neste lote:"
          f" **{sims_dup}**"
      )

    # Opções padrão que preenchem a tabela editável automaticamente
    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    with c1:
      status_padrao = st.selectbox(
          "Status Padrão para o Lote",
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
      log_padrao = st.checkbox("Logística OK (Todos)", value=True)
    with c3:
      st.write("")
      verba_padrao = st.checkbox("Verbas OK (Todos)", value=True)
    with c4:
      obs_padrao = st.text_input(
          "Observação Padrão", placeholder="Opcional..."
      )

    # Adiciona as colunas na tabela para poder alterar linha por linha se quiser
    df_preview["Logística OK"] = log_padrao
    df_preview["Verbas OK"] = verba_padrao
    df_preview["Status"] = status_padrao
    df_preview["Observação"] = obs_padrao

    st.markdown(
        "**💡 Dica:** Se precisar de mudar o status, filial ou observação de"
        " apenas um cliente, dê dois cliques diretamente na célula da tabela"
        " abaixo antes de enviar:"
    )

    # Tabela interativa estilo Excel
    df_editado = st.data_editor(
        df_preview,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Filial": st.column_config.SelectboxColumn(
                "Filial",
                options=["Filial PR", "Filial SC", "Filial RS"],
                required=True,
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=[
                    "1 - Em Triagem (Ana)",
                    "2 - Com Gerente / Niko (IA)",
                    "3 - Pendente Verba Manual (Kauê)",
                    "4 - Pronto para Gerar no Sankhya",
                    "5 - Gerado com Sucesso no Sankhya",
                    "❌ Travado - Limite Financeiro",
                    "❌ Travado - Divergência",
                ],
                required=True,
            ),
        },
    )

    if st.button(
        f"🚀 Confirmar e Enviar {len(df_editado)} Simulador(es) para a"
        " Planilha",
        type="primary",
        use_container_width=True,
    ):
      progresso = st.progress(0)
      enviados = 0
      detalhe_erro = ""

      for idx, item in df_editado.iterrows():
        payload = {
            "dataHora": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "filial": item["Filial"],
            "representante": item["Representante"],
            "cliente": item["Cliente"],
            "simulador": item["Simulador"],
            "logistica": "Sim" if item["Logística OK"] else "Não",
            "verbas": "Sim" if item["Verbas OK"] else "Não",
            "status": item["Status"],
            "obs": item["Observação"],
        }
        try:
          r = requests.post(
              URL_SCRIPT_ATIVA,
              data=json.dumps(payload),
              headers={"Content-Type": "text/plain; charset=utf-8"},
              timeout=20,
              allow_redirects=True,
          )
          if r.status_code in [200, 302]:
            enviados += 1
          else:
            detalhe_erro = f"Status HTTP {r.status_code}"
        except Exception as e:
          detalhe_erro = str(e)

        progresso.progress((idx + 1) / len(df_editado))

      time.sleep(1.5)
      st.session_state.refresh_key = int(time.time())

      if enviados > 0:
        st.success(
            f"✅ Pronto! {enviados} simulador(es) enviado(s) com sucesso!"
        )
        time.sleep(1)
        st.rerun()
      else:
        st.error(f"❌ Falha na comunicação: {detalhe_erro}")

st.divider()

# --- PASSO 2: PLANILHA SEMPRE VISÍVEL EM BAIXO ---
col_p1, col_p2 = st.columns([4, 1])
with col_p1:
  st.subheader("2. Planilha em Tempo Real")
with col_p2:
  if st.button("🔄 Atualizar Visualização", use_container_width=True):
    st.session_state.refresh_key = int(time.time())
    st.rerun()

url_planilha_ao_vivo = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA}/preview?v={st.session_state.refresh_key}"
components.iframe(url_planilha_ao_vivo, height=600, scrolling=True)
