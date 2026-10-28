import datetime
import json
import re
import time
from fpdf import FPDF
import pandas as pd
import pdfplumber
import requests
import streamlit as st
import streamlit.components.v1 as components

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Hub Comercial Sul", page_icon="💼", layout="wide"
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    </style>
""",
    unsafe_allow_html=True,
)

# --- LINKS E CONEXÕES ---
URL_SCRIPT_ATIVA = "https://script.google.com/macros/s/AKfycbyOUlNVz3lEXiFr3QpYmosYno2ulAO80jK8QPTL2eq1sLYyWFhZh1-oFSAwzcuE3hZf/exec"
ID_PLANILHA_SIMULADORES = "1jAFEvGxrHuzdqCrC8VU2bs5_d_D4u918f5UCD2JtBmw"
URL_PLANILHA_SIMULADORES = (
    f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA_SIMULADORES}/edit"
)

# Se a planilha de Demandas for em outro arquivo ou tiver um GID (aba) específico, você pode colar o link completo aqui:
LINK_PADRAO_DEMANDAS = "https://docs.google.com/spreadsheets/d/1CWIF-pJ2W6FKR4LN3fhj3IhjEvM7q7muF3j3uZFmT0o/edit"

# --- MEMÓRIA DO SISTEMA (SESSION STATE) ---
if "refresh_key" not in st.session_state:
  st.session_state.refresh_key = int(time.time())

# Chave dinâmica para limpar o file_uploader automaticamente após o envio
if "uploader_key" not in st.session_state:
  st.session_state.uploader_key = 0

if "ultimos_enviados" not in st.session_state:
  st.session_state.ultimos_enviados = pd.DataFrame()


# --- FUNÇÃO 1: LEITURA AUTOMÁTICA DOS PDFs ---
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


# --- FUNÇÃO 2: GERADOR DE RELATÓRIO PDF PARA GERENTES ---
def limpar_texto_pdf(texto):
  if pd.isna(texto):
    return ""
  # Remove emojis e caracteres fora do padrão latin-1 para não quebrar a fonte do PDF
  return (
      str(texto)
      .encode("latin-1", "ignore")
      .decode("latin-1")
      .replace("Travado", "[TRAVADO]")
      .strip()
  )


def gerar_pdf_gerencia(df_filtrado, nome_filial):
  pdf = FPDF(orientation="L", unit="mm", format="A4")
  pdf.add_page()

  # Cabeçalho do Relatório
  pdf.set_font("Helvetica", "B", 15)
  pdf.set_text_color(30, 58, 138)
  pdf.cell(
      0,
      10,
      limpar_texto_pdf(f"Relatorio de Simuladores Comerciais - {nome_filial}"),
      ln=True,
  )

  pdf.set_font("Helvetica", "", 10)
  pdf.set_text_color(80, 80, 80)
  data_atual = datetime.datetime.now().strftime("%d/%m/%Y as %H:%M")
  pdf.cell(
      0,
      6,
      f"Gerado em: {data_atual}  |  Total de Simuladores listados:"
      f" {len(df_filtrado)}",
      ln=True,
  )
  pdf.ln(4)

  # Cabeçalho da Tabela
  pdf.set_fill_color(44, 62, 80)
  pdf.set_text_color(255, 255, 255)
  pdf.set_font("Helvetica", "B", 9)

  larguras = [22, 58, 82, 22, 55, 38]
  colunas = [
      "Simulador",
      "Representante / Ger.",
      "Cliente",
      "Log/Verba",
      "Status Atual",
      "Observacoes",
  ]

  for larg, col in zip(larguras, colunas):
    pdf.cell(larg, 8, col, border=1, fill=True, align="C")
  pdf.ln()

  # Linhas da Tabela
  pdf.set_text_color(0, 0, 0)
  pdf.set_font("Helvetica", "", 8)

  fill = False
  for _, row in df_filtrado.iterrows():
    pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(
        255, 255, 255
    )

    sim = limpar_texto_pdf(row.get("Simulador", ""))[:12]
    rep = limpar_texto_pdf(row.get("Representante", ""))[:33]
    cli = limpar_texto_pdf(row.get("Cliente", ""))[:46]
    log_v = f"L:{limpar_texto_pdf(row.get('Logística OK', 'S'))[:1]} / V:{limpar_texto_pdf(row.get('Verbas OK', 'S'))[:1]}"
    status = limpar_texto_pdf(row.get("Status", row.get("Status Atual", "")))[
        :32
    ]
    obs = limpar_texto_pdf(row.get("Observação", row.get("Observações", "")))[
        :22
    ]

    pdf.cell(larguras[0], 7, sim, border=1, fill=True, align="C")
    pdf.cell(larguras[1], 7, rep, border=1, fill=True)
    pdf.cell(larguras[2], 7, cli, border=1, fill=True)
    pdf.cell(larguras[3], 7, log_v, border=1, fill=True, align="C")
    pdf.cell(larguras[4], 7, status, border=1, fill=True)
    pdf.cell(larguras[5], 7, obs, border=1, fill=True)
    pdf.ln()
    fill = not fill

  return bytes(pdf.output())


# --- CABEÇALHO DO APP ---
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
  st.title("💼 Hub Comercial Sul — Gestão & Demandas")
with col_t2:
  st.write("")
  st.link_button(
      "📂 Abrir Google Sheets Completo",
      URL_PLANILHA_SIMULADORES,
      use_container_width=True,
  )

# --- NAVEGAÇÃO PRINCIPAL (TUDO NO MESMO LINK) ---
aba_sim, aba_demandas, aba_pdf = st.tabs([
    "🚀 1. Envio & Controle de Simuladores",
    "📌 2. Registro de Demandas (Gerência/RCA)",
    "📄 3. Extrair Relatório PDF (Gerentes)",
])

# ==============================================================================
# ABA 1: SIMULADORES (UPLOAD COM LIMPEZA AUTOMÁTICA + PLANILHA AO VIVO)
# ==============================================================================
with aba_sim:
  st.subheader("Selecionar e Conferir Simuladores (PDF)")

  # A chave dinâmica uploader_key limpa os arquivos automaticamente após o envio!
  arquivos = st.file_uploader(
      "Selecione um ou vários arquivos PDF na sua pasta (segure Ctrl ou Shift"
      " para vários)",
      type=["pdf"],
      accept_multiple_files=True,
      key=f"uploader_{st.session_state.uploader_key}",
  )

  if arquivos:
    dados_lidos = []
    for arq in arquivos:
      info = extrair_dados_pdf(arq)
      if info:
        dados_lidos.append(info)

    if dados_lidos:
      df_preview = pd.DataFrame(dados_lidos)

      # Mini-resumo rápido por Filial
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

      # Detector de duplicados
      duplicados = df_preview[
          df_preview.duplicated(subset=["Simulador"], keep=False)
      ]
      if not duplicados.empty:
        sims_dup = ", ".join(duplicados["Simulador"].unique())
        st.warning(
            f"⚠️ Atenção: Simuladores repetidos neste lote: **{sims_dup}**"
        )

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

      df_preview["Logística OK"] = log_padrao
      df_preview["Verbas OK"] = verba_padrao
      df_preview["Status"] = status_padrao
      df_preview["Observação"] = obs_padrao

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
          f"🚀 Confirmar e Enviar {len(df_editado)} Simulador(es)",
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

        if enviados > 0:
          # Guarda na memória para uso rápido no PDF e limpa a barra de upload!
          st.session_state.ultimos_enviados = pd.concat(
              [st.session_state.ultimos_enviados, df_editado], ignore_index=True
          )
          st.session_state.uploader_key += 1
          st.session_state.refresh_key = int(time.time())
          st.success(
              f"✅ Pronto! {enviados} simulador(es) enviado(s)! Limpando"
              " área de envio..."
          )
          time.sleep(1.2)
          st.rerun()
        else:
          st.error(f"❌ Falha na comunicação: {detalhe_erro}")

  st.divider()

  col_p1, col_p2 = st.columns([4, 1])
  with col_p1:
    st.subheader("📋 Planilha de Simuladores em Tempo Real")
  with col_p2:
    if st.button("🔄 Atualizar Planilha", use_container_width=True):
      st.session_state.refresh_key = int(time.time())
      st.rerun()

  url_sim_ao_vivo = f"https://docs.google.com/spreadsheets/d/{ID_PLANILHA_SIMULADORES}/preview?v={st.session_state.refresh_key}"
  components.iframe(url_sim_ao_vivo, height=600, scrolling=True)

# ==============================================================================
# ABA 2: REGISTRO DE DEMANDAS DA GERÊNCIA / RCA (EDITÁVEL DIRETO NO APP)
# ==============================================================================
with aba_demandas:
  st.subheader("📌 Registro de Demandas da Gerência / RCA")
  st.markdown(
      "Você pode **marcar os checkboxes de Concluído, mudar Status e digitar"
      " observações diretamente na tabela abaixo**, sem sair do aplicativo:"
  )

  with st.expander(
      "🔗 Configurar Link da Aba/Planilha de Demandas (se estiver em outro"
      " arquivo)"
  ):
    url_demandas_input = st.text_input(
        "Cole aqui o link da sua planilha de Registro de Demandas:",
        value=LINK_PADRAO_DEMANDAS,
    ).strip()

  # Transforma o link em modo de edição limpa (rm=minimal) para poder editar dentro do Streamlit
  if "/edit" in url_demandas_input:
    partes = url_demandas_input.split("/edit")
    # Preserva o #gid=... caso seja uma aba específica
    gid_hash = ""
    if "#gid=" in partes[1]:
      gid_hash = "#gid=" + partes[1].split("#gid=")[1]
    url_demandas_embed = f"{partes[0]}/edit?rm=minimal{gid_hash}"
  else:
    url_demandas_embed = url_demandas_input

  components.iframe(url_demandas_embed, height=750, scrolling=True)

# ==============================================================================
# ABA 3: GERADOR DE RELATÓRIO EM PDF POR FILIAL PARA OS GERENTES
# ==============================================================================
with aba_pdf:
  st.subheader("📄 Gerar Relatório em PDF por Filial (Para Gerentes)")
  st.markdown(
      "Escolha a Filial para gerar um PDF limpo e formatado com o status dos"
      " simuladores para enviar ao gerente da região."
  )

  # Tenta buscar os dados completos da planilha (via Apps Script ou CSV) ou usa os lotes enviados na sessão
  df_relatorio = pd.DataFrame()
  try:
    r_get = requests.get(URL_SCRIPT_ATIVA, timeout=8)
    if r_get.status_code == 200:
      dados_json = r_get.json()
      if isinstance(dados_json, list) and len(dados_json) > 1:
        df_relatorio = pd.DataFrame(dados_json[1:], columns=dados_json[0])
  except Exception:
    pass

  if df_relatorio.empty and not st.session_state.ultimos_enviados.empty:
    df_relatorio = st.session_state.ultimos_enviados.copy()

  # Renomeia colunas caso venham da planilha com nomes ligeiramente diferentes
  col_map = {}
  for c in df_relatorio.columns:
    c_low = str(c).lower()
    if "filial" in c_low:
      col_map[c] = "Filial"
    elif "representante" in c_low:
      col_map[c] = "Representante"
    elif "cliente" in c_low:
      col_map[c] = "Cliente"
    elif "simulador" in c_low:
      col_map[c] = "Simulador"
    elif "status" in c_low:
      col_map[c] = "Status"
    elif "obs" in c_low:
      col_map[c] = "Observação"
  if col_map:
    df_relatorio = df_relatorio.rename(columns=col_map)

  if df_relatorio.empty:
    st.info(
        "💡 Nenhum dado carregado ainda nesta sessão. Assim que você enviar um"
        " lote de PDFs na Aba 1 (ou se a leitura da planilha estiver ativa), os"
        " dados aparecerão aqui automaticamente para gerar o PDF!"
    )
  else:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
      opcoes_filial = ["Todas as Filiais"] + sorted(
          df_relatorio["Filial"].dropna().unique().tolist()
      )
      filial_escolhida = st.selectbox(
          "1. Selecione a Filial do Gerente:", opcoes_filial
      )
    with col_f2:
      opcoes_status = ["Todos os Status"] + sorted(
          df_relatorio["Status"].dropna().unique().tolist()
      )
      status_escolhido = st.selectbox(
          "2. Filtrar por Status (Opcional):", opcoes_status
      )

    df_filtrado = df_relatorio.copy()
    if filial_escolhida != "Todas as Filiais":
      df_filtrado = df_filtrado[df_filtrado["Filial"] == filial_escolhida]
    if status_escolhido != "Todos os Status":
      df_filtrado = df_filtrado[df_filtrado["Status"] == status_escolhido]

    st.markdown(
        f"**Pré-visualização do Relatório ({len(df_filtrado)} simuladores):**"
    )
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    if not df_filtrado.empty:
      bytes_pdf = gerar_pdf_gerencia(df_filtrado, filial_escolhida)
      nome_arq = f"Relatorio_{filial_escolhida.replace(' ', '_')}_{datetime.datetime.now().strftime('%d_%m_%Y')}.pdf"

      st.download_button(
          label=f"📥 Baixar Relatório em PDF ({filial_escolhida})",
          data=bytes_pdf,
          file_name=nome_arq,
          mime="application/pdf",
          type="primary",
          use_container_width=True,
      )
