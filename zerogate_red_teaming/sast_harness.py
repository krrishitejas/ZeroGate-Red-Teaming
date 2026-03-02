import json
import subprocess


def run_semgrep(target_path: str) -> list:
    """
    Runs Semgrep against the given target_path and returns a list of findings.
    """
    command = [
        "semgrep",
        "scan",
        "--config",
        "p/default",
        "--config",
        "p/owasp-top-ten",
        "--config",
        "p/security-audit",
        "--config",
        "p/secrets",
        "--json",
        "-q",
        target_path,
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output = result.stdout
    except subprocess.CalledProcessError as e:
        # Semgrep returns exit code 1 if it finds vulnerabilities
        if e.returncode == 1:
            output = e.stdout
        else:
            raise RuntimeError(
                f"Semgrep returned unexpected exit code {e.returncode}: {e.stderr}"
            )
    except Exception as e:
        # Catch any other execution errors (e.g., FileNotFoundError)
        raise RuntimeError(
            f"Semgrep execution failed: {str(e)}. Is semgrep installed and in PATH?"
        )

    try:
        data = json.loads(output)
        results = data.get("results", [])

        parsed_findings = []
        for item in results:
            parsed_findings.append(
                {
                    "id": item.get("check_id"),
                    "vulnerability_name": item.get("check_id"),
                    "file_path": item.get("path"),
                    "message": item.get("extra", {}).get("message"),
                    "start_line": item.get("start", {}).get("line"),
                    "severity": item.get("extra", {}).get("severity"),
                }
            )
        return parsed_findings
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Failed to parse Semgrep JSON output: {str(e)}\nOutput was: {output[:500]}"
        )
