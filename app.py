import streamlit as st
import google.generativeai as genai
import anthropic
from groq import Groq
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
    .badge {padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white;}
    .badge-velo {background-color: #28a745;}
    .badge-ferrari {background-color: #dc3545;}
    .badge-tracteur {background-color: #007bff;}
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION AUX IA ---
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except: pass

groq_client = None
if "GROQ_API_KEY" in st.secrets:
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: pass

claude_client = None
if "ANTHROPIC_API_KEY" in st.secrets:
    try: claude_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except: pass

# --- 3. FONCTIONS TECHNIQUES ---
def get_file_content(uploaded_file):
    text = ""
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        if file_type in ['png', 'jpg', 'jpeg']:
            image = Image.open(uploaded_file)
            vision_model = genai.GenerativeModel('gemini-1.5-flash')
            response = vision_model.generate_content(["Transcris tout le texte :", image])
            text += f"\n--- Image ---\n{response.text}"
        elif file_type == 'pdf':
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
    except Exception as e:
        st.error(f"Erreur lecture {uploaded_file.name}: {e}")
    return text

def select_best_ai(prompt, mode_manuel, has_context=False):
    """Sélecteur de modèle (Smart Router)"""
    
    # 1. MODE MANUEL
    if mode_manuel == "🚲 Éco (Flash)":
        return "gemini-flash", "🚲 Gemini Flash (Forcé)"
    
    if mode_manuel == "🏎️ Expert (Llama/Pro)":
        if claude_client: return "claude", "🧠 Claude 3.5 (Luxe Forcé)"
        if groq_client: return "groq", "🏎️ Llama 3 (Ferrari Forcée)"
        return "gemini-pro", "🚜 Gemini Pro (Expert Forcé)"

    # 2. MODE AUTO
    prompt_lower = prompt.lower()
    complex_triggers = [
        "calcul", "analyse", "synthèse", "résous", "équation", "bilan", 
        "ratio", "expliquer", "détaille", "pourquoi", "comparer", "latex", 
        "formule", "démonstration", "excel", "tableau", "c'est quoi", "définition"
    ]
    
    needs_ferrari = False
    if has_context: needs_ferrari = True
    elif any(t in prompt_lower for t in complex_triggers): needs_ferrari = True
    elif len(prompt.split()) > 15: needs_ferrari = True
        
    if needs_ferrari:
        if claude_client: return "claude", "🧠 Claude 3.5 (Luxe Auto)"
        if groq_client: return "groq", "🏎️ Llama 3 (Ferrari Auto)"
        return "gemini-pro", "🚜 Gemini Pro (Tracteur Auto)"
    else:
        return "gemini-flash", "🚲 Gemini Flash (Vélo Auto)"

def ask_smart_ai(prompt, mode_manuel, context=""):
    has_ctx = len(context) > 10
    model_type, label = select_best_ai(prompt, mode_manuel, has_context=has_ctx)
    full_prompt = f"Contexte : {context}\n\nQuestion : {prompt}" if has_ctx else prompt
    
    system_instruction = "Tu es un expert pédagogique Finance. Utilise $$...$$ pour les formules LaTeX complexes."

    try:
        # --- CAS 1 : CLAUDE ---
        if model_type == "claude":
            msg = claude_client.messages.create(
                model="claude-3-5-sonnet-20240620", max_tokens=4000, temperature=0,
                system=system_instruction, messages=[{"role": "user", "content": full_prompt}]
            )
            return msg.content[0].text, label

        # --- CAS 2 : GROQ ---
        elif model_type == "groq":
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": full_prompt}],
                model="llama-3.3-70b-versatile", temperature=0,
            )
            return chat_completion.choices[0].message.content, label

        # --- CAS 3 : GEMINI PRO ---
        elif model_type == "gemini-pro":
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(system_instruction + "\n\n" + full_prompt)
            return response.text, label

        # --- CAS 4 : LE VÉLO (CORRECTION MAJEURE) ---
        else:
            # On utilise uniquement la famille 1.5 qui est stable
            safe_models = ['gemini-1.5-flash', 'gemini-1.5-pro']
            
            last_err = ""
            for m in safe_models:
                try:
                    model = genai.GenerativeModel(m)
                    # Note : En mode secours, on envoie le prompt directement SANS l'instruction système séparée
                    # pour éviter les erreurs de format sur certains modèles.
                    # On inclut l'instruction dans le texte global.
                    combined_prompt = system_instruction + "\n\n" + full_prompt
                    response = model.generate_content(combined_prompt)
                    return response.text, f"🚲 {m}"
                except Exception as e:
                    last_err = e
                    continue # On essaie le suivant
            
            return f"Erreur Vélo : Impossible de joindre Google ({last_err})", "❌ Panne"

    except Exception as e:
        return f"Erreur technique : {e}", "❌ Erreur"

# --- FONCTIONS DESSIN & WORD ---
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

# --- 4. INTERFACE ---
with st.sidebar:
    st.header("🎒 Cartable")
    
    st.markdown("### 🎛️ Mode de Pilotage")
    mode_choisi = st.radio(
        "Qui conduit ?",
        ["🤖 Auto (Smart)", "🚲 Éco (Flash)", "🏎️ Expert (Llama/Pro)"],
        index=0
    )
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

st.subheader(f"🎓 Tuteur Finance - Mode : {mode_choisi.split(' ')[1]}")
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📝 Synthèses", "🧠 Quiz"])

with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                used_model = msg.get("model_label", "IA")
                if "Vélo" in used_model: badge_class = "badge-velo"
                elif "Ferrari" in used_model: badge_class = "badge-ferrari"
                else: badge_class = "badge-tracteur"
                st.markdown(f'<span class="badge {badge_class}">{used_model}</span>', unsafe_allow_html=True)
                docx = create_word_docx(msg["content"], title=f"Réponse {i}")
                st.download_button("💾 Word", docx.getvalue(), f"note_{i}.docx", key=f"d{i}")

    if user := st.chat_input("Question..."):
        st.session_state.messages.append({"role": "user", "content": user})
        with st.chat_message("user"): st.markdown(user)
        ctx = st.session_state.get('context', '')
        with st.chat_message("assistant"):
            with st.spinner(f"Pilotage ({mode_choisi})..."):
                resp, model_label = ask_smart_ai(user, mode_choisi, context=ctx)
                
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp, "model_label": model_label})
                
                if "Vélo" in model_label: badge_class = "badge-velo"
                elif "Ferrari" in model_label: badge_class = "badge-ferrari"
                else: badge_class = "badge-tracteur"
                st.markdown(f'<span class="badge {badge_class}">{model_label}</span>', unsafe_allow_html=True)
                
                docx = create_word_docx(resp, title="Réponse Instantanée")
                st.download_button("💾 Télécharger", docx.getvalue(), "reponse.docx", key="new")

with tab2:
    if st.button("Générer Synthèse"):
        if 'context' in st.session_state:
            with st.spinner("Rédaction..."):
                resp, label = ask_smart_ai(f"Synthèse structurée.", mode_choisi, context=st.session_state['context'])
                st.markdown(resp)
                st.markdown(f"**{label}**")
                docx = create_word_docx(resp, title="Synthèse")
                st.download_button("📥 Télécharger", docx.getvalue(), "synthese.docx")
        else: st.error("Pas de documents.")

with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            resp, label = ask_smart_ai(f"3 QCM.", mode_choisi, context=st.session_state['context'])
            st.markdown(resp)
            st.markdown(f"**{label}**")
            docx = create_word_docx(resp, title="Quiz")
            st.download_button("📥 Télécharger", docx.getvalue(), "quiz.docx")
        else: st.error("Pas de documents.")
