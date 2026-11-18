import os
import tempfile
import uuid

import ctranslate2
from deep_translator import GoogleTranslator, MyMemoryTranslator
from flask import Flask, jsonify, render_template, request, session
from faster_whisper import WhisperModel

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.secret_key = os.environ.get("SECRET_KEY", uuid.uuid4().hex)

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "tiny")
DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
_languages_cache = None
_model = None
_translators = {}


def resolve_device():
    if DEVICE != "auto":
        return DEVICE
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def get_model():
    global _model
    if _model is None:
        device = resolve_device()
        compute_type = "int8" if device == "cpu" else "float16"
        _model = WhisperModel(MODEL_SIZE, device=device, compute_type=compute_type)
        print(f"Whisper '{MODEL_SIZE}' chargé sur {device} (compute_type={compute_type})")
    return _model


def get_translator(lang):
    if lang not in _translators:
        _translators[lang] = (
            GoogleTranslator(source="auto", target=lang),
            MyMemoryTranslator(
                source="english",
                target=MYMEMORY_LANG_NAMES[lang],
            ),
        )
    return _translators[lang]


LANGUAGES = {
    "fr": "Français",
    "en": "Anglais",
    "es": "Espagnol",
    "de": "Allemand",
    "it": "Italien",
    "pt": "Portugais",
    "ar": "Arabe",
    "nl": "Néerlandais",
    "ru": "Russe",
    "ja": "Japonais",
    "zh-CN": "Chinois (simplifié)",
    "tr": "Turc",
}

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}

MYMEMORY_LANG_NAMES = {
    "fr": "french",
    "en": "english",
    "es": "spanish",
    "de": "german",
    "it": "italian",
    "pt": "portuguese",
    "ar": "arabic",
    "nl": "dutch",
    "ru": "russian",
    "ja": "japanese",
    "zh-CN": "chinese simplified",
    "tr": "turkish",
}


@app.route("/")
def index():
    return render_template("index.html", languages=LANGUAGES)


@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "Aucun fichier reçu."}), 400

    file = request.files["audio"]
    if not file.filename:
        return jsonify({"error": "Aucun fichier sélectionné."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Format non supporté : {ext}"}), 400

    target_lang = request.form.get("target_lang", "fr")
    if target_lang not in LANGUAGES:
        return jsonify({"error": "Langue cible inconnue."}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        file.save(tmp.name)
        audio_path = tmp.name

    try:
        model = get_model()
        segments, info = model.transcribe(audio_path, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()

        result = {
            "detected_lang": info.language,
            "language_probability": round(info.language_probability, 2),
            "duration": round(info.duration, 1),
            "transcription": text,
            "target_lang": target_lang,
        }

        if not text:
            result["translation"] = ""
            return jsonify(result)

        translation = None
        try:
            translators = get_translator(target_lang)
        except Exception:
            translators = ()
        for translator in translators:
            try:
                translation = translator.translate(text)
                if translation:
                    break
            except Exception:
                continue

        if translation:
            result["translation"] = translation
        else:
            result["translation"] = ""
            result["translation_error"] = (
                "Traduction en ligne indisponible. "
                "Seule la transcription est disponible."
            )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": f"Échec du traitement audio : {exc}"}), 500
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
