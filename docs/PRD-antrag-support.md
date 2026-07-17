# DocVerify — Antrag support, dynamic configuration & extraction modes (PRD)

> Generated from design conversations (grilling sessions) on 2026-06-24, amended after a second grill covering dynamic configuration and extraction modes. Extends the original DocVerify PRD (issue #2); builds on existing app code (config schema, result schema, async job API, two-stage pipeline, segmentation, optional rules layer). No backward-compatibility constraints — no deployed consumers yet.

## Problem Statement

DocVerify today has two structural limits:

1. **Configuration is static and server-side.** The validation policy lives in a `config.yaml` loaded once at startup, so the service holds state about *which* document types and rules exist. A calling Fachverfahren cannot vary the policy per request, and the service is not as stateless as the original design intended — it retains policy state and presumes one global configuration.

2. **Every upload is a flat list of independently-validated documents.** A citizen rarely submits one isolated document — they submit an **Antrag**: an application bundle (e.g. Personalausweis + Mietvertrag + Sprachzertifikat) that must be assessed *as a whole*. Treating a bundle as a flat list means there is no overall verdict, no check that an expected document is *missing*, and no cross-document consistency (the name on the ID not matching the Mieter on the lease, etc.).

Callers also have only one interaction shape — "validate against the configured policy." Sometimes they instead want to **just extract** whatever a document contains (without a policy), or to **verify a few specific fields** off a document without describing a whole type.

## Solution

Two coordinated changes, kept strictly **validate-and-extract** (DocVerify produces structured findings + an internal summary; it never generates citizen-facing communication):

### A. Dynamic, per-request configuration (stateless)

The validation policy is passed **in the request payload** as a JSON `config` field (the existing `document_types` shape), validated by the same schema. The server stores **no** configuration and **no** information about the Anträge or documents it processes — the calling Fachverfahren owns policy and is the system of record. `config.yaml` survives only as an example/dev default and a GUI starter.

This unlocks three single-document modes, selected by what the request carries:

- **Validate** (`config` present): classify → validate against the supplied type(s)' criteria/rules → full verdict (today's behavior, now dynamic).
- **Scan** (no `config`): the goal is to extract, not validate — the model infers the document type and extracts **all** available information, returning **no verdict**.
- **Targeted** (`required_fields` present): verify a specific set of requested fields and return **only** those fields, with a verdict — no type classification, no policy.

### B. Antrag (application-bundle) support

An `antrag` submission is the **bundle mode**, selected by a flag (not by file count). It requires a full `config`, which doubles as the **expected-document manifest** (a list of expected documents + their expected values, each flagged `required`/`optional`). Each file is segmented; all sub-documents are validated individually, then reconciled:

- **Cross-document sanity check (Stufe 3):** a single LLM pass flags identity/context discrepancies across the bundle (mismatched names/IDs/addresses).
- **Completeness check:** any `required` document type with no matching sub-document is reported as missing.
- **Bundle roll-up:** a deterministically-derived `antrag_status` plus an internal German prose `summary`.

The downstream Fachverfahren acts on the structured result (including phrasing any citizen letter itself).

## User Stories

1. As an integrating Fachverfahren, I want to pass the validation configuration **in the request** rather than rely on server-side config, so that I control policy per call and the service stays stateless.
2. As the operating authority, I want the service to retain **no information about the Anträge or documents** it processes, so that the citizen-PII surface is minimal and the calling Fachverfahren remains the system of record.
3. As an integrating Fachverfahren, I want to submit a document with a **full config** and get a full validation verdict (classification + criteria + rules + Mängelliste), so that I can automate the Vorprüfung.
4. As an integrating Fachverfahren, I want to submit a document with **no config** and have the system infer its type and extract everything it can, so that I can scan/triage unknown documents without describing a policy.
5. As an integrating Fachverfahren submitting a no-config scan, I want **no validity verdict** returned (just classification + extracted data + a legibility confidence), so that the response honestly reflects that no validation was requested.
6. As an integrating Fachverfahren, I want to submit a document with a **specific list of required fields** and get back only those fields, each verified for presence and legibility, so that I can pull targeted data without describing a whole document type.
7. As an integrating Fachverfahren using targeted mode, I want the document **not** type-checked (no `invalid_type`), so that I get my fields regardless of what the document is.
8. As an integrating Fachverfahren, I want a clear 4xx when I send an **ambiguous request** (both a config and required-fields), so that mode selection is unambiguous.
9. As an integrating Fachverfahren, I want to **declare** a submission as a single `dokument` or a multi-document `antrag`, so that the system applies the correct processing.
10. As an integrating Fachverfahren submitting an `antrag`, I want to send **one bundled PDF or several files** and have every contained document validated individually, so that combined scans are handled without manual separation.
11. As an integrating Fachverfahren, I want the `antrag` config to act as the **expected-document manifest**, so that the system knows which documents the application should contain.
12. As a Fachaufsicht, I want to flag each expected document as **required or optional**, so that genuinely optional attachments don't wrongly fail the application.
13. As an integrating Fachverfahren, I want **entirely missing required documents** reported (as machine-readable type ids and a human-readable note), so that I know an attachment is absent, not just faulty.
14. As an integrating Fachverfahren, I want DocVerify to **check that all documents in an Antrag belong to the same context** (matching names / IDs / addresses), so that internally contradictory applications are flagged.
15. As an integrating Fachverfahren, I want **cross-document discrepancies** returned as an explicit list, so that my downstream process knows what is inconsistent.
16. As an integrating Fachverfahren, I want a single bundle-level verdict (`antrag_status`) that says whether the whole application is in order or has Mängel, so that I can route the Antrag without reconciling N per-document results.
17. As a Sachbearbeiter reviewing an Antrag, I want a concise **internal German summary** of the bundle, so that I can grasp its state at a glance.
18. As an integrating Fachverfahren, I want each document's **individual result to remain unchanged**, so that I still get full per-document detail underneath the bundle verdict.
19. As an integrating Fachverfahren, I want the cross-document check to **re-read the image of any low-legibility document** before concluding, so that a discrepancy isn't asserted or missed because of a poor scan.
20. As an integrating Fachverfahren, I want a **stable, documented response shape per mode**, so that I can rely on the contract.
21. As a developer/Sachbearbeiter using the GUI, I want to **paste or load a config in the GUI** and fire a request, so that I can demo and test dynamic configuration without hand-crafting multipart.
22. As the operating authority, I want the Antrag/extraction flows to generate **no citizen communication**, so that citizen-facing phrasing remains the downstream system's responsibility.

## Implementation Decisions

- **Configuration is per-request, not server-side.** A JSON `config` form field on `POST /documents` carries the `document_types` policy, validated by the existing `Config`/`DocumentTypeConfig` Pydantic schema. The loader is refactored into "read bytes" + "validate dict → Config" so the *same* validation guards both the file (dev/example) and the request payload (runtime). A malformed inline config → 422. The server stores no config.
- **Statelessness means no retained content.** The system keeps no information about the Anträge or documents it processes. The async job model (POST → `202` + `job_id`; poll `GET /jobs/{id}`) stays — it exists so large/multi-page uploads don't block — but the job store is ephemeral, short-TTL, and holds no durable record.
- **Mode is inferred from payload presence.** `config` present → **validate**; `required_fields` present → **targeted**; neither → **scan**. `config` and `required_fields` together → 422. `submission_type` (`dokument`/`antrag`) is an independent axis.
- **Honest polymorphism across modes** (no faked shapes or nullable verdicts): each mode returns its own response shape.
  - *Validate* → the existing `ValidationResult` (status, confidence, classification, extracted_data, deficiencies, internal_note).
  - *Scan* → an extraction-result shape: inferred `classification` + all `extracted_data` + `confidence`; **no** `validation_status`, **no** `deficiencies`.
  - *Targeted* → a field-verification result: `validation_status` (`accepted` iff all requested fields present+legible, else `incomplete`) + `deficiencies` scoped to requested fields + `extracted_data` filtered to **only** the requested fields + `confidence`; **no** `classification`.
- **Targeted required-fields use the `ExpectedField` shape** (`name` + `description` + `type_hint`) as a bare list — no `document_type` wrapper, no criteria, no rules. Targeted mode **skips classification** entirely (no Stufe-1 call, `invalid_type` impossible) and reuses `FieldResult`/`Deficiency`/legibility logic.
- **`submission_type` declares `dokument` vs `antrag`.** `dokument` = exactly one file (422 otherwise), segmentation disabled, one classify + one extract over all pages. `antrag` = bundle mode by the flag, ≥1 file, each segmented, sub-documents unioned in file-upload order.
- **Antrag requires a full `config`.** No-config (scan) and targeted are `dokument`-only (else 422). The antrag config is the expected-document manifest; each `document_type` gains a `required` flag (default `true`).
- **Pipeline gains two entry points:** `run_dokument` and `run_antrag(files) -> AntragResult` (`{results, antrag_metadata}`). Per-document `ValidationResult`s are immutable; the bundle layer is computed on top.
- **Cross-document check + summary are one combined LLM call** behind a new `analyze_antrag` method on the model-client interface, returning `{cross_document_findings: list[str] (German), summary: str (German, internal)}`. Input = compact per-document JSON for all sub-documents (incl. `invalid_type`, as context) **plus** page images only for documents with `confidence` below a configurable threshold (default ~0.8; image cap ~10, logged on truncation). Always runs once (degenerate bundles → empty findings); a discrepancy requires ≥2 documents with comparable identity data.
- **Completeness is deterministic, in code.** A `required` config type with no sub-document classified as it yields `missing_required_documents: [type_id]` (machine-readable) plus an auto-generated German line in the human-readable findings. Computed outside the LLM call.
- **`antrag_status` is derived deterministically** (reusing `ValidationStatus`, emitting only `accepted`/`incomplete`): `accepted` iff every document is `accepted` **and** there are no cross-document findings **and** no missing required documents; otherwise `incomplete`. `invalid_type` is never a bundle status.
- **Response per `submission_type`:** `dokument` → `{ status, submission_type, result }` (the result shape varies by mode as above); `antrag` → `{ status, submission_type, results, antrag_metadata: { cross_document_findings, missing_required_documents, summary, antrag_status } }`.
- **Frontend (Vue 3 + Vuetify, test/assist tool only)** gains: a `dokument`/`antrag` toggle, a 1..N-file upload, a **config editor** (paste/tweak/load JSON to drive dynamic config), and — for Antrag jobs — bundle-status + summary + cross-doc findings + missing-documents rendered above the existing `ResultsList`.

## Testing Decisions

- **Primary seam — the FastAPI HTTP boundary**, model client faked (existing `tests/test_api.py` convention). Tests drive `POST /documents` with the various payload combinations and poll `GET /jobs/{id}`, asserting on the public contract per mode:
  - validate (config) → full `ValidationResult`;
  - scan (no config) → classification + fields + confidence, no verdict;
  - targeted (required_fields) → verdict + requested-fields-only data, no classification;
  - antrag (config) → `results` + `antrag_metadata`.
- **Mode-selection and validation errors at the seam:** `config` + `required_fields` → 422; `dokument` with >1 file → 422; `antrag` without config → 422; empty files / unknown `submission_type` → 422; malformed inline `config` JSON → 422.
- **Inline-config validation reuses the config-loader seam** (`tests/test_config.py`): the validate-dict→Config half is exercised directly with valid and malformed payloads.
- **The model-client fake gains canned `analyze_antrag`**, so the whole Antrag pipeline (segmentation → per-doc validation → cross-doc call → deterministic roll-up) runs offline.
- **Pure logic tested directly:** `antrag_status` derivation and `missing_required_documents` detection are deterministic — unit-tested without the model (all-accepted-no-findings → `accepted`; a finding, an `invalid_type` doc, or a missing required type → `incomplete`; image-inclusion forwards only sub-threshold docs to the fake).
- **Out of scope for the normal suite:** a live Azure integration test — the faked-client HTTP seam is the convention.

## Out of Scope

- **Citizen communication / Nachforderungstext / Textbaustein generation.** Reaffirmed boundary — DocVerify emits only the structured defect picture (`deficiencies` + `cross_document_findings` + `missing_required_documents` + `antrag_status`) and the internal `summary`; the downstream Fachverfahren phrases any letter. No citizen-text field, no frontend copy feature.
- **Server-side / stored configuration.** Config is per-request only; no config is persisted, referenced by id, or merged with a server base.
- **No-config scan or targeted mode for `antrag`.** Bundle reconciliation is policy-driven; those modes are `dokument`-only.
- **A deterministic cross-document identity-marker engine.** Cross-document reconciliation is LLM-only; only completeness (missing required docs) is deterministic.
- **Severity grading or document-index linking of cross-document findings.** Findings are flat German strings.
- **Mutating per-document results based on bundle findings.** Per-document results stay immutable.
- **Durable persistence / system of record**, **auth/TLS**, and **model hosting/region/data-residency** — unchanged from the base project; still out of scope.

## Further Notes

- **The cross-document check is bounded by what per-document extraction captured.** Comparing, e.g., an address across documents only works if "address" is an expected field on the relevant types — make a field comparable by adding it to that type's `expected_fields`, not by re-OCRing in the cross-doc stage.
- **Mode inference has one footgun:** a caller who forgets `config` silently gets *scan* (no verdict) instead of an error. Accepted, because no-config scan is a deliberate first-class intent; revisit with an explicit `mode` field only if it causes real confusion.
- **Suggested first build step:** make config dynamic (refactor the loader, add the `config` field, route validate mode through it) before layering scan/targeted modes and the Antrag bundle path — locking the request contract first keeps the downstream slices stable.
- The exact `config.yaml`/payload keys for the confidence threshold and image cap, and the behavior if `analyze_antrag` fails, are deferred to implementation.
