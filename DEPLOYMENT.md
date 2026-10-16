# Publishing checklist

The source is published at https://github.com/Megha-TR/CRM. Live Gemini inference has been verified directly and through the running app. A hosted deployment has not yet been completed.

## Free Community Cloud deployment

1. Sign into https://share.streamlit.io using the GitHub account that owns Megha-TR/CRM.
2. Create an app from repository `Megha-TR/CRM`, branch `main`, entrypoint `app.py`.
3. Select Python 3.12 in Advanced settings.
4. Add only these Gemini settings to the host's Secrets field, supplying your own key:

```toml
AI_PROVIDER = "gemini"
GEMINI_API_KEY = "your-key-here"
GEMINI_MODEL = "gemini-2.5-flash"
```

5. Deploy, then verify the public URL from a fresh browser. Open a lead, re-analyze it, confirm **Decision: Gemini**, edit a draft, mark it as sent, and add a buyer message.

This is a free demo deployment with ephemeral local storage. All viewers share its demo database. Saved edits may be lost when the host restarts or redeploys; initial sample leads regenerate. Durable storage requires an external database adapter (not implemented) or persistent-disk hosting. Do not describe this free SQLite deployment as durable production storage. Gemini usage remains subject to the configured project's free-tier quotas.

The CI workflow is included as an inactive template at `ci/github-actions-tests.yml.example`, because the GitHub sign-in lacked permission to create active workflows. Local tests have passed; no hosted Actions run is claimed.

## Before sharing with the company

- Configure a Gemini API key through local `.streamlit/secrets.toml` (see the example) or the host's secret environment variables. Never put the key in Git or send it in chat.
- Re-analyze a seeded lead, then add a buyer message. Verify that the decision says **Gemini**, not **Local rules** or **Local fallback**, and inspect tag, reason, date, and draft.
- Push the source to the intended GitHub account and provide reviewer access.
- Deploy to a single app instance with a writable persistent disk mounted at `/app/data`. Configure `CRM_DB_PATH=/app/data/crm.db` and the AI key on the host. The Dockerfile is prepared for this arrangement; it has not yet been built or run here.
- Confirm the public URL opens from a fresh browser, run the full rep workflow, restart the hosted service, and verify the saved lead/message remains.
- Update the submission note with the actual hosting result and storage limitation. The assignment separately requires a short video.

## Storage choice

Local SQLite is appropriate for this small, single-instance app. Persistent hosting keeps edits across process restarts and deployments when the disk is retained. A paid disk or another provider account may be required; no paid service has been provisioned.

Streamlit Community Cloud is a simple demo host, but its local filesystem is not guaranteed to persist. Do not promise durable saved changes with SQLite on that platform. If using Community Cloud, use an external persistent database for durable state; that adapter is not implemented here.

## Local Docker verification (optional)

```bash
docker build -t followup .
docker volume create followup-data
docker run --rm -p 8501:8501 --mount source=followup-data,target=/app/data --env AI_PROVIDER=gemini --env GEMINI_API_KEY followup
```

Export the key in your own terminal beforehand. The named volume preserves the database. No key is stored in the image. Use one running instance for this SQLite setup.

## Current verification

The automated suite covers local rules, structured AI responses with mocks, AI fallback, persistence, stale submissions, opt-outs, and the UI workflow/card filters. Live Gemini provider access was separately verified. Hosted usability and persistence require the checks above.
