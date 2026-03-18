import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple

import gradio as gr


class TrustLevel(Enum):
    """Simple trust levels used in the demo."""
    UNTRUSTED = "UNTRUSTED"
    PROBATION = "PROBATION"
    TRUSTED = "TRUSTED"


@dataclass
class Capability:
    """A dynamically created function with a trust score."""
    name: str
    description: str
    code: str
    func: Callable
    total_executions: int = 0
    successful_executions: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def trust_level(self) -> TrustLevel:
        """Compute the trust level based on executions and success rate."""
        if self.total_executions >= 50 and self.success_rate >= 0.95:
            return TrustLevel.TRUSTED
        if self.total_executions >= 10 and self.success_rate >= 0.90:
            return TrustLevel.PROBATION
        return TrustLevel.UNTRUSTED


class CapabilityManager:
    """Manages dynamic capabilities and their trust scores."""

    def __init__(self) -> None:
        self.capabilities: Dict[str, Capability] = {}

    @staticmethod
    def _safe_exec(user_code: str) -> Tuple[bool, Any, str]:
        """Execute user code in a restricted environment and extract the first function.

        Returns a tuple `(success, function, message)`.  If `success` is False,
        `message` contains an error description; otherwise `function` is the extracted callable.
        """
        # Define a minimal set of safe builtins and modules
        allowed_builtins = {
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'range': range,
            'sorted': sorted,
            'math': math,
        }
        namespace: Dict[str, Any] = {}
        try:
            exec(user_code, {'__builtins__': allowed_builtins}, namespace)
        except Exception as e:
            return False, None, f"Compilation error: {e}"
        # Find the first callable defined in namespace
        func = None
        for obj in namespace.values():
            if callable(obj):
                func = obj
                break
        if func is None:
            return False, None, "No function definition found in the provided code."
        return True, func, ""

    def add_capability(self, name: str, description: str, code: str, tests_json: str) -> str:
        """Add a new capability and run its tests.  Returns a result string."""
        success, func, message = self._safe_exec(code)
        if not success:
            return message
        capability = Capability(name=name, description=description, code=code, func=func)
        # Run tests if provided
        if tests_json.strip():
            try:
                tests = json.loads(tests_json)
            except json.JSONDecodeError as e:
                return f"Invalid JSON for tests: {e}"
            if not isinstance(tests, list):
                return "Tests JSON must be a list of objects with 'input' and 'output'."
            total = 0
            passed = 0
            for t in tests:
                if not isinstance(t, dict) or 'input' not in t or 'output' not in t:
                    return "Each test must be an object with 'input' and 'output' keys."
                args = t['input']
                expected = t['output']
                if not isinstance(args, list):
                    return "The 'input' field must be a list of positional arguments."
                total += 1
                try:
                    result = func(*args)
                    if result == expected:
                        passed += 1
                        capability.successful_executions += 1
                    capability.total_executions += 1
                except Exception:
                    capability.total_executions += 1
            result_msg = f"Tests passed: {passed}/{total}. Trust level: {capability.trust_level.value}"
        else:
            result_msg = "Capability added without tests. Trust level: UNTRUSTED"
        self.capabilities[name] = capability
        return result_msg

    def run_capability(self, name: str, args_json: str) -> str:
        """Execute an existing capability with arguments provided as JSON list."""
        if name not in self.capabilities:
            return f"No capability named '{name}'."
        capability = self.capabilities[name]
        try:
            args = json.loads(args_json) if args_json.strip() else []
            if not isinstance(args, list):
                return "Arguments must be provided as a JSON list."
        except json.JSONDecodeError as e:
            return f"Invalid JSON for arguments: {e}"
        capability.total_executions += 1
        try:
            result = capability.func(*args)
            capability.successful_executions += 1
            return f"Result: {result}\nSuccess rate: {capability.success_rate:.2f}\nTrust level: {capability.trust_level.value}"
        except Exception as e:
            return f"Execution failed: {e}\nSuccess rate: {capability.success_rate:.2f}\nTrust level: {capability.trust_level.value}"


# Create a single CapabilityManager instance
manager = CapabilityManager()


def ui_add_capability(name: str, description: str, code: str, tests: str) -> str:
    return manager.add_capability(name.strip(), description.strip(), code, tests)


def ui_run_capability(name: str, args: str) -> str:
    return manager.run_capability(name.strip(), args)


def get_capability_names() -> List[str]:
    return list(manager.capabilities.keys())


with gr.Blocks() as demo:
    gr.Markdown("""# Dynamic Capability Manager Demo

This demo lets you define Python functions on the fly, test them and then run them.  
Provide the function definition in the **Code** box.  It must define at least one function (any name is accepted; the first defined function will be used).  
Specify tests as a JSON list of objects with `"input"` (a list of arguments) and `"output"` (the expected return value).  When you run the tests, the system records successes and failures and computes a trust level.
""")
    with gr.Tab("Create Capability"):
        cap_name = gr.Textbox(label="Capability Name", placeholder="e.g. square")
        cap_desc = gr.Textbox(label="Description", placeholder="Describe what the function does")
        cap_code = gr.Textbox(label="Code", placeholder="def square(x):\n    return x*x", lines=10)
        cap_tests = gr.Textbox(label="Tests (JSON)", placeholder='[\n  {"input": [3], "output": 9},\n  {"input": [5], "output": 25}\n] ', lines=6)
        add_button = gr.Button("Add Capability & Run Tests")
        add_output = gr.Textbox(label="Result", interactive=False)
        add_button.click(ui_add_capability, inputs=[cap_name, cap_desc, cap_code, cap_tests], outputs=add_output)
    with gr.Tab("Run Capability"):
        sel_cap = gr.Dropdown(label="Select Capability", choices=lambda: get_capability_names())
        run_args = gr.Textbox(label="Arguments (JSON list)", placeholder="[10]")
        run_button = gr.Button("Run Capability")
        run_output = gr.Textbox(label="Execution Result", interactive=False)
        run_button.click(ui_run_capability, inputs=[sel_cap, run_args], outputs=run_output)

if __name__ == "__main__":
    demo.launch()