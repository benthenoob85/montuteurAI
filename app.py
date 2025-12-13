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
        # On demande à l'IA d'être stricte sur le LaTeX
        system_instruction = (
            "Tu es un expert Finance. "
            "RÈGLE 1 : Pour les GRANDES formules complexes, utilise $$ ... $$. "
            "RÈGLE 2 : Pour les symboles dans le texte (comme sigma, xi), utilise le LaTeX simple ($...$). "
            "Sois précis."
        )
        response = model.generate_content(system_instruction + "\n\n" + prompt)
        return response.text
    except Exception as e: return f"Erreur IA : {e}"

def latex_to_image(latex_str):
    """Transforme une grosse formule en image"""
    try:
        fig, ax = plt.subplots(figsize=(6, 1.5)) # Un peu plus haut pour les sommes
        # On nettoie un peu le LaTeX pour matplotlib
        clean_latex = latex_str.replace(r'\ ', ' ') 
        ax.text(0.5, 0.5, f"${clean_latex}$", size=20, ha='center', va='center')
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf
    except:
        return None

def clean_text_for_word(text):
    """Traduit le 'petit' LaTeX du texte en caractères Word lisibles"""
    # 1. On enlève les dollars simples qui polluent la lecture
    text = text.replace('$', '')
    
    # 2. Dictionnaire de traduction (LaTeX -> Caractère Word)
    replacements = {
        r'\sigma': 'σ',
        r'\Sigma': 'Σ',
        r'\mu': 'μ',
        r'\beta': 'β',
        r'\alpha': 'α',
        r'\gamma': 'γ',
        r'\lambda': 'λ',
        r'\sum': '∑',
        r'\approx': '≈',
        r'\times': '×',
        r'\le': '≤',
        r'\ge': '≥',
        r'\infty': '∞',
        # Les indices et exposants financiers courants
        r'_i': 'ᵢ',
        r'_t': 'ₜ',
        r'_0': '₀',
        r'^2': '²',
        r'\%': '%'
    }
    
    for latex_code, unicode_char in replacements.items():
        text = text.replace(latex_code, unicode_char)
        
    return text

def create_word_docx(text_content, title="Document IA"):
    doc = Document()
    doc.add_heading(title, 0)
    
    # On découpe le texte : on sépare les grosses formules ($$) du reste
    parts = re.split(r'(\$\$.*?\$\$)', text_content, flags=re.DOTALL)
    
    for part in parts:
        if part.startswith('$$') and part.endswith('$$'):
            # C'est une GROSSE formule -> On fait une image
            latex_code = part.replace('$$', '').strip()
            image_buffer = latex_to_image(latex_code)
            
            if image_buffer:
                doc.add_picture(image_buffer, width=Inches(2.5))
            else:
                doc.add_paragraph(part) # Secours
        else:
            # C'est du texte ou des petites formules -> On nettoie
            if part.strip():
                clean_text = clean_text_for_word(part)
                doc.add_paragraph(clean_text)
                
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
                docx = create_word_docx(msg["content"], title=f"Réponse {i}")
                st.download_button("💾 Word (Propre)", docx.getvalue(), f"note_{i}.docx", key=f"d{i}")

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
                st.download_button("💾 Télécharger (Word Propre)", docx.getvalue(), "reponse.docx", key="new")

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
