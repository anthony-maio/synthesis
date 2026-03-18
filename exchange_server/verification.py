"""
Capability verification for the Live Exchange.

Runs tests in a sandbox to verify that capabilities work correctly
before making them available to other agents.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


async def verify_capability(
    code: str,
    tests: List[Dict[str, Any]],
    dependencies: List[str],
) -> Dict[str, Any]:
    """
    Verify a capability by running its tests.

    Args:
        code: The capability implementation
        tests: List of test cases
        dependencies: Required packages

    Returns:
        Dict with 'passed' boolean and optional 'error'
    """
    # Create verification script
    test_script = _create_test_script(code, tests)

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(test_script)
        f.flush()
        temp_file = f.name

    try:
        # Run in subprocess with timeout
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            temp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={},  # Isolated environment
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0,  # 60 second timeout for verification
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {"passed": False, "error": "Verification timeout"}

        if process.returncode == 0:
            try:
                result = json.loads(stdout.decode())
                return result
            except json.JSONDecodeError:
                return {"passed": False, "error": "Invalid verification output"}
        else:
            error = stderr.decode() or stdout.decode()
            return {"passed": False, "error": error[:500]}

    finally:
        Path(temp_file).unlink(missing_ok=True)


def _create_test_script(code: str, tests: List[Dict[str, Any]]) -> str:
    """Create a script that runs all tests."""
    tests_json = json.dumps(tests)

    return f'''
import json
import sys

# User code
{code}

# Run tests
tests = {tests_json}
passed = 0
failed = 0
errors = []

for test in tests:
    try:
        # Find the function to call
        func_name = None
        for name in dir():
            obj = eval(name)
            if callable(obj) and not name.startswith("_") and name not in ["json", "sys"]:
                func_name = name
                break

        if not func_name:
            errors.append("No callable function found")
            failed += 1
            continue

        func = eval(func_name)
        result = func(**test.get("inputs", {{}}))
        expected = test.get("expected_output")

        if result == expected:
            passed += 1
        else:
            failed += 1
            errors.append(f"Test '{{test.get('name', 'unnamed')}}': expected {{expected}}, got {{result}}")
    except Exception as e:
        failed += 1
        errors.append(f"Test '{{test.get('name', 'unnamed')}}' error: {{str(e)}}")

# Output result
result = {{
    "passed": failed == 0 and passed > 0,
    "tests_passed": passed,
    "tests_failed": failed,
    "errors": errors[:5]  # Limit errors
}}

print(json.dumps(result))
'''
