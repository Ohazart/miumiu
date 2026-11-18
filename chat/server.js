import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Mistral } from "@mistralai/mistralai";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MODEL = "mistral-small-latest";
const PORT = process.env.PORT || 3000;

const client = process.env.MISTRAL_API_KEY
  ? new Mistral({ apiKey: process.env.MISTRAL_API_KEY })
  : null;

const TRANSCRIBE_MODEL = "voxtral-mini-transcribe-3";

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && (req.url === "/" || req.url === "/index.html" || req.url === "/audio")) {
    try {
      const html = await readFile(
        path.join(__dirname, "public", req.url === "/audio" ? "audio.html" : "index.html"),
        "utf8"
      );
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(html);
    } catch {
      res.writeHead(500);
      res.end("Erreur interne du serveur.");
    }
    return;
  }

  if (req.method === "POST" && req.url === "/api/chat") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1_000_000) req.destroy();
    });
    req.on("end", async () => {
      let messages;
      try {
        const parsed = JSON.parse(body);
        if (!Array.isArray(parsed.messages)) throw new Error("messages manquants");
        messages = parsed.messages
          .filter((m) => m && typeof m.role === "string" && typeof m.content === "string")
          .map((m) => ({ role: m.role, content: m.content }));
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Requête invalide." }));
        return;
      }

      try {
        if (!client) {
          res.writeHead(503, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: "MISTRAL_API_KEY n'est pas configurée sur le serveur." }));
          return;
        }
        const response = await client.chat.complete({
          model: MODEL,
          messages,
        });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ reply: response.choices[0]?.message?.content ?? "" }));
      } catch (err) {
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Échec de l'appel à l'API Mistral." }));
        console.error(err);
      }
    });
    return;
  }

  if (req.method === "POST" && req.url === "/api/transcribe") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > 40_000_000) req.destroy();
    });
    req.on("end", async () => {
      let audioBase64, fileName, language, translateTo;
      try {
        const parsed = JSON.parse(body);
        if (typeof parsed.audioBase64 !== "string" || !parsed.audioBase64) throw new Error();
        audioBase64 = parsed.audioBase64;
        fileName = typeof parsed.fileName === "string" ? parsed.fileName : "audio.mp3";
        language = typeof parsed.language === "string" && parsed.language ? parsed.language : undefined;
        translateTo = typeof parsed.translateTo === "string" ? parsed.translateTo : undefined;
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Requête invalide." }));
        return;
      }

      if (!client) {
        res.writeHead(503, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "MISTRAL_API_KEY n'est pas configurée sur le serveur." }));
        return;
      }

      try {
        const buffer = Buffer.from(audioBase64, "base64");
        const transcription = await client.audio.transcriptions.complete({
          model: TRANSCRIBE_MODEL,
          file: { fileName, content: buffer },
          ...(language ? { language } : {}),
        });
        const text = typeof transcription.text === "string" ? transcription.text : "";
        let translation;
        if (translateTo) {
          const response = await client.chat.complete({
            model: MODEL,
            messages: [
              {
                role: "user",
                content: `Traduis le transcript suivant en ${translateTo}. Réponds uniquement avec la traduction, sans commentaire.

${text}`,
              },
            ],
          });
          translation = response.choices[0]?.message?.content ?? "";
        }
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ text, translation }));
      } catch (err) {
        console.error(err);
        res.writeHead(502, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Échec de la transcription ou de la traduction." }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end("Introuvable.");
});

server.listen(PORT, () => {
  console.log(`Serveur de chat Mistral sur http://localhost:${PORT} (modèle : ${MODEL})`);
});
