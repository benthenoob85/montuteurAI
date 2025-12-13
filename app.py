import streamlit as st
import google.generativeai as genai
from groq import Groq # Optionnel, on le garde en backup au cas où
from pypdf import PdfReader
import pandas as pd
from pptx import Presentation
from docx import Document
from docx.shared import Inches
from PIL import Image
import io
import matplotlib.pyplot as plt
import re
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Tuteur Google Dynamique", layout="wide", page_icon="🎓")

st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px; padding: 10px; margin-bottom: 10px;}
    .badge {padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white;}
    .badge-google {background-color: #28a745;} /* Vert */
    .badge-backup {background-color: #ffc107; color: black;} /* Jaune */
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION ET DÉTECTION DES MODÈLES ---
valid_google_models = []

try:
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # --- C'EST ICI QUE LA MAGIE OPÈRE ---
        # On demande la liste officielle à votre compte pour ne pas avoir de 404
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    # On privilégie les versions stables et "latest"
                    valid_google_models.append(m.name)
        except:
            # Si le listage échoue, on met des valeurs sûres par défaut
            valid_google_models = ["models/gemini-flash-latest", "models/gemini-pro"]
            
except: pass

# Backup Groq (Juste au cas où, mais Google reste prioritaire)
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
            # Vision : On utilise le premier modèle disponible qui n'est pas "lite" (souvent mieux pour l'image)
            vision_model_name = 'gemini-flash-latest' # Par défaut
            for m in valid_google_models:
                if 'flash' in m and 'lite' not in m:
                    vision_model_name = m
                    break
            
            vision_model = genai.GenerativeModel(vision_model_name)
            response = vision_model.generate_content(["Transcris tout le texte :", image])
            text += f"\n--- Image ---\n{response.text}"
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

def get_optimized_model_list(strategy):
    """
    Trie les modèles DISPONIBLES SUR VOTRE COMPTE par ordre de préférence
    selon la stratégie (Pro vs Flash).
    """
    prioritized_list = []
    
    # On nettoie les noms (enlève 'models/')
    clean_models = [m.replace('models/', '') for m in valid_google_models]
    
    if strategy == "pro":
        # 1. On cherche les "Pro" récents
        prioritized_list += [m for m in clean_models if 'pro' in m and '2.5' in m] # Le top
        prioritized_list += [m for m in clean_models if 'pro' in m and 'latest' in m] # Le standard
        prioritized_list += [m for m in clean_models if 'pro' in m] # Les autres pros
        # 2. Si pas de pro, on prend les Flash puissants
        prioritized_list += [m for m in clean_models if 'flash' in m and '2.0' in m]
        
    else: # Strategy Flash
        # 1. On cherche les "Flash" stables
        prioritized_list += [m for m in clean_models if 'flash' in m and 'latest' in m]
        prioritized_list += [m for m in clean_models if 'flash' in m and '2.0' in m]
        prioritized_list += [m for m in clean_models if 'flash' in m]
    
    # On enlève les doublons tout en gardant l'ordre
    seen = set()
    final_list = [x for x in prioritized_list if not (x in seen or seen.add(x))]
    
    return final_list

def ask_smart_ai(prompt, mode_manuel, context=""):
    has_ctx = len(context) > 10
    full_prompt = f"Contexte : {context}\n\nQuestion : {prompt}" if has_ctx else prompt
    system_instruction = "Tu es un expert pédagogique Finance. Utilise $$...$$ pour les formules LaTeX (ex: $$ E=mc^2 $$)."

    # --- DÉTERMINATION DE LA STRATÉGIE ---
    strategy = "flash" # Par défaut
    
    # Mode Manuel
    if "Pro" in mode_manuel: strategy = "pro"
    
    # Mode Auto
    elif "Auto" in mode_manuel:
        technical_triggers = ["analyse", "synthèse", "résous", "calcul", "tableau", "excel", "bilan", "ratio"]
        if has_context or any(t in prompt.lower() for t in technical_triggers):
            strategy = "pro"

    # --- SÉLECTION DE LA LISTE DE BATAILLE ---
    # On récupère la liste des modèles QUI EXISTENT VRAIMENT chez vous
    model_cascade = get_optimized_model_list(strategy)
    
    # On ajoute une sécurité générique à la fin
    model_cascade.append('gemini-flash-latest')

    last_error = ""
    
    # --- EXÉCUTION DE LA CASCADE GOOGLE ---
    for model_name in model_cascade:
        try:
            # Tentative d'appel Google
            model = genai.GenerativeModel(model_name)
            combined_prompt = system_instruction + "\n\n" + full_prompt
            response = model.generate_content(combined_prompt)
            
            # Succès !
            return response.text, f"Google {model_name}"

        except Exception as e:
            last_error = e
            # Si erreur 429 (Quota) ou autre, on passe au suivant
            continue

    # --- DERNIER RECOURS : GROQ (Si Google est totalement mort) ---
    if groq_client:
        try:
            chat = groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": full_prompt}],
                model="llama-3.3-70b-versatile", temperature=0
            )
            return chat.choices[0].message.content, "🦙 Groq (Secours Ultime)"
        except: pass

    return f"Panne totale. Google bloque tous les modèles disponibles. (Erreur: {last_error})", "❌ Erreur"

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
    st.header("🎒 Cartable Google")
    
    st.markdown("### 🎛️ Choix de l'IA")
    mode_choisi = st.radio(
        "Mode :",
        ["🤖 Auto", "⚡ Flash (Rapide)", "🧠 Pro (Expert)"],
        index=0
    )
    
    # Affichage des modèles détectés pour debug
    with st.expander("🔍 Modèles détectés"):
        if valid_google_models:
            for m in valid_google_models: st.write(f"- {m}")
        else:
            st.warning("Aucun modèle détecté (Erreur clé ?)")

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

st.subheader(f"🎓 Tuteur Finance")
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📝 Synthèses", "🧠 Quiz"])

with tab1:
    if "messages" not in st.session_state: st.session_state.messages = []
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                used_model = msg.get("model_label", "IA")
                st.markdown(f'<span class="badge badge-google">{used_model}</span>', unsafe_allow_html=True)
                docx = create_word_docx(msg["content"], title=f"Réponse {i}")
                st.download_button("💾 Word", docx.getvalue(), f"note_{i}.docx", key=f"d{i}")

    if user := st.chat_input("Question..."):
        st.session_state.messages.append({"role": "user", "content": user})
        with st.chat_message("user"): st.markdown(user)
        ctx = st.session_state.get('context', '')
        with st.chat_message("assistant"):
            with st.spinner(f"Réflexion (Google)..."):
                resp, model_label = ask_smart_ai(user, mode_choisi, context=ctx)
                
                st.markdown(resp)
                st.session_state.messages.append({"role": "assistant", "content": resp, "model_label": model_label})
                
                st.markdown(f'<span class="badge badge-google">{model_label}</span>', unsafe_allow_html=True)
                
                docx = create_word_docx(resp, title="Réponse Instantanée")
                st.download_button("💾 Télécharger", docx.getvalue(), "reponse.docx", key="new")

with tab2:
    if st.button("Générer Synthèse"):
        if 'context' in st.session_state:
            with st.spinner("Rédaction..."):
                resp, label = ask_smart_ai(f"Synthèse structurée.", mode_choisi, context=st.session_state['context'])
                st.markdown(resp)
                docx = create_word_docx(resp, title="Synthèse")
                st.download_button("📥 Télécharger", docx.getvalue(), "synthese.docx")
        else: st.error("Pas de documents.")

with tab3:
    if st.button("Lancer Quiz"):
        if 'context' in st.session_state:
            resp, label = ask_smart_ai(f"3 QCM.", mode_choisi, context=st.session_state['context'])
            st.markdown(resp)
            docx = create_word_docx(resp, title="Quiz")
            st.download_button("📥 Télécharger", docx.getvalue(), "quiz.docx")
        else: st.error("Pas de documents.")
