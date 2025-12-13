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
    # On récupère la clé
    if "GOOGLE_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    else:
        st.error("Clé API manquante dans les secrets.")
        st.stop()
    
    # LE COEUR DU REACTEUR : On utilise le modèle puissant que vous avez validé
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
    """Fonction pour envoyer une demande à l'IA"""
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
    
    # Bouton d'analyse (Essentiel pour charger le texte en mémoire)
    if uploaded_files:
        if st.button("🔄 Analyser les documents", type="primary"):
            with st.spinner("Lecture en cours avec Gemini 2.5..."):
                raw_text = extract_text_from_pdf(uploaded_files)
                if raw_text:
                    st.session_state['context'] = raw_text
                    st.success("✅ Documents mémorisés !")
                else:
                    st.warning("Je n'ai trouvé aucun texte lisible dans ce PDF.")
    
    # Indicateur d'état
    if 'context' in st.session_state:
        st.info("🧠 Mémoire active")
    else:
        st.warning("⚠️ Aucun cours en mémoire")

# --- 5. ZONE PRINCIPALE ---
st.title(f"Tutorat : {matiere}")

# Les 3 Onglets
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
        # On crée un prompt intelligent
        full_prompt = f"""
        Agis comme un tuteur expert et pédagogue.
        
        CONTEXTE (Le cours de l'étudiant) :
        {context}
        
        QUESTION DE L'ÉTUDIANT :
        {user_input}
        
        Réponds de manière claire, structure ta réponse. Si la réponse n'est pas dans le cours, dis-le poliment.
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
    
   with col2:
        with st.container(border=True):
            st.write("### 📇 Flashcards")
            st.caption("Cliquez sur une question pour voir la réponse.")
            
            if st.button("Générer 5 cartes"):
                if 'context' in st.session_state:
                    with st.spinner("Création des cartes cache-cache..."):
                        # On demande un format strict à l'IA pour pouvoir séparer Q et R
                        prompt_flash = (
                            f"Extrait 5 concepts clés de ce cours : {st.session_state['context']}. "
                            "Format impératif : sur chaque ligne, écris 'QUESTION ; RÉPONSE' "
                            "(utilise un point-virgule pour séparer). Pas de gras, pas de liste à puces, juste le texte."
                        )
                        cards_text = ask_gemini(prompt_flash)
                        
                        # On découpe le texte reçu pour créer les menus déroulants
                        for line in cards_text.split('\n'):
                            if ";" in line:
                                try:
                                    parts = line.split(";", 1) # On coupe au premier point-virgule
                                    question = parts[0].strip()
                                    reponse = parts[1].strip()
                                    
                                    # C'est ici que la magie opère : st.expander cache le contenu
                                    with st.expander(f"❓ {question}"):
                                        st.write(f"💡 {reponse}")
                                except:
                                    continue # Si une ligne bug, on l'ignore
                else:
                    st.error("Chargez un document d'abord.")

    with col2:
        with st.container(border=True):
            st.write("### 📇 Flashcards")
            if st.button("Générer 5 cartes"):
                if 'context' in st.session_state:
                    with st.spinner("Création..."):
                        prompt_flash = f"Crée 5 flashcards (Question / Réponse cachée) basées sur les définitions importantes de ce texte : {st.session_state['context']}"
                        cards = ask_gemini(prompt_flash)
                        st.markdown(cards)
                else:
                    st.error("Chargez un document d'abord.")

# === ONGLET 3 : QUIZ ===
with tab_quiz:
    st.subheader("Testez vos connaissances")
    if st.button("Lancer un Quiz (3 questions)"):
         if 'context' in st.session_state:
            with st.spinner("Génération du quiz..."):
                prompt_quiz = f"Génère un quiz QCM de 3 questions basé sur ce texte : {st.session_state['context']}. Affiche la correction à la fin uniquement."
                quiz = ask_gemini(prompt_quiz)
                st.markdown(quiz)
         else:
            st.error("Chargez un document d'abord.")
