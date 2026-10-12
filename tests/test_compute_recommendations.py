"""Tests des fonctions de préparation textuelle du pipeline de recommandation."""

import pytest

from src.compute_recommendations import clean_html, extract_franchise_name


class TestCleanHtml:
    """Nettoyage des synopsis AniList, qui arrivent balisés en HTML."""

    def test_supprime_les_balises(self):
        assert clean_html("<p>Un <b>héros</b> caché.</p>") == "Un héros caché."

    def test_remplace_les_balises_par_une_espace(self):
        """Un <br> ne doit pas coller deux mots : cela créerait un faux token."""
        assert clean_html("Première phrase.<br>Seconde phrase.") == (
            "Première phrase. Seconde phrase."
        )

    def test_normalise_les_espaces_multiples(self):
        assert clean_html("trop    d'espaces\n\tici") == "trop d'espaces ici"

    @pytest.mark.parametrize("valeur_vide", ["", None])
    def test_tolere_les_valeurs_vides(self, valeur_vide):
        """Le champ description est nullable côté AniList."""
        assert clean_html(valeur_vide) == ""


class TestExtractFranchiseName:
    """
    Normalisation des titres en nom de franchise.

    Cette fonction conditionne le filtre anti-franchise : si elle échoue,
    les recommandations se remplissent de suites et de spin-offs.
    """

    @pytest.mark.parametrize(
        "titre, franchise_attendue",
        [
            ("Naruto: Shippuden", "naruto"),
            ("Attack on Titan Season 2", "attack on titan"),
            ("One Piece Film: Red", "one piece"),
            ("Fullmetal Alchemist: Brotherhood", "fullmetal alchemist"),
            ("Code Geass: Hangyaku no Lelouch R2", "code geass"),
            ("Mob Psycho 100 II", "mob psycho 100"),
        ],
    )
    def test_supprime_les_suffixes_de_declinaison(self, titre, franchise_attendue):
        assert extract_franchise_name(titre) == franchise_attendue

    @pytest.mark.parametrize("titre_simple", ["Clannad", "Bleach", "Monster"])
    def test_preserve_les_titres_sans_suffixe(self, titre_simple):
        assert extract_franchise_name(titre_simple) == titre_simple.lower()

    def test_regroupe_les_declinaisons_d_une_meme_franchise(self):
        """Propriété réellement utilisée par le filtre anti-franchise."""
        declinaisons = [
            "Attack on Titan",
            "Attack on Titan Season 2",
            "Attack on Titan: Final Season",
            "Attack on Titan OVA",
        ]
        franchises = {extract_franchise_name(titre) for titre in declinaisons}
        assert franchises == {"attack on titan"}

    def test_tolere_un_titre_vide(self):
        assert extract_franchise_name("") == ""
