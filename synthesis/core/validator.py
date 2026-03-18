"""
Code validation and safety analysis.

Validates generated code before execution using AST analysis.
"""

import ast
import re
from typing import List, Set

from synthesis.core.models import RiskLevel, ValidationIssue, ValidationResult


class CodeValidator:
    """Validates Python code for safety and quality"""

    # Libraries that indicate critical security risks
    FORBIDDEN_LIBRARIES: Set[str] = {
        "os",
        "subprocess",
        "sys",
        "importlib",
        "__import__",
        "socket",
        "socketserver",
        "asyncio",  # Can escape isolation
        "threading",
        "multiprocessing",
        "pickle",
        "shelve",
        "marshal",
        "pty",
        "popen2",
        "ctypes",
        "cffi",
    }

    # Libraries that need review but might be acceptable
    REVIEW_LIBRARIES: Set[str] = {
        "requests",
        "urllib",
        "httpx",
        "sqlite3",
        "psycopg2",
        "mysql",
        "redis",
        "aiohttp",
        "aiofiles",
    }

    # Functions that enable code execution or dangerous operations
    FORBIDDEN_FUNCTIONS: Set[str] = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "raw_input",
        "vars",
        "globals",
        "locals",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "callable",
        "breakpoint",
    }

    # Safe builtins that are allowed
    SAFE_BUILTINS: Set[str] = {
        "abs",
        "all",
        "any",
        "ascii",
        "bin",
        "bool",
        "bytes",
        "chr",
        "dict",
        "divmod",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "len",
        "list",
        "map",
        "max",
        "min",
        "oct",
        "ord",
        "pow",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
        "print",
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "RuntimeError",
        "NotImplementedError",
        "AttributeError",
        "StopIteration",
    }

    def __init__(self):
        """Initialize the validator"""
        self.issues: List[ValidationIssue] = []

    async def validate(
        self,
        code: str,
        strict_mode: bool = False
    ) -> ValidationResult:
        """
        Validate Python code for safety.

        Args:
            code: Python code to validate
            strict_mode: If True, be more restrictive about what's allowed

        Returns:
            ValidationResult with findings
        """
        self.issues = []

        # Check syntax
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.issues.append(
                ValidationIssue(
                    severity="critical",
                    category="syntax",
                    message=f"Syntax error: {e.msg}",
                    location=f"line {e.lineno}",
                )
            )
            return self._build_result()

        # Perform checks
        self._check_imports(tree, strict_mode)
        self._check_dangerous_calls(tree)
        self._check_patterns(code)
        self._check_function_definition(tree)

        return self._build_result()

    def _check_imports(self, tree: ast.AST, strict_mode: bool) -> None:
        """Check for dangerous imports"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    self._check_module(module, strict_mode)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split(".")[0]
                    self._check_module(module, strict_mode)

    def _check_module(self, module: str, strict_mode: bool) -> None:
        """Check if a module is safe to import"""
        if module in self.FORBIDDEN_LIBRARIES:
            self.issues.append(
                ValidationIssue(
                    severity="critical",
                    category="import",
                    message=f"Forbidden library: {module}",
                    suggestion="This library is not allowed for security reasons",
                )
            )
        elif module in self.REVIEW_LIBRARIES:
            severity = "high" if strict_mode else "medium"
            self.issues.append(
                ValidationIssue(
                    severity=severity,
                    category="import",
                    message=f"Library requires review: {module}",
                    suggestion="Verify this library is necessary and used safely",
                )
            )

    def _check_dangerous_calls(self, tree: ast.AST) -> None:
        """Check for dangerous function calls"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.FORBIDDEN_FUNCTIONS:
                        self.issues.append(
                            ValidationIssue(
                                severity="critical",
                                category="dangerous_call",
                                message=f"Dangerous function call: {node.func.id}()",
                                suggestion=f"{node.func.id}() is not allowed for security",
                            )
                        )

    def _check_patterns(self, code: str) -> None:
        """Check for dangerous patterns in code"""
        # Check for file operations
        if re.search(r'\bopen\s*\(', code):
            self.issues.append(
                ValidationIssue(
                    severity="critical",
                    category="file_access",
                    message="Direct file access detected",
                    suggestion="Use provided APIs for file operations",
                )
            )

        # Check for exec/eval patterns
        if re.search(r'\b(eval|exec)\s*\(', code):
            self.issues.append(
                ValidationIssue(
                    severity="critical",
                    category="code_execution",
                    message="Dynamic code execution detected",
                    suggestion="Avoid eval() and exec()",
                )
            )

        # Check for shell command patterns
        if re.search(r'os\.(system|popen|spawn)', code):
            self.issues.append(
                ValidationIssue(
                    severity="critical",
                    category="shell_execution",
                    message="Shell command execution detected",
                    suggestion="Shell commands are not allowed",
                )
            )

    def _check_function_definition(self, tree: ast.AST) -> None:
        """Verify code contains function definitions"""
        functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

        if not functions:
            self.issues.append(
                ValidationIssue(
                    severity="high",
                    category="structure",
                    message="No function definitions found",
                    suggestion="Code must define at least one function",
                )
            )

    def _build_result(self) -> ValidationResult:
        """Build validation result from issues"""
        critical_issues = [i for i in self.issues if i.severity == "critical"]
        high_issues = [i for i in self.issues if i.severity == "high"]

        # Determine risk level
        if critical_issues:
            risk_level = RiskLevel.CRITICAL
        elif high_issues:
            risk_level = RiskLevel.HIGH
        elif any(i.severity == "medium" for i in self.issues):
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return ValidationResult(
            is_valid=len(critical_issues) == 0,
            issues=self.issues,
            risk_level=risk_level,
        )
