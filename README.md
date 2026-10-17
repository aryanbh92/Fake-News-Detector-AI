# Fake-News-Detector-AI

A small media-literacy prototype that uses Hugging Face Inference Providers to classify sentences as possible factual claims, opinions, or other text. This is claim detection, **not** fact verification: it does not determine whether a claim is true, inspect its publisher, or verify cited sources.

## Run locally

Requires Python 3.9 or newer. Keep both local servers running while using the app. The article text is sent to Hugging Face for analysis. Your HF token stays in the Python API server and is not included in the browser request.

## Hugging Face analysis

The API uses the multilingual `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` zero-shot classification model. Its model card lists English, Spanish, French, and Hindi support among other languages. Each sentence gets a classification confidence; confidence is **not** a truth score. Inference can take longer than 500 ms, especially on a cold start, and requests are limited to 12 sentences.

1. Create a Hugging Face access token with **Inference Providers** permission. Do not paste the token into chat or add it to project files.

2. In a PowerShell terminal, set the token for that terminal session:

```powershell
$env:HF_TOKEN = "hf_your_token_here"
```

3. In that same terminal, install dependencies and start the API server:

```powershell
python -m pip install -r requirements.txt
python api_server.py
```

4. Open a second PowerShell terminal in this folder and start the web server:

```powershell
python server.py
```

5. Visit [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop each server with `Ctrl+C` in its terminal.

The token is available only to programs started from the PowerShell window where `$env:HF_TOKEN` was set. If you close that window, set it again before restarting `api_server.py`. Never commit the token. If the server reports an authentication error, create a token with Inference Providers permission and replace the old value. This first integration does not include named-entity recognition.

## Deploy on Netlify

The repository includes a Netlify Function at `/api/analyze`. Netlify must deploy both the static site and the function; uploading only the website files will make `/api/analyze` return the site's HTML page, which causes a JSON parsing error.

1. Push the project to a Git provider and import that repository into Netlify, or deploy it with the Netlify CLI from the project directory. A simple drag-and-drop static deploy does not build the function.
2. In Netlify, open **Site configuration → Environment variables** and add `HF_TOKEN` with a new Hugging Face token. Give it **Functions** scope (and the production deploy context). Do not put the token in `netlify.toml`, the browser code, or the repository.
3. Trigger a new deploy after setting the variable and after pushing the Netlify Function files.
4. Open the deployed site and try the sample. The front end now displays a clear message if the API responds with HTML instead of JSON.

The Netlify Function is configured to serve `POST /api/analyze` directly. Local development can continue using `python api_server.py` and `python server.py`.
