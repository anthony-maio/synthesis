"""
Test-Driven Development Synthesizer.

Core engine that generates capabilities through iterative test-driven development.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from synthesis.core.models import (
    Capability,
    CapabilityCategory,
    CapabilityMetadata,
    ExecutionStatus,
    ParameterSchema,
    ReturnSchema,
    SynthesisAttempt,
    SynthesisStatus,
    TestCase,
    TestResult,
    TestSuite,
    RiskLevel,
)
from synthesis.llm.provider import LLMProvider


class TDDSynthesizer:
    """Synthesizes capabilities using test-driven development"""
    
    def __init__(self, llm_provider: LLMProvider, max_iterations: int = 5):
        """
        Initialize synthesizer.
        
        Args:
            llm_provider: LLM provider for generation
            max_iterations: Maximum refinement iterations
        """
        self.llm = llm_provider
        self.max_iterations = max_iterations
    
    async def synthesize(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None,
    ) -> SynthesisAttempt:
        """
        Synthesize a capability from a natural language requirement.
        
        Args:
            requirement: What capability is needed
            category: Optional category hint
            
        Returns:
            SynthesisAttempt with results
        """
        attempt = SynthesisAttempt(
            id=f"syn-{uuid.uuid4().hex[:8]}",
            requirement=requirement,
            category=category or CapabilityCategory.OTHER,
            status=SynthesisStatus.GENERATING_TESTS,
        )
        
        try:
            # Step 1: Generate tests
            attempt.status = SynthesisStatus.GENERATING_TESTS
            test_suite = await self._generate_tests(requirement)
            attempt.test_suite = test_suite
            attempt.tests_generated = len(test_suite.tests)
            attempt.total_tests = len(test_suite.tests)
            
            # Step 2: Generate code and iterate
            attempt.status = SynthesisStatus.GENERATING_CODE
            code = await self._generate_implementation(requirement, test_suite)
            attempt.generated_code = code
            
            # Step 3: Run tests and refine
            for iteration in range(self.max_iterations):
                attempt.iterations = iteration + 1
                attempt.status = SynthesisStatus.RUNNING_TESTS
                
                # Execute tests
                results = await self._run_tests(code, test_suite)
                attempt.test_results = results
                attempt.tests_passed = sum(1 for r in results if r.passed)
                attempt.total_tests = len(results)
                
                # Check if all tests pass
                if attempt.tests_passed == attempt.total_tests:
                    attempt.status = SynthesisStatus.COMPLETE
                    attempt.generated_code = code
                    
                    # Create capability
                    attempt.capability = await self._create_capability(
                        requirement,
                        code,
                        test_suite,
                        category,
                    )
                    break
                
                # If tests fail and iterations remain, refine
                if iteration < self.max_iterations - 1:
                    attempt.status = SynthesisStatus.REFINING
                    code = await self._refine_implementation(
                        requirement,
                        code,
                        test_suite,
                        results,
                        iteration,
                    )
                else:
                    attempt.status = SynthesisStatus.FAILED
                    attempt.errors.append(
                        f"Failed to pass all tests after {self.max_iterations} iterations"
                    )
        
        except Exception as e:
            attempt.status = SynthesisStatus.FAILED
            attempt.errors.append(str(e))
        
        finally:
            attempt.completed_at = datetime.utcnow()
        
        return attempt
    
    async def _generate_tests(self, requirement: str) -> TestSuite:
        """Generate comprehensive test suite from requirement"""
        prompt = f"""You are a senior software engineer. Generate a comprehensive test suite for this capability:

REQUIREMENT: {requirement}

Generate 5-10 test cases that thoroughly exercise the capability. Include:
- Normal case tests
- Edge cases (empty input, None values, etc.)
- Error conditions
- Boundary conditions

Format your response as a JSON object with this structure:
{{
    "name": "test_suite_name",
    "tests": [
        {{
            "name": "test_name",
            "description": "what this test validates",
            "inputs": {{"param1": value1, "param2": value2}},
            "expected_output": expected_result,
            "should_raise": null
        }}
    ]
}}

Be specific with test data. Make tests that will actually validate correctness."""

        response = await self.llm.complete(
            prompt,
            temperature=0.3,
            max_tokens=2048,
        )
        
        # Parse response
        try:
            # Handle markdown code blocks
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            test_data = json.loads(content.strip())
        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"Failed to parse test generation response: {e}")
        
        # Build TestSuite
        tests = [
            TestCase(
                name=t["name"],
                description=t.get("description"),
                inputs=t["inputs"],
                expected_output=t["expected_output"],
                should_raise=t.get("should_raise"),
            )
            for t in test_data.get("tests", [])
        ]
        
        return TestSuite(
            name=test_data.get("name", "generated_tests"),
            tests=tests,
            description=f"Tests for: {requirement}",
        )
    
    async def _generate_implementation(
        self,
        requirement: str,
        test_suite: TestSuite,
    ) -> str:
        """Generate initial implementation"""
        tests_json = json.dumps(
            [
                {
                    "name": t.name,
                    "inputs": t.inputs,
                    "expected": t.expected_output,
                }
                for t in test_suite.tests
            ],
            indent=2,
        )
        
        prompt = f"""You are an expert Python developer. Write a Python function that satisfies this requirement:

REQUIREMENT: {requirement}

The function must pass these test cases:
{tests_json}

Write ONLY valid Python code that:
1. Defines one or more functions
2. Handles edge cases properly
3. Returns the correct type
4. Includes error handling

Do not include imports unless absolutely necessary. Stick to Python builtins.

Code:"""

        response = await self.llm.complete(
            prompt,
            temperature=0.5,
            max_tokens=2048,
        )
        
        # Extract code from response
        code = response.content
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        
        return code.strip()
    
    async def _run_tests(
        self,
        code: str,
        test_suite: TestSuite,
    ) -> list[TestResult]:
        """Execute tests against implementation"""
        results = []
        
        try:
            # Create execution namespace
            namespace: dict = {}
            exec(code, namespace)
            
            # Find the function to test
            func = None
            for name, obj in namespace.items():
                if callable(obj) and not name.startswith("_"):
                    func = obj
                    break
            
            if not func:
                raise ValueError("No callable function found in generated code")
            
            # Run each test
            for test_case in test_suite.tests:
                try:
                    # Call function with test inputs
                    result = func(**test_case.inputs)
                    
                    # Check result
                    passed = result == test_case.expected_output
                    
                    results.append(
                        TestResult(
                            test_case=test_case,
                            passed=passed,
                            actual_output=result,
                        )
                    )
                except Exception as e:
                    results.append(
                        TestResult(
                            test_case=test_case,
                            passed=False,
                            error_message=str(e),
                        )
                    )
        
        except Exception as e:
            # If code won't even execute, mark all tests as failed
            for test_case in test_suite.tests:
                results.append(
                    TestResult(
                        test_case=test_case,
                        passed=False,
                        error_message=str(e),
                    )
                )
        
        return results
    
    async def _refine_implementation(
        self,
        requirement: str,
        current_code: str,
        test_suite: TestSuite,
        test_results: list[TestResult],
        iteration: int,
    ) -> str:
        """Generate refined implementation based on test failures"""
        failed_tests = [r for r in test_results if not r.passed]
        
        failures = []
        for result in failed_tests:
            failures.append(
                f"Test '{result.test_case.name}': "
                f"input={result.test_case.inputs}, "
                f"expected={result.test_case.expected_output}, "
                f"got={result.actual_output}, "
                f"error={result.error_message}"
            )
        
        prompt = f"""You are debugging and improving Python code. The implementation failed some tests.

REQUIREMENT: {requirement}

CURRENT IMPLEMENTATION:
```python
{current_code}
```

FAILED TESTS (Iteration {iteration + 1}):
{chr(10).join(failures)}

Analyze the failures and generate an IMPROVED implementation that fixes these issues.

Common issues to check:
1. Off-by-one errors
2. Type mismatches (returning wrong type)
3. Missing None/empty input handling
4. Logic errors
5. Incorrect assumptions about input format

Write ONLY valid Python code with the corrected implementation:
```python"""

        response = await self.llm.complete(
            prompt,
            temperature=0.3,
            max_tokens=2048,
        )
        
        code = response.content
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
        
        return code.strip()
    
    async def _create_capability(
        self,
        requirement: str,
        code: str,
        test_suite: TestSuite,
        category: Optional[CapabilityCategory],
    ) -> Capability:
        """Create a Capability object from successful synthesis"""
        # Parse requirement to extract capability name
        name = requirement.split()[0].lower().replace(" ", "_")
        
        capability = Capability(
            id=f"cap-{uuid.uuid4().hex[:8]}",
            name=name,
            description=requirement,
            category=category or CapabilityCategory.OTHER,
            parameters=ParameterSchema(properties={}, required=[]),
            returns=ReturnSchema(type="any"),
            implementation_code=code,
            dependencies=[],
            metadata=CapabilityMetadata(
                created_by="synthesizer",
                synthesis_reasoning=f"Auto-synthesized from requirement: {requirement}",
            ),
            risk_level=RiskLevel.MEDIUM,
            test_suite=test_suite,
        )
        
        return capability
