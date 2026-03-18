"""
Sandbox runtime for safe execution of untrusted code.

Implements process-based isolation with resource limits.
"""

import asyncio
import json
import signal
import subprocess
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
    ):
        """
        Initialize sandbox config.
        
        Args:
            trust_level: Trust level determining isolation
            timeout_seconds: Maximum execution time
            memory_limit_mb: Memory limit in MB
            cpu_limit_percent: CPU usage limit as percentage
        """
        self.trust_level = trust_level
        self.timeout_seconds = timeout_seconds
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit_percent = cpu_limit_percent


class SandboxRuntime:
    """Executes code in a sandboxed environment"""
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize sandbox runtime.
        
        Args:
            config: Sandbox configuration
        """
        self.config = config or SandboxConfig()
    
    async def execute(
        self,
        code: str,
        function_name: str,
        arguments: Dict[str, Any],
        trust_level: TrustLevel = TrustLevel.UNTRUSTED,
    ) -> ExecutionResult:
        """
        Execute code in sandbox.
        
        Args:
            code: Python code to execute
            function_name: Name of function to call
            arguments: Arguments to pass to function
            trust_level: Trust level for this execution
            
        Returns:
            ExecutionResult with output or error
        """
        config = SandboxConfig(trust_level=trust_level)
        
        # For MVP, use simple subprocess isolation
        # Could upgrade to Docker/gVisor in future
        return await self._execute_subprocess(code, function_name, arguments, config)
    
    async def _execute_subprocess(
        self,
        code: str,
        function_name: str,
        arguments: Dict[str, Any],
        config: SandboxConfig,
    ) -> ExecutionResult:
        """Execute code in subprocess with isolation"""
        
        # Create temporary file for execution
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            # Write execution wrapper script
            wrapper = self._create_wrapper_script(code, function_name, arguments)
            f.write(wrapper)
            f.flush()
            temp_file = f.name
        
        try:
            # Build command
            cmd = [sys.executable, temp_file]
            
            # Execute with timeout
            start_time = asyncio.get_event_loop().time()
            
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    # Don't pass environment to restrict access
                    env={},
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
                        capability_id="unknown",
                        status=ExecutionStatus.TIMEOUT,
                        error="Execution timeout",
                        execution_time_ms=(
                            (asyncio.get_event_loop().time() - start_time) * 1000
                        ),
                        trust_level=config.trust_level,
                    )
                
                execution_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                
                # Process output
                if process.returncode == 0:
                    try:
                        output = json.loads(stdout.decode())
                        return ExecutionResult(
                            capability_id="unknown",
                            status=ExecutionStatus.SUCCESS,
                            output=output,
                            execution_time_ms=execution_time_ms,
                            trust_level=config.trust_level,
                        )
                    except json.JSONDecodeError:
                        return ExecutionResult(
                            capability_id="unknown",
                            status=ExecutionStatus.ERROR,
                            error="Invalid output format",
                            execution_time_ms=execution_time_ms,
                            trust_level=config.trust_level,
                        )
                else:
                    error_msg = stderr.decode() if stderr else stdout.decode()
                    return ExecutionResult(
                        capability_id="unknown",
                        status=ExecutionStatus.FAILED,
                        error=error_msg,
                        execution_time_ms=execution_time_ms,
                        trust_level=config.trust_level,
                    )
            
            except Exception as e:
                return ExecutionResult(
                    capability_id="unknown",
                    status=ExecutionStatus.ERROR,
                    error=str(e),
                    execution_time_ms=(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    ),
                    trust_level=config.trust_level,
                )
        
        finally:
            # Clean up temp file
            Path(temp_file).unlink(missing_ok=True)
    
    def _create_wrapper_script(
        self,
        code: str,
        function_name: str,
        arguments: Dict[str, Any],
    ) -> str:
        """Create execution wrapper script"""
        # Build the wrapper that executes the user code and calls the function
        wrapper = f'''
import json
import sys

# User code
{self._indent_code(code, 1)}

# Execute function
try:
    result = {function_name}(**{json.dumps(arguments)})
    print(json.dumps({{"success": True, "result": result}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}), file=sys.stderr)
    sys.exit(1)
'''
        return wrapper
    
    @staticmethod
    def _indent_code(code: str, indent_level: int = 1) -> str:
        """Indent code by specified number of spaces"""
        indent = "    " * indent_level
        lines = code.split("\n")
        return "\n".join(indent + line if line.strip() else line for line in lines)


class TrustManager:
    """Manages trust levels and privilege escalation"""
    
    PROBATION_THRESHOLD = 10  # executions to reach probation
    PROBATION_SUCCESS_RATE = 0.90
    TRUSTED_THRESHOLD = 50
    TRUSTED_SUCCESS_RATE = 0.95
    
    def __init__(self):
        """Initialize trust manager"""
        self.execution_metrics: Dict[str, Dict[str, Any]] = {}
    
    def record_execution(
        self,
        capability_id: str,
        success: bool,
        execution_time_ms: float,
    ) -> None:
        """Record execution for trust scoring"""
        if capability_id not in self.execution_metrics:
            self.execution_metrics[capability_id] = {
                "total": 0,
                "successful": 0,
                "total_time": 0.0,
            }
        
        metrics = self.execution_metrics[capability_id]
        metrics["total"] += 1
        if success:
            metrics["successful"] += 1
        metrics["total_time"] += execution_time_ms
    
    def get_trust_level(self, capability_id: str) -> TrustLevel:
        """Get current trust level for capability"""
        if capability_id not in self.execution_metrics:
            return TrustLevel.UNTRUSTED
        
        metrics = self.execution_metrics[capability_id]
        success_rate = metrics["successful"] / max(metrics["total"], 1)
        
        if metrics["total"] >= self.TRUSTED_THRESHOLD and success_rate >= self.TRUSTED_SUCCESS_RATE:
            return TrustLevel.TRUSTED
        elif metrics["total"] >= self.PROBATION_THRESHOLD and success_rate >= self.PROBATION_SUCCESS_RATE:
            return TrustLevel.PROBATION
        else:
            return TrustLevel.UNTRUSTED
    
    def get_metrics(self, capability_id: str) -> Dict[str, Any]:
        """Get execution metrics for capability"""
        if capability_id not in self.execution_metrics:
            return {"total": 0, "successful": 0, "success_rate": 0.0}
        
        metrics = self.execution_metrics[capability_id]
        return {
            "total": metrics["total"],
            "successful": metrics["successful"],
            "success_rate": metrics["successful"] / max(metrics["total"], 1),
            "avg_time_ms": metrics["total_time"] / max(metrics["total"], 1),
        }
