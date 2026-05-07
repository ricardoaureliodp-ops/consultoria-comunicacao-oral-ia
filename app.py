import streamlit as st
import requests
import base64
from datetime import datetime
from streamlit_mic_recorder import mic_recorder

# =========================================================
# CONSULTORIA FALA BONITO - COMUNICAÇÃO ORAL PROFISSIONAL
# Streamlit + Gemini API + Google Sheets via Apps Script
# =========================================================

st.set_page_config(
    page_title="Consultoria Fala Bonito",
    page_icon="🎤",
    layout="wide"
)

# -------------------- CONFIG --------------------
MAX_TENTATIVAS = 2

def get_secret(*names):
    for name in names:
        try:
            value = st.secrets.get(name)
            if value:
                return value
        except Exception:
            pass
    return ""

api_key = get_secret("GEMINI_API_KEY")
webhook_url = get_secret("SHEETS_WEBHOOK_URL", "WEBHOOK_URL")

# -------------------- GEMINI --------------------
def listar_modelos_disponiveis(api_key):
    """Busca modelos disponíveis para a chave e prioriza modelos Gemini 2.5."""
    if not api_key:
        return []

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return []

        modelos = []
        for m in r.json().get("models", []):
            nome = m.get("name", "")
            metodos = m.get("supportedGenerationMethods", [])
            if "generateContent" in metodos and "gemini" in nome:
                modelos.append(nome)

        prioridade = []
        for preferido in [
            "models/gemini-2.5-flash",
            "models/gemini-2.5-flash-lite",
            "models/gemini-2.5-pro",
        ]:
            if preferido in modelos:
                prioridade.append(preferido)

        # Evita modelos antigos que deram erro/indisponibilidade.
        restantes = [
            m for m in modelos
            if m not in prioridade
            and "gemini-1.5" not in m
            and "gemini-2.0" not in m
        ]

        return prioridade + restantes
    except Exception:
        return []


def chamar_gemini_audio(prompt, audio_bytes, mime_type, api_key):
    if not api_key:
        return "ERRO_API_KEY"

    modelos = listar_modelos_disponiveis(api_key)
    if not modelos:
        modelos = ["models/gemini-2.5-flash"]

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    erros = []

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "audio/wav",
                            "data": audio_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "maxOutputTokens": 900
        }
    }

    for modelo in modelos[:4]:
        url_chat = f"https://generativelanguage.googleapis.com/v1beta/{modelo}:generateContent?key={api_key}"

        try:
            r = requests.post(
                url_chat,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=55
            )

            if r.status_code == 200:
                data = r.json()
                try:
                    texto = data["candidates"][0]["content"]["parts"][0]["text"]
                    if texto and texto.strip():
                        return texto.strip()
                except Exception:
                    erros.append(f"{modelo} => resposta sem texto")
                    continue

            if r.status_code == 503:
                erros.append(f"{modelo} => ERRO_503")
                continue

            erros.append(f"{modelo} => ERRO_GEMINI_{r.status_code}: {r.text[:600]}")

        except Exception as e:
            erros.append(f"{modelo} => ERRO_CONEXAO: {e}")

    return "ERRO_GEMINI: " + " | ".join(erros)


# -------------------- PLANILHA --------------------
def salvar_planilha(dados, webhook_url):
    if not webhook_url:
        return False
    try:
        resposta = requests.post(webhook_url, json=dados, timeout=20)
        return resposta.status_code == 200
    except Exception:
        return False


# -------------------- STATUS --------------------
def detectar_status(feedback, tentativa):
    texto = (feedback or "").lower()
    texto_limpo = texto.replace(" ", "").replace("\n", "").replace("-", "")

    if "status:satisfatório" in texto_limpo or "status:satisfatorio" in texto_limpo:
        return "Satisfatório"

    if "pode avançar" in texto or "pode seguir" in texto or "próximo caso" in texto:
        return "Satisfatório"

    if tentativa >= MAX_TENTATIVAS:
        return "Encerrado com orientação"

    return "Precisa melhorar"


# -------------------- CASOS --------------------
casos = [
    {
        "nome": "Caso 1 - Apresentação Profissional",
        "contexto": "Imagine que você está iniciando uma reunião corporativa ou uma pequena apresentação profissional.",
        "tarefa": (
            "Faça uma breve apresentação pessoal. Fale seu nome, sua área de atuação, "
            "experiências ou cargos que já exerceu, o motivo da reunião ou apresentação "
            "e finalize com uma saudação ao público."
        ),
        "tempo": "Tempo sugerido: mínimo de 30 segundos e máximo de 1 minuto.",
        "avaliacao": "Clareza, organização, postura profissional, objetividade e saudação adequada.",
        "exemplo": (
            "Boa tarde a todos. Meu nome é Ricardo, atuo na área administrativa e já tive experiência "
            "com atendimento, organização de documentos e apoio em processos internos. O objetivo desta "
            "reunião é apresentar uma proposta de melhoria para nossa rotina de trabalho. Agradeço a presença "
            "de todos e espero contribuir com uma conversa produtiva."
        )
    },
    {
        "nome": "Caso 2 - Cliente Insatisfeito",
        "contexto": "Um cliente entrou em contato insatisfeito por causa de atraso na entrega de um serviço.",
        "tarefa": (
            "Grave uma resposta profissional para esse cliente. Demonstre empatia, explique a situação "
            "sem colocar culpa em outras pessoas, apresente uma solução ou encaminhamento e finalize "
            "transmitindo confiança."
        ),
        "tempo": "Tempo sugerido: mínimo de 40 segundos e máximo de 1 minuto e 30 segundos.",
        "avaliacao": "Empatia, clareza, controle emocional, objetividade, solução e tom profissional.",
        "exemplo": (
            "Senhor cliente, entendo sua insatisfação e peço desculpas pelo transtorno. Tivemos um atraso "
            "no processo de entrega, mas já estamos verificando a situação para resolver o quanto antes. "
            "A previsão é retornar com uma posição atualizada ainda hoje. Agradeço sua compreensão e reforço "
            "que estamos acompanhando o caso com prioridade."
        )
    }
]


# -------------------- PROMPT --------------------
def montar_prompt(caso, nome, tentativa, autoavaliacao):
    precisa_exemplo = tentativa >= MAX_TENTATIVAS

    return f"""
Você é a Consultoria Fala Bonito, uma consultoria bem-humorada, objetiva e profissional de comunicação oral.
Avalie o áudio de um aluno de Técnico em Administração.

IMPORTANTE:
- Seja breve, claro e útil.
- Não faça textos longos.
- Não use relatório grande.
- Não humilhe o aluno.
- Foque no que ele precisa melhorar para a próxima gravação.
- Avalie a comunicação oral profissional, não apenas o conteúdo.
- Se o áudio estiver vazio, inaudível ou fora da tarefa, informe isso com educação.

DADOS:
Aluno: {nome}
Caso: {caso['nome']}
Contexto: {caso['contexto']}
Tarefa esperada: {caso['tarefa']}
Tempo recomendado: {caso['tempo']}
Foco de avaliação: {caso['avaliacao']}
Tentativa atual: {tentativa} de {MAX_TENTATIVAS}
Autoavaliação do aluno: {autoavaliacao}

CRITÉRIOS:
- Clareza da mensagem
- Organização com começo, meio e fim
- Linguagem profissional
- Objetividade
- Naturalidade, ritmo e pausas
- Adequação ao contexto

FORMATO OBRIGATÓRIO DA RESPOSTA:
Use exatamente estes blocos, com frases curtas:

Resumo da fala:
- Escreva em até 2 linhas o que o aluno disse.

Pontos positivos:
- Liste até 3 pontos positivos.

O que melhorar:
- Liste até 3 melhorias, explicando rapidamente o motivo.

Dica prática:
- Dê 1 orientação objetiva para a próxima gravação.

{"Exemplo curto de fala profissional:" if precisa_exemplo else ""}
{("- Traga obrigatoriamente um exemplo curto que o aluno possa usar como referência, mesmo que seja genérico para o caso. Exemplo-base: " + caso['exemplo']) if precisa_exemplo else ""}

Status:
- Escreva apenas uma das opções:
Status: Satisfatório
Status: Precisa melhorar
Status: Encerrado com orientação

REGRA DE STATUS:
- Se a fala cumprir o mínimo do caso com clareza e profissionalismo, use Status: Satisfatório.
- Se for tentativa 1 e ainda precisar melhorar, use Status: Precisa melhorar.
- Se for tentativa 2 e ainda precisar melhorar, use Status: Encerrado com orientação e traga o exemplo curto.
"""


# -------------------- SESSION STATE --------------------
defaults = {
    "indice_caso": 0,
    "tentativa": 1,
    "ultimo_feedback": "",
    "ultimo_erro": "",
    "caso_finalizado": False,
    "atividade_finalizada": False,
    "audio_bytes": None,
    "audio_mime": "audio/wav",
    "autoavaliacao": "Razoável",
    "processando": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# -------------------- SIDEBAR --------------------
with st.sidebar:
    st.header("👤 Identificação")
    nome = st.text_input("Nome do aluno:")

    st.divider()
    st.info("🎧 Antes de enviar, ouça seu áudio. Se não gostar, apague e grave novamente.")

    with st.expander("⚙️ Opções avançadas"):
        confirmar = st.checkbox("Confirmo que quero apagar todo o progresso desta atividade.")
        if st.button("🔄 Reiniciar atividade"):
            if confirmar:
                st.session_state.clear()
                st.rerun()
            else:
                st.warning("Marque a confirmação antes de reiniciar.")


# -------------------- HEADER --------------------
st.title("🎤 Consultoria Fala Bonito - Comunicação Oral Profissional")
st.write("Atividade prática de oratória, clareza, postura profissional e comunicação empresarial com feedback de IA.")

if not nome:
    st.warning("👈 Digite seu nome na barra lateral para começar.")
    st.stop()


total_casos = len(casos)

if st.session_state.atividade_finalizada:
    st.success("🎉 Parabéns! Você concluiu os dois casos da atividade.")
    st.info("Suas respostas foram registradas na planilha.")
    st.stop()

caso = casos[st.session_state.indice_caso]

st.progress(st.session_state.indice_caso / total_casos)
st.write(f"### Progresso: Caso {st.session_state.indice_caso + 1} de {total_casos}")

with st.expander("ℹ️ Orientações gerais da atividade", expanded=False):
    st.write("""
Nesta atividade, você vai treinar comunicação oral profissional.

A proposta não é falar perfeito. A proposta é melhorar clareza, organização, postura e segurança.

Antes de gravar:
- organize começo, meio e fim;
- fale com calma;
- evite excesso de “né”, “tipo”, “tá” e “então”;
- finalize com uma mensagem clara;
- ouça seu áudio antes de enviar.
    """)

st.subheader(f"📚 {caso['nome']}")
st.info(caso["contexto"])

col_a, col_b = st.columns([2, 1])

with col_a:
    st.write("### 🎯 Sua tarefa")
    st.write(caso["tarefa"])
    st.warning(caso["tempo"])

    st.write("### 🔎 Foco da avaliação")
    st.write(caso["avaliacao"])

with col_b:
    st.write("### ✅ Checklist antes de gravar")
    checklist = [
        "Comece com uma saudação profissional.",
        "Organize sua fala com começo, meio e fim.",
        "Evite vícios de linguagem em excesso.",
        "Fale com calma e clareza.",
        "Use pausas curtas.",
        "Finalize com uma mensagem objetiva."
    ]
    for item in checklist:
        st.write(f"✔️ {item}")


st.write(f"## Tentativa atual: {st.session_state.tentativa} de {MAX_TENTATIVAS}")

if st.session_state.caso_finalizado:
    st.success("✅ Este caso foi encerrado. Leia o feedback e clique em **Próximo caso** quando estiver pronto.")
else:
    if st.session_state.tentativa == 1:
        st.info("🟢 Primeira tentativa: grave sua fala com clareza e profissionalismo.")
    else:
        st.warning("🟡 Segunda tentativa: use o feedback anterior para melhorar. Se ainda não atingir o mínimo, a consultoria trará um exemplo.")


# -------------------- AUDIO --------------------
if not st.session_state.caso_finalizado:
    st.divider()
    st.subheader("🎙️ Gravação do áudio")
    st.caption("Permita o uso do microfone no navegador. Depois de gravar, ouça o áudio antes de enviar.")
    st.info("Use os botões abaixo para iniciar e parar a gravação. Depois, ouça seu áudio antes de enviar.")

    audio = mic_recorder(
        start_prompt="🎙️ Iniciar gravação",
        stop_prompt="⏹️ Parar gravação",
        just_once=False,
        use_container_width=True,
        key=f"gravador_{st.session_state.indice_caso}_{st.session_state.tentativa}"
    )

    if audio and isinstance(audio, dict) and audio.get("bytes"):
        st.session_state.audio_bytes = audio.get("bytes")
        st.session_state.audio_mime = audio.get("mime_type") or "audio/wav"
        st.success("Áudio gravado. Ouça antes de enviar.")

    if st.session_state.audio_bytes:
        st.audio(st.session_state.audio_bytes, format=st.session_state.audio_mime)

        st.write("Antes de enviar, como você avalia sua própria fala?")
        st.session_state.autoavaliacao = st.radio(
            "Autoavaliação:",
            ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"],
            horizontal=True,
            label_visibility="collapsed",
            index=["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"].index(st.session_state.autoavaliacao)
            if st.session_state.autoavaliacao in ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"] else 1
        )

        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("🗑️ Apagar e gravar novamente"):
                st.session_state.audio_bytes = None
                st.session_state.ultimo_erro = ""
                st.rerun()

        with col2:
            enviar = st.button("📩 Enviar áudio para análise da Consultoria Fala Bonito", type="primary")

        if enviar:
            if st.session_state.autoavaliacao == "Ainda quero refazer":
                st.warning("Você marcou que ainda quer refazer. Apague e grave novamente antes de enviar.")
                st.stop()

            st.info("⏳ Envio recebido. A Consultoria Fala Bonito está analisando seu áudio. Aguarde sem atualizar a página.")

            with st.spinner("Analisando áudio... isso pode levar alguns segundos."):
                prompt = montar_prompt(caso, nome, st.session_state.tentativa, st.session_state.autoavaliacao)
                feedback = chamar_gemini_audio(
                    prompt,
                    st.session_state.audio_bytes,
                    st.session_state.audio_mime,
                    api_key
                )

            if feedback == "ERRO_API_KEY" or feedback.startswith("ERRO_GEMINI") or "ERRO_503" in feedback or "ERRO_CONEXAO" in feedback:
                st.session_state.ultimo_erro = feedback
                st.error("⚠️ A IA não conseguiu analisar agora ou ocorreu falha de conexão.")
                st.info("Não atualize a página. Sua gravação continua disponível. Clique novamente em **Enviar áudio**. Esta tentativa não foi registrada, não foi salva na planilha e não contou como tentativa.")
                with st.expander("🧾 Detalhe técnico para o professor"):
                    st.code(feedback)
                st.stop()

            st.session_state.ultimo_feedback = feedback
            st.session_state.ultimo_erro = ""

            status = detectar_status(feedback, st.session_state.tentativa)

            dados = {
                "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "nome": nome,
                "caso": caso["nome"],
                "tentativa": st.session_state.tentativa,
                "feedback": feedback,
                "status": status
            }

            salvou = salvar_planilha(dados, webhook_url)
            if not salvou:
                st.warning("Feedback gerado, mas houve falha ao salvar na planilha. Verifique o Apps Script e a URL do webhook.")

            if status == "Satisfatório":
                st.session_state.caso_finalizado = True
                st.session_state.audio_bytes = None
                st.success("✅ Resposta satisfatória. Leia o feedback e avance quando estiver pronto.")
                st.rerun()

            elif st.session_state.tentativa >= MAX_TENTATIVAS:
                st.session_state.caso_finalizado = True
                st.session_state.audio_bytes = None
                st.warning("📌 Caso encerrado com orientação. Leia o feedback e avance quando estiver pronto.")
                st.rerun()

            else:
                st.session_state.tentativa += 1
                st.session_state.audio_bytes = None
                st.warning("Use o feedback recebido para gravar uma nova tentativa.")
                st.rerun()

    else:
        st.info("Grave seu áudio para liberar o envio à Consultoria Fala Bonito.")


# -------------------- FEEDBACK --------------------
if st.session_state.ultimo_feedback:
    st.divider()
    st.subheader("📋 Retorno da Consultoria Fala Bonito")
    st.write(st.session_state.ultimo_feedback)


# -------------------- PROXIMO CASO --------------------
if st.session_state.caso_finalizado:
    st.divider()

    if st.session_state.indice_caso < total_casos - 1:
        if st.button("➡️ Próximo caso"):
            st.session_state.indice_caso += 1
            st.session_state.tentativa = 1
            st.session_state.ultimo_feedback = ""
            st.session_state.ultimo_erro = ""
            st.session_state.caso_finalizado = False
            st.session_state.audio_bytes = None
            st.session_state.autoavaliacao = "Razoável"
            st.rerun()
    else:
        if st.button("🏁 Finalizar atividade"):
            st.session_state.atividade_finalizada = True
            st.rerun()
