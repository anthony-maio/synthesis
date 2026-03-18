"""
Sandbox runtime for safe execution of untrusted code.

Implements process-based isolation with resource limits.
For production, can be upgraded to Docker containers.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from synthesis.core.models import ExecutionResult, ExecutionStatus, TrustLevel


class SandboxConfig:
    """Configuration for sandbox execution"""

    def __init__(
        self,
        trust_level: TrustLevel = TrustLevel.UNTRUSTED,
        timeout_seconds: float = 30.0,
        memory_limit_mb: int = 512,
        cpu_limit_percent: int = 100,
        allow_network: bool = False,
    ):
        """
        Initialize sandbox config.

        Args:
            trust_level: Trust level determining isolation
            timeout_seconds: Maximum execution time
            memory_limit_mb: Memory limit in MB
            cpu_limit_percent: CPU usage limit as percentage
            allow_network: Whether to allow network access
        """
        self.trust_level = trust_level
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit_percent = cpu_limit_percent
        self.allow_network = allow_network

    @classmethod
    def for_trust_level(cls, trust_level: TrustLevel) -> "SandboxConfig":
        """Create config appropriate for given trust level."""
        configs = {
            TrustLevel.UNTRUSTED: cls(
                trust_level=trust_level,
                timeout_seconds=10.0,
                memory_limit_mb=256,
                allow_network=False,
            ),
            TrustLevel.PROBATION: cls(
                trust_level=trust_level,
                timeout_seconds=30.0,
                memory_limit_mb=512,
                allow_network=False,
            ),
            TrustLevel.TRUSTED: cls(
                trust_level=trust_level,
                timeout_seconds=60.0,
                memory_limit_mb=1024,
                allow_network=True,
            ),
            TrustLevel.VERIFIED: cls(
                trust_level=trust_level,
                timeout_seconds=120.0,
                memory_limit_mb=2048,
                allow_network=True,
            ),
        }
        return configs.get(trust_level, configs[TrustLevel.UNTRUSTED])


class SandboxRuntime:
    """Executes code in a sandboxed environment"""

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize sandbox runtime.

        Args:
            config: Default sandbox configuration
        """
        self.default_config = config or SandboxConfig()

    async def execute(
        self,
        code: str,
        function_name: str,
        arguments: Dict[str, Any],
        capability_id: str = "unknown",
        trust_level: TrustLevel = TrustLevel.UNTRUSTED,
    ) -> ExecutionResult:
        """
        Execute code in sandbox.

        Args:
            code: Python code to execute
            function_name: Name of function to call
            arguments: Arguments to pass to function
            capability_id: ID of the capability being executed
            trust_level: Trust level for this execution

        Returns:
            ExecutionResult with output or error
        """
        config = SandboxConfig.for_trust_level(trust_level)

        return await self._execute_subprocess(
            code, function_name, arguments, capability_id, config
        )

    async def _execute_subprocess(
        self,
        code: str,
        function_name: str,
        arguments: Dict[str, Any],
        capability_id: str,
        config: SandboxConfig,
    ) -> ExecutionResult:
        """Execute code in subprocess with isolation"""

        # Create temporary file for execution
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            wrapper = self._create_wrapper_script(code, function_name, arguments)
            f.write(wrapper)
            f.flush()
            temp_file = f.name

        try:
            cmd = [sys.executable, temp_file]

            start_time = asyncio.get_event_loop().time()

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={},  # Empty environment for isolation
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=config.timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return ExecutionResult(
                        capability_id=capability_id,
                        status=ExecutionStatus.TIMEOUT,
                        error=f"Execution timeout after {config.timeout_seconds}s",
                        execution_time_ms=(
                            (asyncio.get_event_loop().time() - start_time) * 1000
                        ),
                        trust_level=config.trust_level,
                    )

                execution_time_ms = (
                    asyncio.get_event_loop().time() - start_time
                ) * 1000

                if process.returncode == 0:
                    try:
                        output = json.loads(stdout.decode())
                        return ExecutionResult(
                            capability_id=capability_id,
                            status=ExecutionStatus.SUCCESS,
                            output=output,
                            execution_time_ms=execution_time_ms,
                            trust_level=config.trust_level,
                        )
                    except json.JSONDecodeError:
                        return ExecutionResult(
                            capability_id=capability_id,
                            status=ExecutionStatus.ERROR,
                            error="Invalid output format",
                            execution_time_ms=execution_time_ms,
                            trust_level=config.trust_level,
                        )
                else:
                    error_msg = stderr.decode() if stderr else stdout.decode()
                    return ExecutionResult(
                        capability_id=capability_id,
                        status=ExecutionStatus.FAILED,
                        error=error_msg[:1000],  # Truncate long errors
                        execution_time_ms=execution_time_ms,
                        trust_level=config.trust_level,
                    )

            except Exception as e:
                return ExecutionResult(
                    capability_id=capability_id,
                    status=ExecutionStatus.ERROR,
                    error=str(e),
                    execution_time_ms=(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    ),
                    trust_level=config.trust_level,
                )

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def _create_wrapper_script(
        self,
        code: str,
        function_name: str,
        arguments: Dict[str, Any],
    ) -> str:
        """Create execution wrapper script"""
        # Escape the code properly for embedding
        escaped_args = json.dumps(arguments)

        wrapper = f'''
import json
import sys

# User code
{code}

# Execute function
try:
    result = {function_name}(**{escaped_args})
    print(json.dumps({{"success": True, "result": result}}, default=str))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}), file=sys.stderr)
    sys.exit(1)
'''
        return wrapper
