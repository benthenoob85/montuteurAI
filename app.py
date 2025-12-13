import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
from pptx import Presentation
from docx import Document
from PIL import Image
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Mon Tuteur IA", layout="wide", page_icon="🎓")

st.markdown("""
<style>
    .stButton>button {border-radius: 20px; background-color: #F8F9FA; border: 1px solid #E0E0E0;}
    .stButton>button:hover {border-color: #6C5CE7; color: #6C5CE7;}
    .stChatMessage {background-color: #FFFFFF; border-radius: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);}
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
            response = model.generate_content(["Transcris tout le texte de cette image :", image])
            text += f"\n--- Image ---\n{response.text}"
    except Exception as e:
        st.error(f"Erreur lecture {uploaded_file.name}: {e}")
    return text

def ask_gemini(prompt):
    try:
        # On force le mode LaTeX pour les maths
        system_instruction = " Tu es un expert. Pour les formules mathématiques, utilise impérativement le format LaTeX entre des dollars (ex: $E = mc^2$). "
        response = model.generate_content(system_instruction + prompt)
        return response.text
    except Exception as e: return f"Erreur IA : {e}"

def create_word_docx(text_content):
    """Génère un fichier Word téléchargeable"""
    doc = Document()
    doc.add_heading('Note de Synthèse - Tuteur IA', 0)
    doc.add_paragraph(text_content)
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- 4. INTERFACE ---
with st.sidebar:
    st.header("🎒 Cartable Numérique")
    matiere = st.selectbox("Matière", ["Finance", "Stats", "Comptabilité", "Droit", "Autre"])
    st.divider()
    uploaded_files = st.file_uploader("Fichiers", accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🔄 Analyser", type="primary"):
            with st.spinner("Analyse approfondie..."):
                raw_text = ""
                for file in uploaded_files: raw_text += get_file_content(file)
                st.session_state['context'] = raw_text
                st.success("Documents mémorisés !")

    if 'context' in st.session_state:
        st.info("🧠 Mémoire active")
    else: st.warning("⚠️ Vide")

st.title(f"Tutorat : {matiere}")
tab1, tab2, tab3 = st.tabs(["💬 Chat & Formules", "📝 Synthèses & Export", "🧠 Quiz"])

# CHAT
with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
    if user_input := st.chat_input("Question (ex: Calcule le ratio...)"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)
        
        context = st.session_state.get('context', '')
        # Prompt optimisé pour la Finance
        full_prompt = f"Contexte : {context}. Question : {user_input}. Si tu dois utiliser des maths, utilise LaTeX."
        
        with st.chat_message("assistant"):
            with st.spinner("Calcul..."):
                resp = ask_gemini(full_prompt)
                st.markdown(resp) # Streamlit affiche le LaTeX automatiquement ici
                st.session_state.messages.append({"role": "assistant", "content": resp})

# SYNTHÈSE + EXPORT WORD
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📄 Générateur de Fiches")
        if st.button("Générer une synthèse"):
            if 'context' in st.session_state:
                with st.spinner("Rédaction..."):
                    res = ask_gemini(f"Fais une fiche de révision structurée sur : {st.session_state['context']}")
                    st.markdown(res)
                    st.session_state['last_summary'] = res # On sauvegarde pour le bouton téléchargement
            else: st.error("Pas de cours.")

    with col2:
        st.write("### 💾 Sauvegarde")
        if 'last_summary' in st.session_state:
            st.success("Une synthèse est prête à être téléchargée !")
            # Le bouton magique de téléchargement
            docx_file = create_word_docx(st.session_state['last_summary'])
            st.download_button(
                label="📥 Télécharger en Word (.docx)",
                data=docx_file.getvalue(),
                file_name="ma_synthese_finance.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            st.info("Générez d'abord une synthèse à gauche pour pouvoir la télécharger.")

# QUIZ
with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            st.markdown(ask_gemini(f"3 questions QCM difficiles sur : {st.session_state['context']}"))
