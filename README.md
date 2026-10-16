# FollowUp — packaging-equipment sales desk

A small, runnable Streamlit app for five sales reps. SQLite stores lead decisions, editable drafts, and conversations. No login, WhatsApp integration, or payments are included. Publishing instructions are in DEPLOYMENT.md.

## Run locally

Python 3.11 or 3.12 is recommended.

```bash
git clone https://github.com/Megha-TR/CRM.git
cd CRM
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501. On this machine the dependencies are already installed, so `python3 -m streamlit run app.py` is sufficient. First launch seeds 25 fictional leads, five rep owners, and 25 two-message WhatsApp-style conversations. Dates are relative to that first launch. All phone numbers are intentionally dummy numbers.

## Optional AI mode

The entire workflow runs without credentials using local rules. **Local mode is deterministic automation, not an LLM.** For actual model-based reasoning and tailored drafts, supply your own OpenAI API key before starting the server:

```bash
export OPENAI_API_KEY='your-key-here'
export OPENAI_MODEL='gpt-4.1-mini'
python -m streamlit run app.py
```

Never commit the key. The app does not read `.env` automatically. It uses the OpenAI Responses API with a Pydantic structured output schema ([official documentation](https://developers.openai.com/api/docs/guides/structured-outputs)). Model access and API billing depend on your account. AI mode sends the selected lead and conversation to OpenAI. Seed creation deliberately uses local rules to avoid 25 API calls; use **Re-analyze this lead** to get an AI decision for a seeded lead. Added leads and chats are analyzed automatically. A live API request was attempted with a configured key, but the provider returned insufficient quota (exhausted credits). Successful live inference remains unverified; failure fallback and structured-response integration are tested with mocks.

If AI times out, refuses, or fails validation, the app persists a local decision and shows an explicit warning. Calls have a 20-second timeout and no retries. No paid call occurs on routine screen reruns or draft edits.

## Try the main flow

1. Select Asha or All reps. The due queue shows overdue leads first, then Hot, Warm, Cold, with oldest deadlines first within each group. Open Aarav at FreshBox Foods: his quote request is Hot and overdue.
2. Read the conversation, tag, reason, date, and draft. Edit the draft, click **Save draft**, then **Mark as sent**. The exact edited text is logged as a rep message. The lead moves out of today's queue and its next check-in is scheduled.
3. Under **Add a chat message**, add a buyer reply such as `Please schedule a demo tomorrow`. The agent updates only that lead.
4. Add a new lead using the expander near the top, with an initial buyer message. Clear filters if the assigned rep differs from the current filter.
5. In **All leads**, open Kiara at DailyHarvest. Her stop request pauses outreach. A subsequent buyer message expressing renewed interest can reactivate the lead.
6. Restart the app: drafts, new leads, and sent history remain in SQLite. CSV export provides a readable lead snapshot.

## Dashboard cards and colors

Click a summary card to filter the lead queue and workspace: **Due now** includes today and overdue; **Overdue** includes only dates before today; **Hot leads** includes active Hot leads; **Active leads** includes every lead whose outreach is not paused. Sidebar filters apply to all four counts. **Show all leads** includes paused leads too. The total and temperature legend show the full database counts. Hot badges and card borders are red, Warm yellow, and Cold blue; text labels remain visible so color is not the only signal.

## How the agent works

- `agent.py`: decision schema, local policy, optional OpenAI call, and visible failure fallback.
- `store.py`: SQLite schema, seed, read/write transactions, and revision checks against stale edits.
- `sample_data.py`: fictional lead and conversation fixtures.
- `app.py`: one-screen due queue, filters, lead detail, chat entry, draft editor, and new lead form.
- `tests/test_workflow.py`: seed, decision, persistence, opt-out, concurrency, fallback, and UI checks.

Local policy reads the lead's last contact date and the newest buyer message in chronological date/entry order. It ignores rep text for intent. Explicit stop/decline signals take precedence, then demo/quote/order intent (Hot), budget/timing constraints (Warm), staleness beyond 21 days without a stronger signal (Cold), otherwise Warm. This is deliberately a small English-language baseline: negation, paraphrases, mixed intent, and non-English messages need AI mode or improved rules.

Default follow-up dates use last contact + 1/3/7/14 days depending on intent and age; declined leads keep a review date but are excluded from outreach. Explicit ISO dates and today/tomorrow/next week/next month/next quarter override the date, relative to the buyer message's date. Past deadlines remain past so overdue work is visible. The LLM can understand more natural wording. After a rep marks a message sent, the app schedules a check-in in 2/7/14 days for Hot/Warm/Cold, preserving any later existing requested date. A sent-message record is added atomically, and revision checks reject duplicate/stale submissions.

## Test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use temporary databases and never change the demo database. Streamlit's AppTest exercises the app itself without needing a browser.

## Storage and scope

Database: `data/crm.db` (created automatically and excluded from Git). Set `CRM_DB_PATH` to override. Static sample exports are in `data/sample_leads.csv` and `data/sample_chats.json`; the app seeds from `sample_data.py`, so no import step is needed. Back up the database before changing it. For a fresh demo, stop the app and point `CRM_DB_PATH` at a new file.

SQLite is simpler here than Google Sheets: no service account, spreadsheet sharing, or network dependency, and chat plus follow-up updates can be atomic. Google Sheets is suitable for shared spreadsheet viewing, but adds integration work for this app. For hosted multi-instance production use, move to managed Postgres; SQLite needs a persistent disk and a single app instance. Ephemeral hosting may discard local files.

The brief's short submission note is in `SUBMISSION_NOTE.md`; read and personalize it before sending. The brief also requires a live link, visible GitHub repo, and video. Repository publishing is now authorized; deployment and the video remain outstanding. No email has been sent.
