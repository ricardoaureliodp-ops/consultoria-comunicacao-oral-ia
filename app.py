import streamlit as st
import requests
import base64
from datetime import datetime
from streamlit_mic_recorder import mic_recorder

# =========================================================
# CONSULTORIA FALA MESTRE - COMUNICAÇÃO ORAL PROFISSIONAL
# Streamlit + Gemini API + Google Sheets via Apps Script
# =========================================================

# ---------- GEMINI ----------
def chamar_gemini_audio(prompt, audio_bytes, mime_type, api_key):
    if not api_key:
        return "ERRO_API_KEY"

    modelo = "gemini-2.5-flash"
    url_chat = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": audio_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.9,
            "maxOutputTokens": 2048
        }
    }

    try:
        r = requests.post(url_chat, json=payload, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"}, timeout=90)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if r.status_code == 503:
            return "ERRO_503"
        return f"ERRO_GEMINI_{r.status_code}: {r.text[:800]}"
    except Exception as e:
        return f"ERRO_CONEXAO: {e}"

# ---------- PLANILHA ----------
def salvar_planilha(dados, webhook_url):
    if not webhook_url:
        return False
    try:
        resposta = requests.post(webhook_url, json=dados, timeout=20)
        return resposta.status_code == 200
    except:
        return False

# ---------- STATUS ----------
def detectar_status(feedback, tentativa):
    texto = feedback.lower().replace(" ", "").replace("\n", "").replace("*", "")
    if "status:satisfatório" in texto or "status:-satisfatório" in texto:
        return "Satisfatório"
    if "status:encerradocomorientação" in texto or "status:-encerradocomorientação" in texto:
        return "Encerrado com orientação"
    if tentativa >= 3:
        return "Encerrado com orientação"
    return "Precisa melhorar"

# ---------- CASOS ----------
casos = [
    {
        "nome": "Caso 1 - Apresentação Profissional",
        "contexto": "Imagine que você está iniciando uma reunião corporativa ou uma pequena palestra profissional.",
        "tarefa": "Faça uma breve apresentação pessoal. Fale seu nome, sua área de interesse, uma experiência ou objetivo profissional e finalize cumprimentando o público.",
        "tempo": "Tempo sugerido: mínimo de 30 segundos e máximo de 1 minuto.",
        "foco": "Clareza, naturalidade, organização básica da fala, postura profissional e fechamento adequado.",
        "dicas": [
            "Comece com uma saudação profissional.",
            "Apresente-se de forma simples e segura.",
            "Evite excesso de 'né', 'tipo', 'tá' e 'então'.",
            "Finalize com uma frase de fechamento."
        ]
    },
    {
        "nome": "Caso 2 - Feedback Assertivo",
        "contexto": "Você é responsável por orientar um colaborador que cometeu um erro administrativo recorrente.",
        "tarefa": "Grave um áudio dando um feedback firme, respeitoso e empático. Explique o problema, mostre o impacto e direcione uma melhoria.",
        "tempo": "Tempo sugerido: mínimo de 45 segundos e máximo de 1 minuto e 30 segundos.",
        "foco": "Tom firme sem agressividade, comunicação não violenta, clareza na orientação e foco na solução.",
        "dicas": [
            "Não acuse a pessoa.",
            "Fale sobre o comportamento ou erro, não sobre o caráter do colaborador.",
            "Mostre consequência prática do erro.",
            "Termine combinando uma ação de melhoria."
        ]
    },
    {
        "nome": "Caso 3 - Gestão de Crise",
        "contexto": "Um cliente VIP está insatisfeito por causa de um atraso crítico na entrega de um serviço.",
        "tarefa": "Grave uma resposta profissional pedindo desculpas, explicando a situação com cuidado e mostrando o encaminhamento da solução.",
        "tempo": "Tempo sugerido: mínimo de 45 segundos e máximo de 1 minuto e 30 segundos.",
        "foco": "Empatia, naturalidade, uso de pausas, respeito, objetividade e segurança na condução do problema.",
        "dicas": [
            "Assuma o problema sem criar desculpas excessivas.",
            "Use tom respeitoso e calmo.",
            "Explique o próximo passo com clareza.",
            "Demonstre compromisso com a solução."
        ]
    },
    {
        "nome": "Caso 4 - Discurso de Persuasão",
        "contexto": "Você está em uma reunião com seu superior e precisa defender um aumento de orçamento para seu setor.",
        "tarefa": "Grave um discurso curto justificando o pedido com argumentos profissionais, como eficiência, melhoria de resultados, redução de falhas ou retorno sobre investimento.",
        "tempo": "Tempo sugerido: mínimo de 1 minuto e máximo de 2 minutos.",
        "foco": "Argumentação racional, credibilidade, entonação, objetividade e capacidade de convencer sem impor.",
        "dicas": [
            "Apresente o pedido logo no início.",
            "Use até 3 argumentos principais.",
            "Evite tom de exigência.",
            "Conclua reforçando o benefício para a organização."
        ]
    }
]

# ---------- CONFIGURAÇÃO STREAMLIT ----------
st.set_page_config(
    page_title="Consultoria Fala Mestre - Comunicação Oral",
    page_icon="🎤",
    layout="wide"
)

st.title("🎤 Consultoria Fala Mestre - Comunicação Oral Profissional")
st.write("Atividade prática de oratória, clareza, postura profissional e comunicação empresarial com feedback de IA.")

api_key = st.secrets.get("GEMINI_API_KEY", "")
webhook_url = st.secrets.get("SHEETS_WEBHOOK_URL", "")

# Modelo atual usado na análise de áudio: gemini-2.5-flash

# ---------- SESSION STATE ----------
if "indice_caso" not in st.session_state: st.session_state.indice_caso = 0
if "tentativa" not in st.session_state: st.session_state.tentativa = 1
if "ultimo_feedback" not in st.session_state: st.session_state.ultimo_feedback = ""
if "caso_finalizado" not in st.session_state: st.session_state.caso_finalizado = False
if "atividade_finalizada" not in st.session_state: st.session_state.atividade_finalizada = False
if "audio_key" not in st.session_state: st.session_state.audio_key = 0

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("👤 Identificação")
    nome = st.text_input("Nome do aluno:")
    turma = st.text_input("Turma:", value="")
    st.divider()
    st.write("🎧 Antes de enviar, ouça seu áudio. Se não gostar, apague e grave novamente.")

    with st.expander("⚙️ Opções avançadas"):
        st.warning("Use esta opção somente se precisar começar tudo de novo.")
        confirmar_reinicio = st.checkbox("Entendo que vou perder o progresso desta atividade.")
        if confirmar_reinicio:
            if st.button("🔄 Reiniciar atividade"):
                st.session_state.clear()
                st.rerun()

if not nome:
    st.warning("👈 Digite seu nome na barra lateral para começar.")
    st.stop()

total_casos = len(casos)

if st.session_state.atividade_finalizada:
    st.success("🎉 Parabéns! Você concluiu todos os casos da atividade.")
    st.info("Suas respostas foram registradas na planilha.")
    st.stop()

caso = casos[st.session_state.indice_caso]

# ---------- PROGRESSO ----------
st.progress(st.session_state.indice_caso / total_casos)
st.write(f"### Progresso: Caso {st.session_state.indice_caso + 1} de {total_casos}")

# ---------- EXPLICAÇÃO GERAL ----------
with st.expander("📘 Orientações gerais da atividade", expanded=(st.session_state.indice_caso == 0 and st.session_state.tentativa == 1)):
    st.write("""
Nesta atividade, você vai treinar comunicação oral profissional.  
A proposta não é falar perfeito, mas melhorar sua clareza, organização, postura e segurança.

A IA vai avaliar sua fala com base em critérios de comunicação empresarial:
- clareza da mensagem;
- estrutura com início, meio e fim;
- postura profissional;
- objetividade;
- ritmo, pausas e naturalidade;
- uso adequado da linguagem;
- conexão com o público.
""")
    st.info("Você poderá ouvir o áudio antes de enviar. Só envie quando considerar que a gravação ficou adequada.")

# ---------- CASO ----------
st.subheader(f"📚 {caso['nome']}")
st.info(caso["contexto"])

col_a, col_b = st.columns([2, 1])
with col_a:
    st.markdown("### 🎯 Sua tarefa")
    st.write(caso["tarefa"])
    st.warning(caso["tempo"])
    st.markdown("### 🔎 Foco da avaliação")
    st.write(caso["foco"])

with col_b:
    st.markdown("### ✅ Checklist antes de gravar")
    for d in caso["dicas"]:
        st.write(f"✔️ {d}")
    st.write("✔️ Organize sua fala com início, meio e fim.")
    st.write("✔️ Use pausas e fale com calma.")
    st.write("✔️ Conclua com uma mensagem clara.")

st.write(f"### Tentativa atual: {st.session_state.tentativa} de 3")

if st.session_state.caso_finalizado:
    st.success("✅ Este caso foi encerrado. Clique em **Próximo caso** para continuar.")
elif st.session_state.tentativa == 1:
    st.info("🟢 Primeira tentativa: grave sua fala com clareza e profissionalismo.")
elif st.session_state.tentativa == 2:
    st.warning("🟡 Segunda tentativa: use o feedback anterior para melhorar. A IA ainda não dará exemplo pronto.")
elif st.session_state.tentativa == 3:
    st.error("🔴 Terceira tentativa: se ainda não estiver adequado, a IA dará um exemplo recomendado e encerrará o caso.")

# ---------- ÁUDIO ----------
if not st.session_state.caso_finalizado:
    st.divider()
    st.subheader("🎙️ Gravação do áudio")

    st.caption("Permita o uso do microfone no navegador. Depois de gravar, ouça o áudio antes de enviar.")

    st.info("Use os botões abaixo para iniciar e parar a gravação. Depois, ouça seu áudio antes de enviar.")

    gravacao = mic_recorder(
        start_prompt="🎙️ Iniciar gravação",
        stop_prompt="⏹️ Parar gravação",
        just_once=False,
        use_container_width=True,
        key=f"mic_{st.session_state.indice_caso}_{st.session_state.tentativa}_{st.session_state.audio_key}"
    )

    if gravacao and gravacao.get("bytes"):
        audio_bytes = gravacao["bytes"]
        mime_type = "audio/wav"

        st.success("Áudio gravado. Ouça antes de enviar.")
        st.audio(audio_bytes, format=mime_type)

        autoavaliacao = st.radio(
            "Antes de enviar, como você avalia sua própria fala?",
            ["Muito nervoso(a)", "Razoável", "Confiante", "Ainda quero refazer"],
            horizontal=True
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            apagar = st.button("🗑️ Apagar e gravar novamente")
        with col2:
            enviar = st.button("📩 Enviar áudio para análise da Consultoria Fala Mestre")

        if apagar:
            st.session_state.audio_key += 1
            st.rerun()

        if enviar:
            if autoavaliacao == "Ainda quero refazer":
                st.warning("Então apague esta gravação e faça outra antes de enviar.")
                st.stop()

            st.info("⏳ Envio recebido. A Consultoria Fala Mestre está analisando seu áudio. Aguarde sem atualizar a página.")
            with st.spinner("Analisando áudio... isso pode levar alguns segundos."):
                prompt = f"""
Você é um especialista em oratória e comunicação empresarial.
Avalie o áudio de um aluno de Técnico em Administração em uma atividade de comunicação oral profissional.

IMPORTANTE:
- Seja técnico, educativo, acolhedor e respeitoso.
- Não humilhe nem ridicularize o aluno.
- Nervosismo não deve ser tratado como fracasso; oriente como melhorar.
- Avalie a comunicação oral, não a personalidade do aluno.
- Considere que o aluno está em processo de aprendizagem.

CASO ATUAL:
{caso['nome']}

CONTEXTO:
{caso['contexto']}

TAREFA PEDIDA AO ALUNO:
{caso['tarefa']}

TEMPO SUGERIDO:
{caso['tempo']}

FOCO DA AVALIAÇÃO:
{caso['foco']}

TENTATIVA ATUAL:
{st.session_state.tentativa}

AUTOAVALIAÇÃO DO ALUNO:
{autoavaliacao}

CRITÉRIOS DE AVALIAÇÃO:
1. Clareza: a mensagem foi fácil de entender?
2. Estrutura: houve início, desenvolvimento e fechamento?
3. Profissionalismo: a linguagem e o tom foram adequados ao ambiente corporativo?
4. Objetividade: a fala foi direta, sem rodeios excessivos?
5. Ritmo e naturalidade: a fala teve fluidez, pausas e ritmo adequado?
6. Linguagem: houve excesso de vícios como "né", "tipo", "tá", "então", "ééé"?
7. Conexão com o público: a fala gerou confiança, empatia ou interesse?
8. Segurança comunicativa: a fala transmitiu calma e direção, mesmo com possível nervosismo?

REGRAS PEDAGÓGICAS:
- Nas tentativas 1 e 2, NÃO entregue resposta pronta nem roteiro completo.
- Nas tentativas 1 e 2, dê orientação clara para o aluno melhorar no próximo envio.
- Na tentativa 3, se ainda não estiver satisfatório, apresente um exemplo recomendado de fala.
- Se o áudio estiver satisfatório, elogie de forma profissional e libere o avanço.
- Se o áudio estiver muito curto, vazio, inaudível ou fora da proposta, explique o problema e oriente a refazer.
- Sempre que possível, transcreva ou resuma a fala do aluno para registrar o conteúdo.

FORMATO OBRIGATÓRIO DA RESPOSTA:

Transcrição ou resumo da fala:
- ...

Pontos fortes:
- ...

Oportunidades de melhoria:
- ...

Notas visuais:
- Clareza: X/5
- Estrutura: X/5
- Profissionalismo: X/5
- Ritmo/Naturalidade: X/5
- Objetividade: X/5

Dica de ouro:
- ...

Orientação para o próximo envio:
- ...

Exemplo recomendado:
- Preencher somente na tentativa 3 se ainda não estiver satisfatório. Nas tentativas 1 e 2 escreva: "Ainda não será apresentado exemplo pronto nesta tentativa."

Status:
- Escreva exatamente uma das opções:
Status: Satisfatório
Status: Precisa melhorar
Status: Encerrado com orientação
"""
                feedback = chamar_gemini_audio(prompt, audio_bytes, mime_type, api_key)

                if feedback in ["ERRO_503"] or feedback.startswith("ERRO_CONEXAO") or feedback.startswith("ERRO_GEMINI"):
                    st.error("⚠️ A IA não conseguiu analisar agora ou ocorreu falha de conexão.")
                    st.info("Não atualize a página. Sua gravação continua disponível. Clique novamente em **Enviar áudio para análise da Consultoria Fala Mestre**. Esta tentativa não foi registrada, não foi salva na planilha e não contou como tentativa.")
                    with st.expander("Detalhe técnico para o professor"):
                        st.code(feedback)
                    st.stop()

                if feedback == "ERRO_API_KEY":
                    st.error("Erro: chave do Gemini não configurada corretamente nos Secrets.")
                    st.stop()

                st.session_state.ultimo_feedback = feedback
                st.subheader("📋 Retorno da Consultoria Fala Mestre")
                st.write(feedback)

                status = detectar_status(feedback, st.session_state.tentativa)

                dados = {
                    "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "nome": nome,
                    "turma": turma,
                    "caso": caso["nome"],
                    "contexto": caso["contexto"],
                    "tarefa": caso["tarefa"],
                    "tentativa": st.session_state.tentativa,
                    "autoavaliacao": autoavaliacao,
                    "feedback_ia": feedback,
                    "status": status
                }

                salvou = salvar_planilha(dados, webhook_url)
                if salvou:
                    st.success("Resposta salva na planilha.")
                else:
                    st.error("Erro ao salvar na planilha. Verifique o webhook nos Secrets ou o Apps Script.")

                if status == "Satisfatório":
                    st.session_state.caso_finalizado = True
                    st.success("✅ Resposta satisfatória. Clique em **Próximo caso** para continuar.")
                    st.rerun()
                elif st.session_state.tentativa >= 3:
                    st.session_state.caso_finalizado = True
                    st.warning("📌 Este caso foi encerrado com orientação. Clique em **Próximo caso** para continuar.")
                    st.rerun()
                else:
                    st.session_state.tentativa += 1
                    st.session_state.audio_key += 1
                    st.warning("Use o feedback recebido para gravar uma nova tentativa.")
                    st.rerun()
    else:
        st.info("Grave seu áudio para liberar o envio à Consultoria Fala Mestre.")

# ---------- ÚLTIMO FEEDBACK ----------
if st.session_state.ultimo_feedback:
    st.divider()
    st.subheader("🧾 Último retorno recebido")
    st.write(st.session_state.ultimo_feedback)

# ---------- PRÓXIMO CASO ----------
if st.session_state.caso_finalizado:
    st.divider()
    if st.session_state.indice_caso < total_casos - 1:
        if st.button("➡️ Próximo caso"):
            st.session_state.indice_caso += 1
            st.session_state.tentativa = 1
            st.session_state.ultimo_feedback = ""
            st.session_state.caso_finalizado = False
            st.session_state.audio_key += 1
            st.rerun()
    else:
        if st.button("🏁 Finalizar atividade"):
            st.session_state.atividade_finalizada = True
            st.rerun()
