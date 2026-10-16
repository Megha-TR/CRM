"""SQLite transactions keep chats, decisions, and contact dates consistent."""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from agent import analyze, today
from sample_data import records


def db_path():
    return Path(os.getenv('CRM_DB_PATH', str(Path(__file__).parent / 'data' / 'crm.db')))


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def initialize():
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS app_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, company TEXT NOT NULL,
            phone TEXT NOT NULL, source TEXT NOT NULL, rep TEXT NOT NULL, last_contact TEXT NOT NULL,
            tag TEXT NOT NULL DEFAULT 'Warm', reason TEXT NOT NULL DEFAULT '',
            next_followup TEXT NOT NULL DEFAULT '', draft TEXT NOT NULL DEFAULT '',
            paused INTEGER NOT NULL DEFAULT 0, engine TEXT NOT NULL DEFAULT '',
            warning TEXT, revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id),
            sender TEXT NOT NULL CHECK(sender IN ('Rep','Buyer')), body TEXT NOT NULL,
            created_at TEXT NOT NULL);
        ''')
        if not con.execute("SELECT 1 FROM app_metadata WHERE key='seeded'").fetchone() and con.execute('SELECT COUNT(*) FROM leads').fetchone()[0] == 0:
            from agent import local_decision
            for lead, chats in records(today()):
                lead_id = insert_lead(con, lead)
                for msg in chats:
                    con.execute('INSERT INTO chats(lead_id,sender,body,created_at) VALUES (?,?,?,?)', (lead_id, msg['sender'], msg['body'], msg['created_at']))
                save_decision(con, lead_id, local_decision(lead, chats), 'Local rules', None)
        con.execute("INSERT OR IGNORE INTO app_metadata(key,value) VALUES ('seeded','1')")


def insert_lead(con, lead):
    return con.execute('INSERT INTO leads(name,company,phone,source,rep,last_contact) VALUES (?,?,?,?,?,?)', tuple(lead[k] for k in ['name','company','phone','source','rep','last_contact'])).lastrowid


def save_decision(con, lead_id, decision, engine, warning):
    con.execute('UPDATE leads SET tag=?,reason=?,next_followup=?,draft=?,paused=?,engine=?,warning=?,revision=revision+1 WHERE id=?',
                (decision.tag, decision.reason, decision.next_followup.isoformat(), decision.draft, decision.paused, engine, warning, lead_id))


def all_leads():
    with connect() as con:
        return [dict(row) for row in con.execute('SELECT * FROM leads')]


def get_lead(lead_id):
    with connect() as con:
        row = con.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
        chats = [dict(r) for r in con.execute('SELECT * FROM chats WHERE lead_id=? ORDER BY substr(created_at,1,10),id', (lead_id,))]
        return dict(row), chats


def reanalyze(lead_id, preserve_on_failure=True):
    lead, chats = get_lead(lead_id)
    decision, engine, warning = analyze(lead, chats)
    with connect() as con:
        current = con.execute('SELECT revision FROM leads WHERE id=?', (lead_id,)).fetchone()[0]
        if current != lead['revision']:
            raise ValueError('Lead changed in another session. Please retry.')
        if warning and preserve_on_failure:
            warning += ' Previous recommendation and draft were kept.'
            con.execute('UPDATE leads SET warning=?,revision=revision+1 WHERE id=?', (warning, lead_id))
        else:
            save_decision(con, lead_id, decision, engine, warning)
    return warning


def add_lead(lead, initial_chat=''):
    with connect() as con:
        lead_id = insert_lead(con, lead)
        if initial_chat.strip():
            con.execute('INSERT INTO chats(lead_id,sender,body,created_at) VALUES (?,?,?,?)', (lead_id, 'Buyer', initial_chat.strip(), lead['last_contact'] + 'T12:00:00'))
    reanalyze(lead_id, preserve_on_failure=False)
    return lead_id


def add_chat(lead_id, sender, body, contact):
    if not body.strip():
        raise ValueError('Enter a message first.')
    with connect() as con:
        con.execute('INSERT INTO chats(lead_id,sender,body,created_at) VALUES (?,?,?,?)', (lead_id, sender, body.strip(), contact.isoformat() + 'T12:00:00'))
        con.execute('UPDATE leads SET last_contact=MAX(last_contact,?),revision=revision+1 WHERE id=?', (contact.isoformat(), lead_id))
    reanalyze(lead_id, preserve_on_failure=False)


def save_draft(lead_id, draft, revision):
    with connect() as con:
        count = con.execute('UPDATE leads SET draft=?,revision=revision+1 WHERE id=? AND revision=?', (draft.strip(), lead_id, revision)).rowcount
        if not count:
            raise ValueError('Lead changed in another session. Reload before editing.')


def mark_sent(lead_id, draft, revision):
    if not draft.strip():
        raise ValueError('A sent message cannot be empty.')
    with connect() as con:
        lead = con.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
        if lead['paused']:
            raise ValueError('Outreach is paused for this buyer.')
        if lead['revision'] != revision:
            raise ValueError('Lead changed in another session. Reload before marking sent.')
        stamp = datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(timespec='seconds')
        con.execute('INSERT INTO chats(lead_id,sender,body,created_at) VALUES (?,?,?,?)', (lead_id,'Rep',draft.strip(),stamp))
        delay = {'Hot': 2, 'Warm': 7, 'Cold': 14}[lead['tag']]
        due = max(lead['next_followup'], (today() + timedelta(days=delay)).isoformat())
        con.execute('UPDATE leads SET last_contact=?,next_followup=?,draft=?,revision=revision+1 WHERE id=?', (today().isoformat(),due,draft.strip(),lead_id))


def delete_lead(lead_id, revision):
    """Delete the lead and its history atomically; reject stale confirmations."""
    with connect() as con:
        con.execute('BEGIN IMMEDIATE')
        lead = con.execute('SELECT revision FROM leads WHERE id=?', (lead_id,)).fetchone()
        if lead is None:
            raise ValueError('This lead has already been deleted. Reload the app.')
        if lead['revision'] != revision:
            raise ValueError('Lead changed in another session. Reload before deleting.')
        con.execute('DELETE FROM chats WHERE lead_id=?', (lead_id,))
        con.execute('DELETE FROM leads WHERE id=?', (lead_id,))
