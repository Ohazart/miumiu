# Chat Mistral — app web minimale

Petite application web de chat qui appelle l'**API Mistral** avec le **SDK
TypeScript officiel** (`@mistralai/mistralai`), modèle **`mistral-small-latest`**.

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
