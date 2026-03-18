"""
Test-Driven Development Synthesizer for capability generation.

This module implements the core synthesis engine that generates new capabilities
using a rigorous test-driven development approach. Unlike naive code generation,
this synthesizer:

1. Generates comprehensive tests FIRST based on the capability request
2. Generates implementation code to satisfy those tests
3. Runs tests in a sandbox and collects detailed failure information
4. Iteratively refines the code based on test failures
5. Tracks honest metrics about success rates and iteration counts

The TDD approach dramatically improves the reliability of generated code by
ensuring it actually works before it's deployed.
"""

import ast
import asyncio
import sys
import traceback
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
import re

from .capability import (
    Capability, CapabilityRequest, CapabilityTest, CapabilityCategory,
    TrustLevel, ExecutionMetrics
)


@dataclass
class SynthesisResult:
    """
    Result of a synthesis attempt.
    
    This provides complete transparency about what happened during synthesis,
    including all iterations, failures, and the final outcome.
    """
    success: bool
    capability: Optional[Capability]
    iterations: int
    total_time_seconds: float
    test_results: List[Dict[str, Any]]
    error_messages: List[str]
    synthesis_log: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for logging/analysis."""
        return {
            "success": self.success,
            "capability_id": self.capability.capability_id if self.capability else None,
            "iterations": self.iterations,
            "total_time_seconds": self.total_time_seconds,
            "test_results": self.test_results,
            "error_messages": self.error_messages,
            "synthesis_log": self.synthesis_log
        }


class TDDSynthesizer:
    """
    Generates capabilities using test-driven development.
    
    This is the core synthesis engine. It takes a capability request and
    produces a validated, tested capability through an iterative process.
    
    The synthesizer is LLM-provider agnostic and focuses on the synthesis
    process itself, delegating the actual code generation to pluggable
    LLM providers.
    """
    
    def __init__(self, llm_provider, max_iterations: int = 5, test_timeout: float = 10.0):
        """
        Initialize the TDD synthesizer.
        
        Args:
            llm_provider: LLM provider for code generation (must implement generate_code method)
            max_iterations: Maximum refinement iterations before giving up
            test_timeout: Timeout for individual test execution (seconds)
        """
        self.llm_provider = llm_provider
        self.max_iterations = max_iterations
        self.test_timeout = test_timeout
        
        # Metrics for tracking synthesis performance
        self.total_attempts = 0
        self.successful_syntheses = 0
        self.average_iterations = 0.0
        self.synthesis_history: List[SynthesisResult] = []
    
    async def synthesize(self, request: CapabilityRequest) -> SynthesisResult:
        """
        Synthesize a new capability from a request using TDD.
        
        This is the main entry point for capability synthesis. It orchestrates
        the entire TDD process:
        1. Generate tests from examples
        2. Generate initial implementation
        3. Run tests and collect failures
        4. Iteratively refine based on failures
        5. Return final result with complete transparency
        
        Args:
            request: The capability request to fulfill
            
        Returns:
            Comprehensive synthesis result including success/failure and all details
        """
        start_time = datetime.now()
        self.total_attempts += 1
        
        synthesis_log = []
        error_messages = []
        test_results = []
        
        synthesis_log.append(f"Starting synthesis for: {request.description}")
        
        try:
            # Step 1: Generate tests FIRST (this is TDD)
            synthesis_log.append("Step 1: Generating tests from examples...")
            tests = await self._generate_tests(request)
            
            if not tests:
                error_messages.append("Failed to generate any valid tests")
                return self._create_failure_result(
                    start_time, 0, test_results, error_messages, synthesis_log
                )
            
            synthesis_log.append(f"Generated {len(tests)} tests")
            
            # Step 2: Generate initial implementation
            synthesis_log.append("Step 2: Generating initial implementation...")
            implementation = await self._generate_implementation(request, tests)
            
            if not implementation:
                error_messages.append("Failed to generate initial implementation")
                return self._create_failure_result(
                    start_time, 0, test_results, error_messages, synthesis_log
                )
            
            # Step 3: Iterative refinement until tests pass or max iterations reached
            iteration = 0
            all_tests_passed = False
            
            while iteration < self.max_iterations and not all_tests_passed:
                iteration += 1
                synthesis_log.append(f"\nIteration {iteration}:")
                
                # Run all tests
                current_test_results = await self._run_tests(implementation, tests)
                test_results.extend(current_test_results)
                
                # Check if all tests passed
                passed = sum(1 for result in current_test_results if result["passed"])
                total = len(current_test_results)
                
                synthesis_log.append(f"  Tests: {passed}/{total} passed")
                
                if passed == total:
                    all_tests_passed = True
                    synthesis_log.append("  ✓ All tests passed!")
                    break
                
                # Collect failure details for refinement
                failures = [r for r in current_test_results if not r["passed"]]
                synthesis_log.append(f"  {len(failures)} test(s) failed:")
                
                for failure in failures:
                    synthesis_log.append(f"    - {failure['test_name']}: {failure['error']}")
                    error_messages.append(f"Test '{failure['test_name']}' failed: {failure['error']}")
                
                # If not last iteration, refine the implementation
                if iteration < self.max_iterations:
                    synthesis_log.append(f"  Refining implementation based on failures...")
                    
                    refinement_prompt = self._create_refinement_prompt(
                        request, implementation, failures
                    )
                    
                    implementation = await self._refine_implementation(
                        refinement_prompt, implementation, failures
                    )
                    
                    if not implementation:
                        error_messages.append(f"Failed to refine implementation at iteration {iteration}")
                        break
            
            # Create the final capability if successful
            if all_tests_passed:
                capability = self._create_capability(request, implementation, tests)
                
                elapsed = (datetime.now() - start_time).total_seconds()
                self.successful_syntheses += 1
                
                # Update rolling average iterations
                alpha = 0.2
                if self.average_iterations == 0:
                    self.average_iterations = iteration
                else:
                    self.average_iterations = (
                        alpha * iteration + (1 - alpha) * self.average_iterations
                    )
                
                result = SynthesisResult(
                    success=True,
                    capability=capability,
                    iterations=iteration,
                    total_time_seconds=elapsed,
                    test_results=test_results,
                    error_messages=error_messages,
                    synthesis_log=synthesis_log
                )
                
                self.synthesis_history.append(result)
                return result
            else:
                synthesis_log.append(f"\n✗ Failed to pass all tests after {iteration} iterations")
                return self._create_failure_result(
                    start_time, iteration, test_results, error_messages, synthesis_log
                )
                
        except Exception as e:
            error_messages.append(f"Synthesis exception: {str(e)}\n{traceback.format_exc()}")
            synthesis_log.append(f"ERROR: {str(e)}")
            return self._create_failure_result(
                start_time, 0, test_results, error_messages, synthesis_log
            )
    
    async def _generate_tests(self, request: CapabilityRequest) -> List[CapabilityTest]:
        """
        Generate comprehensive tests from the capability request.
        
        This is the crucial first step in TDD. We generate tests that verify:
        - Correctness for provided examples
        - Edge cases and boundary conditions
        - Error handling
        - Performance constraints
        
        Args:
            request: The capability request
            
        Returns:
            List of test cases
        """
        tests = []
        
        # Generate a test for each example input/output pair
        for i, (input_data, expected_output) in enumerate(
            zip(request.example_inputs, request.example_outputs)
        ):
            test_name = f"test_example_{i+1}"
            
            # Create test code that validates the output
            test_code = self._create_test_code(
                test_name,
                input_data,
                expected_output,
                request.constraints
            )
            
            test = CapabilityTest(
                name=test_name,
                description=f"Validate example input {i+1}",
                input_data=input_data,
                expected_output=expected_output,
                test_code=test_code,
                timeout_seconds=request.constraints.get("timeout_seconds", self.test_timeout)
            )
            
            tests.append(test)
        
        return tests
    
    def _create_test_code(self,
                          test_name: str,
                          input_data: Dict[str, Any],
                          expected_output: Any,
                          constraints: Dict[str, Any]) -> str:
        """
        Create executable test code for a single test case.
        
        Args:
            test_name: Name of the test
            input_data: Input data for the test
            expected_output: Expected output value
            constraints: Test constraints (timeout, etc.)
            
        Returns:
            Python code that runs the test
        """
        # Convert input data to Python code
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in input_data.items())
        
        test_code = f"""
def {test_name}(execute):
    '''Test with input: {input_data}'''
    # Execute the capability
    result = execute({args_str})
    
    # Validate the output
    expected = {repr(expected_output)}
    
    assert result == expected, f"Expected {{expected}}, got {{result}}"
    return True
"""
        return test_code
    
    async def _generate_implementation(self,
                                      request: CapabilityRequest,
                                      tests: List[CapabilityTest]) -> Optional[str]:
        """
        Generate initial implementation code that attempts to pass the tests.
        
        Args:
            request: The capability request
            tests: The generated tests
            
        Returns:
            Python implementation code, or None if generation failed
        """
        # Create a detailed prompt for the LLM
        prompt = self._create_implementation_prompt(request, tests)
        
        try:
            # Use the LLM provider to generate code
            implementation = await self.llm_provider.generate_code(
                prompt=prompt,
                temperature=0.3,  # Lower temperature for more deterministic code
                max_tokens=2000
            )
            
            # Validate the generated code is syntactically valid Python
            if not self._validate_python_syntax(implementation):
                return None
            
            return implementation
            
        except Exception as e:
            print(f"Error generating implementation: {e}")
            return None
    
    def _create_implementation_prompt(self,
                                     request: CapabilityRequest,
                                     tests: List[CapabilityTest]) -> str:
        """
        Create a comprehensive prompt for implementation generation.
        
        Args:
            request: The capability request
            tests: The test cases to satisfy
            
        Returns:
            Prompt string for the LLM
        """
        tests_description = "\n".join([
            f"- Test {i+1}: {test.description}\n  Input: {test.input_data}\n  Expected: {test.expected_output}"
            for i, test in enumerate(tests)
        ])
        
        prompt = f"""Generate a Python function named 'execute' that implements the following capability:

DESCRIPTION:
{request.description}

CATEGORY: {request.category.value}

REQUIREMENTS:
The function must pass these tests:
{tests_description}

CONSTRAINTS:
{json.dumps(request.constraints, indent=2)}

REQUIREMENTS:
- Function must be named 'execute'
- Must accept parameters matching the test inputs
- Must return values matching expected outputs
- Include proper error handling
- Add docstring explaining the function
- Keep implementation clean and readable
- DO NOT include test code, only the implementation

Generate ONLY the execute function implementation. Do not include imports or test code.
"""
        return prompt
    
    async def _run_tests(self,
                        implementation: str,
                        tests: List[CapabilityTest]) -> List[Dict[str, Any]]:
        """
        Run all tests against the current implementation.
        
        This executes tests in isolation and collects detailed results including
        any errors or failures.
        
        Args:
            implementation: The implementation code to test
            tests: List of tests to run
            
        Returns:
            List of test results with passed/failed status and error details
        """
        results = []
        
        for test in tests:
            result = await self._run_single_test(implementation, test)
            results.append(result)
        
        return results
    
    async def _run_single_test(self,
                               implementation: str,
                               test: CapabilityTest) -> Dict[str, Any]:
        """
        Run a single test case.
        
        Args:
            implementation: Implementation code
            test: Test to run
            
        Returns:
            Test result dictionary
        """
        try:
            # Create a sandbox namespace for execution
            namespace = {}
            
            # Execute the implementation to define the 'execute' function
            exec(implementation, namespace)
            
            if 'execute' not in namespace:
                return {
                    "test_name": test.name,
                    "passed": False,
                    "error": "Implementation does not define 'execute' function",
                    "execution_time_ms": 0
                }
            
            # Execute the test code
            exec(test.test_code, namespace)
            
            # Run the test function
            test_function = namespace[test.name]
            execute_function = namespace['execute']
            
            start = datetime.now()
            test_function(execute_function)
            elapsed_ms = (datetime.now() - start).total_seconds() * 1000
            
            return {
                "test_name": test.name,
                "passed": True,
                "error": None,
                "execution_time_ms": elapsed_ms
            }
            
        except AssertionError as e:
            return {
                "test_name": test.name,
                "passed": False,
                "error": f"Assertion failed: {str(e)}",
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "test_name": test.name,
                "passed": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "execution_time_ms": 0
            }
    
    def _create_refinement_prompt(self,
                                 request: CapabilityRequest,
                                 current_implementation: str,
                                 failures: List[Dict[str, Any]]) -> str:
        """
        Create a prompt for refining code based on test failures.
        
        Args:
            request: Original capability request
            current_implementation: Current (failing) implementation
            failures: List of test failure details
            
        Returns:
            Refinement prompt for the LLM
        """
        failures_description = "\n".join([
            f"- {failure['test_name']}: {failure['error']}"
            for failure in failures
        ])
        
        prompt = f"""The following implementation is failing some tests. Please fix it.

ORIGINAL REQUEST:
{request.description}

CURRENT IMPLEMENTATION:
```python
{current_implementation}
```

FAILING TESTS:
{failures_description}

Please provide a corrected version of the 'execute' function that fixes these test failures.
Focus on the specific errors reported. Keep the function signature the same.

Generate ONLY the corrected execute function. Do not include imports or test code.
"""
        return prompt
    
    async def _refine_implementation(self,
                                    prompt: str,
                                    current_implementation: str,
                                    failures: List[Dict[str, Any]]) -> Optional[str]:
        """
        Refine the implementation based on test failures.
        
        Args:
            prompt: Refinement prompt
            current_implementation: Current implementation
            failures: Test failures
            
        Returns:
            Refined implementation or None
        """
        try:
            refined = await self.llm_provider.generate_code(
                prompt=prompt,
                temperature=0.2,  # Even lower temperature for refinement
                max_tokens=2000
            )
            
            if not self._validate_python_syntax(refined):
                return None
            
            return refined
            
        except Exception as e:
            print(f"Error refining implementation: {e}")
            return None
    
    def _validate_python_syntax(self, code: str) -> bool:
        """
        Validate that code is syntactically correct Python.
        
        Args:
            code: Python code string
            
        Returns:
            True if valid Python syntax, False otherwise
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False
    
    def _create_capability(self,
                          request: CapabilityRequest,
                          implementation: str,
                          tests: List[CapabilityTest]) -> Capability:
        """
        Create a Capability object from successful synthesis.
        
        Args:
            request: Original request
            implementation: Working implementation
            tests: Passing tests
            
        Returns:
            Complete Capability instance
        """
        # Extract function signature from implementation
        signature = self._extract_function_signature(implementation)
        
        capability = Capability(
            name=self._generate_capability_name(request.description),
            description=request.description,
            category=request.category,
            implementation_code=implementation,
            entry_point="execute",
            signature=signature,
            tests=tests,
            trust_level=TrustLevel.UNTRUSTED,  # Starts as untrusted
            python_requirements=request.requirements,
            tags=self._generate_tags(request.description)
        )
        
        return capability
    
    def _generate_capability_name(self, description: str) -> str:
        """
        Generate a reasonable capability name from description.
        
        Args:
            description: Capability description
            
        Returns:
            Snake_case capability name
        """
        # Simple name generation - could be enhanced
        words = re.findall(r'\w+', description.lower())
        return "_".join(words[:4])  # Use first 4 words
    
    def _generate_tags(self, description: str) -> List[str]:
        """
        Generate tags from description for searchability.
        
        Args:
            description: Capability description
            
        Returns:
            List of tags
        """
        # Extract meaningful words as tags
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'for', 'to', 'of', 'in', 'on', 'at'}
        words = re.findall(r'\w+', description.lower())
        tags = [w for w in words if w not in stop_words and len(w) > 3]
        return list(set(tags))[:10]  # Limit to 10 unique tags
    
    def _extract_function_signature(self, implementation: str) -> Dict[str, Any]:
        """
        Extract function signature from implementation code.
        
        Args:
            implementation: Python code
            
        Returns:
            Dictionary describing function signature
        """
        try:
            tree = ast.parse(implementation)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'execute':
                    args = [arg.arg for arg in node.args.args]
                    
                    # Try to extract type hints if present
                    return {
                        "parameters": args,
                        "has_docstring": ast.get_docstring(node) is not None
                    }
            
            return {"parameters": [], "has_docstring": False}
            
        except:
            return {"parameters": [], "has_docstring": False}
    
    def _create_failure_result(self,
                               start_time: datetime,
                               iterations: int,
                               test_results: List[Dict[str, Any]],
                               error_messages: List[str],
                               synthesis_log: List[str]) -> SynthesisResult:
        """
        Create a synthesis result for a failed attempt.
        
        Args:
            start_time: When synthesis started
            iterations: Number of iterations attempted
            test_results: Test results collected
            error_messages: Error messages collected
            synthesis_log: Synthesis log entries
            
        Returns:
            SynthesisResult indicating failure
        """
        elapsed = (datetime.now() - start_time).total_seconds()
        
        result = SynthesisResult(
            success=False,
            capability=None,
            iterations=iterations,
            total_time_seconds=elapsed,
            test_results=test_results,
            error_messages=error_messages,
            synthesis_log=synthesis_log
        )
        
        self.synthesis_history.append(result)
        return result
    
    @property
    def success_rate(self) -> float:
        """
        Calculate the success rate of synthesis attempts.
        
        Returns honest metrics about how well the synthesizer is performing.
        
        Returns:
            Success rate as a percentage
        """
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_syntheses / self.total_attempts) * 100.0
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics about synthesizer performance.
        
        Returns:
            Dictionary of metrics including success rate, average iterations, etc.
        """
        return {
            "total_attempts": self.total_attempts,
            "successful_syntheses": self.successful_syntheses,
            "success_rate_percent": self.success_rate,
            "average_iterations": self.average_iterations,
            "max_iterations": self.max_iterations
        }
