"""TaskPilot: deployed-friendly Streamlit AI agent."""
from __future__ import annotations
import json
import os
from pathlib import Path
import streamlit as st
from actions import DATA_DIR, LOG_PATH, WORKSPACE, audit, execute, setup
from agent import AgentError, offline_plan, plan_with_llm

st.set_page_config(page_title='TaskPilot | AI Action Agent', page_icon='🤖', layout='wide')
setup()
st.markdown('''<style>
.block-container {padding-top: 2rem; max-width: 1140px;}
.hero {border: 1px solid #3b4967; background: linear-gradient(110deg,#101a31,#233a58); border-radius:18px; padding:27px 30px;color:#f5f8ff;margin-bottom:20px;}
.hero h1 {font-size:2.2rem; margin:0 0 5px 0; color:#f5f8ff;}
.hero p {margin:0;color:#cbd5e1;}
.small {font-size:0.87rem; opacity:.8}
</style>''', unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🤖 TaskPilot AI Agent</h1><p>From natural-language requests to validated, real-world actions · CS4680 Project</p></div>', unsafe_allow_html=True)


def secret(name: str, default: str = '') -> str:
    try:
        return str(st.secrets.get(name, os.environ.get(name, default)))
    except (FileNotFoundError, KeyError):
        return os.environ.get(name, default)

if 'history' not in st.session_state:
    st.session_state.history = []
if 'pending' not in st.session_state:
    st.session_state.pending = []

with st.sidebar:
    st.header('⚙️ Agent settings')
    saved_key = secret('OPENAI_API_KEY')
    provided_key = st.text_input('OpenAI API key', type='password', help='Optional when key is configured as a Streamlit secret. Never commit it to GitHub.')
    api_key = provided_key.strip() or saved_key
    mode = st.radio('Mode', ['OpenAI LLM', 'Offline demo'], index=0 if api_key else 1,
                    help='Offline demo uses simple rules; LLM mode makes a real API request.')
    model = st.selectbox('OpenAI model', ['gpt-4o-mini', 'gpt-4o'], index=0)
    st.caption('🟢 Real LLM connected' if mode == 'OpenAI LLM' and api_key else '🟡 Offline demonstration / API key needed')
    st.divider()
    st.markdown('**Example requests**')
    st.code('Calculate (25 + 15) * 3\nList my files\nCreate a file named tasks.md with a study checklist\nSave a note about my CS4680 deadline\nWhat is the weather in Pomona?')
    st.caption('For offline mode: calculate (25+15)*3; create file: tasks.md | Study tonight; save note: review chapter 3; list files; delete file: tasks.md')
    st.divider()
    st.caption('Actions are restricted to a local workspace, notes database, calculator, and public weather lookup. Deletions always require confirmation.')

chat_tab, files_tab, notes_tab, log_tab, help_tab = st.tabs(['💬 Agent', '📁 Workspace', '🗒️ Notes', '🧾 Audit log', '📘 Help'])

with chat_tab:
    st.subheader('Ask the agent to do something')
    st.caption('The LLM creates a structured JSON action plan. Python validates and executes each approved action.')
    for entry in st.session_state.history:
        with st.chat_message(entry['role']):
            st.markdown(entry['text'])
    if st.session_state.pending:
        st.warning('⚠️ A destructive action is awaiting confirmation. Review the filename before proceeding.')
        for i, pending in enumerate(st.session_state.pending):
            st.code(json.dumps(pending, indent=2))
        left, right = st.columns(2)
        if left.button('✅ Confirm delete', use_container_width=True, type='primary'):
            results = [execute(item['type'], item['args'], confirmed_delete=True) for item in st.session_state.pending]
            st.session_state.history.append({'role': 'assistant', 'text': '**Confirmation results:**\n\n' + '\n\n'.join(results)})
            st.session_state.pending = []
            st.rerun()
        if right.button('❌ Cancel deletion', use_container_width=True):
            for item in st.session_state.pending:
                audit(item['type'], item['args'], 'cancelled', 'User declined deletion')
            st.session_state.pending = []
            st.session_state.history.append({'role': 'assistant', 'text': 'Deletion cancelled. No files were deleted.'})
            st.rerun()
    user_prompt = st.chat_input('Example: Create a file named plan.md with a three-step study plan', disabled=bool(st.session_state.pending))
    if user_prompt:
        st.session_state.history.append({'role': 'user', 'text': user_prompt})
        try:
            if mode == 'OpenAI LLM':
                if not api_key:
                    raise AgentError('Enter an OpenAI API key or select Offline demo.')
                with st.spinner('LLM planning actions...'):
                    plan = plan_with_llm(user_prompt, api_key, model)
            else:
                plan = offline_plan(user_prompt)
            output = [plan['message']]
            output.append('**Validated action plan:**')
            if plan['actions']:
                output.append('```json\n' + json.dumps(plan['actions'], indent=2, ensure_ascii=False) + '\n```')
            else:
                output.append('No action requested.')
            for action in plan['actions']:
                if action['type'] == 'delete_file':
                    st.session_state.pending.append(action)
                    output.append(f"⏸️ **Awaiting confirmation:** delete `{action['args'].get('filename', '')}`")
                else:
                    result = execute(action['type'], action['args'])
                    output.append(('✅' if not result.startswith('ERROR:') else '❌') + ' ' + result)
            st.session_state.history.append({'role': 'assistant', 'text': '\n\n'.join(output)})
        except AgentError as exc:
            audit('llm_request', {}, 'error', str(exc))
            st.session_state.history.append({'role': 'assistant', 'text': f'❌ {exc}'})
        except Exception as exc:
            audit('agent_request', {}, 'error', type(exc).__name__)
            st.session_state.history.append({'role': 'assistant', 'text': f'❌ Unexpected error: {type(exc).__name__}. Check server logs.'})
        st.rerun()

with files_tab:
    st.subheader('Workspace files')
    paths = sorted(p for p in WORKSPACE.rglob('*') if p.is_file() and not p.is_symlink())
    if not paths:
        st.info('No files yet. Ask the agent to create one.')
    for path in paths[:100]:
        rel = path.relative_to(WORKSPACE)
        with st.expander(f'📄 {rel} ({path.stat().st_size} bytes)'):
            if path.stat().st_size <= 50000:
                st.code(path.read_text(encoding='utf-8'), language='text')
            st.download_button('Download file', data=path.read_bytes(), file_name=path.name, key=f'dl_{rel}')
    st.caption('Files live in the server workspace. Streamlit Community Cloud may erase these files when the app restarts.')

with notes_tab:
    st.subheader('Saved notes (SQLite)')
    import sqlite3
    with sqlite3.connect(DATA_DIR / 'agent.db') as db:
        rows = db.execute('SELECT id,title,body,created_at FROM notes ORDER BY id DESC LIMIT 100').fetchall()
    if not rows:
        st.info('No notes yet. Ask the agent to add a note.')
    for note_id, title, body, created in rows:
        with st.expander(f'#{note_id} · {title}'):
            st.write(body)
            st.caption(created)
    st.caption('For a production multi-user service, replace local SQLite storage with a persistent database and add authentication.')

with log_tab:
    st.subheader('Action audit trail')
    if LOG_PATH.exists():
        logs = []
        for line in LOG_PATH.read_text(encoding='utf-8').splitlines()[-100:]:
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        if logs:
            st.dataframe(list(reversed(logs)), use_container_width=True, hide_index=True)
            st.download_button('Download audit log', LOG_PATH.read_bytes(), 'audit.jsonl', mime='application/json')
        else:
            st.info('No entries yet.')
    else:
        st.info('Actions will appear here after your first request.')

with help_tab:
    st.subheader('How this application works')
    st.markdown('''**1. Request → 2. LLM → 3. JSON plan → 4. Validation → 5. Executor → 6. Audit log**

**Available actions**: create/read/list/delete text files, save/list/search notes (SQLite), safe arithmetic, and current weather (Open-Meteo public API).

**Safety controls**: allowlisted tools, restricted file extensions, path traversal protection, no shell execution, maximum content sizes, confirmation before deletes, and logging of successes/failures/cancellations.

**Real AI vs demonstration**: OpenAI LLM mode uses an API request to interpret free-form language. Offline demo is explicitly rule-based and is included so the UI can be previewed without paid API access.

**Cloud deployment**: Add your OpenAI key in Streamlit Community Cloud app secrets as `OPENAI_API_KEY = "..."`. Do not put a key in any GitHub file.

**Important limitations**: weather calls require internet; real LLM calls may incur charges; the online hosting filesystem and SQLite database are temporary and shared among app visitors. Avoid uploading personal or confidential content.''')
