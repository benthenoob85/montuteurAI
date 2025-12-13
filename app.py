import streamlit as st
import google.generativeai as genai

st.title("🕵️ Détective des Modèles Google")

# 1. Vérification de la clé
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
    st.success(f"✅ Clé API détectée (début: {api_key[:5]}...)")
else:
    st.error("❌ Aucune clé API trouvée dans les secrets.")
    st.stop()

# 2. Interrogation de Google
st.write("Je demande la liste officielle à Google...")

try:
    found_any = False
    # On parcourt tous les modèles disponibles
    for m in genai.list_models():
        # On ne garde que ceux qui savent écrire du texte (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            found_any = True
            with st.expander(f"✅ Modèle disponible : {m.name}"):
                st.code(m.name)
                st.write(f"**Description :** {m.description}")
                st.write(f"**Version :** {m.version}")

    if not found_any:
        st.warning("⚠️ Aucun modèle de texte trouvé. Votre clé API est peut-être restreinte ou la librairie est trop ancienne.")

except Exception as e:
    st.error(f"Erreur critique : {e}")
    st.info("💡 Conseil : Si vous voyez une erreur 'AttributeError', c'est que votre fichier requirements.txt utilise une version trop vieille de google-generativeai.")
