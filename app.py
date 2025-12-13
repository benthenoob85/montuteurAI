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
st.set_page_config(page_title="Tuteur IA Smart-Routing", layout="wide", page_icon="🎓")

st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px; padding: 10px; margin-bottom: 10px;}
    .stDownloadButton > button {height: 30px; padding: 0px;}
    .badge {padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white;}
    .badge-velo {background-color: #28a745;} /* Vert */
    .badge-ferrari {background-color: #dc3545;} /* Rouge */
    .badge-tracteur {background-color: #007bff;} /* Bleu */
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION AUX ÉCURIES D'IA ---
# Google
try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except: pass

# Groq (La Ferrari Gratuite)
groq_client = None
if "GROQ_API_KEY" in st.secrets:
    try: groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    except: pass

# Anthropic (Optionnel)
claude_client = None
if "ANTHROPIC_API_KEY" in st.secrets:
    try: claude_client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except: pass

# --- 3. FONCTIONS TECHNIQUES ---
def get_file_content(uploaded_file):
    text = ""
    file_type = uploaded_file.name.split('.')[-1].lower()
    try:
        # Pour la vision (images), Gemini est le seul roi gratuit
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

def select_best_ai(prompt, has_context=False):
    """
    LE CHEF DE GARE : Choisit le véhicule selon la mission.
    """
    prompt_lower = prompt.lower()
    
    # Mots-clés qui nécessitent la FERRARI (Raisonnement/Maths)
    complex_triggers = [
        "calcul", "analyse", "synthèse", "résous", "équation", "bilan", 
        "ratio", "expliquer", "détaille", "pourquoi", "comparer", "latex", 
        "formule", "démonstration", "excel", "tableau"
    ]
    
    # 1. ANALYSE DE LA COMPLEXITÉ
    needs_ferrari = False
    
    # Si on a des documents chargés, on privilégie toujours l'intelligence
    if has_context: 
        needs_ferrari = True
    # Si la question contient des mots complexes
    elif any(trigger in prompt_lower for trigger in complex_triggers):
        needs_ferrari = True
    # Si la question est longue (> 15 mots), c'est souvent complexe
    elif len(prompt.split()) > 15:
        needs_ferrari = True
        
    # 2. SÉLECTION DU MODÈLE
    
    # SCÉNARIO A : Besoin de puissance (Ferrari)
    if needs_ferrari:
        # Priorité 1 : Claude (Si payé - Le Top du Top)
        if claude_client:
            return "claude", "🧠 Claude 3.5 (Luxe)"
            
        # Priorité 2 : Llama 3 via Groq (Gratuit & Intelligent)
        if groq_client:
            return "groq", "🏎️ Llama 3 (Ferrari)"
            
        # Priorité 3 : Gemini Pro (Solide)
        return "gemini-pro", "🚜 Gemini Pro (Tracteur)"

    # SCÉNARIO B : Pas besoin de puissance (Vélo)
    else:
        # Gemini Flash est parfait pour le chat rapide
        return "gemini-flash", "🚲 Gemini Flash (Vélo)"


def ask_smart_ai(prompt, context=""):
    """Exécute la demande avec le modèle choisi par le Chef de Gare"""
    
    # 1. On appelle le Chef de Gare
    has_ctx = len(context) > 10
    model_type, label = select_best_ai(prompt, has_context=has_ctx)
    
    full_prompt = f"Contexte : {context}\n\nQuestion : {prompt}" if has_ctx else prompt
    
    system_instruction = (
        "Tu es un expert pédagogique Finance. "
        "RÈGLE : Utilise $$ ... $$ pour les formules complexes (LaTeX) et $...$ pour les symboles."
    )

    try:
        # EXÉCUTION SELON LE CHOIX
        
        # --- CAS 1 : CLAUDE ---
        if model_type == "claude":
            msg = claude_client.messages.create(
                model="claude-3-5-sonnet-20240620", max_tokens=4000, temperature=0,
                system=system_instruction, messages=[{"role": "user", "content": full_prompt}]
            )
            return msg.content[0].text, label

        # --- CAS 2 : GROQ (LLAMA 3) ---
        elif model_type == "groq":
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": full_prompt}
                ],
                model="llama-3.3-70b-versatile", # Le modèle le plus intelligent de Groq
                temperature=0,
            )
            return chat_completion.choices[0].message.content, label

        # --- CAS 3 : GEMINI PRO ---
        elif model_type == "gemini-pro":
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(system_instruction + "\n\n" + full_prompt)
            return response.text, label

        # --- CAS 4 : GEMINI FLASH (Défaut) ---
        else:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(system_instruction + "\n\n" + full_prompt)
            return response.text, label

    except Exception as e:
        # EN CAS DE PANNE : On sort le vieux vélo de secours (Gemini Flash)
        try:
            fallback = genai.GenerativeModel('gemini-1.5-flash')
            resp = fallback.generate_content(full_prompt)
            return resp.text, "🚲 Gemini Flash (Secours)"
        except:
            return f"Erreur technique : {e}", "❌ Panne"

# --- FONCTIONS DESSIN & WORD (Inchangées et Indispensables) ---
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

st.subheader("🎓 Tuteur Optimisé (Smart Routing)")
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📝 Synthèses", "🧠 Quiz"])

with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                used_model = msg.get("model_label", "IA")
                # Affichage visuel du modèle utilisé (Badge)
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
            with st.spinner("Le Chef de Gare choisit le véhicule..."):
                resp, model_label = ask_smart_ai(user, context=ctx)
                
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp, "model_label": model_label})
                
                # Badge visuel
                if "Vélo" in model_label: badge_class = "badge-velo"
                elif "Ferrari" in model_label: badge_class = "badge-ferrari"
                else: badge_class = "badge-tracteur"
                st.markdown(f'<span class="badge {badge_class}">{model_label}</span>', unsafe_allow_html=True)
                
                docx = create_word_docx(resp, title="Réponse Instantanée")
                st.download_button("💾 Télécharger", docx.getvalue(), "reponse.docx", key="new")

# Les autres onglets utilisent aussi le Smart AI (par défaut Ferrari car c'est de l'analyse)
with tab2:
    if st.button("Générer Synthèse"):
        if 'context' in st.session_state:
            with st.spinner("Rédaction..."):
                resp, label = ask_smart_ai(f"Synthèse structurée de ce cours.", context=st.session_state['context'])
                st.markdown(resp)
                st.markdown(f"**Généré par : {label}**")
                docx = create_word_docx(resp, title="Synthèse Complète")
                st.download_button("📥 Télécharger", docx.getvalue(), "synthese.docx")
        else: st.error("Pas de documents.")

with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            resp, label = ask_smart_ai(f"3 QCM difficiles.", context=st.session_state['context'])
            st.markdown(resp)
            st.markdown(f"**Généré par : {label}**")
            docx = create_word_docx(resp, title="Quiz")
            st.download_button("📥 Télécharger", docx.getvalue(), "quiz.docx")
        else: st.error("Pas de documents.")
