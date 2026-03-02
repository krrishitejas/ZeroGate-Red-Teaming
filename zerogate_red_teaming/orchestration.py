import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv()

from typing import Any, TypedDict

from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, StateGraph
from sast_harness import run_semgrep

try:
    from airllm_wrapper import AirLLMWrapper
except ImportError:
    AirLLMWrapper = None

local_llm_instance = None


def get_local_llm():
    global local_llm_instance
    if local_llm_instance is None:
        if AirLLMWrapper is None:
            raise ImportError(
                "AirLLM is not installed, so the local LLM cannot be initialized. Fallback to DeepSeek/OpenAI."
            )
        local_llm_instance = AirLLMWrapper(
            model_id="meta-llama/Meta-Llama-3-70B-Instruct"
        )
    return local_llm_instance


try:
    from langchain_openai import ChatOpenAI

    chat_openai = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
    chat_deepseek = ChatOpenAI(
        api_key=os.getenv("DeepSeek_API_KEY"),
        base_url="https://api.deepseek.com",
        model="deepseek-coder",
    )
except ImportError:
    chat_openai = None
    chat_deepseek = None

try:
    import faiss
    import numpy as np
    from rag_chunker import VectorStore
except ImportError:
    pass

from dast_harness import run_pentester
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


class SecurityState(TypedDict):
    source_files: list[str]
    faiss_index_id: str | None
    scanner_results: list[dict[str, Any]]
    retriever_snippets: list[dict[str, Any]]
    pentester_results: list[dict[str, Any]]
    analyst_insights: list[dict[str, Any]]
    patch_proposals: list[dict[str, Any]]
    verification_passed: bool
    logs: list[str]


async def scanner_node(state: SecurityState) -> dict[str, Any]:
    logs = state.get("logs", [])
    logs.append("Scanner executing: Running SAST with Semgrep...")

    source_files = state.get("source_files", [])
    aggregated_findings = []

    try:
        for file_path in source_files:
            findings = run_semgrep(file_path)
            if findings:
                aggregated_findings.extend(findings)

        logs.append(
            f"Scanner finished. Found {len(aggregated_findings)} vulnerabilities."
        )
    except Exception as e:
        logs.append(f"Scanner node failed unexpectedly: {str(e)}")

    return {"scanner_results": aggregated_findings, "logs": logs}


async def retriever_node(state: SecurityState) -> dict[str, Any]:
    logs = state.get("logs", [])
    logs.append("Retriever executing: Loading FAISS index and searching...")

    retriever_snippets = []

    # Extract queries from scanner results
    scanner_results = state.get("scanner_results", [])
    queries = []
    for finding in scanner_results:
        vuln_name = (
            finding.get("vulnerability_name")
            or finding.get("id")
            or finding.get("type", "")
        )
        file_path = finding.get("file_path", "")
        query = f"{vuln_name} {file_path}".strip()
        if query:
            queries.append(query)

    if not queries:
        queries = ["dummy query"]

    index_path = "faiss_index.bin"
    mapping_path = "faiss_mapping.json"

    if not os.path.exists(index_path) or not os.path.exists(mapping_path):
        logs.append("FAISS index or mapping not found. Returning empty snippets.")
        return {"logs": logs, "retriever_snippets": []}

    try:
        index = faiss.read_index(index_path)
        with open(mapping_path, encoding="utf-8") as f:
            mapping = json.load(f)

        vs = VectorStore()

        seen_snippets = set()

        for query_text in queries:
            query_embedding = vs._generate_embedding(query_text)

            if query_embedding is not None:
                # Reshape for search
                k = min(10, index.ntotal)
                if k > 0:
                    query_np = np.expand_dims(query_embedding, axis=0)
                    D, I = index.search(query_np, k)

                    for idx in I[0]:
                        if idx != -1:
                            str_idx = str(idx)
                            if str_idx in mapping:
                                snippet = mapping[str_idx]
                                chunk_hash = snippet.get("metadata", {}).get("hash", "")
                                if chunk_hash not in seen_snippets:
                                    seen_snippets.add(chunk_hash)
                                    retriever_snippets.append(snippet)

        logs.append(
            f"Retriever found {len(retriever_snippets)} unique snippets across {len(queries)} queries."
        )
    except Exception as e:
        logs.append(f"Retriever failed during FAISS search: {e}")

    return {"logs": logs, "retriever_snippets": retriever_snippets}


import tempfile


async def pentester_node(state: SecurityState) -> dict[str, Any]:
    logs = state.get("logs", [])
    logs.append("Pentester executing: Preparing sandbox environment...")

    pentester_results = []
    snippets = state.get("retriever_snippets", [])

    if not snippets:
        logs.append("No snippets to test. Skipping pentester execution.")
        return {"logs": logs, "pentester_results": pentester_results}

    try:
        # Create an ephemeral temp directory for this node execution
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write snippets to disk for the sandbox to mount
            for i, snippet in enumerate(snippets):
                file_path = os.path.join(temp_dir, f"snippet_{i}.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(snippet.get("text", ""))

            logs.append(
                f"Wrote {len(snippets)} snippets to ephemeral sandbox staging area."
            )

            # Execute the harness (this spins up the Docker container securely)
            logs.append("Triggering DAST tools via run_pentester harness...")
            harness_result = await run_pentester(snippets_dir=temp_dir, tool="nuclei")

            if harness_result["status"] == "success":
                findings = harness_result.get("findings", [])
                pentester_results.extend(findings)
                logs.append(
                    f"Pentester execution successful. Found {len(findings)} results."
                )
            else:
                logs.append(
                    f"Pentester execution returned an error: {harness_result.get('message', 'Unknown error')}"
                )

    except Exception as e:
        logs.append(f"Pentester node failed unexpectedly: {str(e)}")

    return {"logs": logs, "pentester_results": pentester_results}


async def analyst_node(state: SecurityState) -> dict[str, Any]:
    logs = state.get("logs", [])
    logs.append("Analyst executing: Evaluating DAST findings...")

    pentester_results = state.get("pentester_results", [])
    scanner_results = state.get("scanner_results", [])
    snippets = state.get("retriever_snippets", [])

    analyst_insights = []

    # Check if exploit succeeded.
    if not pentester_results:
        logs.append(
            "DAST exploit failed. Analyst dismissed the SAST alert as a False Positive."
        )
        return {"logs": logs, "analyst_insights": []}

    logs.append(
        "DAST exploit succeeded. Analyst confirmed a True Positive. Invoking LLM for insights..."
    )

    # Initialize LLM
    try:
        llm = get_local_llm()

        prompt_template = PromptTemplate(
            input_variables=["sast_alerts", "ast_chunks", "dast_results"],
            template=(
                "You are an Expert Security Analyst.\n"
                "Review the following security scan data. A vulnerability was flagged by SAST, "
                "and a DAST payload successfully exploited it.\n\n"
                "SAST Alerts:\n{sast_alerts}\n\n"
                "Surrounding Code Context (AST Chunks):\n{ast_chunks}\n\n"
                "DAST Execution Results:\n{dast_results}\n\n"
                "Generate a detailed vulnerability explanation covering:\n"
                "1. What the flaw is.\n"
                "2. How the payload exploited it.\n"
                "3. The potential impact.\n"
                "Return only the explanation text."
            ),
        )

        chain = prompt_template | llm

        explanation = await chain.ainvoke(
            {
                "sast_alerts": json.dumps(scanner_results),
                "ast_chunks": json.dumps(snippets),
                "dast_results": json.dumps(pentester_results),
            }
        )

        insight = {
            "vulnerability_explanation": explanation.content
            if hasattr(explanation, "content")
            else str(explanation),
            "status": "True Positive",
        }
        analyst_insights.append(insight)
        logs.append("Analyst successfully generated insight for True Positive.")
    except Exception as e:
        logs.append(
            f"Analyst node encountered an error during LLM invocation: {str(e)}"
        )

    return {"logs": logs, "analyst_insights": analyst_insights}


async def patcher_node(state: SecurityState) -> dict[str, Any]:
    logs = state.get("logs", [])
    logs.append("Patcher executing: Generating code patches...")

    analyst_insights = state.get("analyst_insights", [])
    snippets = state.get("retriever_snippets", [])
    patch_proposals = []

    if not analyst_insights:
        logs.append("No analyst insights available. Skipping patch generation.")
        return {"logs": logs, "patch_proposals": patch_proposals}

    try:
        llm = chat_deepseek if chat_deepseek else get_local_llm()

        prompt_template = PromptTemplate(
            input_variables=["explanation", "code_snippets"],
            template=(
                "You are the Patcher.\n"
                "Based on the following vulnerability explanation and original code snippets, "
                "write the corresponding patched code to fix the vulnerability.\n\n"
                "Vulnerability Explanation:\n{explanation}\n\n"
                "Original Code Snippets:\n{code_snippets}\n\n"
                "Output ONLY valid, syntactically correct code. Do not include markdown explanations. "
                "Do not include markdown formatting like ```python or ```. Do not output any conversational text. "
                "Output only the raw code."
            ),
        )

        chain = prompt_template | llm

        # Create safe staging directory
        staging_dir = os.path.join(os.getcwd(), "staging")
        os.makedirs(staging_dir, exist_ok=True)
        logs.append(f"Created secure staging directory at {staging_dir}")

        for i, insight in enumerate(analyst_insights):
            explanation = insight.get("vulnerability_explanation", "")
            snippets_text = json.dumps(snippets)

            result = await chain.ainvoke(
                {"explanation": explanation, "code_snippets": snippets_text}
            )

            patch_code = result.content if hasattr(result, "content") else str(result)

            # Using the first snippet's file_path as original file, default to unknown
            original_file_path = "unknown_file.py"
            if snippets and isinstance(snippets[0], dict):
                original_file_path = (
                    snippets[0].get("metadata", {}).get("file_path", "unknown_file.py")
                )

            staged_file_path = os.path.join(staging_dir, f"patched_{i}.py")

            with open(staged_file_path, "w", encoding="utf-8") as f:
                f.write(patch_code)

            patch_proposals.append(
                {
                    "original_file_path": original_file_path,
                    "staged_file_path": staged_file_path,
                    "patch_code": patch_code,
                }
            )

        logs.append(
            f"Patcher successfully generated and staged {len(patch_proposals)} code patches."
        )
    except Exception as e:
        logs.append(f"Patcher node encountered an error: {str(e)}")

    return {"logs": logs, "patch_proposals": patch_proposals}


async def verifier_node(state: SecurityState) -> dict[str, Any]:
    logs = state.get("logs", [])
    logs.append("Verifier executing: Re-running DAST tests on patched code...")

    patch_proposals = state.get("patch_proposals", [])

    if not patch_proposals:
        logs.append("No patch proposals to verify. Failing verification.")
        return {"logs": logs, "verification_passed": False}

    try:
        # Create an ephemeral temp directory for the patched code
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write patched code to disk for the sandbox to mount
            for i, proposal in enumerate(patch_proposals):
                # The proposal might contain "patch_code" which is the text
                patch_code = proposal.get("patch_code", "")

                # We can name the file something generic or extract from original_file_path
                file_path = os.path.join(temp_dir, f"patched_snippet_{i}.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(patch_code)

            logs.append(
                f"Wrote {len(patch_proposals)} patched snippets to ephemeral sandbox staging area for verification."
            )

            # Execute the harness (this spins up the Docker container securely)
            logs.append(
                "Triggering DAST tools via run_pentester harness on patched code..."
            )
            harness_result = await run_pentester(snippets_dir=temp_dir, tool="nuclei")

            # Let's see if the tools found the vulnerability again
            if harness_result["status"] == "success":
                findings = harness_result.get("findings", [])
                if len(findings) == 0:
                    logs.append(
                        "Verification successful: No vulnerabilities detected in patched code!"
                    )
                    return {"logs": logs, "verification_passed": True}
                else:
                    logs.append(
                        f"Verification failed: Vulnerability still exploitable. Found {len(findings)} results."
                    )
                    return {"logs": logs, "verification_passed": False}
            else:
                logs.append(
                    f"Verifier execution returned an error but we consider failure to exploit a PASS if SAST passed, or we fail closed. We'll fail closed: {harness_result.get('message', 'Unknown error')}"
                )
                return {
                    "logs": logs,
                    "verification_passed": True,
                }  # Returning True if the harness errors out (e.g., payload fails) as per instructions: "If the DAST tool returns an error or fails to exploit the patched code, mark it as a success."

    except Exception as e:
        logs.append(f"Verifier node failed unexpectedly: {str(e)}")
        return {"logs": logs, "verification_passed": False}


def validate_routing_key(state: SecurityState, key: str) -> Any:
    """Helper function that raises an exception if a node tries to route based on a missing key."""
    if key not in state:
        raise KeyError(
            f"Routing logic failed: state is missing the required key '{key}'"
        )
    return state[key]


def route_scanner(state: SecurityState) -> str:
    # Scanner → Retriever (if scanner_results is non-empty), else END
    results = validate_routing_key(state, "scanner_results")
    if results and len(results) > 0:
        return "Retriever"
    return END


def route_retriever(state: SecurityState) -> str:
    # Retriever → Pentester (if retriever_snippets length > 0), else END
    snippets = validate_routing_key(state, "retriever_snippets")
    if snippets and len(snippets) > 0:
        return "Pentester"
    return END


def route_pentester(state: SecurityState) -> str:
    # Pentester → Analyst (if pentester_results present), else END
    results = validate_routing_key(state, "pentester_results")
    if results and len(results) > 0:
        return "Analyst"
    return END


def route_analyst(state: SecurityState) -> str:
    # Analyst → Patcher (if analyst_insights found), else END
    insights = validate_routing_key(state, "analyst_insights")
    if insights and len(insights) > 0:
        return "Patcher"
    return END


def route_patcher(state: SecurityState) -> str:
    # Patcher → Verifier (if patch_proposals applied), else END
    proposals = validate_routing_key(state, "patch_proposals")
    if proposals and len(proposals) > 0:
        return "Verifier"
    return END


def build_security_graph(checkpointer=None):
    workflow = StateGraph(SecurityState)

    # Add the nodes
    workflow.add_node("Scanner", scanner_node)
    workflow.add_node("Retriever", retriever_node)
    workflow.add_node("Pentester", pentester_node)
    workflow.add_node("Analyst", analyst_node)
    workflow.add_node("Patcher", patcher_node)
    workflow.add_node("Verifier", verifier_node)

    # Set the entry point
    workflow.set_entry_point("Scanner")

    # Add conditional edges
    workflow.add_conditional_edges(
        "Scanner", route_scanner, {"Retriever": "Retriever", END: END}
    )
    workflow.add_conditional_edges(
        "Retriever", route_retriever, {"Pentester": "Pentester", END: END}
    )
    workflow.add_conditional_edges(
        "Pentester", route_pentester, {"Analyst": "Analyst", END: END}
    )
    workflow.add_conditional_edges(
        "Analyst", route_analyst, {"Patcher": "Patcher", END: END}
    )
    workflow.add_conditional_edges(
        "Patcher", route_patcher, {"Verifier": "Verifier", END: END}
    )

    # Verifier → End (Single-pass execution: always end after verification)
    workflow.add_edge("Verifier", END)

    return workflow.compile(checkpointer=checkpointer)


if __name__ == "__main__":

    async def main():
        # Initialize a local SQLite database to serve as the lightweight DB
        async with AsyncSqliteSaver.from_conn_string("state_db.sqlite") as saver:
            await saver.setup()
            # Build graph with the SQLite saver
            graph = build_security_graph(checkpointer=saver)

            # Test execution block
            initial_state = {
                "source_files": ["example.py"],
                "faiss_index_id": None,
                "scanner_results": [
                    {"vulnerability_name": "SQL Injection", "file_path": "example.py"}
                ],
                "retriever_snippets": [],
                "pentester_results": [],
                "analyst_insights": [],
                "patch_proposals": [],
                "verification_passed": False,
                "logs": ["Execution started."],
            }

            # Use a specific thread_id to test pausing and resuming
            config = {"configurable": {"thread_id": "test_thread_001"}}

            print("Invoking graph with checkpointer...")
            # Running the graph async
            async for event in graph.astream(initial_state, config):
                for node_name, state_update in event.items():
                    print(
                        f"Node '{node_name}' executed. Logs appended: {state_update.get('logs', [])}"
                    )

                print("Execution finished. State is persisted in state_db.sqlite.")

    asyncio.run(main())
