from datetime import timedelta
import pytest
import store
from agent import local_decision, today

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('CRM_DB_PATH', str(tmp_path / 'crm.db'))
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    store.initialize()


def test_seed_and_idempotency():
    assert len(store.all_leads()) == 25
    store.initialize()
    assert len(store.all_leads()) == 25
    assert all(len(store.get_lead(l['id'])[1]) == 2 for l in store.all_leads())


def test_priority_and_pause():
    leads = store.all_leads()
    assert leads[0]['tag'] == 'Hot'
    assert leads[0]['next_followup'] < today().isoformat()
    assert leads[11]['paused'] and leads[11]['draft'] == ''
    with pytest.raises(ValueError, match='paused'):
        store.mark_sent(leads[11]['id'], 'Hi', leads[11]['revision'])


def test_add_update_edit_send_persistence():
    lead_id = store.add_lead(dict(name='Test Buyer', company='Test Ltd', phone='1234567890', source='WhatsApp', rep='Asha', last_contact=today().isoformat()))
    store.add_chat(lead_id, 'Buyer', 'Please send a quote tomorrow', today())
    lead, _ = store.get_lead(lead_id)
    assert lead['tag'] == 'Hot'
    assert lead['next_followup'] == (today() + timedelta(days=1)).isoformat()
    store.save_draft(lead_id, 'A hand-edited draft', lead['revision'])
    lead, _ = store.get_lead(lead_id)
    assert lead['draft'] == 'A hand-edited draft'
    store.mark_sent(lead_id, 'The actual sent text', lead['revision'])
    updated, chats = store.get_lead(lead_id)
    assert chats[-1]['body'] == 'The actual sent text'
    assert updated['last_contact'] == today().isoformat()
    assert updated['next_followup'] > today().isoformat()
    with pytest.raises(ValueError, match='changed'):
        store.mark_sent(lead_id, 'Duplicate', lead['revision'])
    assert len(store.get_lead(lead_id)[1]) == 2


def test_latest_buyer_intent_over_rep_words():
    lead, chats = store.get_lead(1)
    chats += [dict(sender='Buyer', body='Not interested', created_at=today().isoformat()), dict(sender='Rep', body='Urgent demo quote', created_at=today().isoformat())]
    assert local_decision(lead, chats).paused


def test_requested_date_and_old_chat():
    lead, chats = store.get_lead(1)
    requested = (today() + timedelta(days=10)).isoformat()
    store.add_chat(1, 'Buyer', f'Please follow up on {requested}', today())
    assert store.get_lead(1)[0]['next_followup'] == requested
    store.add_chat(1, 'Buyer', 'Not interested', today() - timedelta(days=60))
    assert not store.get_lead(1)[0]['paused']


def test_ai_failure_fallback(monkeypatch):
    import openai
    from agent import analyze
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    def unavailable(*args, **kwargs):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(openai, 'OpenAI', unavailable)
    lead, chats = store.get_lead(1)
    result, engine, warning = analyze(lead, chats)
    assert result.tag == 'Hot' and engine == 'Local fallback' and warning


def test_ui_loads():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app.py')).run()
    assert not at.exception
    assert at.title[0].value == 'Your next conversation starts here.'
    assert any(b.label == 'Mark as sent' for b in at.button)


def test_ai_structured_success(monkeypatch):
    import openai
    from types import SimpleNamespace
    from agent import analyze, Decision
    expected = Decision(tag='Hot', reason='Buyer requested a quote.', next_followup=today(), draft='Hi Aarav, can we confirm your packing requirements?')
    calls = []
    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_parsed=expected)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setattr(openai, 'OpenAI', lambda **kwargs: SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    lead, chats = store.get_lead(1)
    result, engine, warning = analyze(lead, chats)
    assert result == expected and engine == 'OpenAI' and warning is None
    assert calls[0]['text_format'] is Decision
    assert 'FreshBox Foods' in calls[0]['input'][1]['content']


def test_ui_edit_send_add_chat_and_create():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    def button(label):
        return next(b for b in at.button if b.label == label)
    def text(label):
        return next(t for t in at.text_area if t.label == label)
    # Due queue starts with the oldest overdue Hot lead.
    assert any(h.value == '### Kabir Rao' for h in at.markdown)
    text('Next follow-up message').set_value('Hi Kabir, shall we confirm the configuration?')
    button('Save draft').click().run()
    assert not at.exception
    assert store.get_lead(3)[0]['draft'] == 'Hi Kabir, shall we confirm the configuration?'
    button('Mark as sent').click().run()
    assert not at.exception
    assert store.get_lead(3)[1][-1]['body'] == 'Hi Kabir, shall we confirm the configuration?'
    # Explicitly open Kabir again from the all-leads directory.
    next(b for b in at.button if b.label.startswith('Kabir Rao')).click().run()
    text('Message').set_value('Please send a quotation tomorrow')
    button('Add chat & update agent').click().run()
    assert not at.exception
    assert store.get_lead(3)[0]['tag'] == 'Hot'
    for label,value in [('Buyer name *','Demo Buyer'),('Company *','Demo Co'),('Phone *','9876543210')]:
        next(t for t in at.text_input if t.label == label).set_value(value)
    text('Initial buyer message (optional)').set_value('Please schedule a demo tomorrow')
    button('Create lead & run agent').click().run()
    assert not at.exception
    assert len(store.all_leads()) == 26
    assert store.get_lead(26)[0]['tag'] == 'Hot'


def test_summary_cards_filter_queue_and_detail():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    active = [l for l in store.all_leads() if not l['paused']]
    expected = {
        'Due now': [l for l in active if l['next_followup'] <= today().isoformat()],
        'Overdue': [l for l in active if l['next_followup'] < today().isoformat()],
        'Hot leads': [l for l in active if l['tag'] == 'Hot'],
        'Active leads': active,
    }
    for label, leads in expected.items():
        at.button(key=f'view_{label}').click().run()
        assert not at.exception
        queue_ids = {int(b.key.removeprefix('open_')) for b in at.button if b.key and b.key.startswith('open_')}
        assert queue_ids == {l['id'] for l in leads}
        assert any(m.value == f'### {l["name"]}' for m in at.markdown for l in leads)
    next(b for b in at.button if b.label == 'Show all leads').click().run()
    assert len([b for b in at.button if b.key and b.key.startswith('open_')]) == 25
    badges = ' '.join(m.value for m in at.markdown)
    assert all(f'temperature-{tag}' in badges for tag in ['hot', 'warm', 'cold'])


def test_gemini_structured_response_and_provider_selection(monkeypatch):
    import io
    import json
    import agent
    calls = []
    decision = dict(tag='Hot', reason='Buyer requested a quote.', next_followup=today().isoformat(), draft='Hi Aarav, what output does your line need?', paused=False)
    def respond(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(decision)}]}}]}).encode())
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-gemini-key')
    monkeypatch.setenv('OPENAI_API_KEY', 'unused-openai-key')
    monkeypatch.setattr(agent, 'urlopen', respond)
    lead, chats = store.get_lead(1)
    result, engine, warning = agent.analyze(lead, chats)
    assert engine == 'Gemini' and not warning and result.tag == 'Hot'
    request, timeout = calls[0]
    assert request.headers['X-goog-api-key'] == 'fake-gemini-key'
    assert 'fake-gemini-key' not in request.full_url
    body = json.loads(request.data)
    assert 'FreshBox Foods' in body['contents'][0]['parts'][0]['text']
    assert body['generationConfig']['responseMimeType'] == 'application/json'
    assert timeout == 20


@pytest.mark.parametrize('response_body', [
    {'candidates': [{'finishReason': 'MAX_TOKENS'}]},
    {'candidates': []},
    {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': '{invalid'}]}}]},
])
def test_gemini_invalid_response_falls_back(monkeypatch, response_body):
    import io
    import json
    import agent
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('GEMINI_API_KEY', 'fake')
    monkeypatch.setattr(agent, 'urlopen', lambda *a, **kw: io.BytesIO(json.dumps(response_body).encode()))
    lead, chats = store.get_lead(1)
    result, engine, warning = agent.analyze(lead, chats)
    assert result.tag == 'Hot' and engine == 'Local fallback' and warning


@pytest.mark.parametrize('status, expected', [(429, 'quota'), (402, 'prepaid credits')])
def test_gemini_quota_and_missing_key_do_not_switch_providers(monkeypatch, status, expected):
    import agent
    from urllib.error import HTTPError
    monkeypatch.setenv('AI_PROVIDER', 'gemini')
    monkeypatch.setenv('OPENAI_API_KEY', 'unused-openai-key')
    lead, chats = store.get_lead(1)
    result, engine, warning = agent.analyze(lead, chats)
    assert engine == 'Local rules' and 'key is missing' in warning
    monkeypatch.setenv('GEMINI_API_KEY', 'fake')
    def quota(*a, **kw):
        raise HTTPError('https://example.com', status, 'secret must not appear', {}, None)
    monkeypatch.setattr(agent, 'urlopen', quota)
    result, engine, warning = agent.analyze(lead, chats)
    assert engine == 'Local fallback' and expected in warning and 'secret' not in warning


def test_delete_removes_only_selected_lead_and_history():
    lead, _ = store.get_lead(1)
    with pytest.raises(ValueError, match='changed'):
        store.delete_lead(1, lead['revision'] - 1)
    assert len(store.get_lead(1)[1]) == 2
    store.delete_lead(1, lead['revision'])
    assert len(store.all_leads()) == 24
    with store.connect() as con:
        assert con.execute('SELECT COUNT(*) FROM chats WHERE lead_id=1').fetchone()[0] == 0
    assert len(store.get_lead(2)[1]) == 2
    with pytest.raises(ValueError, match='already been deleted'):
        store.delete_lead(1, lead['revision'])


def test_deleting_all_leads_does_not_reseed():
    for lead in store.all_leads():
        store.delete_lead(lead['id'], lead['revision'])
    store.initialize()
    assert store.all_leads() == []


def test_ui_delete_requires_confirmation():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    next(b for b in at.button if b.label == 'Delete lead permanently').click().run()
    assert len(store.all_leads()) == 25
    assert any('Confirm the checkbox' in e.value for e in at.error)
    next(c for c in at.checkbox if c.label.startswith('I understand')).check()
    next(b for b in at.button if b.label == 'Delete lead permanently').click().run()
    assert not at.exception
    assert len(store.all_leads()) == 24
    assert not any(l['id'] == 3 for l in store.all_leads())


def test_rep_lead_dropdown_filters_resets_and_opens_upcoming():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    assert len(at.selectbox(key='lead_picker').options) == 26  # All option plus 25 leads.
    at.selectbox(key='rep_filter').select('Asha').run()
    options = at.selectbox(key='lead_picker').options
    assert len(options) == 6
    assert any('Ishita Jain' in option for option in options)
    assert not any('Diya Patel' in option for option in options)
    # Ishita is upcoming, so picking her must open the All leads view.
    at.selectbox(key='lead_picker').select(6).run()
    assert not at.exception
    assert any(m.value == '### Ishita Jain' for m in at.markdown)
    assert any(h.value == 'All leads' for h in at.subheader)
    at.selectbox(key='rep_filter').select('Rohan').run()
    assert not at.exception
    assert at.selectbox(key='lead_picker').value is None
    assert any('Diya Patel' in option for option in at.selectbox(key='lead_picker').options)
    assert not any('Ishita Jain' in option for option in at.selectbox(key='lead_picker').options)


def test_deleted_lead_clears_dropdown_selection():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    at.selectbox(key='lead_picker').select(1).run()
    next(c for c in at.checkbox if c.label.startswith('I understand')).check()
    next(b for b in at.button if b.label == 'Delete lead permanently').click().run()
    assert not at.exception
    assert at.selectbox(key='lead_picker').value is None
    assert not any('Aarav Shah' in option for option in at.selectbox(key='lead_picker').options)


def test_failed_manual_reanalysis_preserves_saved_work(monkeypatch):
    import agent
    lead, chats = store.get_lead(1)
    store.save_draft(1, 'My carefully edited draft', lead['revision'])
    before, chats = store.get_lead(1)
    monkeypatch.setattr(store, 'analyze', lambda *a: (agent.local_decision(before, chats), 'Local fallback', 'Gemini prepaid credits are depleted.'))
    warning = store.reanalyze(1)
    after, _ = store.get_lead(1)
    assert 'were kept' in warning
    for field in ['draft', 'tag', 'reason', 'engine', 'next_followup']:
        assert before[field] == after[field]
    assert after['warning'] == warning


def test_ui_failed_reanalysis_shows_warning_instead_of_success(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    import agent
    monkeypatch.setattr(store, 'analyze', lambda lead, chats: (agent.local_decision(lead, chats), 'Local fallback', 'Gemini prepaid credits are depleted.'))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
    next(b for b in at.button if b.label == 'Re-analyze this lead').click().run()
    assert not at.exception
    assert any('prepaid credits' in w.value for w in at.warning)
    assert not any('Agent decision updated' in s.value for s in at.success)
