import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
from pptx import Presentation
from docx import Document
from PIL import Image
import io

# --- 1. CONFIGURATION VISUELLE ---
st.set_page_config(page_title="Tuteur IA Finance", layout="wide", page_icon="🎓")

# CSS pour imiter le style "Message" et fixer la zone de chat
st.markdown("""
<style>
    .stChatMessage {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 10px;
    }
    /* Pour que le bouton download soit discret */
    .stDownloadButton > button {
        height: 30px;
        padding-top: 0px;
        padding-bottom: 0px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION IA ---
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-2.5-flash')
    else:
        st.error("Clé API manquante.")
        st.stop()
except Exception as e:
    st.error(f"Erreur connexion : {e}")

# --- 3. FONCTIONS TECHNIQUES ---
def get_file_content(uploaded_file):
    text = ""
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type == 'pdf':
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages: text += page.extract_text() or ""
        elif file_type in ['xlsx', 'xls']:
            xls = pd.ExcelFile(uploaded_file)
            for sheet in xls.sheet_names:
                text += f"\n--- Excel: {sheet} ---\n" + pd.read_excel(xls, sheet_name=sheet).to_string()
        elif file_type == 'pptx':
            for slide in Presentation(uploaded_file).slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text += shape.text + "\n"
        elif file_type == 'docx':
            for para in Document(uploaded_file).paragraphs: text += para.text + "\n"
        elif file_type in ['png', 'jpg', 'jpeg']:
            image = Image.open(uploaded_file)
            response = model.generate_content(["Transcris tout le texte :", image])
            text += f"\n--- Image ---\n{response.text}"
    except Exception as e:
        st.error(f"Erreur lecture {uploaded_file.name}: {e}")
    return text

def ask_gemini(prompt):
    try:
        # LA RÈGLE D'OR : On force l'IA à écrire pour Word (pas de LaTeX complexe)
        system_instruction = (
            "Tu es un expert pédagogique. "
            "RÈGLE CRUCIALE DE FORMATAGE : N'utilise JAMAIS de code LaTeX (pas de $$, pas de \\frac). "
            "Utilise uniquement des caractères Unicode standards pour les maths afin que ce soit lisible dans Word. "
            "Exemple : écris 'σ² = Σ(x - μ)² / n' et NON pas le code LaTeX. "
            "Fais des réponses structurées."
        )
        response = model.generate_content(system_instruction + "\n\n" + prompt)
        return response.text
    except Exception as e: return f"Erreur IA : {e}"

def create_word_docx(text_content, title="Note de Cours"):
    """Crée un fichier Word propre"""
    doc = Document()
    doc.add_heading(title, 0)
    doc.add_paragraph(text_content)
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- 4. SIDEBAR (Le Cartable) ---
with st.sidebar:
    st.header("🎒 Cartable")
    uploaded_files = st.file_uploader("Documents", accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🔄 Analyser", type="primary"):
            with st.spinner("Lecture..."):
                raw_text = ""
                for file in uploaded_files: raw_text += get_file_content(file)
                st.session_state['context'] = raw_text
                st.success("Mémoire à jour !")

    st.divider()
    if 'context' in st.session_state:
        st.info("🧠 Cerveau chargé")
    else: st.warning("⚠️ Cerveau vide")

# --- 5. INTERFACE PRINCIPALE ---
# On enlève les titres énormes pour gagner de la place
st.subheader("🎓 Tuteur Privé")

tab1, tab2, tab3 = st.tabs(["💬 Discussion (Word)", "📝 Synthèses", "🧠 Quiz"])

# === ONGLET 1 : CHAT AVEC EXPORT DIRECT ===
with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    
    # Affichage de l'historique
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # Si c'est une réponse de l'IA, on ajoute un petit bouton Word en dessous
            if msg["role"] == "assistant":
                # On crée une clé unique pour chaque bouton (indispensable)
                btn_key = f"dl_btn_{i}"
                docx = create_word_docx(msg["content"], title=f"Réponse IA - {i}")
                st.download_button(
                    label="💾 Word",
                    data=docx.getvalue(),
                    file_name=f"note_ia_{i}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=btn_key
                )

    # Zone de saisie
    if user_input := st.chat_input("Posez votre question (ex: Formule écart-type)..."):
        # 1. Message Utilisateur
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)
        
        # 2. Réponse IA
        context = st.session_state.get('context', '')
        full_prompt = f"Contexte du cours : {context}. Question : {user_input}."
        
        with st.chat_message("assistant"):
            with st.spinner("Réflexion..."):
                resp = ask_gemini(full_prompt)
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp})
                
                # 3. Le bouton Word apparaît tout de suite après la réponse
                docx = create_word_docx(resp, title="Réponse Instantanée")
                st.download_button(
                    label="💾 Télécharger cette réponse en Word",
                    data=docx.getvalue(),
                    file_name="reponse_finance.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="dl_btn_last"
                )

# === ONGLET 2 : SYNTHÈSE ===
with tab2:
    if st.button("Générer Synthèse Complète"):
        if 'context' in st.session_state:
            with st.spinner("Rédaction..."):
                res = ask_gemini(f"Fais une fiche de révision complète sur : {st.session_state['context']}")
                st.markdown(res)
                # Bouton de téléchargement
                docx = create_word_docx(res, title="Synthèse Complète")
                st.download_button("📥 Télécharger la synthèse", docx.getvalue(), "synthese.docx")
        else: st.error("Pas de documents.")

# === ONGLET 3 : QUIZ ===
with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            res = ask_gemini(f"3 QCM difficiles sur : {st.session_state['context']}. Avec correction.")
            st.markdown(res)
            # Bouton de téléchargement du quiz
            docx = create_word_docx(res, title="Quiz Entraînement")
            st.download_button("📥 Télécharger le Quiz", docx.getvalue(), "quiz.docx")
        else: st.error("Pas de documents.")
