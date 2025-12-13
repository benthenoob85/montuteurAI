import streamlit as st
import google.generativeai as genai

st.title("🔍 Diagnostic Technique")

# 1. Vérification de la configuration
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    # On affiche juste le début pour être sûr qu'elle est lue
    st.write(f"Clé API lue : `{api_key[:8]}...`")
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Problème de lecture des secrets : {e}")
    st.stop()

# 2. Interrogation des modèles
st.write("Demande de la liste des modèles à Google...")

try:
    available_models = []
    # On demande la liste brute
    for m in genai.list_models():
        # On ne garde que ceux qui servent à générer du texte (chat)
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)

    if available_models:
        st.success("✅ VICTOIRE ! Voici les modèles exacts acceptés par votre clé :")
        # On affiche la liste pour que vous puissiez la copier
        st.code(available_models)
    else:
        st.warning("⚠️ La connexion fonctionne, mais aucun modèle n'est retourné. La clé est peut-être restreinte géographiquement.")

except Exception as e:
    st.error(f"❌ Erreur de connexion fatale : {e}")
