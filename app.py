import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import pandas as pd
from pptx import Presentation
from docx import Document
from docx.shared import Inches
from PIL import Image
import io
import matplotlib.pyplot as plt
import re

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Tuteur IA Finance", layout="wide", page_icon="🎓")

st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px; padding: 10px; margin-bottom: 10px;}
    .stDownloadButton > button {height: 30px; padding: 0px;}
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
        # On demande du LaTeX strict pour pouvoir le détecter et le transformer en image
        system_instruction = (
            "Tu es un expert Finance. "
            "RÈGLE OBLIGATOIRE : Pour toute formule mathématique, utilise le format LaTeX encadré par des DOLLARS DOUBLES ($$). "
            "Ne mets jamais de formule dans le texte courant, isole-les toujours sur une nouvelle ligne avec $$."
            "Exemple : \n$$ \sigma = \sqrt{variance} $$\n"
        )
        response = model.generate_content(system_instruction + "\n\n" + prompt)
        return response.text
    except Exception as e: return f"Erreur IA : {e}"

def latex_to_image(latex_str):
    """Transforme une formule LaTeX en image PNG transparente"""
    try:
        # Configuration d'une petite figure matplotlib
        fig, ax = plt.subplots(figsize=(6, 1)) # Taille rectangle
        # On dessine la formule
        ax.text(0.5, 0.5, f"${latex_str}$", size=18, ha='center', va='center')
        ax.axis('off') # On cache les axes
        
        # Sauvegarde en mémoire
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf
    except:
        return None

def create_word_docx(text_content, title="Document IA"):
    """Génère un Word en remplaçant les $$...$$ par des images"""
    doc = Document()
    doc.add_heading(title, 0)
    
    # On découpe le texte par blocs de formules $$
    # Le regex capture ce qui est entre $$
    parts = re.split(r'(\$\$.*?\$\$)', text_content, flags=re.DOTALL)
    
    for part in parts:
        if part.startswith('$$') and part.endswith('$$'):
            # C'est une formule ! On nettoie les $$
            latex_code = part.replace('$$', '').strip()
            image_buffer = latex_to_image(latex_code)
            
            if image_buffer:
                # On ajoute l'image centrée
                doc.add_picture(image_buffer, width=Inches(2))
            else:
                # Si l'image plante, on met le code en secours
                doc.add_paragraph(part)
        else:
            # C'est du texte normal
            if part.strip(): # On évite les lignes vides inutiles
                doc.add_paragraph(part.strip())
                
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- 4. INTERFACE ---
with st.sidebar:
    st.header("🎒 Cartable")
    uploaded_files = st.file_uploader("Fichiers", accept_multiple_files=True)
    if uploaded_files:
        if st.button("🔄 Analyser"):
            with st.spinner("Lecture..."):
                raw = ""
                for f in uploaded_files: raw += get_file_content(f)
                st.session_state['context'] = raw
                st.success("Chargé !")
    st.divider()
    if 'context' in st.session_state: st.info("Mémoire active")

# --- 5. ZONES ---
st.subheader("🎓 Tuteur Finance")
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📝 Synthèses", "🧠 Quiz"])

with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                # Bouton de téléchargement avec conversion d'images
                docx = create_word_docx(msg["content"], title=f"Réponse {i}")
                st.download_button("💾 Word (Avec Images)", docx.getvalue(), f"note_{i}.docx", key=f"d{i}")

    if user := st.chat_input("Question (ex: Formule Écart-Type)..."):
        st.session_state.messages.append({"role": "user", "content": user})
        with st.chat_message("user"): st.markdown(user)
        
        ctx = st.session_state.get('context', '')
        with st.chat_message("assistant"):
            with st.spinner("Calcul..."):
                resp = ask_gemini(f"Contexte: {ctx}. Question: {user}")
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp})
                
                docx = create_word_docx(resp, title="Réponse Instantanée")
                st.download_button("💾 Télécharger (Format Image)", docx.getvalue(), "reponse.docx", key="new")

with tab2:
    if st.button("Générer Synthèse"):
        if 'context' in st.session_state:
            with st.spinner("Rédaction..."):
                res = ask_gemini(f"Synthèse structurée sur : {st.session_state['context']}")
                st.markdown(res)
                docx = create_word_docx(res, title="Synthèse Complète")
                st.download_button("📥 Télécharger", docx.getvalue(), "synthese.docx")
        else: st.error("Pas de documents.")

with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            res = ask_gemini(f"3 QCM sur : {st.session_state['context']}")
            st.markdown(res)
            docx = create_word_docx(res, title="Quiz")
            st.download_button("📥 Télécharger", docx.getvalue(), "quiz.docx")
        else: st.error("Pas de documents.")
