# src/app.py (Version optimisée)
import streamlit as st
import json
import os

# --- CONFIG ---
st.set_page_config(page_title="Anime Recommender Lite", page_icon="⚡")
JSON_PATH = os.path.join(os.path.dirname(__file__), '../data/recommendations.json')

@st.cache_data
def load_recommendations():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

st.title("Anime Recommender (Fast Version)")

# Bouton pour vider le cache
if st.sidebar.button("🔄 Recharger les données"):
    st.cache_data.clear()
    st.rerun()

try:
    recos_dict = load_recommendations()
    all_titles = sorted(recos_dict.keys())
    
    st.info(f"📚 {len(recos_dict):,} animes disponibles")
    
    selected_anime = st.selectbox("Tu as aimé :", all_titles)
    
    # Afficher le nombre de recommandations disponibles
    if selected_anime in recos_dict:
        nb_recos = len(recos_dict[selected_anime])
        st.caption(f"{nb_recos} recommandations disponibles")

    if st.button("🔍 Trouver des recommandations"):
        if selected_anime in recos_dict:
            recommendations = recos_dict[selected_anime]
            
            if recommendations:
                st.success(f"**Recommandations pour {selected_anime}** ({len(recommendations)} trouvées) :")
                
                for i, (reco_title, score) in enumerate(recommendations[:10], 1):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{i}. {reco_title}**")
                    with col2:
                        st.write(f"🎯 {int(score*100)}%")
                    st.progress(score)
            else:
                st.warning(f"⚠️ Aucune recommandation trouvée pour **{selected_anime}**")
        else:
            st.error("❌ Anime non trouvé dans la base pré-calculée.")

except FileNotFoundError:
    st.error("⚠️ Fichier de recommandations introuvable. Assurez-vous d'avoir lancé le script de pré-calcul.")
except Exception as e:
    st.error(f"❌ Erreur lors du chargement des recommandations : {e}")