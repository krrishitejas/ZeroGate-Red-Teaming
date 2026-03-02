import json
import subprocess
import tempfile
import uuid

from dotenv import load_dotenv

load_dotenv()

from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from orchestration import build_security_graph
from pydantic import BaseModel

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ImportError:
    pass

app = FastAPI(
    title="Automated Red Teaming MCP API",
    description="FastAPI Backend exposing the LangGraph orchestration for scanning.",
)

# Set up CORS middleware to allow the MCP UI to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    source_repo: str
    config: dict[str, Any] | None = None


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


async def stream_scan(repo_url: str) -> AsyncGenerator[str, None]:
    """
    Async generator that initializes the orchestrator graph, triggers the execution,
    and yields JSON-formatted events sequentially as nodes complete.
    """
    # Use the async SQLite saver as the checkpointer
    async with AsyncSqliteSaver.from_conn_string("state_db.sqlite") as saver:
        await saver.setup()

        # Create an ephemeral directory to clone the remote repository into
        with tempfile.TemporaryDirectory() as temp_dir:
            # Yield initial pre-processing status
            yield (
                json.dumps(
                    {
                        "node": "Preprocessor",
                        "update": {
                            "logs": [f"Cloning repository: {repo_url} into {temp_dir}"]
                        },
                    }
                )
                + "\n"
            )

            try:
                # Run shallow clone
                subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, temp_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                yield (
                    json.dumps(
                        {
                            "node": "Preprocessor",
                            "update": {"logs": [f"Successfully cloned {repo_url}"]},
                        }
                    )
                    + "\n"
                )
            except subprocess.CalledProcessError as e:
                yield (
                    json.dumps(
                        {
                            "node": "ERROR",
                            "error": f"Failed to clone repository: {e.stderr}",
                        }
                    )
                    + "\n"
                )
                return

            graph = build_security_graph(checkpointer=saver)

            initial_state = {
                "source_files": [temp_dir],
                "faiss_index_id": None,
                "scanner_results": [],
                "retriever_snippets": [],
                "pentester_results": [],
                "analyst_insights": [],
                "patch_proposals": [],
                "verification_passed": False,
                "logs": ["Execution started via API."],
            }

            # Generate a unique thread ID for tracking this specific scan
            thread_id = f"api_scan_{uuid.uuid4().hex[:8]}"
            config = {"configurable": {"thread_id": thread_id}}

        try:
            # Iterate through the execution stream
            async for event in graph.astream(initial_state, config):
                for node_name, state_update in event.items():
                    # Format as JSON newline for streaming response
                    payload = {"node": node_name, "update": state_update}
                    yield json.dumps(payload) + "\n"

            # Confirm completion
            yield json.dumps({"node": "END", "status": "completed"}) + "\n"
        except Exception as e:
            yield json.dumps({"node": "ERROR", "error": str(e)}) + "\n"


@app.post("/scan")
async def trigger_scan(request: ScanRequest):
    """
    Triggers a new scan with real-time streaming results from LangGraph nodes.
    """
    return StreamingResponse(
        stream_scan(str(request.source_repo)), media_type="application/x-ndjson"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
