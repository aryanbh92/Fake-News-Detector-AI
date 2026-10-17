"""Sentence-level claim classification using Hugging Face Inference Providers."""

import json
import math
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request
from langdetect import LangDetectException, detect


app = Flask(__name__)
MODEL_ID = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
MODEL_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_ID}"
MAX_TEXT_LENGTH = 12_000
MAX_SENTENCES = 12
REQUEST_TIMEOUT_SECONDS = 45
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
CANDIDATE_LABELS = [
    "a verifiable factual claim",
    "an opinion or personal interpretation",
    "a question or other non-claim",
]


class InferenceFailure(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def split_sentences(text):
    """Split pasted text into non-empty sentence-sized inputs."""
    return [sentence.strip() for sentence in SENTENCE_SPLIT.split(text.strip()) if sentence.strip()]


def classify_sentence(sentence, token, timeout_seconds):
    """Return the model's top label and score for one sentence."""
    payload = {
        "inputs": sentence,
        "parameters": {
            "candidate_labels": CANDIDATE_LABELS,
            "hypothesis_template": "This text is {}.",
            "multi_label": False,
        },
    }
    model_request = Request(
        MODEL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(model_request, timeout=timeout_seconds) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise InferenceFailure(
                "Hugging Face rejected the token. Create a token with Inference Providers permission.",
                503,
            ) from None
        if error.code == 429:
            raise InferenceFailure("Hugging Face rate limit reached. Wait a moment and try again.", 429) from None
        if error.code == 503:
            raise InferenceFailure("The Hugging Face model is loading or unavailable. Please retry shortly.", 503) from None
        raise InferenceFailure(f"Hugging Face inference failed (HTTP {error.code}).") from None
    except (TimeoutError, URLError, OSError):
        raise InferenceFailure("Could not reach Hugging Face before the request timed out.", 504) from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise InferenceFailure("Hugging Face returned an unreadable response.") from None

    if isinstance(result, list) and len(result) == 1:
        result = result[0]
    if not isinstance(result, dict):
        raise InferenceFailure("Hugging Face returned an unexpected response format.")

    labels = result.get("labels")
    scores = result.get("scores")
    if not isinstance(labels, list) or not isinstance(scores, list) or len(labels) != len(scores) or not labels:
        raise InferenceFailure("Hugging Face returned an incomplete classification.")

    try:
        ranked = [
            (str(label), float(score))
            for label, score in zip(labels, scores)
            if math.isfinite(float(score)) and 0 <= float(score) <= 1
        ]
    except (TypeError, ValueError):
        raise InferenceFailure("Hugging Face returned invalid confidence scores.") from None
    if len(ranked) != len(labels):
        raise InferenceFailure("Hugging Face returned invalid confidence scores.")

    label, score = max(ranked, key=lambda item: item[1])
    claim_score = next(
        (score for candidate, score in ranked if candidate == CANDIDATE_LABELS[0]),
        None,
    )
    if claim_score is None:
        raise InferenceFailure("Hugging Face returned labels that do not match the requested classification.")
    return {
        "text": sentence,
        "label": "claim" if label == CANDIDATE_LABELS[0] else "context",
        "category": label,
        "score": round(score, 3),
        "claim_score": round(claim_score, 3),
        "signals": [],
    }


@app.post("/api/analyze")
def analyze():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Send a JSON object containing article text."}), 400

    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "Add article text before requesting an analysis."}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text must be no longer than {MAX_TEXT_LENGTH:,} characters."}), 413

    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        return jsonify({"error": "HF_TOKEN is missing. Set it in the terminal before starting api_server.py."}), 503

    sentences = split_sentences(text)
    if len(sentences) > MAX_SENTENCES:
        return jsonify({
            "error": f"This first version analyzes up to {MAX_SENTENCES} sentences per request. Shorten the text and try again."
        }), 413

    deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
    sentence_results = []
    try:
        for sentence in sentences:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise InferenceFailure("Analysis exceeded the 45-second time limit.", 504)
            sentence_results.append(classify_sentence(sentence, token, remaining))
    except InferenceFailure as error:
        return jsonify({"error": str(error)}), error.status_code

    try:
        language = detect(text)
    except LangDetectException:
        language = "unknown"

    overall = sum(item["claim_score"] for item in sentence_results) / len(sentence_results)
    return jsonify({
        "language": language,
        "overall_score": round(overall, 3),
        "model": MODEL_ID,
        "sentences": sentence_results,
    })


if __name__ == "__main__":
    print("Hugging Face analysis API running at http://127.0.0.1:9000")
    app.run(host="127.0.0.1", port=9000)
