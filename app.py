import streamlit as st
import google.generativeai as genai
from groq import Groq
from pypdf import PdfReader
import pandas as pd
from pptx import Presentation
from docx import Document
from docx.shared import Inches
from fpdf import FPDF  # Pour le PDF
from PIL import Image
import io
import matplotlib.pyplot as plt
import re
import tempfile
import os

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Tuteur Intelligent (PDF/Word)", layout="wide", page_icon="🎓")

st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px; padding: 10px; margin-bottom: 10px;}
    .badge {padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white;}
    .badge-flash {background-color: #28a745;} /* Vert */
    .badge-pro {background-color: #007bff;}   /* Bleu */
    .badge-groq {background-color: #dc3545;}  /* Rouge */
    /* Ajustement des boutons pour qu'ils soient jolis côte à côte */
    .stButton button {width: 100%;}
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION AUX IA ---
valid_google_models = []

# Connexion Google
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    valid_google_models.append(m.name)
        except:
            valid_google_models = ["models/gemini-flash-latest", "models/gemini-pro"]
except: pass

# Connexion Groq
groq_client = None
if "GROQ_API_KEY" in st.secrets:
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: pass


# --- 3. FONCTIONS TECHNIQUES ---
def get_file_content(uploaded_file):
    text = ""
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type in ['png', 'jpg', 'jpeg']:
            image = Image.open(uploaded_file)
            # Vision : Utilisation d'un modèle Flash
            vision_model_name = 'gemini-flash-latest'
            for m in valid_google_models:
                if 'flash' in m and 'lite' not in m:
                    vision_model_name = m
                    break
            try:
                vision_model = genai.GenerativeModel(vision_model_name)
                response = vision_model.generate_content(["Transcris tout le texte :", image])
                text += f"\n--- Image ---\n{response.text}"
            except Exception as e:
                text += f"\n[Erreur Image: {e}]"
                
        elif file_type == 'pdf':
            pdf_reader = PdfReader(uploaded_file)
            for page in pdf_reader.pages: text += page.extract_text() or ""
        elif file_type in ['xlsx', 'xls']:
            xls = pd.ExcelFile(uploaded_file)
            for sheet in xls.sheet_names:
                text += f"\n--- Excel: {sheet} ---\n" + pd.read_excel(xls, sheet_name=sheet).to_string()
        elif file_type == 'docx':
            for para in Document(uploaded_file).paragraphs: text += para.text + "\n"
    except Exception as e:
        st.error(f"Erreur lecture {uploaded_file.name}: {e}")
    return text

def get_google_model_name(type="flash"):
    """Trouve le meilleur nom de modèle valide sur votre compte"""
    clean_models = [m.replace('models/', '') for m in valid_google_models]
    
    if type == "pro":
        candidates = [m for m in clean_models if 'pro' in m and '2.5' in m]
        if not candidates: candidates = [m for m in clean_models if 'pro' in m and 'latest' in m]
        if not candidates: candidates = [m for m in clean_models if 'pro' in m]
        return candidates[0] if candidates else 'gemini-pro'
    else: 
        candidates = [m for m in clean_models if 'flash' in m and 'latest' in m]
        if not candidates: candidates = [m for m in clean_models if 'flash' in m]
        return candidates[0] if candidates else 'gemini-flash-latest'

def ask_groq(prompt, system_instruction):
    if not groq_client: raise Exception("Pas de clé Groq")
    chat = groq_client.chat.completions.create(
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile", temperature=0
    )
    return chat.choices[0].message.content

def ask_smart_ai(prompt, context=""):
    has_ctx = len(context) > 10
    full_prompt = f"Contexte : {context}\n\nQuestion : {prompt}" if has_ctx else prompt
    system_instruction = "Tu es un expert pédagogique Finance. Utilise $$...$$ pour les formules LaTeX (ex: $$ E=mc^2 $$)."

    complexity_keywords = ["analyse", "synthèse", "résous", "calcul", "tableau", "excel", "bilan", "ratio", "formule", "développe", "argumente", "comparer", "pourquoi"]
    
    is_complex = False
    if has_ctx: is_complex = True
    elif any(k in prompt.lower() for k in complexity_keywords): is_complex = True
    elif len(prompt.split()) > 15: is_complex = True

    # CAS A : SIMPLE -> FLASH
    if not is_complex:
        try:
            model_name = get_google_model_name("flash")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(system_instruction + "\n\n" + full_prompt)
            return response.text, f"⚡ Gemini Flash ({model_name})"
        except Exception as e:
            try:
                return ask_groq(full_prompt, system_instruction), "🦙 Groq (Secours Flash)"
            except:
                return f"Erreur Flash & Groq: {e}", "❌ Panne"

    # CAS B : COMPLEXE -> PRO -> GROQ -> FLASH
    else:
        try:
            model_name = get_google_model_name("pro")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(system_instruction + "\n\n" + full_prompt)
            return response.text, f"🧠 Gemini Pro ({model_name})"
        
        except Exception as google_error:
            try:
                resp = ask_groq(full_prompt, system_instruction)
                return resp, "🦙 Groq (Relais Pro)"
            except Exception as groq_error:
                try:
                    model_name = get_google_model_name("flash")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(system_instruction + "\n\n" + full_prompt)
                    return response.text, "⚡ Gemini Flash (Secours Ultime)"
                except:
                    return f"Échec total.", "❌ Panne Totale"

# --- FONCTIONS DESSIN & DOCUMENTS ---
def latex_to_image(latex_str):
    try:
        fig, ax = plt.subplots(figsize=(6, 1.5))
        clean_latex = latex_str.replace(r'\ ', ' ') 
        ax.text(0.5, 0.5, f"${clean_latex}$", size=20, ha='center', va='center')
        ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf
    except: return None

def clean_text_for_word(text):
    text = text.replace('$', '')
    # Nettoyage des caractères LaTeX
    replacements = {
        r'\sigma': 'σ', r'\Sigma': 'Σ', r'\mu': 'μ', r'\beta': 'β', r'\alpha': 'α',
        r'\gamma': 'γ', r'\lambda': 'λ', r'\sum': '∑', r'\approx': '≈', r'\times': '×',
        r'\le': '≤', r'\ge': '≥', r'\infty': '∞', r'_i': 'ᵢ', r'_t': 'ₜ', r'_0': '₀', r'^2': '²', r'\%': '%'
    }
    for latex, char in replacements.items(): text = text.replace(latex, char)
    return text

def create_word_docx(text_content, title="Document IA"):
    doc = Document()
    doc.add_heading(title, 0)
    parts = re.split(r'(\$\$.*?\$\$)', text_content, flags=re.DOTALL)
    for part in parts:
        if part.startswith('$$') and part.endswith('$$'):
            image_buffer = latex_to_image(part.replace('$$', '').strip())
            if image_buffer: doc.add_picture(image_buffer, width=Inches(2.5))
            else: doc.add_paragraph(part)
        else:
            if part.strip(): doc.add_paragraph(clean_text_for_word(part))
    bio = io.BytesIO()
    doc.save(bio)
    return bio

def create_pdf(text_content, title="Document IA"):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, title, 0, 1, 'C')
            self.ln(5)

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    # Découpage pour gérer les formules LaTeX
    parts = re.split(r'(\$\$.*?\$\$)', text_content, flags=re.DOTALL)
    
    for part in parts:
        if part.startswith('$$') and part.endswith('$$'):
            # Image Math
            image_buffer = latex_to_image(part.replace('$$', '').strip())
            if image_buffer:
                # FPDF a besoin d'un fichier physique temporaire pour l'image
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                    temp_img.write(image_buffer.getvalue())
                    temp_img_path = temp_img.name
                
                try:
                    pdf.image(temp_img_path, w=100, x=55) # Centré à peu près
                except: pass
                
                # Nettoyage fichier temporaire
                try: os.remove(temp_img_path)
                except: pass
        else:
            # Texte normal (encodage latin-1 pour FPDF standard)
            # On remplace les caractères non supportés par '?' pour éviter le crash
            clean_txt = clean_text_for_word(part)
            clean_txt = clean_txt.encode('latin-1', 'replace').decode('latin-1')
            if clean_txt.strip():
                pdf.multi_cell(0, 7, txt=clean_txt)
                pdf.ln(2)

    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFACE ---
with st.sidebar:
    st.header("🎒 Cartable")
    
    if groq_client: st.success("✅ Groq Connecté")
    else: st.warning("⚠️ Groq Absent (Ajoutez la clé)")
    
    st.divider()
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

st.subheader(f"🎓 Tuteur Automatique")
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📝 Synthèses", "🧠 Quiz"])

with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                used_model = msg.get("model_label", "IA")
                if "Groq" in used_model: badge = "badge-groq"
                elif "Pro" in used_model: badge = "badge-pro"
                else: badge = "badge-flash"
                st.markdown(f'<span class="badge {badge}">{used_model}</span>', unsafe_allow_html=True)
                
                # --- NOUVEAU : DOUBLE BOUTONS ---
                col1, col2 = st.columns(2)
                with col1:
                    docx = create_word_docx(msg["content"], title=f"Réponse {i}")
                    st.download_button("💾 Word", docx.getvalue(), f"note_{i}.docx", key=f"d{i}w")
                with col2:
                    try:
                        pdf_data = create_pdf(msg["content"], title=f"Réponse {i}")
                        st.download_button("📄 PDF", pdf_data, f"note_{i}.pdf", key=f"d{i}p")
                    except Exception as e:
                        st.error("Erreur PDF")

    if user := st.chat_input("Question..."):
        st.session_state.messages.append({"role": "user", "content": user})
        with st.chat_message("user"): st.markdown(user)
        ctx = st.session_state.get('context', '')
        with st.chat_message("assistant"):
            with st.spinner(f"Analyse..."):
                resp, model_label = ask_smart_ai(user, context=ctx)
                
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp, "model_label": model_label})
                
                if "Groq" in model_label: badge = "badge-groq"
                elif "Pro" in model_label: badge = "badge-pro"
                else: badge = "badge-flash"
                st.markdown(f'<span class="badge {badge}">{model_label}</span>', unsafe_allow_html=True)
                
                # --- NOUVEAU : DOUBLE BOUTONS ---
                col1, col2 = st.columns(2)
                with col1:
                    docx = create_word_docx(resp, title="Réponse Instantanée")
                    st.download_button("💾 Word", docx.getvalue(), "reponse.docx", key="new_w")
                with col2:
                    try:
                        pdf_data = create_pdf(resp, title="Réponse Instantanée")
                        st.download_button("📄 PDF", pdf_data, "reponse.pdf", key="new_p")
                    except: st.error("Erreur PDF")

with tab2:
    if st.button("Générer Synthèse"):
        if 'context' in st.session_state:
            with st.spinner("Rédaction..."):
                resp, label = ask_smart_ai(f"Synthèse structurée.", context=st.session_state['context'])
                st.markdown(resp)
                
                c1, c2 = st.columns(2)
                with c1:
                    docx = create_word_docx(resp, title="Synthèse")
                    st.download_button("💾 Word", docx.getvalue(), "synthese.docx")
                with c2:
                    pdf = create_pdf(resp, title="Synthèse")
                    st.download_button("📄 PDF", pdf, "synthese.pdf")
        else: st.error("Pas de documents.")

with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            resp, label = ask_smart_ai(f"3 QCM.", context=st.session_state['context'])
            st.markdown(resp)
            
            c1, c2 = st.columns(2)
            with c1:
                docx = create_word_docx(resp, title="Quiz")
                st.download_button("💾 Word", docx.getvalue(), "quiz.docx")
            with c2:
                pdf = create_pdf(resp, title="Quiz")
                st.download_button("📄 PDF", pdf, "quiz.pdf")
        else: st.error("Pas de documents.")
