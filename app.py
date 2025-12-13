import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Mon Tuteur IA", layout="wide", page_icon="🎓")

# CSS Personnalisé pour le look "Zen"
st.markdown("""
<style>
    .stButton>button {
        border-radius: 20px;
        background-color: #F8F9FA;
        border: 1px solid #E0E0E0;
    }
    .stButton>button:hover {
        border-color: #6C5CE7;
        color: #6C5CE7;
    }
    .stChatMessage {
        background-color: #FFFFFF;
        border-radius: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNEXION IA ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    # On reste sur le modèle Flash
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    # C'est ici qu'on demande à voir la vraie erreur
    st.error(f"ERREUR TECHNIQUE DÉTAILLÉE : {e}")

# --- 3. FONCTIONS UTILITAIRES ---
def extract_text_from_pdf(uploaded_files):
    text = ""
    for pdf in uploaded_files:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
    return text

def ask_gemini(prompt):
    """Fonction pour envoyer une demande à l'IA"""
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erreur : {e}"

# --- 4. SIDEBAR (LE CARTABLE) ---
with st.sidebar:
    st.header("🎒 Mon Cartable")
    matiere = st.selectbox("Matière", ["Finance", "Stats", "Droit", "Biologie", "Autre"])
    
    st.divider()
    st.caption("Documents du cours")
    uploaded_files = st.file_uploader("Déposez vos PDF ici", accept_multiple_files=True, type=['pdf'])
    
    # Bouton d'analyse (Essentiel pour charger le texte en mémoire)
    if uploaded_files:
        if st.button("🔄 Analyser les documents", type="primary"):
            with st.spinner("Lecture en cours..."):
                raw_text = extract_text_from_pdf(uploaded_files)
                st.session_state['context'] = raw_text
                st.success("Documents mémorisés !")
    
    # Indicateur d'état
    if 'context' in st.session_state:
        st.info("✅ Mémoire active : L'IA connait votre cours.")
    else:
        st.warning("⚠️ Aucun cours en mémoire.")

# --- 5. ZONE PRINCIPALE ---
st.title(f"Tutorat : {matiere}")

# Les 3 Onglets magiques
tab_chat, tab_outils, tab_quiz = st.tabs(["💬 Discussion", "📝 Synthèses & Outils", "🧠 Quiz & Entraînement"])

# === ONGLET 1 : CHAT ===
with tab_chat:
    # Historique
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Zone de saisie
    if user_input := st.chat_input("Posez une question sur le cours..."):
        # Afficher message utilisateur
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        # Réponse IA
        context = st.session_state.get('context', '')
        full_prompt = f"Tu es un tuteur en {matiere}. Basé sur ce cours : {context}. Réponds à : {user_input}"
        
        with st.chat_message("assistant"):
            with st.spinner("Réflexion..."):
                response = ask_gemini(full_prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# === ONGLET 2 : SYNTHÈSES ===
with tab_outils:
    st.subheader("Générateurs Automatiques")
    col1, col2 = st.columns(2)
    
    # Outil 1 : Résumé
    with col1:
        with st.container(border=True):
            st.write("### 📄 Synthèse de cours")
            st.caption("Génère un résumé structuré du PDF chargé.")
            if st.button("Générer la synthèse"):
                if 'context' in st.session_state:
                    with st.spinner("Rédaction en cours..."):
                        prompt_resume = f"Fais une synthèse structurée et pédagogique de ce cours : {st.session_state['context']}"
                        resume = ask_gemini(prompt_resume)
                        st.markdown(resume)
                else:
                    st.error("Veuillez d'abord analyser un document (Menu de gauche).")

    # Outil 2 : Flashcards
    with col2:
        with st.container(border=True):
            st.write("### 📇 Créer des Flashcards")
            st.caption("Extrait 5 concepts clés avec définitions.")
            if st.button("Générer les cartes"):
                if 'context' in st.session_state:
                    with st.spinner("Extraction des concepts..."):
                        prompt_flash = f"Extrait 5 concepts clés de ce cours : {st.session_state['context']}. Format : Concept - Définition courte."
                        cards = ask_gemini(prompt_flash)
                        st.info(cards)
                else:
                    st.error("Document manquant.")

# === ONGLET 3 : QUIZ ===
with tab_quiz:
    st.subheader("Testez vos connaissances")
    with st.container(border=True):
        difficulte = st.select_slider("Niveau", options=["Facile", "Moyen", "Difficile"])
        if st.button("Générer un Quiz"):
             if 'context' in st.session_state:
                with st.spinner(f"Création du quiz {difficulte}..."):
                    prompt_quiz = f"Génère un quiz de 3 questions (Niveau {difficulte}) basé sur ce cours : {st.session_state['context']}. Donne les réponses à la toute fin (cachées)."
                    quiz = ask_gemini(prompt_quiz)
                    st.markdown(quiz)
             else:
                st.error("Chargez un document d'abord.")
