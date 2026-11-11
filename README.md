# TaskPilot AI Agent — CS4680 Assignment 4

A Streamlit AI agent that uses an OpenAI large language model to translate natural-language requests into **validated, executable actions**. It includes a safe file workspace, SQLite notes, arithmetic, Open-Meteo weather lookup, destructive-operation confirmation, and an audit trail.

> **For class/demo purposes:** This is a working prototype, not a secure multi-user production service. The online deployment shares one temporary workspace and database across visitors. Do not save confidential data.

## Requirements mapping

| Professor's requirement | Implementation |
|---|---|
| LLM API with prompt and response | `agent.py`: `plan_with_llm()` uses OpenAI chat completions, JSON response mode |
| API errors and rate limits | `agent.py`: OpenAI exception handling and retry settings |
| Parse LLM commands | `agent.py`: `validate_plan()` checks JSON shape and action allowlist |
| Execute concrete actions | `actions.py`: files, SQLite, safe arithmetic, Open-Meteo public REST API |
| Natural-language UI & status | `app.py`: Streamlit chat, action plans, feedback, tabs |
| Validation/safety | restricted workspace, no shell execution, limits, delete confirmation |
| Audit logging | `actions.py`: `audit()` stores timestamps, outcomes, sanitized arguments |
| Prompt engineering | `SYSTEM_PROMPT`: role, output format, tool schema, constraints, examples |

## Local setup (Windows)

1. Download and extract the ZIP file.
2. Install **Python 3.11 or 3.12** from https://www.python.org/downloads/ and check **Add Python to PATH**.
3. Open the extracted `CS4680_AI_Agent_Project` folder in File Explorer. Click the folder address bar, type `powershell`, and press Enter.
4. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

5. Install dependencies (you do not need to activate the venv):

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

6. Run tests:

   ```powershell
   .\.venv\Scripts\python.exe tests.py
   ```

7. Start the app:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

8. Open http://localhost:8501 if the app did not open automatically. Select **Offline demo** to test without API access.
9. To enable the real AI, generate a key from https://platform.openai.com/api-keys and paste it into the sidebar **OpenAI API key** field. Choose **OpenAI LLM**. API billing/quota is separate from ChatGPT subscriptions. You may also set a local environment variable `OPENAI_API_KEY`, but never commit the key to GitHub.

### Mac/Linux terminal

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tests.py
python -m streamlit run app.py
```

## Try these requests (LLM mode)

- `Calculate (25 + 15) * 3`
- `Create a file called study_plan.md with a checklist for preparing for an AI exam`
- `List my files`
- `Read study_plan.md`
- `Save a note titled Project Deadline reminding me to record my demo`
- `List my notes`
- `Search my notes for demo`
- `What is the current weather in Pomona?`
- `Delete study_plan.md` (confirm via the UI; demonstrate cancel first)

For **Offline demo mode**, use exact formats: `calculate (25+15)*3`, `create file: todo.md | Finish homework`, `read file: todo.md`, `list files`, `save note: Study at 6 PM`, `list notes`, `search notes: Study`, `delete file: todo.md`, `weather in Pomona`. Offline mode uses rules, **not an LLM**, and should not be presented as a live AI request.

## GitHub publishing (without Git)

1. Sign in to https://github.com and choose **New repository**.
2. Name it `cs4680-taskpilot-ai-agent`, choose Public if your course requires an accessible link, and click **Create repository**.
3. Choose **uploading an existing file**.
4. Upload `app.py`, `agent.py`, `actions.py`, `requirements.txt`, `README.md`, `tests.py`, `.gitignore`, `.env.example`, the `.streamlit/config.toml` file (GitHub's browser uploader may require creating the `.streamlit` folder via Git or web editor), and documentation files.
5. **Do not upload**: `.venv/`, `.env` with real credentials, `agent_data/`, `secrets.toml`, or your real API key.
6. Commit changes and copy your repository URL: `https://github.com/YOUR_USERNAME/cs4680-taskpilot-ai-agent`.

### GitHub publishing (recommended Git commands)

From the project folder:

```bash
git init
git add .
git commit -m "Complete CS4680 AI agent project"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/cs4680-taskpilot-ai-agent.git
git push -u origin main
```

Create the empty GitHub repository first; sign in when Git prompts you. Avoid committing credentials.

## Deploy on Streamlit Community Cloud

1. Visit https://share.streamlit.io and sign in with GitHub.
2. Select **Create app** (or **New app**) → **Deploy a public app from GitHub**.
3. Select your repository, branch `main`, and app entrypoint file `app.py`.
4. In the deployment settings, open **Advanced settings** and set the Python version if offered (3.11 or 3.12 recommended).
5. Under **Secrets**, add:

   ```toml
   OPENAI_API_KEY = "YOUR_ACTUAL_API_KEY"
   ```

   **Do this only in Streamlit's secrets panel, never in GitHub.**
6. Click **Deploy**. When the build finishes, copy the URL, typically `https://YOUR-APP-NAME.streamlit.app`.
7. Visit the app in a private/incognito browser window. Switch to OpenAI LLM, try one command, and verify the output and Audit log.
8. If deployment fails, open **Manage app → Logs** and check for missing packages, API key configuration, or account quota errors.

**Note:** The cloud app's files and SQLite data are ephemeral, can be shared with all visitors, and may disappear when the instance restarts. This is appropriate for a classroom demo but not production. Do not put sensitive data into the public demo.

## Demo video (1–2 minutes)

See `DEMO_SCRIPT.md`. Record your screen using OBS Studio, Windows Snipping Tool screen recorder, or Zoom. You can upload an unlisted video to YouTube, then submit its shareable URL.

## Submission

Your assignment asks for **three URLs**: repository URL, deployed app URL, and 1–2 minute demo video URL. Submit them through https://forms.gle/nMHp5owwYidszwt58 (confirm the due date in Canvas). `SUBMISSION_CHECKLIST.md` includes a fill-in template.

## Architecture

```text
User message (Streamlit UI)
    |
    v
OpenAI LLM + SYSTEM_PROMPT (or clearly labeled offline demo parser)
    |
    v
Structured JSON: {message, actions: [{type, args}]}
    |
    v
validate_plan: JSON shape, 5-action maximum, allowlist
    |
    v
Python action executor -> file workspace / SQLite / calculator / weather API
    |                    -> delete requires confirmation
    v
Result in chat + audit.jsonl
```

## Project files

- `app.py` — Streamlit UI, interaction, confirmations, tabs
- `agent.py` — LLM integration, prompt engineering, JSON extraction, offline parser
- `actions.py` — safe tools, database, network weather, audit logging
- `tests.py` — offline tests for action execution and safety
- `requirements.txt` — deployment dependencies
- `.streamlit/config.toml` — dark theme
- `.gitignore` — credential/data exclusions
- `.env.example` — key naming example only
- `DEMO_SCRIPT.md` — presentation script with timings
- `SUBMISSION_CHECKLIST.md` — final review

## Security and limitations

1. Only the nine documented tools are accepted. No arbitrary terminal command or system-control capability is provided.
2. File operations are limited to the generated `agent_data/workspace/` folder; only `.txt`, `.md`, `.csv`, `.json` extensions are allowed. New files cannot overwrite existing files. Symlink and traversal escaping is blocked.
3. Deleting any file requires explicit user approval.
4. Calculator uses an AST allowlist, not `eval`.
5. Audit entries record sanitized parameters and outcomes without storing note/file bodies.
6. Online accounts are not isolated; Streamlit hosted storage is ephemeral; no sign-in or per-user authentication is implemented. For production, add authentication, per-user scoped storage, durable database and limits.
7. API requests may fail because of rate limits, credits, or connectivity. Weather data require network availability.
8. Calls to OpenAI were **not** validated using a paid API key during packaging. Configure your own key and verify on your deployed app before turning in.
