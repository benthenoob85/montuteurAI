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

# --- 3. MOTEUR D'EXTRACTION UNIVERSEL ---
def get_file_content(uploaded_file):
    """Fonction qui transforme n'importe quel fichier en texte"""
    text = ""
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        # CAS 1 : PDF
        if file_type == 'pdf':
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        
        # CAS 2 : EXCEL (On lit toutes les feuilles)
        elif file_type in ['xlsx', 'xls']:
            xls = pd.ExcelFile(uploaded_file)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                text += f"\n--- Feuille Excel : {sheet_name} ---\n"
                text += df.to_string() # Convertit le tableau en texte
                
        # CAS 3 : POWERPOINT
        elif file_type == 'pptx':
            prs = Presentation(uploaded_file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
                        
        # CAS 4 : WORD
        elif file_type == 'docx':
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
                
        # CAS 5 : IMAGES & NOTES MANUSCRITES (La Magie !)
        elif file_type in ['png', 'jpg', 'jpeg']:
            image = Image.open(uploaded_file)
            # On demande à l'IA de transcrire l'image tout de suite
            response = model.generate_content(["Transcris intégralement et précisément tout le texte visible sur cette image (notes manuscrites ou tableau).", image])
            text += f"\n--- Transcription Image ({uploaded_file.name}) ---\n"
            text += response.text

    except Exception as e:
        st.error(f"Erreur de lecture sur {uploaded_file.name}: {e}")
        
    return text

def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erreur IA : {e}"

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("🎒 Mon Cartable Polyvalent")
    matiere = st.selectbox("Matière", ["Finance", "Stats", "Droit", "Comptabilité", "Autre"])
    st.divider()
    
    # Upload universel
    st.caption("Chargez vos cours (Tout format)")
    uploaded_files = st.file_uploader(
        "PDF, Excel, Word, PPT, Images...", 
        accept_multiple_files=True, 
        type=['pdf', 'xlsx', 'xls', 'pptx', 'docx', 'png', 'jpg', 'jpeg']
    )
    
    if uploaded_files:
        if st.button("🔄 Analyser les fichiers", type="primary"):
            with st.spinner("Lecture et analyse (OCR pour les images)..."):
                raw_text = ""
                for file in uploaded_files:
                    content = get_file_content(file)
                    raw_text += f"\n\n--- DOCUMENT : {file.name} ---\n{content}"
                
                if len(raw_text) > 20:
                    st.session_state['context'] = raw_text
                    st.success(f"✅ {len(uploaded_files)} documents intégrés en mémoire !")
                else:
                    st.warning("Aucun texte exploitable trouvé.")

    if 'context' in st.session_state:
        st.info("🧠 Mémoire active")
    else:
        st.warning("⚠️ Aucun document chargé")

# --- 5. INTERFACE PRINCIPALE ---
st.title(f"Tutorat : {matiere}")
tab_chat, tab_outils, tab_quiz = st.tabs(["💬 Discussion", "📝 Synthèses", "🧠 Quiz"])

# CHAT
with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if user_input := st.chat_input("Une question sur vos documents ?"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)
        
        context = st.session_state.get('context', '')
        full_prompt = f"Tu es un tuteur expert. Contexte du cours : {context}. Question : {user_input}"
        
        with st.chat_message("assistant"):
            with st.spinner("Réflexion..."):
                resp = ask_gemini(full_prompt)
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp})

# OUTILS (Code identique mais connecté au nouveau contexte)
with tab_outils:
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📄 Synthèse")
        if st.button("Résumer le contenu"):
            if 'context' in st.session_state:
                with st.spinner("Rédaction..."):
                    st.markdown(ask_gemini(f"Fais une synthèse structurée de : {st.session_state['context']}"))
            else: st.error("Chargez des documents.")
            
    with col2:
        st.write("### 📇 Flashcards")
        if st.button("Créer des cartes"):
            if 'context' in st.session_state:
                with st.spinner("Génération..."):
                    prompt = f"5 Flashcards (Question ; Réponse) sur : {st.session_state['context']}. Format 'Q ; R' par ligne."
                    res = ask_gemini(prompt)
                    for line in res.split('\n'):
                        if ";" in line:
                            p = line.split(";", 1)
                            with st.expander(f"❓ {p[0]}"): st.write(f"💡 {p[1]}")
            else: st.error("Chargez des documents.")

# QUIZ
with tab_quiz:
    if st.button("Lancer un Quiz"):
        if 'context' in st.session_state:
            with st.spinner("Génération..."):
                st.markdown(ask_gemini(f"Quiz QCM de 3 questions sur : {st.session_state['context']}. Correction à la fin."))
        else: st.error("Chargez des documents.")
