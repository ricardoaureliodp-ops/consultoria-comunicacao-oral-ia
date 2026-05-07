import streamlit as st
import requests
import base64
import time
from datetime import datetime
from streamlit_mic_recorder import mic_recorder

# =========================================================
# CONSULTORIA FALA BONITO - COMUNICAÇÃO ORAL PROFISSIONAL
# Streamlit + Gemini API + Google Sheets via Apps Script
# Versão: 2 casos, 2 tentativas, feedback curto, sem turma
# =========================================================

# ---------- CONFIGURAÇÕES ----------
st.set_page_config(
    page_title="Consultoria Fala Bonito",
    page_icon="🎤",
    layout="wide"
)

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
# Aceita os dois nomes para evitar erro nos Secrets
WEBHOOK_URL = st.secrets.get("SHEETS_WEBHOOK_URL", "") or st.secrets.get("WEBHOOK_URL", "")

# ---------- GEMINI ----------
def escolher_modelo_gemini(api_key: str) -> str:
    """
    Tenta encontrar um modelo Gemini 2.5 disponível na chave.
    Se a listagem falhar, usa gemini-2.5-flash como padrão.
    """
    modelo_padrao = "models/gemini-2.5-flash"

    if not api_key:
        return modelo_padrao

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        r = requests.get(url, timeout=12)
        if r.status_code != 200:
            return modelo_padrao

        modelos = r.json().get("models", [])

        # Preferência: modelos 2.5 Flash com generateContent
        preferidos = []
        outros_25 = []

        for m in modelos:
            nome = m.get("name", "")
            metodos = m.get("supportedGenerationMethods", [])
            if "generateContent" not in metodos:
                continue

            if "gemini-2.5-flash" in nome:
                preferidos.append(nome)
            elif "gemini-2.5" in nome:
                outros_25.append(nome)

        if preferidos:
            # Evita modelos preview/live se houver opção estável
            preferidos_ordenados = sorted(
                preferidos,
                key=lambda x: ("preview" in x.lower(), "live" in x.lower(), len(x))
            )
            return preferidos_ordenados[0]

        if outros_25:
            return sorted(outros_25, key=lambda x: ("preview" in x.lower(), len(x)))[0]

        return modelo_padrao

    except Exception:
        return modelo_padrao


def chamar_gemini_audio(prompt: str, audio_bytes: bytes, mime_type: str, api_key: str):
    """
    Envia áudio + prompt ao Gemini.
    Retorna texto da IA ou código de erro amigável.
    """
    if not api_key:
        return "ERRO_API_KEY"

    if not audio_bytes:
        return "ERRO_AUDIO_VAZIO"

    modelo = escolher_modelo_gemini(api_key)
    url_chat = f"https://generativelanguage.googleapis.com/v1beta/{modelo}:generateContent?key={api_key}"

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

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
            "temperature": 0.3,
            "topP": 0.8,
            "maxOutputTokens": 850
        }
    }

    try:
        r = requests.post(url_chat, json=payload, timeout=55)

        if r.status_code == 200:
            data = r.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                return f"ERRO_RETORNO_GEMINI: {str(data)[:500]}"

        if r.status_code == 503:
            return "ERRO_503"

        return f"ERRO_GEMINI_{r.status_code}: {r.text[:700]}"

    except requests.exceptions.Timeout:
        return "ERRO_TIMEOUT"
    except Exception as e:
        return f"ERRO_CONEXAO: {e}"


# ---------- PLANILHA ----------
def salvar_planilha(dados: dict, webhook_url: str) -> bool:
    if not webhook_url:
        return False

    try:
        resposta = requests.post(webhook_url, json=dados, timeout=20)
        return resposta.status_code == 200
    except Exception:
        return False


# ---------- STATUS ----------
def detectar_status(feedback: str, tentativa: int) -> str:
    texto = (feedback or "").lower()
    texto_limpo = texto.replace(" ", "").replace("\n", "").replace("*", "")

    if "status:satisfatório" in texto_limpo or "status:-satisfatório" in texto_limpo:
        return "Satisfatório"

    if "status:precisamelhorar" in texto_limpo or "status:-precisamelhorar" in texto_limpo:
        return "Precisa melhorar"

    if "satisfatório" in texto and "precisa melhorar" not in texto:
        return "Satisfatório"

    if tentativa >= 2:
        return "Encerrado com exemplo"

    return "Precisa melhorar"


def resposta_eh_erro(feedback: str) -> bool:
    if not feedback:
        return True
    return (
        feedback.startswith("ERRO_")
        or "ERRO_GEMINI" in feedback
        or "ERRO_CONEXAO" in feedback
        or "ERRO_TIMEOUT" in feedback
    )


# ---------- CASOS ----------
casos = [
    {
        "nome": "Caso 1 - Apresentação Profissional",
        "contexto": "Imagine que você está iniciando uma reunião corporativa ou uma pequena apresentação profissional.",
        "tarefa": (
            "Faça uma breve apresentação pessoal. Fale seu nome, sua área de atuação, "
            "experiências ou cargos que já exerceu, o motivo da reunião/apresentação "
            "e finalize com uma saudação ao público."
        ),
        "tempo": "Tempo sugerido: mínimo de 30 segundos e máximo de 1 minuto.",
        "foco": "Clareza, organização, postura profissional, objetividade e saudação adequada.",
        "exemplo": (
            "Boa tarde a todos. Meu nome é Ricardo, atuo na área administrativa e tenho experiência "
            "com atendimento, organização de processos e apoio à gestão. O objetivo desta apresentação "
            "é compartilhar uma proposta de melhoria para nossa rotina de trabalho. Agradeço a presença "
            "de todos e espero contribuir com ideias úteis para a equipe."
        )
    },
    {
        "nome": "Caso 2 - Cliente Insatisfeito",
        "contexto": "Imagine que um cliente entrou em contato reclamando de atraso em um serviço importante.",
        "tarefa": (
            "Grave uma resposta profissional para esse cliente. Demonstre empatia, reconheça o problema, "
            "explique de forma objetiva o que será feito e finalize transmitindo segurança."
        ),
        "tempo": "Tempo sugerido: mínimo de 40 segundos e máximo de 1 minuto e 20 segundos.",
        "foco": "Empatia, controle emocional, clareza, objetividade, tom profissional e solução.",
        "exemplo": (
            "Senhor cliente, compreendo sua insatisfação e peço desculpas pelo transtorno causado. "
            "Já estamos verificando o ocorrido para corrigir a situação com prioridade. "
            "Nossa equipe acompanhará o caso até a conclusão e manterá você informado sobre os próximos passos. "
            "Agradeço sua compreensão e reforço nosso compromisso em resolver essa situação da melhor forma possível."
        )
    }
]


# ---------- SESSION STATE ----------
defaults = {
    "indice_caso": 0,
    "tentativa": 1,
    "audio_bytes": None,
    "audio_mime": "audio/wav",
    "ultimo_feedback": "",
    "ultimo_erro_tecnico": "",
    "status_atual": "",
    "caso_finalizado": False,
    "atividade_finalizada": False,
    "recorder_key": "gravador_inicial",
    "autoavaliacao": "Razoável",
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def limpar_audio():
    st.session_state.audio_bytes = None
    st.session_state.audio_mime = "audio/wav"
    st.session_state.autoavaliacao = "Razoável"
    st.session_state.recorder_key = f"gravador_{time.time()}"


def limpar_feedback():
    st.session_state.ultimo_feedback = ""
    st.session_state.ultimo_erro_tecnico = ""
    st.session_state.status_atual = ""


# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("👤 Identificação")
    nome = st.text_input("Nome do aluno:", key="nome_aluno").strip()

    st.divider()
    st.write("🎧 Antes de enviar, ouça seu áudio.")
    st.write("Se não gostar, apague e grave novamente.")

    with st.expander("⚙️ Opções avançadas"):
        st.warning("Use somente se precisar recomeçar a atividade.")
        confirmar = st.checkbox("Confirmo que quero apagar meu progresso.")
        if st.button("🔄 Reiniciar atividade", disabled=not confirmar):
            st.session_state.clear()
            st.rerun()


# ---------- TELA INICIAL ----------
st.title("🎤 Consultoria Fala Bonito - Comunicação Oral Profissional")
st.write("Atividade prática de oratória, clareza, postura profissional e comunicação empresarial com feedback de IA.")

if not nome:
    st.warning("👈 Digite seu nome na barra lateral para começar.")
    st.stop()

total_casos = len(casos)

if st.session_state.atividade_finalizada:
    st.success("🎉 Atividade finalizada. Parabéns pela participação!")
    st.info("Suas respostas foram registradas na planilha.")
    st.stop()


# ---------- CASO ATUAL ----------
caso = casos[st.session_state.indice_caso]

st.progress((st.session_state.indice_caso) / total_casos)
st.write(f"### Progresso: Caso {st.session_state.indice_caso + 1} de {total_casos}")

with st.expander("ℹ️ Orientações gerais da atividade"):
    st.write("""
Nesta atividade, você vai treinar comunicação oral profissional.

**Como fazer:**
1. Leia o caso.
2. Pense em um pequeno roteiro.
3. Grave sua fala.
4. Ouça antes de enviar.
5. Se não gostar, apague e grave novamente.
6. Envie para receber o feedback da Consultoria Fala Bonito.

**Importante:** não atualize a página enquanto a análise estiver acontecendo.
""")

st.subheader(f"📚 {caso['nome']}")
st.info(caso["contexto"])

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 🎯 Sua tarefa")
    st.write(caso["tarefa"])
    st.warning(caso["tempo"])

    st.markdown("### 🔎 Foco da avaliação")
    st.write(caso["foco"])

with col2:
    st.markdown("### ✅ Checklist antes de gravar")
    st.write("✔ Comece com uma saudação profissional.")
    st.write("✔ Organize sua fala com começo, meio e fim.")
    st.write("✔ Evite vícios de linguagem em excesso.")
    st.write("✔ Fale com calma e clareza.")
    st.write("✔ Use pausas curtas.")
    st.write("✔ Finalize com uma mensagem objetiva.")


st.divider()
st.write(f"## Tentativa atual: {st.session_state.tentativa} de 2")

if st.session_state.caso_finalizado:
    st.success("✅ Este caso foi encerrado. Leia o feedback e clique em **Próximo caso** para continuar.")
else:
    if st.session_state.tentativa == 1:
        st.info("🟢 Primeira tentativa: grave sua fala com clareza e profissionalismo.")
    else:
        st.warning("🟡 Segunda tentativa: use o feedback anterior para melhorar. Se ainda não atingir o mínimo, a Consultoria trará um exemplo.")


# ---------- GRAVAÇÃO ----------
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
        key=st.session_state.recorder_key
    )

    if audio and isinstance(audio, dict) and audio.get("bytes"):
        st.session_state.audio_bytes = audio["bytes"]
        st.session_state.audio_mime = audio.get("mime_type", "audio/wav")
        limpar_feedback()

    if st.session_state.audio_bytes:
        st.success("Áudio gravado. Ouça antes de enviar.")
        st.audio(st.session_state.audio_bytes, format=st.session_state.audio_mime)

        st.write("Antes de enviar, como você avalia sua própria fala?")
        st.session_state.autoavaliacao = st.radio(
            "Autoavaliação",
            ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"],
            horizontal=True,
            label_visibility="collapsed",
            index=["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"].index(st.session_state.autoavaliacao)
            if st.session_state.autoavaliacao in ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"] else 1
        )

        col_apagar, col_enviar = st.columns([1, 2])

        with col_apagar:
            if st.button("🗑️ Apagar e gravar novamente", key=f"apagar_{st.session_state.indice_caso}_{st.session_state.tentativa}"):
                limpar_audio()
                limpar_feedback()
                st.rerun()

        with col_enviar:
            enviar = st.button(
                "📩 Enviar áudio para análise da Consultoria Fala Bonito",
                key=f"enviar_{st.session_state.indice_caso}_{st.session_state.tentativa}",
                type="primary"
            )

        if enviar:
            st.info("⏳ Envio recebido. A Consultoria Fala Bonito está analisando seu áudio. Aguarde sem atualizar a página.")

            incluir_exemplo = st.session_state.tentativa == 2

            prompt = f"""
Você é a Consultoria Fala Bonito, especialista em comunicação oral profissional para alunos de Técnico em Administração.

Analise o áudio do aluno com foco em:
- clareza;
- organização da fala;
- postura profissional;
- objetividade;
- adequação ao contexto;
- naturalidade;
- vícios de linguagem, se forem perceptíveis.

CASO:
{caso["nome"]}

CONTEXTO:
{caso["contexto"]}

TAREFA:
{caso["tarefa"]}

FOCO DA AVALIAÇÃO:
{caso["foco"]}

TENTATIVA:
{st.session_state.tentativa} de 2

AUTOAVALIAÇÃO DO ALUNO:
{st.session_state.autoavaliacao}

REGRAS IMPORTANTES:
- Responda em português do Brasil.
- Seja curto, direto e pedagógico.
- Não faça introdução longa.
- Não escreva relatório extenso.
- Não humilhe o aluno.
- Valorize o que estiver bom.
- Explique claramente o que precisa melhorar.
- Se a fala estiver minimamente clara, organizada e profissional, considere satisfatória.
- Na tentativa 1, se precisar melhorar, NÃO dê texto pronto completo. Dê apenas orientação.
- Na tentativa 2, se ainda precisar melhorar, dê um EXEMPLO curto de resposta profissional.
- O exemplo pode ser genérico, baseado no caso, mesmo que não copie o áudio do aluno.

FORMATO OBRIGATÓRIO:
Resumo da fala:
- escreva no máximo 2 linhas.

Pontos positivos:
- no máximo 3 itens.

O que melhorar:
- no máximo 3 itens, com explicação curta.

Dica prática:
- uma dica objetiva para o próximo envio ou para a vida profissional.

{"Exemplo profissional curto:\n- traga um exemplo completo e curto, com 4 a 6 frases, adequado ao caso." if incluir_exemplo else ""}

Status:
- escreva exatamente uma das opções:
Status: Satisfatório
Status: Precisa melhorar
Status: Encerrado com exemplo
"""

            with st.spinner("Analisando áudio... isso pode levar alguns segundos."):
                feedback = chamar_gemini_audio(
                    prompt=prompt,
                    audio_bytes=st.session_state.audio_bytes,
                    mime_type=st.session_state.audio_mime,
                    api_key=GEMINI_API_KEY
                )

            if resposta_eh_erro(feedback):
                st.session_state.ultimo_erro_tecnico = feedback
                st.error("⚠️ A IA não conseguiu analisar agora ou ocorreu falha de conexão.")
                st.info(
                    "Não atualize a página. Sua gravação continua disponível. "
                    "Clique novamente em **Enviar áudio para análise da Consultoria Fala Bonito**. "
                    "Esta tentativa não foi registrada, não foi salva na planilha e não contou como tentativa."
                )
            else:
                st.session_state.ultimo_feedback = feedback
                status = detectar_status(feedback, st.session_state.tentativa)
                st.session_state.status_atual = status

                dados = {
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "nome": nome,
                    "caso": caso["nome"],
                    "tentativa": st.session_state.tentativa,
                    "feedback": feedback,
                    "status": status
                }

                salvou = salvar_planilha(dados, WEBHOOK_URL)

                st.subheader("📋 Feedback da Consultoria Fala Bonito")
                st.write(feedback)

                if salvou:
                    st.success("Resposta registrada na planilha.")
                else:
                    st.warning("A resposta foi analisada, mas não foi possível salvar na planilha. Verifique o Apps Script/Secrets.")

                if status == "Satisfatório":
                    st.session_state.caso_finalizado = True
                    st.success("✅ Resposta satisfatória. Leia o feedback e avance quando estiver pronto.")
                    limpar_audio()
                    st.rerun()

                elif st.session_state.tentativa >= 2:
                    st.session_state.caso_finalizado = True
                    st.warning("📌 Este caso foi encerrado com orientação/exemplo. Leia com atenção e avance quando estiver pronto.")
                    limpar_audio()
                    st.rerun()

                else:
                    st.session_state.tentativa += 1
                    limpar_audio()
                    st.info("Agora grave a segunda tentativa usando o feedback recebido.")
                    st.rerun()

    else:
        st.info("Grave seu áudio para liberar o envio à Consultoria Fala Bonito.")


# ---------- FEEDBACK ----------
if st.session_state.ultimo_feedback:
    st.divider()
    with st.expander("📋 Último feedback recebido", expanded=True):
        st.write(st.session_state.ultimo_feedback)

if st.session_state.ultimo_erro_tecnico:
    st.divider()
    with st.expander("🔎 Detalhe técnico para o professor"):
        st.code(st.session_state.ultimo_erro_tecnico)


# ---------- NAVEGAÇÃO MANUAL ----------
if st.session_state.caso_finalizado:
    st.divider()

    if st.session_state.indice_caso < total_casos - 1:
        if st.button("➡️ Próximo caso"):
            st.session_state.indice_caso += 1
            st.session_state.tentativa = 1
            st.session_state.caso_finalizado = False
            limpar_audio()
            limpar_feedback()
            st.rerun()
    else:
        if st.button("🏁 Finalizar atividade"):
            st.session_state.atividade_finalizada = True
            limpar_audio()
            st.rerun()
