# 📰 Page2Markdown

Page2Markdown est une application **Streamlit** qui permet d’extraire, convertir et télécharger le contenu d’articles web en **Markdown**, **PDF** ou **TXT**.  
Elle respecte par défaut le fichier `robots.txt` des sites et détecte les paywalls (désactivables dans les options).

---

## 🚀 Fonctionnalités

- Extraction d’articles depuis une **URL**.
- Respect de `robots.txt` (désactivable).
- Détection automatique de paywalls (désactivable).
- Support du **rendu JavaScript** via Selenium/ChromeDriver (optionnel).
- Conversion et export en plusieurs formats :
  - **Markdown** (`.md`)
  - **PDF** (`.pdf`)
  - **Texte brut** (`.txt`)
- Affichage du contenu dans plusieurs onglets :
  - Article formaté
  - Markdown brut
  - Métadonnées (JSON)
  - Source HTML (aperçu)
- Bouton pour réinitialiser le cache et la session.

---

## 📋 Prérequis

Avant de commencer, assurez-vous d'avoir installé :
- **Git** pour cloner le projet.
- **Python** 3.8 ou supérieur.

---

## 📦 Installation

Suivez ces étapes pour lancer le projet en local.

```bash
# 1. Cloner le projet
git clone https://github.com/votre-pseudo/page2markdown.git
cd page2markdown

# 2. Créer un environnement virtuel (recommandé)
# Pour macOS/Linux
python3 -m venv venv
source venv/bin/activate
# Pour Windows
python -m venv venv
venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt
```

### 📝 requirements.txt
```
streamlit
trafilatura
requests
fpdf2
beautifulsoup4
selenium
webdriver-manager
```

---

## ▶️ Utilisation

Lancez l’application avec la commande :

```bash
streamlit run app.py
```

Une interface web sera disponible dans votre navigateur (par défaut sur [http://localhost:8501](http://localhost:8501)).

---

## ⚙️ Options disponibles

Depuis la barre latérale, vous pouvez configurer l'extraction :

- **Activer le rendu JavaScript** : à utiliser si un article n'apparaît pas ou est incomplet.  
- **Ignorer robots.txt** : contourne les restrictions d'indexation (⚠️ à utiliser avec prudence).  
- **Ignorer la détection de paywall** : utile pour extraire le contenu avant un mur payant (inefficace contre les paywalls "durs").  
- **Purger le cache et la session** : réinitialise complètement l'application.

---

## 🔧 Notes techniques

- L’application utilise **Trafilatura** pour l’extraction du contenu principal.  
- La génération **PDF** est assurée par **fpdf2** avec un en-tête et un pied de page personnalisés.  
- **BeautifulSoup4** est utilisé pour le parsing HTML et l'extraction de métadonnées.  
- **Selenium + ChromeDriverManager** permettent le rendu JavaScript (si activé).  
- Les résultats sont mis en cache grâce aux décorateurs `st.cache_data` et `st.cache_resource`.  

---

## ⚠️ Limites connues

- **Images et multimédia** : seuls les contenus textuels sont extraits (pas d’images, vidéos, etc.).  
- **Mise en forme PDF** : le texte est "sanitisé" avant conversion en PDF, ce qui supprime le formatage avancé (gras, italique, listes).  

---

## 📜 Licence

Ce projet est distribué sous licence **MIT**.  
Vous pouvez l’utiliser, le modifier et le redistribuer librement.
