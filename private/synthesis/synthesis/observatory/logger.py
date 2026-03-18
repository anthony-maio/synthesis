"""
Observatory for comprehensive system observability.

Logs all synthesis attempts and executions for analysis and debugging.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from synthesis.core.models import (
    ExecutionResult,
    SynthesisAttempt,
    SynthesisMetrics,
)


class Logger:
    """Comprehensive logging for Synthesis"""
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize logger.
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = log_dir or Path("./synthesis_logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up file logging
        self.logger = logging.getLogger("synthesis")
        self.logger.setLevel(logging.DEBUG)
        
        # Create formatters
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Add file handler
        fh = logging.FileHandler(self.log_dir / "synthesis.log")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        # Add console handler for important messages
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
    
    def log_synthesis_start(self, attempt_id: str, requirement: str) -> None:
        """Log start of synthesis attempt"""
        self.logger.info(f"[{attempt_id}] Starting synthesis: {requirement}")
    
    def log_synthesis_complete(self, attempt: SynthesisAttempt) -> None:
        """Log completion of synthesis attempt"""
        status = "SUCCESS" if attempt.success else "FAILED"
        self.logger.info(
            f"[{attempt.id}] Synthesis {status}: "
            f"{attempt.tests_passed}/{attempt.total_tests} tests passed "
            f"in {attempt.iterations} iterations ({attempt.total_time_ms:.0f}ms)"
        )
        
        # Write attempt details to file
        attempt_file = self.log_dir / f"synthesis_{attempt.id}.json"
        with open(attempt_file, "w") as f:
            data = attempt.model_dump()
            data["completed_at"] = attempt.completed_at.isoformat()
            data["created_at"] = attempt.created_at.isoformat()
            json.dump(data, f, indent=2, default=str)
    
    def log_execution(self, result: ExecutionResult) -> None:
        """Log capability execution"""
        status = result.status.value.upper()
        self.logger.debug(
            f"[{result.capability_id}] Execution {status}: "
            f"{result.execution_time_ms:.0f}ms"
        )
        
        # Write execution details
        exec_file = self.log_dir / f"execution_{result.capability_id}_{datetime.utcnow().timestamp()}.json"
        with open(exec_file, "w") as f:
            data = result.model_dump()
            data["timestamp"] = result.timestamp.isoformat()
            json.dump(data, f, indent=2, default=str)


class MetricsCollector:
    """Collects and analyzes system metrics"""
    
    def __init__(self):
        """Initialize metrics collector"""
        self.synthesis_attempts: List[SynthesisAttempt] = []
        self.executions: List[ExecutionResult] = []
    
    def record_synthesis(self, attempt: SynthesisAttempt) -> None:
        """Record a synthesis attempt"""
        self.synthesis_attempts.append(attempt)
    
    def record_execution(self, result: ExecutionResult) -> None:
        """Record an execution"""
        self.executions.append(result)
    
    def get_synthesis_metrics(self) -> SynthesisMetrics:
        """Get overall synthesis metrics"""
        if not self.synthesis_attempts:
            return SynthesisMetrics()
        
        attempts = self.synthesis_attempts
        successful = [a for a in attempts if a.success]
        
        metrics = SynthesisMetrics(
            total_attempts=len(attempts),
            successful_attempts=len(successful),
            failed_attempts=len(attempts) - len(successful),
        )
        
        if successful:
            metrics.average_iterations = sum(a.iterations for a in successful) / len(successful)
            metrics.average_time_ms = sum(a.total_time_ms for a in successful) / len(successful)
        
        # Group by category
        from collections import defaultdict
        by_category = defaultdict(lambda: {"total": 0, "successful": 0})
        
        for attempt in attempts:
            cat = attempt.category.value if attempt.category else "unknown"
            by_category[cat]["total"] += 1
            if attempt.success:
                by_category[cat]["successful"] += 1
        
        metrics.by_category = dict(by_category)
        
        return metrics
    
    def get_execution_metrics(self, capability_id: Optional[str] = None) -> Dict[str, Any]:
        """Get execution metrics"""
        executions = self.executions
        if capability_id:
            executions = [e for e in executions if e.capability_id == capability_id]
        
        if not executions:
            return {"total": 0, "successful": 0, "success_rate": 0.0}
        
        successful = sum(1 for e in executions if e.status.value == "success")
        avg_time = sum(e.execution_time_ms for e in executions) / len(executions)
        
        return {
            "total": len(executions),
            "successful": successful,
            "success_rate": successful / len(executions),
            "avg_execution_time_ms": avg_time,
        }
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        synth_metrics = self.get_synthesis_metrics()
        
        return {
            "synthesis": {
                "total_attempts": synth_metrics.total_attempts,
                "success_rate": synth_metrics.success_rate,
                "successful": synth_metrics.successful_attempts,
                "failed": synth_metrics.failed_attempts,
                "avg_iterations": synth_metrics.average_iterations,
                "avg_time_ms": synth_metrics.average_time_ms,
            },
            "executions": self.get_execution_metrics(),
            "timestamp": datetime.utcnow().isoformat(),
        }


class Observatory:
    """Combined logging and metrics system"""
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize observatory.
        
        Args:
            log_dir: Directory for logs
        """
        self.logger = Logger(log_dir)
        self.metrics = MetricsCollector()
    
    def record_synthesis_attempt(self, attempt: SynthesisAttempt) -> None:
        """Record a complete synthesis attempt"""
        self.logger.log_synthesis_start(attempt.id, attempt.requirement)
        self.logger.log_synthesis_complete(attempt)
        self.metrics.record_synthesis(attempt)
    
    def record_execution_result(self, result: ExecutionResult) -> None:
        """Record an execution result"""
        self.logger.log_execution(result)
        self.metrics.record_execution(result)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get system summary"""
        return self.metrics.get_stats_summary()
    
    def export_metrics(self, path: Path) -> None:
        """Export metrics to file"""
        summary = self.get_summary()
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
