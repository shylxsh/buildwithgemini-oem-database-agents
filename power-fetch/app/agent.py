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


def _http_get(url: str) -> Dict[str, Any]:
    """Helper to perform HTTP GET requests to the FastAPI mock database service."""
    req = urllib.request.Request(url, headers={"User-Agent": "power-fetch-agent"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return {"error": f"HTTP {e.code}: {e.reason}", "detail": body}
    except Exception as e:
        return {"error": f"Failed to connect to database service: {str(e)}"}


def list_projects() -> List[Dict[str, Any]]:
    """List all available OEM projects and their collections from the database.
    
    Returns:
        A list of project summaries containing project_id, oem, project_name, and available collections.
    """
    url = f"{DB_BASE_URL}/projects"
    return _http_get(url)


def get_project_collections(project_id: str) -> Dict[str, Any]:
    """Get collection details for a specific OEM project.
    
    Args:
        project_id: The ID of the project (e.g., 'tata-nexon-ev', 'skoda-kushaq', 'mahindra-xuv700').
        
    Returns:
        Information about the project and its available collections.
    """
    url = f"{DB_BASE_URL}/projects/{project_id}"
    return _http_get(url)


def list_collection_records(project_id: str, collection_name: str) -> Dict[str, Any]:
    """List all available records under a specific collection in an OEM project.
    
    Args:
        project_id: The ID of the project (e.g., 'tata-nexon-ev').
        collection_name: The name of the collection ('details', 'git', or 'manifest').
        
    Returns:
        The list of record IDs inside this collection.
    """
    url = f"{DB_BASE_URL}/projects/{project_id}/{collection_name}"
    return _http_get(url)


def fetch_record(project_id: str, collection_name: str, record: str) -> Dict[str, Any]:
    """Fetch the raw JSON document for a specific record in an OEM project collection.
    
    Args:
        project_id: The ID of the project (e.g., 'tata-nexon-ev', 'skoda-kushaq', 'mahindra-xuv700').
        collection_name: The collection name ('details', 'git', or 'manifest').
        record: The record identifier (e.g., 'overview', 'repo_info', 'build_manifest').
        
    Returns:
        A dictionary containing the endpoint URL and the raw JSON document.
    """
    endpoint_path = f"/projects/{project_id}/{collection_name}/{record}"
    url = f"{DB_BASE_URL}{endpoint_path}"
    raw_data = _http_get(url)
    return {
        "endpoint": endpoint_path,
        "full_url": url,
        "raw_json": raw_data
    }


def fuzzy_match_query(query: str) -> Dict[str, Any]:
    """Search and perform fuzzy matching across all projects, collections, and records in the database.
    Use this tool whenever:
    1. The user query is complex, vague, or cross-cutting (e.g., mentions a specific chip, battery size, or feature).
    2. The exact project ID, collection, or record name is not explicitly clear.
    
    Args:
        query: The search query string.
        
    Returns:
        A list of matched database endpoints, project IDs, and snippet previews.
    """
    url = f"{DB_BASE_URL}/search?q={urllib.parse.quote(query)}"
    res = _http_get(url)
    return {
        "status": "fuzzy_matching_completed",
        "tag": "COMPLEX_QUERY_FUZZY_MATCHING",
        "query": query,
        "matches": res.get("results", [])
    }


INSTRUCTION = """
You are the Power-Fetch Agent, an expert system that navigates OEM project databases (TATA, SKODA, Mahindra, etc.).
The database is structured as:
  /projects/<project_id>/<collection_name>/<record>

Available collections for each project are:
  1. details (specs, platforms, battery/powertrain, wikipedia links)
  2. git (repository URLs, branches, pipelines, maintainers)
  3. manifest (firmware version, target ECU, OS, software dependencies, checksums)

Operational Guidelines:
1. Always State the Endpoint:
   Whenever you answer a query about a project, collection, or record, you MUST explicitly provide the exact API endpoint URL:
   Endpoint: /projects/<project_id>/<collection_name>/<record>

2. Summarize the Raw JSON:
   Go through the raw JSON returned by fetch_record and provide a clear, concise, well-structured summary of the key fields in your response.

3. Complex Questions & Fuzzy Matching:
   If the user asks a complex question, a cross-collection query (e.g., "Which project uses Android Automotive?", "Find the car with 40 kWh battery", "Who maintains the ADAS radar?"), or if the project/record is not immediately obvious:
   - Call the fuzzy_match_query tool.
   - In your response, explicitly include this warning tag:
     > ⚠️ **Complex query detected — performing fuzzy matching across database endpoints...**
   - Show which endpoints matched and provide the summarized answer from the matching record.

4. Conversational Memory & Statefulness:
   - Maintain active context across conversational turns. For instance, if the user asks about "Nexon" or "TATA", remember tata-nexon-ev. Subsequent questions like "Show its git repository" or "What OS does its manifest use?" must automatically resolve to tata-nexon-ev.
   - If the user intent is ambiguous or you cannot determine which project they mean, list the available projects and ask for clarification.
"""

root_agent = Agent(
    name="power_fetch_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INSTRUCTION,
    tools=[
        list_projects,
        get_project_collections,
        list_collection_records,
        fetch_record,
        fuzzy_match_query,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
