"use strict";

const form = document.querySelector("#analyze-form");
const SERVER_ENDPOINT = '/api/analyze';
const SERVER_TIMEOUT = 55_000;
const analyzeButton = form.querySelector('button[type="submit"]');
const articleInput = document.querySelector("#article-text");
const charCount = document.querySelector("#char-count");
const formError = document.querySelector("#form-error");
const analysisStatus = document.querySelector("#analysis-status");
const results = document.querySelector("#results");
const resultSummary = document.querySelector("#result-summary");
const signalsContainer = document.querySelector("#signals");
const sampleButton = document.querySelector("#sample-button");
const sampleText = "SHOCKING: They don't want you to know this secret! A new study proves once and for all that everyone should act now. Share this before it's too late.";

function renderSignal(title, description, icon, count) {
  const item = document.createElement("article");
  item.className = "signal";

  const marker = document.createElement("span");
  marker.className = "signal-icon";
  marker.setAttribute("aria-hidden", "true");
  marker.textContent = icon;

  const content = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = title;
  const detail = document.createElement("p");
  detail.textContent = description;
  if (count !== null) {
    const countLabel = document.createElement("span");
    countLabel.className = "signal-count";
    countLabel.textContent = `${count} detected · `;
    detail.prepend(countLabel);
  }

  content.append(heading, detail);
  item.append(marker, content);
  signalsContainer.append(item);
}

async function analyze(text) {
  formError.hidden = true;
  analysisStatus.hidden = false;
  analysisStatus.textContent = "Sending text to Hugging Face for multilingual claim analysis…";
  analyzeButton.disabled = true;
  results.hidden = true;
  try {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), SERVER_TIMEOUT);
    try {
      const resp = await fetch(SERVER_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({ text }),
      });
      const contentType = resp.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        throw new Error(
          "The deployed API returned a web page instead of JSON. Redeploy the site with its Netlify Function enabled.",
        );
      }
      const payload = await resp.json();
      if (!resp.ok) {
        throw new Error(payload.error || `Analysis failed (HTTP ${resp.status}).`);
      }
      renderServerResults(payload);
    } finally {
      clearTimeout(id);
    }
  } catch (error) {
    formError.textContent = error.name === "AbortError"
      ? "Analysis took too long. Please try again with fewer sentences."
      : error.message || "Analysis failed. Check that both local servers are running.";
    formError.hidden = false;
  } finally {
    analysisStatus.hidden = true;
    analyzeButton.disabled = false;
  }
}

function renderServerResults(payload) {
  signalsContainer.replaceChildren();
  resultSummary.textContent = `Multilingual model review (${payload.language || "language not identified"}). Average claim-likeness confidence: ${Math.round(payload.overall_score * 100)}%. A claim classification is not a truth rating.`;

  payload.sentences.forEach((sentence) => {
    const confidence = Math.round(sentence.score * 100);
    const heading = sentence.label === "claim"
      ? `Possible factual claim · ${confidence}% model confidence`
      : `${sentence.category} · ${confidence}% model confidence`;
    renderSignal(
      heading,
      sentence.text,
      sentence.label === "claim" ? "!" : "•",
      null,
    );
  });

  results.hidden = false;
}

articleInput.addEventListener("input", () => {
  charCount.textContent = `${articleInput.value.length.toLocaleString()} / 12,000 characters`;
  formError.hidden = true;
});

sampleButton.addEventListener("click", () => {
  articleInput.value = sampleText;
  articleInput.dispatchEvent(new Event("input"));
  articleInput.focus();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = articleInput.value.trim();
  if (text.length < 30) {
    formError.textContent = "Add at least 30 characters so there is enough text to review.";
    formError.hidden = false;
    articleInput.focus();
    return;
  }
  analyze(text);
  results.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
