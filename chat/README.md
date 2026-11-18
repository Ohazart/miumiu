# Chat & audio Mistral — app web minimale

Petite application web qui appelle l'**API Mistral** avec le **SDK
TypeScript officiel** (`@mistralai/mistralai`) :

- **Chat** (`/`) : modèle **`mistral-small-latest`**.
- **Transcription & traduction audio** (`/audio`) : upload d'un fichier
  audio (MP3…) transcrit par **`voxtral-mini-transcribe-3`**, puis traduit
  par `mistral-small-latest` dans la langue de votre choix.

La clé `MISTRAL_API_KEY` reste **côté serveur** : le navigateur ne parle jamais
directement à l'API Mistral, il passe par la route `POST /api/chat`.

## Installation

```bash
cd chat
npm install
```

## Configuration

Définissez la variable d'environnement `MISTRAL_API_KEY` (ne la committez jamais) :

```bash
export MISTRAL_API_KEY="votre_cle_api"
```

## Exécution locale

```bash
npm start
```

Puis ouvrez [http://localhost:3000](http://localhost:3000).

## Structure

- `server.js` — serveur Node (sans dépendance autre que le SDK) : sert
  l'interface et expose `POST /api/chat`, qui appelle `mistral-small-latest`.
- `public/index.html` — interface de chat (HTML/CSS/JS, sans build).
- `.env.example` — exemple de variable d'environnement.

## Déploiement Mistral Apps (accessible en continu)

L'app est définie comme une Mistral App (`mistral.json` à la racine du dépôt,
module `chat`, image `chat/Dockerfile`). Pour la déployer :

```bash
mistral login            # ou : mistral login --api-key
mistral deploy            # construit le commit poussé et déploie en production
```

Une fois l'app créée, définissez `MISTRAL_API_KEY` dans l'onglet **Secrets**
de l'app dans Studio (module `chat`) : la CLI n'upload jamais le `.env` local.
L'app est alors servie en continu sur son URL publique.
