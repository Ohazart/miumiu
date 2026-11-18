# Miumiu — Audio Translator 🎧

Application web locale qui **transcrit** un fichier audio (MP3, WAV, M4A, OGG, FLAC, WebM) grâce à Whisper, puis **traduit** le texte dans la langue de votre choix.

## Fonctionnalités

- Transcription automatique via `faster-whisper` (modèle Whisper, CPU)
- Détection automatique de la langue source
- Traduction dans 12 langues cibles (français, anglais, espagnol, allemand, etc.) avec repli Google Translate → MyMemory
- Interface web en français : glisser-déposer, file d'attente visuelle, résultats transcription + traduction
- Limites : 200 Mo par fichier, format MP3/WAV/M4A/OGG/FLAC/WebM

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

```bash
python app.py
```

Puis ouvrez http://127.0.0.1:5000 dans votre navigateur et déposez un fichier audio.

### Options

- `WHISPER_MODEL` : taille du modèle Whisper, `tiny` par défaut (`base`, `small`, `medium`, `large-v3`…). Un modèle plus grand = meilleure précision, traitement plus lent.
- `SECRET_KEY` : clé de session Flask (générée aléatoirement si absente).

```bash
WHISPER_MODEL=base python app.py
```

## Architecture

- `app.py` — serveur Flask (écoute sur 127.0.0.1 uniquement) : upload, transcription, traduction, API JSON
- `templates/index.html` — interface utilisateur
- `requirements.txt` — dépendances

## Notes

- La traduction nécessite un accès internet ; si le service est indisponible, la transcription seule est retournée.
- Pour dépasser 200 Mo, modifiez `MAX_CONTENT_LENGTH` dans `app.py`.
- Le premier lancement télécharge le modèle Whisper (~75 Mo pour `tiny`).
