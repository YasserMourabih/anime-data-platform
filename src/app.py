# src/app.py (Version optimisée)
import streamlit as st
import json
import os

# --- CONFIG ---
st.set_page_config(page_title="Anime Recommender Lite", page_icon="⚡")
JSON_PATH = os.path.join(os.path.dirname(__file__), '../data/recommendations.json')

@st.cache_data
def load_recommendations():
    with open(JSON_PATH, 'r') as f:
        return json.load(f)

st.title("⚡ Anime Recommender (Fast Version)")

try:
    recos_dict = load_recommendations()
    all_titles = sorted(recos_dict.keys())
    
    selected_anime = st.selectbox("Tu as aimé :", all_titles)

    if st.button("Trouver des recommandations"):
        if selected_anime in recos_dict:
            st.success(f"Recommandations pour **{selected_anime}** :")
            for reco_title, score in recos_dict[selected_anime][:10]: # On affiche les top 10
                st.write(f"**{reco_title}** ({int(score*100)}% similarité)")
                st.progress(score)
        else:
            st.error("Anime non trouvé dans la base pré-calculée.")

except FileNotFoundError:
    st.error("⚠️ Fichier de recommandations introuvable. Assurez-vous d'avoir lancé le script de pré-calcul.")