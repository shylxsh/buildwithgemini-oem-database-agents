# ruff: noqa
import json
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse
import urllib.error

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

MODEL = "gemini-3.6-flash"
DB_BASE_URL = "http://127.0.0.1:8001"


def _http_get(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Helper to perform HTTP GET requests."""
    default_headers = {"User-Agent": "power-store-agent/1.0 (test-workshop-agent)"}
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": body}
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}


def _http_post(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to perform HTTP POST requests to the mock database service."""
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={
            "User-Agent": "power-store-agent/1.0",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": body}
    except Exception as e:
        return {"error": f"POST failed: {str(e)}"}


def fetch_wikipedia_data(topic_or_url: str) -> Dict[str, Any]:
    """Fetch article summary, extract, and metadata from the official Wikipedia REST API.
    
    Args:
        topic_or_url: The title of the Wikipedia page (e.g. 'Mahindra_Thar', 'Hyundai_Creta', 'Tata_Curvv') or a full Wikipedia URL.
        
    Returns:
        Structured Wikipedia page data including title, description, extract, and page URLs.
    """
    clean_title = topic_or_url.strip()
    if "wikipedia.org/wiki/" in clean_title:
        clean_title = clean_title.split("wikipedia.org/wiki/")[-1].split("#")[0].split("?")[0]
    
    clean_title = clean_title.replace(" ", "_")
    encoded_title = urllib.parse.quote(clean_title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
    res = _http_get(url)
    if "error" in res:
        return {
            "status": "error",
            "message": f"Could not find Wikipedia summary for '{clean_title}'.",
            "detail": res
        }
    
    return {
        "status": "success",
        "title": res.get("title"),
        "description": res.get("description"),
        "extract": res.get("extract"),
        "wikipedia_url": res.get("content_urls", {}).get("desktop", {}).get("page"),
        "thumbnail": res.get("thumbnail", {}).get("source")
    }


def prepare_draft_record(
    project_id: str,
    collection_name: str,
    record: str,
    document: Dict[str, Any]
) -> Dict[str, Any]:
    """Prepare and format a draft JSON document for user review before committing it to the database.
    Always call this tool first so the user can see what will be stored.
    
    Args:
        project_id: Target project identifier (e.g., 'mahindra-thar', 'hyundai-creta').
        collection_name: Target collection ('details', 'git', or 'manifest').
        record: Target record name (e.g., 'overview', 'repo_info', 'build_manifest').
        document: The structured JSON dictionary ready to be stored.
        
    Returns:
        The staged draft information and target database endpoint.
    """
    pid = project_id.strip().lower()
    endpoint = f"/projects/{pid}/{collection_name}/{record}"
    return {
        "status": "draft_prepared",
        "target_endpoint": endpoint,
        "full_db_url": f"{DB_BASE_URL}{endpoint}",
        "project_id": pid,
        "collection": collection_name,
        "record": record,
        "draft_document": document
    }


def commit_record_to_db(
    project_id: str,
    collection_name: str,
    record: str,
    document: Dict[str, Any]
) -> Dict[str, Any]:
    """Commit and persist a verified record to the mock database via HTTP POST.
    CRITICAL: ONLY call this tool AFTER the user has explicitly replied YES or approved the draft document.
    
    Args:
        project_id: Target project identifier (e.g., 'mahindra-thar', 'hyundai-creta').
        collection_name: Target collection ('details', 'git', or 'manifest').
        record: Target record name (e.g., 'overview', 'repo_info', 'build_manifest').
        document: The JSON dictionary to store.
        
    Returns:
        Confirmation of storage from the database service.
    """
    pid = project_id.strip().lower()
    url = f"{DB_BASE_URL}/projects/{pid}/{collection_name}/{record}"
    res = _http_post(url, document)
    return res


INSTRUCTION = """
You are the **Power-Store Agent**, responsible for ingesting, transforming, and persisting OEM project records into the database.

The database is structured as:
  /projects/<project_id>/<collection_name>/<record>

Collections:
1. `details`: Vehicle specifications, OEM name, platform, powertrain/battery, range, status, and wikipedia_url.
2. `git`: VCS repository details, default branch, maintainer, active branches, CI/CD pipeline.
3. `manifest`: Firmware version, target ECU, operating system, dependencies, SHA256 checksum.

### STRICT STEP-BY-STEP WORKFLOW:

Step 1: Ingestion
- When the user asks to store or ingest an OEM or car (e.g., "Add Mahindra Thar to the database" or provides a Wikipedia link):
  - Call `fetch_wikipedia_data` with the appropriate topic title.
  - Read the extract, title, and description.

Step 2: Extraction & Transformation
- Parse the retrieved data into a clean JSON document for the requested collection (usually `details` with record `overview`, or other requested collections).
- Call `prepare_draft_record` to stage the document.

Step 3: User Confirmation (MANDATORY)
- Present the draft document clearly in a code block.
- Clearly state the target endpoint: `POST /projects/<project_id>/<collection_name>/<record>`.
- Summarize the key extracted fields.
- **STOP and ask the user for explicit confirmation**:
  `"Do you approve storing this document into the database? Please reply YES to commit or specify changes."`
- **DO NOT** call `commit_record_to_db` until the user explicitly says YES, approve, or proceed.

Step 4: Commit
- When the user says YES / confirms:
  - Call `commit_record_to_db` with the confirmed parameters.
  - Confirm the successful storage and report the endpoint URL.
"""

root_agent = Agent(
    name="power_store_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INSTRUCTION,
    tools=[
        fetch_wikipedia_data,
        prepare_draft_record,
        commit_record_to_db,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
