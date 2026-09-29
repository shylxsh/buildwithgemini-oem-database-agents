# Local Setup & Architecture Guide

This guide provides a comprehensive breakdown of each script and directory in this repository, along with step-by-step instructions to run the entire project locally on your own machine (Mac, Linux, or Windows via WSL) without needing any cloud workstation.

---

## 1. Repository Architecture & Script Breakdown

```
.
├── mock_db/
│   ├── data/
│   │   └── projects.json            # Persistent JSON database storage
│   └── server.py                    # FastAPI mock database REST service (Port 8001)
│
├── power-fetch/                     # The Query & Discovery Agent
│   ├── app/
│   │   ├── agent.py                 # Core agent definition, ADK tools & logic
│   │   ├── fast_api_app.py          # A2A / Agent Platform FastAPI entrypoint
│   │   └── app_utils/               # A2A protocol helpers and services
│   ├── static/
│   │   └── index.html               # Web UI (Clickable pills, chat, JSON viewer)
│   ├── frontend_app.py              # Local Web UI bridge server (Port 8080)
│   ├── pyproject.toml               # Python dependencies and agent metadata
│   └── .env.example                 # Environment variable template
│
├── power-store/                     # The Knowledge Ingestion & Storage Agent
│   ├── app/
│   │   ├── agent.py                 # Core agent definition, Wikipedia tools & commit guardrails
│   │   ├── fast_api_app.py          # A2A / Agent Platform FastAPI entrypoint
│   │   └── app_utils/               # A2A protocol helpers and services
│   ├── pyproject.toml               # Python dependencies and agent metadata
│   └── .env.example                 # Environment variable template
│
└── project_brief.md                 # Design specifications & database contracts
```

### Detailed Script Breakdown

| Script / File | Role & Purpose | Key Endpoints / Functions |
| :--- | :--- | :--- |
| **`mock_db/server.py`** | Serves as the central REST database holding OEM car projects and collections. Handles queries, record insertions, and fuzzy search across records. Writes to `mock_db/data/projects.json`. | • `GET /projects`<br>• `POST /projects`<br>• `GET /projects/{project_id}/{collection_name}/{record}`<br>• `POST /projects/{project_id}/{collection_name}/{record}`<br>• `GET /search?q={query}` |
| **`mock_db/data/projects.json`** | JSON store with OEM projects (`tata-nexon-ev`, `skoda-kushaq`, `mahindra-xuv700`, `mahindra-thar`). Each has collections: `details`, `git`, and `manifest`. | Stores raw documents. |
| **`power-fetch/app/agent.py`** | Defines the `power_fetch_agent`. Implements tools to list projects, fetch records, synthesize summaries, cite exact API endpoints, tag fuzzy searches, and maintain conversational memory across turns. | • `list_projects()`<br>• `get_project_collections(project_id)`<br>• `list_collection_records(project_id, collection_name)`<br>• `fetch_record(project_id, collection_name, record)`<br>• `fuzzy_match_query(query)` |
| **`power-fetch/frontend_app.py`** | Local FastAPI server serving the dedicated chat web interface on port 8080. Bridges user prompts into the ADK local runner, executes the agent, and extracts the cited endpoint and raw JSON for the UI card. | • `GET /`<br>• `GET /api/projects`<br>• `POST /chat` |
| **`power-fetch/static/index.html`** | Single-page modern frontend with interactive project pills, chat bubble history, complex query badges, and collapsible JSON document viewers. | Client-side UI. |
| **`power-store/app/agent.py`** | Defines the `power_store_agent`. Integrates with the official Wikipedia API, parses unstructured knowledge into structured schema, stages draft JSON records, and mandates explicit user approval before persisting to `mock_db`. | • `fetch_wikipedia_data(topic_or_url)`<br>• `prepare_draft_record(...)`<br>• `commit_record_to_db(...)` |

---

## 2. Prerequisites for Local Execution

1. **Git**
2. **Python 3.11, 3.12, or 3.13**
3. **Google Agents CLI (`agents-cli`)** or `uv` / standard `pip`
4. **Google Gemini API Key or GCP Credentials**:
   - Option A (**Easiest**): A Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/).
   - Option B: Google Cloud Vertex AI credentials via `gcloud auth application-default login`.

---

## 3. Step-by-Step Local Setup Guide

### Step 1: Clone the Repository
```bash
git clone https://github.com/shylxsh/buildwithgemini-oem-database-agents.git
cd buildwithgemini-oem-database-agents
```

### Step 2: Create and Activate a Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 3: Install Dependencies
Install the required packages for the database, agents, and web UI:
```bash
pip install fastapi uvicorn httpx python-dotenv sse-starlette google-adk google-genai
```
*(Alternatively, install the `agents-cli` tool globally: `pip install google-agents-cli`)*

### Step 4: Configure Environment Variables
You need credentials for Gemini. In both `power-fetch/` and `power-store/`, configure the `.env` file:

**Using Gemini API Key (Google AI Studio - Recommended for local machines):**
Create `power-fetch/.env` and `power-store/.env`:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

**Using Google Cloud Vertex AI:**
```ini
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=global
```

---

## 4. How to Run Everything Locally

### Terminal 1: Start the Mock Database Service (Port 8001)
From the repository root:
```bash
source .venv/bin/activate
python3 -m uvicorn mock_db.server:app --host 127.0.0.1 --port 8001 --reload
```
- API Docs will be live at: `http://127.0.0.1:8001/docs`
- Health check: `curl http://127.0.0.1:8001/projects`

---

### Terminal 2: Run the `power-fetch` Agent & Web UI (Port 8080)
In a new terminal window:
```bash
cd power-fetch
source ../.venv/bin/activate
python3 frontend_app.py
```
- Open your browser at: **`http://localhost:8080`**
- You will see the clickable OEM project pills (`TATA`, `SKODA`, `Mahindra`), chat interface, and final details cards.
- **CLI Alternative**: You can also run the agent purely in your terminal:
  ```bash
  agents-cli run "Show me the details for Tata Nexon EV"
  ```

---

### Terminal 3: Run the `power-store` Agent
In a third terminal window:
```bash
cd power-store
source ../.venv/bin/activate
```

#### Running queries with `power-store`:
```bash
agents-cli run "Fetch information about Hyundai Creta from Wikipedia and prepare to store its details overview in the database."
```
1. The agent fetches data from Wikipedia and generates a draft JSON document.
2. It stops and asks:
   > *"Do you approve storing this document into the database? Please reply YES to commit or specify changes."*
3. Notice the session ID output in your terminal (e.g. `--session-id <SESSION_ID>`).
4. Approve and commit the record:
   ```bash
   agents-cli run "YES" --session-id <SESSION_ID>
   ```
5. Check your `mock_db` database — the new car is immediately stored and queryable!

---

## 5. Troubleshooting & Tips

- **Database Connection**: Ensure `mock_db` is running on port `8001` before starting `power-fetch` or `power-store`.
- **Port Conflicts**: If port `8080` or `8001` is already in use on your machine, you can change the port in `uvicorn.run(..., port=...)` or set `PORT=8081 python3 frontend_app.py`.
- **Checking Stored Data**: You can inspect or reset stored data at any time by viewing or editing [`mock_db/data/projects.json`](mock_db/data/projects.json).
