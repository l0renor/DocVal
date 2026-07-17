# Running DocVerify

This guide covers everything needed to get the backend and frontend running locally, from first checkout to a working browser session.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.14+ | https://python.org or `pyenv` |
| `uv` | latest | `pip install uv` or https://docs.astral.sh/uv/ |
| Node.js | 18+ | https://nodejs.org |
| npm | bundled with Node | — |

You also need access to an **Azure OpenAI** resource with a GPT-5.5 deployment.

---

## 1. Clone and install backend dependencies

```sh
git clone https://github.com/l0renor/DocVal.git
cd DocVal

uv sync          # creates .venv and installs all runtime + dev deps
```

`uv sync` reads `uv.lock` and reproduces the exact locked versions. It is idempotent — safe to re-run after pulling changes.

---

## 2. Create `.env`

The backend reads Azure credentials from a local `.env` file that is **not committed**:

```sh
cp .env.example .env
```

Then open `.env` and fill in your values:

```ini
AZURE_OPENAI_API_KEY=<your key>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=<your deployment name, e.g. gpt-5.5>

# Optional — defaults to "2024-10-21" if omitted:
AZURE_OPENAI_API_VERSION=2024-10-21
```

Leave `AZURE_OPENAI_API_VERSION` commented out unless you need a specific version.

---

## 3. Configure document types

The backend is driven by `config.yaml`. An annotated example is provided:

```sh
cp config.example.yaml config.yaml
```

Edit `config.yaml` to add or change document types. The file is schema-validated on server startup — a malformed config produces a clear error before the server accepts any requests. The `DOCVAL_CONFIG` environment variable overrides the default path if you want to keep multiple configs:

```sh
DOCVAL_CONFIG=./configs/staging.yaml uv run uvicorn --factory docval.main:create
```

---

## 4. Start the backend

```sh
uv run uvicorn --factory docval.main:create --reload
```

| | |
|---|---|
| **URL** | http://127.0.0.1:8000 |
| **OpenAPI docs** | http://127.0.0.1:8000/docs |
| `--reload` | Auto-restarts on source changes (development only) |

To bind to a different address or port:

```sh
uv run uvicorn --factory docval.main:create --host 0.0.0.0 --port 8080 --reload
```

### Verify it is running

```sh
curl http://127.0.0.1:8000/docs   # should return HTML
```

Or open http://127.0.0.1:8000/docs in a browser to see the interactive Swagger UI.

---

## 5. Start the frontend

In a **second terminal**:

```sh
cd frontend
npm install       # first time only; also after pulling dependency changes
npm run dev
```

| | |
|---|---|
| **URL** | http://127.0.0.1:5173 |
| **Backend proxy** | `/api/*` → http://127.0.0.1:8000 |

The Vite dev server proxies all `/api/*` requests to the backend, so no CORS configuration is needed during development. The backend **must** be running before you submit documents through the UI.

If your backend runs on a different host or port, update the `proxy.target` in [frontend/vite.config.js](../frontend/vite.config.js):

```js
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8080',   // change to match your backend
    ...
  },
},
```

---

## 6. Submit a document

**Via the UI:**  
Open http://127.0.0.1:5173, upload a PDF or image, and click **Prüfen**. The UI polls the job endpoint and renders the result with a colour-coded Ampel (green / yellow / red) per detected sub-document.

**Via curl:**

```sh
# Submit (returns a job_id immediately)
curl -s -X POST http://127.0.0.1:8000/documents \
  -F "file=@testdata/Personalausweis_Rueckseite_Bild_2.jpg" \
  | python -m json.tool

# Poll (replace <job_id> with the id from the previous response)
curl -s http://127.0.0.1:8000/jobs/<job_id> | python -m json.tool
```

For antrag (multi-document bundle) mode add `-F "mode=antrag"`:

```sh
curl -s -X POST http://127.0.0.1:8000/documents \
  -F "file=@testdata/Mietvertrag_und_Zertifikat.pdf" \
  -F "mode=antrag" \
  | python -m json.tool
```

---

## 7. Run tests

Tests are offline — no Azure calls are made. The model client is replaced with a `FakeModelClient` in all test fixtures.

**Backend:**

```sh
uv run pytest           # all tests
uv run pytest -v        # verbose
uv run pytest tests/test_antrag_mode.py   # single module
```

**Frontend:**

```sh
cd frontend
npm test                # single run (jsdom, no real backend)
npm run test:watch      # re-run on file changes
```

---

## 8. Production build

The frontend compiles to a static bundle that can be served by any web server or CDN:

```sh
cd frontend
npm run build           # outputs to frontend/dist/
npm run preview         # local preview of the production bundle
```

For the backend in production, drop `--reload` and consider running behind a process manager (e.g. `systemd`, `supervisord`, or a container):

```sh
uv run uvicorn --factory docval.main:create --host 0.0.0.0 --port 8000 --workers 4
```

---

## Troubleshooting

**`ModuleNotFoundError` on startup**  
Run `uv sync` again — a pull may have introduced new dependencies.

**`ConfigError` on startup**  
`config.yaml` is malformed or missing. Check indentation and required keys against `config.example.yaml`, or set `DOCVAL_CONFIG` to a valid path.

**`AuthenticationError` from Azure**  
`.env` is missing or has incorrect `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT`. Values are logged (redacted) at startup — check the server console.

**Frontend shows "Network Error" or requests fail**  
Confirm the backend is running (`curl http://127.0.0.1:8000/docs`). If the backend is on a different port, update `proxy.target` in `frontend/vite.config.js` and restart `npm run dev`.

**Job stays in `pending` indefinitely**  
The Azure call is likely hanging or erroring. Check the backend console for exceptions. Ensure the deployment name matches an active deployment in your Azure resource.
