import streamlit as st

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Mon Tuteur IA",
    layout="wide",
    page_icon="🎓"
)

# --- STYLE CSS (Pour le look épuré) ---
st.markdown("""
<style>
    .stButton>button {
        border-radius: 20px;
        background-color: #F0F2F6;
        color: #333;
        border: none;
    }
    .stButton>button:hover {
        background-color: #E0E2E6;
        color: #000;
    }
    .stChatMessage {
        border-radius: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- BARRE LATÉRALE (BIBLIOTHÈQUE) ---
with st.sidebar:
    st.header("📚 Bibliothèque")
    
    # Sélecteur de matière
    matiere = st.selectbox(
        "Matière actuelle",
        ["Finance", "Statistiques", "Droit", "Gestion de projet", "Autre"]
    )
    
    st.divider()
    
    # Upload de fichiers
    st.caption("Ajouter des documents")
    uploaded_files = st.file_uploader(
        "PDF, Excel, Word",
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        st.success(f"{len(uploaded_files)} document(s) chargé(s)")

# --- ZONE PRINCIPALE ---
st.title(f"Tutorat : {matiere}")

# Les Onglets
tab1, tab2, tab3 = st.tabs(["💬 Discussion", "📝 Synthèses & Fiches", "🧠 Exercices"])

# ONGLET 1 : CHAT
with tab1:
    st.info("👋 Bonjour ! Je suis prêt à analyser vos cours. Posez une question ci-dessous.")
    
    # Zone de chat fictive pour l'instant
    chat_container = st.container()
    with chat_container:
        with st.chat_message("user"):
            st.write("Ceci est un test d'affichage.")
        with st.chat_message("assistant"):
            st.write("L'interface fonctionne parfaitement. Nous connecterons mon cerveau à l'étape suivante !")
            
    st.chat_input("Votre message...")

# ONGLET 2 : SYNTHÈSES
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.write("### Résumer le cours")
        st.button("📄 Générer une synthèse")
    with col2:
        st.write("### Flashcards")
        st.button("📇 Créer des cartes de révision")

# ONGLET 3 : EXERCICES
with tab3:
    st.write("### Générateur de Quiz")
    st.radio("Niveau", ["Débutant", "Intermédiaire", "Expert"])
    st.button("Lancer un test")
