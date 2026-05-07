import streamlit as st
import requests
import base64
import time
from datetime import datetime

try:
    from streamlit_mic_recorder import mic_recorder
except Exception:
    mic_recorder = None

# =========================================================
# CONSULTORIA FALA BONITO - COMUNICAÇÃO ORAL PROFISSIONAL
# Versão 13 - feedback enxuto, completo e com fallback
# Streamlit + Gemini API + Google Sheets via Apps Script
# =========================================================

APP_VERSION = "v13_fala_bonito_limpo_final"

# ---------- CONFIG ----------
st.set_page_config(
    page_title="Consultoria Fala Bonito",
    page_icon="🎤",
    layout="wide"
)

# ---------- SECRETS ----------
def get_secret(*names):
    for name in names:
        try:
            value = st.secrets.get(name)
            if value:
                return value
        except Exception:
            pass
    return ""

api_key = get_secret("GEMINI_API_KEY", "GOOGLE_API_KEY")
webhook_url = get_secret("SHEETS_WEBHOOK_URL", "WEBHOOK_URL")

# ---------- CASOS ----------
casos = [
    {
        "nome": "Caso 1 - Apresentação Profissional",
        "contexto": "Imagine que você está iniciando uma reunião corporativa ou uma pequena apresentação profissional.",
        "tarefa": "Faça uma breve apresentação pessoal. Fale seu nome, sua área de atuação, experiências ou cargos que já exerceu, o motivo da reunião ou apresentação e finalize com uma saudação ao público.",
        "tempo": "Tempo sugerido: mínimo de 20 segundos e máximo de 1 minuto.",
        "foco": "Clareza, organização, postura profissional, objetividade e saudação adequada.",
        "exemplo": "Boa tarde a todos. Meu nome é Ricardo, atuo na área administrativa e tenho experiência em atendimento, rotinas de escritório e apoio à gestão de processos. O motivo desta reunião é apresentar uma proposta de melhoria na organização das atividades da equipe. Agradeço a atenção de todos e espero contribuir com boas ideias.",
    },
    {
        "nome": "Caso 2 - Cliente Insatisfeito",
        "contexto": "Imagine que um cliente entrou em contato reclamando de atraso na entrega de um serviço ou solução administrativa.",
        "tarefa": "Grave uma resposta profissional para esse cliente. Demonstre empatia, reconheça o problema, explique de forma clara o que será feito e finalize transmitindo segurança.",
        "tempo": "Tempo sugerido: mínimo de 30 segundos e máximo de 1 minuto e 20 segundos.",
        "foco": "Empatia, controle emocional, clareza, solução do problema e tom profissional.",
        "exemplo": "Olá, compreendo sua insatisfação e peço desculpas pelo atraso. Vamos verificar imediatamente o andamento da sua solicitação e informar um novo prazo com clareza. Nosso objetivo é resolver a situação da forma mais rápida e segura possível. Agradeço sua compreensão e permanecemos à disposição.",
    },
]

# ---------- ESTADO ----------
def init_state():
    defaults = {
        "indice_caso": 0,
        "tentativa": 1,
        "caso_finalizado": False,
        "atividade_finalizada": False,
        "ultimo_feedback": "",
        "ultimo_erro_tecnico": "",
        "audio_bytes": None,
        "audio_mime": "audio/wav",
        "autoavaliacao": "Razoável",
        "recorder_key": f"gravador_{time.time()}",
        "state_version": APP_VERSION,
    }
    # Limpa somente estados incompatíveis de versões antigas, mas preserva campos de texto do usuário.
    if st.session_state.get("state_version") != APP_VERSION:
        for k in list(defaults.keys()):
            if k not in ["state_version"]:
                st.session_state.pop(k, None)
        st.session_state.state_version = APP_VERSION
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

def limpar_audio():
    st.session_state.audio_bytes = None
    st.session_state.audio_mime = "audio/wav"
    st.session_state.autoavaliacao = "Razoável"
    st.session_state.recorder_key = f"gravador_{time.time()}"
    st.rerun()

def proximo_caso():
    if st.session_state.indice_caso < len(casos) - 1:
        st.session_state.indice_caso += 1
        st.session_state.tentativa = 1
        st.session_state.caso_finalizado = False
        st.session_state.ultimo_feedback = ""
        st.session_state.ultimo_erro_tecnico = ""
        limpar_audio()
    else:
        st.session_state.atividade_finalizada = True
        st.rerun()

# ---------- GEMINI ----------
def listar_modelos_disponiveis(api_key):
    if not api_key:
        return []
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []
        modelos = []
        for m in r.json().get("models", []):
            name = m.get("name", "")
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" not in methods:
                continue
            nome_baixo = name.lower()
            # Evita modelos que não servem para este fluxo simples.
            if any(x in nome_baixo for x in ["tts", "image", "embedding", "aqa", "live"]):
                continue
            modelos.append(name.replace("models/", ""))
        return modelos
    except Exception:
        return []

def escolher_modelos(api_key):
    disponiveis = listar_modelos_disponiveis(api_key)
    preferidos = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    ]
    lista = []
    for p in preferidos:
        if not disponiveis or p in disponiveis:
            lista.append(p)
    # Se a chave listar nomes diferentes, tenta qualquer 2.5 flash/pro atual.
    for m in disponiveis:
        mb = m.lower()
        if "gemini" in mb and "2.5" in mb and m not in lista:
            lista.append(m)
    return lista or ["gemini-2.5-flash"]

def chamar_gemini_audio(prompt, audio_bytes, mime_type, api_key):
    if not api_key:
        return "ERRO_API_KEY", "Chave Gemini não configurada."
    if not audio_bytes:
        return "ERRO_AUDIO", "Áudio vazio."

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    modelos = escolher_modelos(api_key)
    ultimo_erro = ""

    for modelo in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type or "audio/wav",
                                "data": audio_b64,
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "maxOutputTokens": 2400,
            },
        }
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                texto = "".join([p.get("text", "") for p in parts if "text" in p]).strip()
                if texto:
                    return texto, ""
                ultimo_erro = f"{modelo} => resposta vazia"
            elif r.status_code == 503:
                ultimo_erro = f"{modelo} => ERRO_503"
                continue
            else:
                ultimo_erro = f"{modelo} => ERRO_GEMINI_{r.status_code}: {r.text[:500]}"
                continue
        except Exception as e:
            ultimo_erro = f"{modelo} => ERRO_CONEXAO: {e}"
            continue

    return "ERRO_GEMINI", ultimo_erro or "Falha sem detalhe técnico."

# ---------- PLANILHA ----------
def salvar_planilha(dados, webhook_url):
    if not webhook_url:
        return False
    try:
        r = requests.post(webhook_url, json=dados, timeout=20)
        return r.status_code == 200
    except Exception:
        return False

# ---------- STATUS ----------
def normalizar(txt):
    return (txt or "").lower().replace("á", "a").replace("à", "a").replace("ã", "a").replace("â", "a").replace("é", "e").replace("ê", "e").replace("í", "i").replace("ó", "o").replace("ô", "o").replace("õ", "o").replace("ú", "u").replace("ç", "c")

def detectar_status(feedback, tentativa):
    f = normalizar(feedback)
    if "status: satisfatorio" in f or "status:satisfatorio" in f or "pode avancar" in f:
        return "Satisfatório"
    if tentativa >= 2:
        return "Encerrado com exemplo"
    return "Precisa melhorar"

def feedback_incompleto(feedback):
    f = normalizar(feedback)
    if not feedback or len(feedback.strip()) < 350:
        return True
    obrigatorios = ["resumo", "pontos positivos", "melhorar", "dica", "status"]
    return any(item not in f for item in obrigatorios)

def montar_feedback_reserva(caso, tentativa, nome, status=None):
    # Usado somente se a IA devolver texto cortado. Mantém a atividade funcionando em sala.
    exemplo = caso.get("exemplo", "")
    if tentativa >= 2:
        status_txt = "Encerrado com exemplo"
        exemplo_bloco = f"\n\n**Exemplo curto:**\n{exemplo}"
    else:
        status_txt = status or "Precisa melhorar"
        exemplo_bloco = ""

    if "Apresentação" in caso["nome"]:
        resumo = "Você realizou uma apresentação profissional inicial, com foco em se identificar e explicar o objetivo da fala."
        positivos = "- Cumpriu a proposta principal da atividade.\n- Demonstrou iniciativa ao organizar uma fala oral."
        melhorar = "- Organize melhor a sequência: saudação, nome, área de atuação, experiências e motivo da apresentação.\n- Fale com calma e finalize com uma saudação objetiva ao público."
        dica = "Antes de gravar, escreva 4 palavras-chave em ordem: quem sou, onde atuo, experiência e objetivo da reunião."
    else:
        resumo = "Você respondeu a uma situação de cliente insatisfeito e tentou apresentar uma solução profissional."
        positivos = "- Procurou responder ao problema apresentado.\n- Demonstrou preocupação em manter uma postura profissional."
        melhorar = "- Comece reconhecendo a insatisfação do cliente com empatia.\n- Explique claramente o que será feito e finalize transmitindo segurança."
        dica = "Use a sequência: acolher, explicar, resolver e tranquilizar."

    return f"""**Resumo da fala:**
{resumo}

**Pontos positivos:**
{positivos}

**O que melhorar:**
{melhorar}

**Dica prática:**
{dica}{exemplo_bloco}

**Status:** {status_txt}"""

# ---------- PROMPT ----------
def montar_prompt(caso, tentativa, nome, autoavaliacao):
    exemplo_obrigatorio = tentativa >= 2
    regra_exemplo = """
**Exemplo curto:**
Se a fala ainda precisar melhorar, escreva um exemplo profissional de 3 a 5 frases baseado no caso.
Se estiver satisfatória, escreva: Não necessário.
""" if exemplo_obrigatorio else "Não traga exemplo nesta primeira tentativa."

    return f"""
Você é a Consultoria Fala Bonito, avaliando áudio de aluno de Técnico em Administração.
Responda em português do Brasil, de forma curta, objetiva e útil para o aluno melhorar.

Aluno: {nome}
Autoavaliação: {autoavaliacao}
Tentativa: {tentativa} de 2
Caso: {caso['nome']}
Tarefa: {caso['tarefa']}
Foco: {caso['foco']}

REGRAS:
- Não faça saudação longa.
- Não faça relatório extenso.
- Preencha todos os campos abaixo.
- Cada campo deve ter no máximo 2 frases ou 2 bullets.
- Na tentativa 1, não dê exemplo pronto.
- Na tentativa 2, se ainda precisar melhorar, dê exemplo curto.
- Status deve ser exatamente: Satisfatório, Precisa melhorar ou Encerrado com exemplo.

FORMATO OBRIGATÓRIO:

**Resumo da fala:**
[1 frase]

**Pontos positivos:**
- [ponto 1]
- [ponto 2]

**O que melhorar:**
- [orientação prática 1]
- [orientação prática 2]

**Dica prática:**
[1 dica simples]

{regra_exemplo}

**Status:** [Satisfatório | Precisa melhorar | Encerrado com exemplo]

Exemplo de referência do caso, se necessário:
{caso['exemplo']}
"""

# ---------- UI ----------
st.title("🎤 Consultoria Fala Bonito - Comunicação Oral Profissional")
st.caption("Atividade prática de oratória, clareza, postura profissional e comunicação empresarial com feedback de IA.")
st.divider()

with st.sidebar:
    st.header("👤 Identificação")
    nome = st.text_input("Nome do aluno:", key="nome_aluno")
    st.divider()
    st.info("🎧 Antes de enviar, ouça seu áudio. Se não gostar, apague e grave novamente.")
    with st.expander("⚙️ Opções avançadas"):
        st.warning("Use apenas se precisar recomeçar a atividade.")
        confirmar = st.checkbox("Confirmo que quero apagar meu progresso desta atividade.")
        if confirmar and st.button("🔄 Reiniciar atividade"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

if not nome:
    st.warning("👈 Digite seu nome na barra lateral para começar.")
    st.stop()

if st.session_state.atividade_finalizada:
    st.success("🎉 Atividade concluída. Suas respostas foram registradas na planilha.")
    st.stop()

caso = casos[st.session_state.indice_caso]
total_casos = len(casos)
st.write(f"### Progresso: Caso {st.session_state.indice_caso + 1} de {total_casos}")
st.progress(st.session_state.indice_caso / total_casos)

with st.expander("ℹ️ Orientações gerais da atividade"):
    st.write("Nesta atividade, você vai treinar comunicação oral profissional com feedback da IA.")
    st.write("A proposta não é falar perfeito, mas melhorar clareza, organização, postura e segurança.")
    st.markdown("""
**Antes de gravar:**
- pense em começo, meio e fim;
- fale com clareza;
- evite correr demais;
- use linguagem profissional;
- ouça seu áudio antes de enviar.
""")

st.subheader(f"📚 {caso['nome']}")
st.info(caso["contexto"])

col_tarefa, col_check = st.columns([2, 1])
with col_tarefa:
    st.write("### 🎯 Sua tarefa")
    st.write(caso["tarefa"])
    st.warning(caso["tempo"])
    st.write("### 🔎 Foco da avaliação")
    st.write(caso["foco"])

with col_check:
    st.write("### ✅ Checklist antes de gravar")
    st.markdown("""
- Comece com uma saudação profissional.
- Organize sua fala com começo, meio e fim.
- Evite vícios de linguagem em excesso.
- Fale com calma e clareza.
- Use pausas curtas.
- Finalize com uma mensagem objetiva.
""")

st.write(f"### Tentativa atual: {st.session_state.tentativa} de 2")
if st.session_state.caso_finalizado:
    st.success("✅ Este caso foi encerrado. Clique em **Próximo caso** para continuar.")
elif st.session_state.tentativa == 1:
    st.info("🟢 Primeira tentativa: grave sua fala com clareza e profissionalismo.")
else:
    st.warning("🟡 Segunda tentativa: use o feedback anterior. Se ainda precisar melhorar, a IA trará um exemplo curto.")

st.divider()

# ---------- GRAVAÇÃO ----------
if not st.session_state.caso_finalizado:
    st.write("## 🎙️ Gravação do áudio")
    st.caption("Permita o uso do microfone no navegador. Depois de gravar, ouça o áudio antes de enviar.")

    if mic_recorder is None:
        st.error("Componente de gravação não carregado. Aguarde alguns segundos e atualize a página.")
        st.stop()

    st.info("Use os botões abaixo para iniciar e parar a gravação. Depois, ouça seu áudio antes de enviar.")

    audio = mic_recorder(
        start_prompt="🎙️ Iniciar gravação",
        stop_prompt="⏹️ Parar gravação",
        just_once=False,
        use_container_width=True,
        key=st.session_state.recorder_key,
    )

    if audio and isinstance(audio, dict) and audio.get("bytes"):
        st.session_state.audio_bytes = audio["bytes"]
        st.session_state.audio_mime = audio.get("mime_type") or "audio/wav"

    if st.session_state.audio_bytes:
        st.success("Áudio gravado. Ouça antes de enviar.")
        st.audio(st.session_state.audio_bytes, format=st.session_state.audio_mime)
        st.write("Antes de enviar, como você avalia sua própria fala?")
        st.session_state.autoavaliacao = st.radio(
            "Autoavaliação",
            ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"],
            index=["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"].index(st.session_state.autoavaliacao) if st.session_state.autoavaliacao in ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"] else 1,
            horizontal=True,
            label_visibility="collapsed",
        )

        col_apagar, col_enviar = st.columns([1, 2])
        with col_apagar:
            if st.button("🗑️ Apagar e gravar novamente"):
                limpar_audio()
        with col_enviar:
            enviar = st.button("📩 Enviar áudio para análise da Consultoria Fala Bonito", type="primary")

        if enviar:
            st.info("⏳ Envio recebido. A Consultoria Fala Bonito está analisando seu áudio. Aguarde sem atualizar a página.")
            with st.spinner("Analisando áudio... isso pode levar alguns segundos."):
                prompt = montar_prompt(caso, st.session_state.tentativa, nome, st.session_state.autoavaliacao)
                feedback, detalhe = chamar_gemini_audio(
                    prompt=prompt,
                    audio_bytes=st.session_state.audio_bytes,
                    mime_type=st.session_state.audio_mime,
                    api_key=api_key,
                )

            if feedback in ["ERRO_GEMINI", "ERRO_API_KEY", "ERRO_AUDIO"]:
                st.session_state.ultimo_erro_tecnico = detalhe
                st.error("⚠️ A IA não conseguiu analisar agora ou ocorreu falha de conexão.")
                st.info("Não atualize a página. Sua gravação continua disponível. Clique novamente em **Enviar áudio para análise**. Esta tentativa não foi registrada, não foi salva na planilha e não contou como tentativa.")
            else:
                status = detectar_status(feedback, st.session_state.tentativa)
                if feedback_incompleto(feedback):
                    feedback = montar_feedback_reserva(caso, st.session_state.tentativa, nome, status)
                    status = detectar_status(feedback, st.session_state.tentativa)
                st.session_state.ultimo_feedback = feedback
                st.session_state.ultimo_erro_tecnico = ""

                dados = {
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "nome": nome,
                    "caso": caso["nome"],
                    "tentativa": st.session_state.tentativa,
                    "feedback": feedback,
                    "status": status,
                }
                salvou = salvar_planilha(dados, webhook_url)
                if not salvou:
                    st.warning("A análise foi feita, mas não foi possível salvar na planilha. Verifique o Apps Script depois.")

                if status == "Satisfatório":
                    st.session_state.caso_finalizado = True
                    st.success("✅ Resposta satisfatória. Leia o feedback e clique em **Próximo caso** quando estiver pronto.")
                    st.rerun()
                elif st.session_state.tentativa >= 2:
                    st.session_state.caso_finalizado = True
                    st.warning("📌 Caso encerrado com orientação e exemplo. Leia o feedback e clique em **Próximo caso** quando estiver pronto.")
                    st.rerun()
                else:
                    st.session_state.tentativa += 1
                    st.warning("Use o feedback abaixo para gravar uma nova tentativa.")
                    limpar_audio()
    else:
        st.info("Grave seu áudio para liberar o envio à Consultoria Fala Bonito.")

# ---------- FEEDBACK ----------
if st.session_state.ultimo_feedback:
    st.divider()
    with st.expander("📋 Último feedback recebido", expanded=True):
        st.markdown(st.session_state.ultimo_feedback)

# ---------- PRÓXIMO CASO ----------
if st.session_state.caso_finalizado:
    st.divider()
    if st.session_state.indice_caso < total_casos - 1:
        if st.button("➡️ Próximo caso"):
            st.session_state.indice_caso += 1
            st.session_state.tentativa = 1
            st.session_state.caso_finalizado = False
            st.session_state.ultimo_feedback = ""
            st.session_state.ultimo_erro_tecnico = ""
            st.session_state.audio_bytes = None
            st.session_state.audio_mime = "audio/wav"
            st.session_state.recorder_key = f"gravador_{time.time()}"
            st.rerun()
    else:
        if st.button("🏁 Finalizar atividade"):
            st.session_state.atividade_finalizada = True
            st.rerun()
