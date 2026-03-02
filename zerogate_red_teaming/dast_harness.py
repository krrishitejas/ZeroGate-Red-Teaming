import json
import pathlib
import uuid

from opensandbox import Sandbox


async def run_pentester(snippets_dir: str, tool: str = "nuclei") -> dict:
    """
    Safely spins up the OpenSandbox environment to execute DAST tools against code snippets.
    Returns structured JSON findings.
    """
    sandbox_name = f"redteam-{tool}-{uuid.uuid4().hex[:8]}"

    try:
        # Create a secure sandbox instance
        sandbox = await Sandbox.create(
            image="opensandbox/code-interpreter:latest", name=sandbox_name
        )

        # Upload all snippets in the directory
        snippets_path = pathlib.Path(snippets_dir)
        for snippet_file in snippets_path.glob("*.txt"):
            with open(snippet_file, encoding="utf-8") as f:
                content = f.read()
                # OpenSandbox write_file
                await sandbox.files.write_file(
                    f"/app/snippets/{snippet_file.name}", content
                )

        # Read results based on the tool
        if tool == "nuclei":
            # Execute the tool
            result = await sandbox.commands.run("nuclei -l /app/snippets/*.txt -json")

            stdout = result.stdout
            if stdout:
                lines = stdout.splitlines()
                try:
                    findings = [json.loads(line) for line in lines if line.strip()]
                    return {"status": "success", "findings": findings}
                except json.JSONDecodeError:
                    return {
                        "status": "success",
                        "findings": [],
                        "message": "Failed to decode Nuclei output",
                    }
            else:
                return {
                    "status": "success",
                    "findings": [],
                    "message": "No results found from Nuclei.",
                }

        elif tool == "sqlmap":
            # SQLMap logic
            # Execute the tool
            result = await sandbox.commands.run(
                'sqlmap -u "$(cat /app/snippets/sql.txt)" --batch'
            )
            # For SQLMap, we can just return stdout if results aren't explicitly structured yet
            return {
                "status": "success",
                "findings": [{"type": "sqlmap output", "output": result.stdout}],
            }
        else:
            return {
                "status": "error",
                "message": f"Unknown tool: {tool}",
                "findings": [],
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"An unexpected error occurred during OpenSandbox execution: {str(e)}",
            "findings": [],
        }
    finally:
        if "sandbox" in locals() and sandbox:
            await sandbox.close()
