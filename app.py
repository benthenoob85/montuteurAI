import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Mon Tuteur IA", layout="wide", page_icon="🎓")

# CSS Personnalisé
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
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        st.error("Clé API manquante dans les secrets.")
        st.stop()
    
    # Modèle validé ensemble (Rapide et Gratuit)
    model = genai.GenerativeModel('gemini-2.5-flash')

except Exception as e:
    st.error(f"Erreur de connexion : {e}")

# --- 3. FONCTIONS UTILITAIRES ---
def extract_text_from_pdf(uploaded_files):
    text = ""
    for pdf in uploaded_files:
        try:
            pdf_reader = PdfReader(pdf)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        except:
            st.warning(f"Impossible de lire {pdf.name}")
    return text

def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erreur de l'IA : {e}"

# --- 4. SIDEBAR (LE CARTABLE) ---
with st.sidebar:
    st.header("🎒 Mon Cartable")
    matiere = st.selectbox("Matière", ["Finance", "Stats", "Droit", "Biologie", "Autre"])
    
    st.divider()
    st.caption("Documents du cours")
    uploaded_files = st.file_uploader("Déposez vos PDF ici", accept_multiple_files=True, type=['pdf'])
    
    if uploaded_files:
        if st.button("🔄 Analyser les documents", type="primary"):
            with st.spinner("Lecture en cours avec Gemini 2.5..."):
                raw_text = extract_text_from_pdf(uploaded_files)
                if raw_text:
                    st.session_state['context'] = raw_text
                    st.success("✅ Documents mémorisés !")
                else:
                    st.warning("Je n'ai trouvé aucun texte lisible.")
    
    if 'context' in st.session_state:
        st.info("🧠 Mémoire active")
    else:
        st.warning("⚠️ Aucun cours en mémoire")

# --- 5. ZONE PRINCIPALE ---
st.title(f"Tutorat : {matiere}")

tab_chat, tab_outils, tab_quiz = st.tabs(["💬 Discussion", "📝 Synthèses & Outils", "🧠 Quiz & Entraînement"])

# === ONGLET 1 : CHAT ===
with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Posez une question sur le cours..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        context = st.session_state.get('context', '')
        full_prompt = f"""
        Agis comme un tuteur expert et pédagogue.
        CONTEXTE : {context}
        QUESTION : {user_input}
        Réponds de manière claire et structurée.
        """
        
        with st.chat_message("assistant"):
            with st.spinner("Réflexion..."):
                response = ask_gemini(full_prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# === ONGLET 2 : SYNTHÈSES ===
with tab_outils:
    st.subheader("Outils d'étude")
    col1, col2 = st.columns(2)
    
    # Outil Résumé
    with col1:
        with st.container(border=True):
            st.write("### 📄 Synthèse de cours")
            if st.button("Générer le résumé"):
                if 'context' in st.session_state:
                    with st.spinner("Rédaction..."):
                        prompt_resume = f"Fais une synthèse structurée de ce texte : {st.session_state['context']}"
                        resume = ask_gemini(prompt_resume)
                        st.markdown(resume)
                else:
                    st.error("Chargez un document d'abord.")

    # Outil Flashcards (Correction de l'erreur ici)
    with col2:
        with st.container(border=True):
            st.write("### 📇 Flashcards")
            st.caption("Cliquez sur une question pour voir la réponse.")
            
            if st.button("Générer 5 cartes"):
                if 'context' in st.session_state:
                    with st.spinner("Création des cartes..."):
                        prompt_flash = (
                            f"Extrait 5 concepts clés de ce cours : {st.session_state['context']}. "
                            "Format impératif : sur chaque ligne, écris 'QUESTION ; RÉPONSE' "
                            "(utilise un point-virgule pour séparer). Pas de gras, pas de liste."
                        )
                        cards_text = ask_gemini(prompt_flash)
                        
                        # Logique d'affichage déroulant
                        for line in cards_text.split('\n'):
                            if ";" in line:
                                try:
                                    parts = line.split(";", 1)
                                    q = parts[0].strip()
                                    r = parts[1].strip()
                                    with st.expander(f"❓ {q}"):
                                        st.write(f"💡 {r}")
                                except:
                                    continue
                else:
                    st.error("Chargez un document d'abord.")

# === ONGLET 3 : QUIZ ===
with tab_quiz:
    st.subheader("Testez vos connaissances")
    if st.button("Lancer un Quiz (3 questions)"):
         if 'context' in st.session_state:
            with st.spinner("Génération du quiz..."):
                prompt_quiz = f"Génère un quiz QCM de 3 questions sur : {st.session_state['context']}. Correction à la fin."
                quiz = ask_gemini(prompt_quiz)
                st.markdown(quiz)
         else:
            st.error("Chargez un document d'abord.")
