# Publishing checklist

The app works locally. Publishing has not been completed. OpenAI was rejected for exhausted credits. Gemini is now the configured provider; a live Gemini request still needs verification.

## Before sharing with the company

- Configure a Gemini API key through local `.streamlit/secrets.toml` (see the example) or the host's secret environment variables. Never put the key in Git or send it in chat.
- Re-analyze a seeded lead, then add a buyer message. Verify that the decision says **Gemini**, not **Local rules** or **Local fallback**, and inspect tag, reason, date, and draft.
- Push the source to the intended GitHub account and provide reviewer access.
- Deploy to a single app instance with a writable persistent disk mounted at `/app/data`. Configure `CRM_DB_PATH=/app/data/crm.db` and the AI key on the host. The Dockerfile is prepared for this arrangement; it has not yet been built or run here.
- Confirm the public URL opens from a fresh browser, run the full rep workflow, restart the hosted service, and verify the saved lead/message remains.
- Update the submission note with the actual hosting and AI validation results. The assignment separately requires a short video.

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

The automated suite covers local rules, structured AI responses with mocks, AI fallback, persistence, stale submissions, opt-outs, and the UI workflow/card filters. It does not prove live provider access or hosted durability; those require the checks above.
