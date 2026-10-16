import csv
import io
import os
from datetime import date
import streamlit as st
from agent import today, provider_settings
from sample_data import REPS
import store

st.set_page_config(page_title='FollowUp • Sales desk', page_icon='◉', layout='wide')
store.initialize()
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1500px}
.st-key-summary_cards button{min-height:100px;background:white;border:1px solid #d9e2ed;text-align:left}
.st-key-summary_cards button p{white-space:pre-line;font-size:20px;font-weight:600}
.st-key-summary_cards button[kind="primary"]{background:#0f766e;color:white;border-color:#0f766e}
.temperature{display:inline-block;padding:4px 12px;border-radius:20px;font-weight:700;font-size:14px;margin:4px 0 8px}
.temperature-hot{color:#b91c1c;background:#fee2e2;border:1px solid #fca5a5}
.temperature-warm{color:#854d0e;background:#fef9c3;border:1px solid #facc15}
.temperature-cold{color:#1d4ed8;background:#dbeafe;border:1px solid #93c5fd}
[class*="st-key-hot_lead_"]{border-left:4px solid #dc2626!important}
[class*="st-key-warm_lead_"]{border-left:4px solid #eab308!important}
[class*="st-key-cold_lead_"]{border-left:4px solid #2563eb!important}
h1{letter-spacing:-1.5px} .stButton>button{border-radius:8px}
</style>''', unsafe_allow_html=True)


COLORS = {'Hot': '🔴', 'Warm': '🟡', 'Cold': '🔵'}


def temperature_badge(tag):
    # Only fixed enum values enter this HTML, never buyer-provided content.
    if tag in COLORS:
        st.markdown(f'<span class="temperature temperature-{tag.lower()}">{tag}</span>', unsafe_allow_html=True)


def choose_view(view):
    st.session_state['lead_view'] = view
    st.session_state.pop('selected_id', None)


def refresh(message):
    st.session_state['notice'] = message
    st.rerun()


def perform(action, message):
    try:
        action()
        refresh(message)
    except ValueError as exc:
        st.error(str(exc))


with st.sidebar:
    st.markdown('## ◉ FollowUp')
    st.caption('PACKAGING EQUIPMENT · SALES DESK')
    rep = st.selectbox('Sales rep', ['All reps'] + REPS)
    search = st.text_input('Search leads', placeholder='Name, company or phone')
    tag_filter = st.multiselect('Temperature', ['Hot', 'Warm', 'Cold'], format_func=lambda tag: f'{COLORS[tag]} {tag}')
    st.divider()
    st.caption('AI mode')
    provider, api_key, _ = provider_settings()
    st.write(f'{provider.title()} configured' if api_key else 'Local rules · no API key')
    st.caption('Each lead shows which engine generated its decision. AI runs on new leads, new chats, and re-analysis. Sample data starts with local decisions.')
    st.caption('Dates use Asia/Kolkata. Data persists in local SQLite.')
    st.caption('Demo data is fictional. No messages are actually sent.')

st.title('Your next conversation starts here.')
st.caption(f'{today().strftime("%A, %d %B %Y")} · Follow up with the right buyer, at the right time.')
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))
leads = store.all_leads()
filtered = [l for l in leads if (rep == 'All reps' or l['rep'] == rep)
            and (not tag_filter or l['tag'] in tag_filter)
            and (not search or search.lower() in ' '.join([l['name'], l['company'], l['phone']]).lower())]
active = [l for l in filtered if not l['paused']]
today_str = today().isoformat()
due = [l for l in active if l['next_followup'] <= today_str]
# Overdue first, then buying intent, then oldest deadline.
due.sort(key=lambda l: (l['next_followup'] > today_str, l['next_followup'] == today_str, {'Hot': 0, 'Warm': 1, 'Cold': 2}[l['tag']], l['next_followup'], l['id']))
views = {
    'Due now': due,
    'Overdue': [l for l in due if l['next_followup'] < today_str],
    'Hot leads': [l for l in active if l['tag'] == 'Hot'],
    'Active leads': active,
    'All leads': filtered,
}
view = st.session_state.get('lead_view', 'Due now')
with st.container(key='summary_cards'):
    metrics = st.columns(4)
    for col, label in zip(metrics, ['Due now', 'Overdue', 'Hot leads', 'Active leads']):
        col.button(f'{label}\n\n{len(views[label])}', key=f'view_{label}',
                   type='primary' if view == label else 'secondary', use_container_width=True,
                   on_click=choose_view, args=(label,))
st.caption(f"{len(leads)} total leads · {sum(not l['paused'] for l in leads)} active · {sum(bool(l['paused']) for l in leads)} paused. Cards respect your sidebar filters; Due now includes overdue follow-ups.")
st.markdown(' '.join(
    f'<span class="temperature temperature-{tag.lower()}">{tag} · {sum(l["tag"] == tag for l in leads)}</span>'
    for tag in COLORS
), unsafe_allow_html=True)
st.button('Show all leads', on_click=choose_view, args=('All leads',))
visible = sorted(views[view], key=lambda l: (l['paused'], l['next_followup'] > today_str, l['next_followup'] == today_str, {'Hot': 0, 'Warm': 1, 'Cold': 2}[l['tag']], l['next_followup'], l['id']))
# Default queue also provides a directory to open upcoming and paused leads.
directory = filtered if view == 'Due now' else visible

with st.expander('＋ Add a new lead'):
    with st.form('new_lead', clear_on_submit=True):
        a, b = st.columns(2)
        name = a.text_input('Buyer name *', max_chars=100)
        company = b.text_input('Company *', max_chars=150)
        phone = a.text_input('Phone *', max_chars=30)
        source = b.selectbox('Source', ['WhatsApp', 'Excel', 'Referral', 'Website', 'Other'])
        owner = a.selectbox('Assigned rep', REPS)
        last_contact = b.date_input('Last contact date', max_value=today())
        initial = st.text_area('Initial buyer message (optional)', max_chars=5000)
        if st.form_submit_button('Create lead & run agent', type='primary'):
            digits = ''.join(c for c in phone if c.isdigit())
            if not name.strip() or not company.strip() or not (7 <= len(digits) <= 15):
                st.error('Enter a buyer name, company, and phone with 7–15 digits.')
            else:
                with st.spinner('Creating lead…'):
                    new_id = store.add_lead(dict(name=name.strip(), company=company.strip(), phone=phone.strip(), source=source, rep=owner, last_contact=last_contact.isoformat()), initial)
                    st.session_state['selected_id'] = new_id
                    refresh('Lead created. Clear filters if it is not visible in your current view.')


queue, detail = st.columns([1.05, 1.25], gap='large')
with queue:
    st.subheader('Today’s follow-ups' if view == 'Due now' else view)
    st.caption(f'{len(visible)} leads shown · Overdue first · Hot → Warm → Cold · oldest deadline within each group')
    with st.container(height=640, border=False):
        if not visible:
            st.info('No leads match this view. Choose another card or adjust the sidebar filters.')
        for item in visible:
            with st.container(border=True, key=f'{item["tag"].lower()}_lead_{item["id"]}'):
                overdue = (today() - date.fromisoformat(item['next_followup'])).days
                if item['paused']:
                    st.warning('OUTREACH PAUSED')
                elif overdue > 0:
                    st.error(f'OVERDUE · {overdue} day{"s" if overdue != 1 else ""} · {item["next_followup"]}', icon='⚠️')
                elif overdue == 0:
                    st.info('DUE TODAY', icon='🕒')
                else:
                    st.caption(f'UPCOMING · {item["next_followup"]}')
                st.markdown(f'**{item["name"]} · {item["company"]}**')
                temperature_badge(item['tag'])
                st.caption(f'{item["rep"]} · {item["source"]}')
                st.write(item['reason'])
                if st.button('Open lead →', key=f'open_{item["id"]}', use_container_width=True):
                    st.session_state['selected_id'] = item['id']
                    st.rerun()
        with st.expander('Lead directory · upcoming & paused' if view == 'Due now' else 'Lead directory · current view', expanded=not visible):
            for item in sorted(directory, key=lambda l: (l['paused'], l['next_followup'])):
                state = 'Paused' if item['paused'] else f'Due {item["next_followup"]}'
                if st.button(f'{item["name"]} · {item["company"]} | {COLORS[item["tag"]]} {item["tag"]} | {state}', key=f'all_{item["id"]}', use_container_width=True):
                    st.session_state['selected_id'] = item['id']
                    st.rerun()
            if not directory:
                st.info('No leads match these filters.')

with detail:
    st.subheader('Lead workspace')
    ids = [l['id'] for l in directory]
    selected = st.session_state.get('selected_id')
    if selected not in ids:
        selected = visible[0]['id'] if visible else (ids[0] if ids else None)
    if selected is None:
        st.info('Add a lead below or change your filters to get started.')
    else:
        lead, chats = store.get_lead(selected)
        st.markdown(f'### {lead["name"]}')
        st.write(f'{lead["company"]} · {lead["phone"]}')
        st.caption(f'Owner: {lead["rep"]} · Source: {lead["source"]} · Last contact: {lead["last_contact"]}')
        temperature_badge(lead['tag'])
        st.write(lead['reason'])
        st.caption(f'Next follow-up: {lead["next_followup"]} · Decision: {lead["engine"]}')
        if lead['warning']:
            st.warning(lead['warning'])
        if lead['paused']:
            st.warning('Outreach paused: buyer declined or asked to stop. A new buyer message can update this decision.')
        with st.expander(f'Conversation · {len(chats)} messages', expanded=True):
            if not chats:
                st.caption('No conversation yet. Add a buyer message to give the agent more context.')
            for chat in chats:
                with st.chat_message('user' if chat['sender'] == 'Buyer' else 'assistant'):
                    st.caption(f'{chat["sender"]} · {chat["created_at"][:16].replace("T", " ")}')
                    st.write(chat['body'])
        with st.form(f'draft_{selected}_{lead["revision"]}'):
            draft = st.text_area('Next follow-up message', value=lead['draft'], height=130, disabled=bool(lead['paused']), max_chars=1500)
            st.caption('Edit before using. “Mark as sent” logs the message and schedules the next check-in; it does not send WhatsApp.')
            c1, c2 = st.columns(2)
            save = c1.form_submit_button('Save draft', use_container_width=True, disabled=bool(lead['paused']))
            sent = c2.form_submit_button('Mark as sent', type='primary', use_container_width=True, disabled=bool(lead['paused']))
            if save:
                perform(lambda: store.save_draft(selected, draft, lead['revision']), 'Draft saved.')
            if sent:
                perform(lambda: store.mark_sent(selected, draft, lead['revision']), 'Message logged as sent. Next follow-up scheduled.')
        with st.expander('Add a chat message'):
            with st.form(f'chat_{selected}', clear_on_submit=True):
                sender = st.selectbox('Sender', ['Buyer', 'Rep'])
                contact = st.date_input('Message date', value=today(), max_value=today())
                body = st.text_area('Message', max_chars=5000)
                if st.form_submit_button('Add chat & update agent', type='primary'):
                    with st.spinner('Updating this lead…'):
                        perform(lambda: store.add_chat(selected, sender, body, contact), 'Chat added and lead updated.')
        st.caption('Re-analysis replaces the draft with a fresh suggestion. Save or copy edits first.')
        if st.button('Re-analyze this lead', key=f'analyze_{selected}'):
            with st.spinner('Reading lead and conversation…'):
                perform(lambda: store.reanalyze(selected), 'Agent decision updated.')


buffer = io.StringIO()
writer = csv.DictWriter(buffer, fieldnames=list(leads[0].keys()) if leads else ['id'])
writer.writeheader()
# Prevent spreadsheet formula execution in exported user-controlled text.
for row in leads:
    writer.writerow({k: ("'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v) for k, v in row.items()})
st.download_button('Export all leads (CSV)', buffer.getvalue(), 'followup-leads.csv', 'text/csv')
