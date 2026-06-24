# DocVerify Frontend

A Vue 3 + Vuetify single-page **testing/assistance tool** over the DocVerify
validate-and-extract API. It is *not* a required review step — DocVerify reports
its verdict via the API; this GUI just makes that verdict easy to inspect.

For each submitted document it shows, per detected sub-document:

- a status **Ampel** (green `accepted` · yellow `incomplete` · red `invalid_type`),
- the extracted fields, with **missing / illegible** fields flagged red,
- the **Mängel** (deficiencies) list,
- the optional **Sachbearbeiter-Hinweis** (`internal_note`).

There is intentionally **no Textbaustein / citizen-communication** feature — that
lives in another system.

## Develop

```sh
npm install
npm run dev      # serves on :5173, proxies /api -> http://127.0.0.1:8000
npm test         # Vitest + @testing-library/vue (jsdom), offline
npm run build
```

The dev server proxies `/api/*` to the FastAPI backend (run it with
`uv run uvicorn --factory docval.main:create`). Adjust the target in
`vite.config.js` if the backend runs elsewhere.
