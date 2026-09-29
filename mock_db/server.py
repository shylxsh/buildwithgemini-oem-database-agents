import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="OEM Projects Mock Database Service", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).parent / "data" / "projects.json"

def load_data() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data: Dict[str, Any]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.get("/")
def root():
    return {
        "service": "OEM Projects Mock DB API",
        "endpoints": [
            "GET /projects",
            "POST /projects",
            "GET /projects/{project_id}",
            "GET /projects/{project_id}/{collection_name}",
            "GET /projects/{project_id}/{collection_name}/{record}",
            "POST /projects/{project_id}/{collection_name}/{record}",
            "GET /search?q={query}"
        ]
    }

@app.get("/projects")
def list_projects() -> List[Dict[str, Any]]:
    """List all available OEM projects."""
    data = load_data()
    results = []
    for pid, pdata in data.items():
        results.append({
            "project_id": pid,
            "oem": pdata.get("oem"),
            "project_name": pdata.get("project_name"),
            "collections": list(pdata.get("collections", {}).keys())
        })
    return results

class CreateProjectPayload(BaseModel):
    project_id: str
    oem: str
    project_name: str

@app.post("/projects")
def create_project(payload: CreateProjectPayload):
    """Create a new OEM project container."""
    data = load_data()
    pid = payload.project_id.strip().lower()
    if pid in data:
        return {
            "status": "already_exists",
            "message": f"Project '{pid}' already exists.",
            "project": data[pid]
        }
    data[pid] = {
        "oem": payload.oem,
        "project_name": payload.project_name,
        "collections": {
            "details": {},
            "git": {},
            "manifest": {}
        }
    }
    save_data(data)
    return {
        "status": "created",
        "message": f"Project '{pid}' created successfully.",
        "project_id": pid,
        "endpoint": f"/projects/{pid}"
    }

@app.get("/projects/{project_id}")
def get_project_collections(project_id: str) -> Dict[str, Any]:
    """Get project info and list available collections."""
    data = load_data()
    if project_id not in data:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    pdata = data[project_id]
    return {
        "project_id": project_id,
        "oem": pdata.get("oem"),
        "project_name": pdata.get("project_name"),
        "available_collections": list(pdata.get("collections", {}).keys())
    }

@app.get("/projects/{project_id}/{collection_name}")
def list_collection_records(project_id: str, collection_name: str) -> Dict[str, Any]:
    """List all records within a project's collection."""
    data = load_data()
    if project_id not in data:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    cols = data[project_id].get("collections", {})
    if collection_name not in cols:
        raise HTTPException(
            status_code=404, 
            detail=f"Collection '{collection_name}' not found for project '{project_id}'. Available: {list(cols.keys())}"
        )
    return {
        "project_id": project_id,
        "collection": collection_name,
        "records": list(cols[collection_name].keys())
    }

@app.get("/projects/{project_id}/{collection_name}/{record}")
def get_record(project_id: str, collection_name: str, record: str) -> Dict[str, Any]:
    """Return the raw JSON document for a specific record."""
    data = load_data()
    if project_id not in data:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    cols = data[project_id].get("collections", {})
    if collection_name not in cols:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found.")
    rec_dict = cols[collection_name]
    if record not in rec_dict:
        raise HTTPException(
            status_code=404, 
            detail=f"Record '{record}' not found in collection '{collection_name}'. Available: {list(rec_dict.keys())}"
        )
    return rec_dict[record]

@app.post("/projects/{project_id}/{collection_name}/{record}")
def store_or_update_record(
    project_id: str, 
    collection_name: str, 
    record: str, 
    document: Dict[str, Any] = Body(...)
):
    """Store or update a raw JSON document in a project collection."""
    data = load_data()
    pid = project_id.strip().lower()
    
    # Auto-initialize project if it doesn't exist
    if pid not in data:
        data[pid] = {
            "oem": document.get("oem", "Unknown OEM"),
            "project_name": document.get("project_name", pid.replace("-", " ").title()),
            "collections": {
                "details": {},
                "git": {},
                "manifest": {}
            }
        }
    
    collections = data[pid].setdefault("collections", {})
    if collection_name not in collections:
        collections[collection_name] = {}
        
    collections[collection_name][record] = document
    save_data(data)
    
    return {
        "status": "stored",
        "project_id": pid,
        "collection": collection_name,
        "record": record,
        "endpoint": f"/projects/{pid}/{collection_name}/{record}",
        "document_keys": list(document.keys())
    }

@app.get("/search")
def search_database(q: str = Query(..., description="Query string to search across database")):
    """Helper search endpoint to support fuzzy query lookups."""
    query_str = q.lower().strip()
    data = load_data()
    matches = []

    for pid, pdata in data.items():
        oem = str(pdata.get("oem", "")).lower()
        pname = str(pdata.get("project_name", "")).lower()

        for cname, cdata in pdata.get("collections", {}).items():
            for rname, rdoc in cdata.items():
                doc_str = json.dumps(rdoc).lower()
                match_score = 0
                if query_str in pid or query_str in oem or query_str in pname:
                    match_score += 5
                if query_str in cname:
                    match_score += 3
                if query_str in rname:
                    match_score += 2
                if query_str in doc_str:
                    match_score += 1

                if match_score > 0:
                    matches.append({
                        "score": match_score,
                        "project_id": pid,
                        "oem": pdata.get("oem"),
                        "collection": cname,
                        "record": rname,
                        "endpoint": f"/projects/{pid}/{cname}/{rname}",
                        "preview": {k: v for k, v in list(rdoc.items())[:3]}
                    })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return {"query": q, "results": matches}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
