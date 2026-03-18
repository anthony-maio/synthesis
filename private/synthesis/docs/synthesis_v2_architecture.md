# Synthesis Framework v2: Architecture & Design Document

**Status:** Design Phase  
**Version:** 2.0 (Production-Ready Implementation)  
**Date:** October 2025  
**Audience:** Implementation Team, Portfolio Review  

---

## Executive Summary

Synthesis is an AI capability synthesis framework that enables agentic AI systems to autonomously create, validate, sandbox, and improve their own tools. The key innovation is replacing one-shot code generation (40-60% failure rate) with test-driven iterative synthesis that produces reliably working capabilities (targeting 80-85% on realistic tasks).

This document describes a production-grade architecture that addresses the critical flaws identified in the initial brainstorm: unrealistic success claims, unsafe code generation patterns, incomplete sandboxing, and missing observability. We'll build a system that is scientifically honest about what LLMs can do, prioritizes security from day one, and measures everything we claim.

The architecture is organized in three layers that can ship independently: a working TDD synthesis core, real sandboxing infrastructure, and finally a repository system with network effects.

---

## Part 1: Problem Statement & Vision

### Why Synthesis Matters

Modern agentic AI systems face a fundamental limitation: they're constrained to pre-defined tools. When an agent encounters a task it cannot perform, it has three poor options. First, it can fail the task entirely. Second, it can wait for a human developer to write the needed capability, which introduces latency and dependency on human availability. Third, it can attempt to hack together a solution with existing tools, which leads to brittle, inefficient results.

Synthesis reimagines this constraint as an opportunity. Instead of waiting for humans, agents should synthesize their own capabilities when needed. This requires solving several interconnected problems: the code generation problem (LLMs are bad at one-shot code generation), the validation problem (how do we know generated code works?), the safety problem (how do we run untrusted code?), and the network problem (how do agents share and improve capabilities collaboratively?).

### Why Current Approaches Fall Short

One-shot code generation from language models produces correct, working code only 40-60% of the time on non-trivial tasks. The failures fall into several categories: logic errors (the code runs but does the wrong thing), type mismatches (returning the wrong data structure), missing edge case handling (crashes on empty input or None values), and incorrect assumptions about API contracts or data formats.

The critical insight is that this isn't a limitation of the model's knowledge—it's a limitation of the generation process. Just as human developers don't write correct code on the first try, LLMs perform much better when given feedback and opportunities to refine. Research shows that incorporating test-driven development during generation significantly improves correctness, with some studies showing improvements from 45% to 80-85% on identical tasks.

Current frameworks either ignore this reality or claim to solve it without evidence. They also typically treat security as an afterthought, using theatrical measures like restricting `__builtins__` that provide a false sense of safety. Real sandboxing requires real isolation—containers, separate processes with resource limits, or carefully designed restricted execution environments.

### The Vision: Self-Improving AI Capability Ecosystems

Synthesis envisions a future where agentic AI systems can not only create their own tools but improve them continuously. An agent encounters a need, generates a capability through test-driven synthesis, validates it in a sandbox, shares it with other agents, and then automatically improves it based on real-world usage patterns. Other agents discover these capabilities, reuse them, fork and improve them, creating a network effect where the system becomes increasingly capable over time.

This isn't science fiction—the components are well-understood. What's novel is combining them coherently: TDD synthesis for reliability, graduated trust systems for realistic security, observability for understanding what actually works, and repository infrastructure for network effects.

---

## Part 2: Foundational Principles

### Principle 1: Honest Measurement Over Optimistic Claims

We will measure what actually works rather than asserting success rates. For any claim about synthesis success, we'll implement the measurement infrastructure first and report real results. We won't claim "85%+ success rate"—we'll implement comprehensive logging, run synthesis against a real test suite, and report what percentage of generated capabilities pass their tests on the first attempt, second attempt, third attempt, etc.

This principle affects architecture in concrete ways. Every synthesis attempt must log: what was requested, what tests were generated, what code was generated, how many refinement iterations occurred, what the final test pass rate was, and what the failure modes were. This data is the raw material for understanding how to improve the system and being honest about its capabilities.

### Principle 2: Security as a First-Class Concern

Untrusted code should be treated as hostile by default. We will not rely on runtime restrictions like limiting built-ins or preventing import statements—these are speed bumps, not barriers. Instead, we'll use real isolation: Docker containers for maximum isolation, subprocess boundaries for medium isolation, and restricted execution contexts for low-risk code.

The security architecture will implement graduated trust, where capabilities earn privileges through proven safe execution. A new capability starts in maximum isolation (Docker container with no network, read-only filesystem), and only after demonstrating successful, safe execution over a sufficient number of invocations does it graduate to less restrictive sandboxes. This creates a realistic security model that doesn't demand perfect code generation while still protecting the system.

### Principle 3: Observable by Default

We will build observability into every layer of the system from day one. This means comprehensive logging of synthesis attempts, execution traces for all capability invocations, metrics for trust escalation, and dashboards showing system health. The goal is that we can answer questions like "why did this synthesis fail?" and "which types of tasks generate unreliable code?" without guessing or adding observability later.

### Principle 4: Pragmatic Engineering

We won't build what we don't need yet. The MVP focuses ruthlessly on making the core TDD synthesis loop work reliably and safely. Repositories, automatic evolution, and network effects are powerful but secondary. We'll implement them in subsequent phases once the foundation is solid.

### Principle 5: Collaborative Partnership

This framework is designed for partnership between humans and AI systems. Humans validate generated code, decide when to deploy capabilities, review evolution suggestions, and maintain the repository. AI systems generate, refine, test, and improve. Neither is in control—they're partners in the process, each contributing what they do well.

---

## Part 3: System Architecture Overview

### High-Level Architecture

The Synthesis system consists of five major subsystems working in concert. Understanding how they interact is essential to understanding the overall design.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SYNTHESIS CORE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐        ┌──────────────────┐                  │
│  │  Agent Interface │        │  Human Interface │                  │
│  │   (Need Tool)    │        │  (Create Tool)   │                  │
│  └────────┬─────────┘        └────────┬─────────┘                  │
│           │                           │                             │
│           └──────────────┬────────────┘                             │
│                          ▼                                           │
│           ┌──────────────────────────────┐                         │
│           │  Synthesis Request Router    │                         │
│           │  • Parse requirements        │                         │
│           │  • Check repository first    │                         │
│           │  • Decide: generate or reuse │                         │
│           └──────────────┬───────────────┘                         │
│                          │                                           │
│          ┌───────────────┴───────────────┐                         │
│          │                               │                          │
│          ▼                               ▼                          │
│  ┌──────────────────┐        ┌──────────────────────┐             │
│  │   Repository     │        │  TDD Synthesizer     │             │
│  │   • Search       │        │  • Test Generation   │             │
│  │   • Retrieve     │        │  • Code Generation   │             │
│  │   • Metadata     │        │  • Iterative Refine  │             │
│  └──────────────────┘        │  • Knowledge Base    │             │
│          │                   └──────────┬───────────┘             │
│          │                              │                          │
│          └──────────────────┬───────────┘                          │
│                             ▼                                       │
│           ┌──────────────────────────────┐                        │
│           │  Safe Code Validator         │                        │
│           │  • AST Analysis              │                        │
│           │  • Dependency Audit          │                        │
│           │  • Risk Assessment           │                        │
│           └──────────────┬───────────────┘                        │
│                          │                                          │
│                          ▼                                          │
│           ┌──────────────────────────────┐                        │
│           │  Sandboxed Runtime           │                        │
│           │  • UNTRUSTED (Docker)        │                        │
│           │  • PROBATION (Process)       │                        │
│           │  • TRUSTED (Direct)          │                        │
│           └──────────────┬───────────────┘                        │
│                          │                                          │
│          ┌───────────────┴───────────────┐                        │
│          │                               │                         │
│          ▼                               ▼                         │
│  ┌──────────────────┐        ┌──────────────────────┐            │
│  │  Observatory     │        │  Evolution Engine    │            │
│  │  • Metrics       │        │  • Performance Track │            │
│  │  • Logging       │        │  • Automatic Improve │            │
│  │  • Dashboards    │        │  • A/B Testing       │            │
│  └──────────────────┘        └──────────────────────┘            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

The flow is roughly: an agent or human expresses a need, the system checks the repository first (why synthesize if someone already solved it?), if needed it synthesizes using TDD, validates the code for safety, runs it in an appropriate sandbox, and observes what happens. Over time, capabilities that work well get used more, and the evolution engine automatically improves them.

### Layered Implementation Strategy

We'll implement this system in three distinct layers that can be deployed independently, each providing value even without the subsequent layers.

**Layer 1: Core Synthesis & Safety (MVP)** focuses on making the TDD synthesis loop work reliably and safely. This layer includes the synthesizer engine, test generation, code validation, and sandbox infrastructure. By the end of this layer, agents can request capabilities, get them synthesized, and execute them safely. This alone is valuable—it demonstrates the core innovation.

**Layer 2: Repository & Trust** adds the infrastructure for capabilities to be stored, discovered, and reused. This layer includes the capability repository, metadata management, trust scoring based on execution history, and graduated privilege escalation. With this layer, multiple agents can benefit from each other's synthesized capabilities, and the trust system begins creating real security properties.

**Layer 3: Evolution & Network Effects** implements automatic capability improvement based on usage metrics, A/B testing of improvements, and collaborative development workflows. This is where the system becomes self-improving and achieves true network effects.

---

## Part 4: Layer 1 - Core Synthesis & Safety

### The TDD Synthesizer: Making Code Generation Actually Work

The TDD synthesizer is the heart of the system, and its design directly addresses the one-shot code generation problem. Instead of asking an LLM to write correct code once, we ask it to iterate until the code passes tests.

The synthesis flow consists of these steps. First, we parse the natural language requirement and generate a comprehensive test suite. This is critical—the tests define what "correct" means. Second, we generate an initial implementation based on the requirements and tests. Third, we execute the tests against the implementation in a sandbox. Fourth, if tests fail, we analyze the failures, feed them back to the LLM with specific error messages and context, and generate a refined implementation. Fifth, we repeat steps three through four until tests pass or we hit a maximum iteration limit.

The key insight is that this process is much more reliable than one-shot generation. The LLM sees real feedback—not just "your code is wrong" but "test 3 failed because you returned a list when you should return a dict" or "your function raises ValueError on empty input". With this concrete feedback, the LLM can make targeted fixes rather than regenerating from scratch.

```python
class TDDSynthesizer:
    """
    Test-Driven Development based capability synthesis engine.
    
    The core insight: LLMs are bad at one-shot code generation but excellent
    at iterative refinement when given concrete test failures.
    """
    
    async def synthesize(
        self,
        requirement: str,
        max_iterations: int = 5,
        timeout_per_iteration: float = 30.0
    ) -> SynthesisResult:
        """
        Synthesize a capability using test-driven development.
        
        Args:
            requirement: Natural language description of what capability is needed
            max_iterations: Maximum refinement iterations before giving up
            timeout_per_iteration: Maximum time for code execution per iteration
            
        Returns:
            SynthesisResult with generated capability, test results, and metadata
            
        The flow:
        1. Generate test suite from requirement
        2. Generate implementation from requirement + tests
        3. Execute tests and collect results
        4. If tests pass, return success
        5. If tests fail, analyze failures and generate refined implementation
        6. Repeat steps 3-5 until success or iteration limit
        """
```

The test generation phase deserves special attention. We're asking the LLM to generate tests that thoroughly exercise the capability. These tests should cover normal cases, edge cases, and error conditions. The quality of these tests directly determines whether the synthesized code will be useful, so we invest effort here. We prompt the LLM to generate tests that are specific, independent (each test is self-contained), and cover edge cases like empty inputs, None values, type mismatches, and boundary conditions.

For the implementation generation, we provide the LLM with the requirement, the generated tests, and (on subsequent iterations) the failures from previous attempts. On iteration N, the prompt includes concrete error messages from iteration N-1, so the LLM can see exactly what went wrong. This dramatically improves the quality of refinements.

The sandbox execution is where safety comes in. All generated code runs in a restricted environment where we can observe what happens and catch errors safely. We'll cover the sandbox architecture in the next section.

### Safe Code Generation: Treating Implementation as a Module

The initial design had a critical flaw: directly concatenating implementation code into a template string. This creates several problems. First, indentation issues in generated code can cause syntax errors. Second, quote characters in the code can break the string literal. Third, it's hard to validate or transform the code before execution. Fourth, it's conceptually wrong—the implementation should be a proper Python module, not string interpolation.

We'll instead treat the generated implementation as a separate module with explicit function signatures. Here's the pattern:

```python
class SafeCodeGenerator:
    """
    Generates code safely by treating implementation as a separate module.
    """
    
    def generate_capability_module(
        self,
        function_name: str,
        parameters: ParameterSchema,
        returns: ReturnSchema,
        implementation_code: str,
        dependencies: List[str]
    ) -> Tuple[str, str]:
        """
        Generate a complete, validated capability module.
        
        Returns:
            (module_code, validation_errors)
            
        The generated module has this structure:
        
        ```python
        # capabilities/[name]_[version].py
        # Generated by Synthesis - DO NOT EDIT
        
        from typing import Any, Dict, List, Optional
        
        # Implementation (user-generated code goes here)
        [IMPLEMENTATION_CODE]
        
        # Entry point that Synthesis calls
        def _synthesize_entry_point(args: Dict[str, Any]) -> Any:
            # Unpack arguments according to ParameterSchema
            # Call the capability function
            # Type-check return value against ReturnSchema
            # Return result or raise with clear error message
        ```
        
        This approach:
        1. Isolates implementation code (easier to validate)
        2. Enforces explicit signatures (prevents hidden assumptions)
        3. Enables type checking (catch mismatches early)
        4. Creates audit trail (module path and version)
        """
```

The generation process has several validation steps. First, we parse the generated code as an AST to check that it's syntactically valid. Second, we analyze the AST to identify problematic patterns: direct file I/O, network access, database connections, subprocess spawning, or imports of modules we've marked as risky. Third, we verify that the code contains exactly one function with a name matching what we expect (or we can extract the first function defined). Fourth, we perform a "dry run" that type-checks the function against the declared parameters and return types using Python's inspect module.

Only after passing all validations do we load and execute the module.

### Sandbox Architecture: Graduated Trust Through Real Isolation

The sandbox subsystem implements graduated trust—new capabilities start maximally isolated and earn privileges through proven safe execution. There are three trust levels, each with different isolation mechanisms.

**UNTRUSTED** is the maximum isolation level, used for all newly synthesized capabilities. Code runs in a Docker container with these properties: the container has no network access (networking is disabled), the filesystem is read-only except for a small temporary directory (capabilities can't modify anything on the host), and resource limits are strict (max 256MB memory, 1 CPU core, 30-second timeout). The container also has no access to any host environment variables or secrets. This is meant to make it impossible for even deliberately malicious code to escape or harm the system.

**PROBATION** is the intermediate level, used after a capability has passed 10 executions with 90%+ success rate and hasn't been running for fewer than 7 days in UNTRUSTED mode (giving time to detect subtle issues). Code at this level runs in a separate Python process from the main Synthesis process but on the same machine. The process has resource limits (512MB memory, 2 CPU cores, 60-second timeout) but does have access to a limited set of standard library modules and can read (but not write) certain approved directories. No network access or database access yet.

**TRUSTED** is used for capabilities with strong track records: 50+ executions at 95%+ success rate and at least 30 days at PROBATION level. Code runs directly in the main Synthesis process but with a runtime watchdog that can terminate it if it exceeds resource limits. It has access to a broader set of standard libraries and can make outbound network connections to approved domains. This level is for proven, stable capabilities where the performance overhead of isolation is no longer justified.

```python
class SandboxRuntime:
    """
    Executes code with isolation appropriate to its trust level.
    """
    
    async def execute(
        self,
        capability: Capability,
        arguments: Dict[str, Any],
        trust_level: TrustLevel
    ) -> ExecutionResult:
        """
        Execute capability in a sandbox appropriate to its trust level.
        
        Args:
            capability: The capability to execute
            arguments: Arguments to pass to the capability
            trust_level: Current trust level of the capability
            
        Returns:
            ExecutionResult with output, metrics, and any errors
            
        Dispatch logic:
        - TrustLevel.UNTRUSTED: Docker container
        - TrustLevel.PROBATION: Subprocess isolation
        - TrustLevel.TRUSTED: Direct execution with watchdog
        """
```

The Docker implementation uses container orchestration to spawn, monitor, and clean up containers. We use minimal base images to reduce attack surface. The subprocess implementation uses Python's subprocess module with careful handling of input/output, resource limits via psutil, and timeout management. The direct execution implementation uses signal handlers and resource monitoring to catch runaway code.

### Code Validator: Static Analysis Before Execution

Before code ever runs, we analyze it statically to identify risky patterns. This isn't a security guarantee—all static analysis has limitations—but it's a useful first line of defense that catches obvious problems.

The validator works on the Python AST (Abstract Syntax Tree), which we can analyze without executing the code. We check for problematic imports (like `os.system` or `subprocess`), direct file access patterns (open(), read(), write()), network operations (socket, http.client, urllib), and suspicious function calls. We maintain a whitelist of safe imports and functions and a blacklist of dangerous ones, with a review layer for the gray areas.

```python
class CodeValidator:
    """
    Validates generated code for safety before execution.
    """
    
    UNSAFE_IMPORTS = {
        'os', 'subprocess', 'sys', 'importlib', '__import__',
        'socket', 'urllib', 'requests', 'paramiko',  # network
        'sqlite3', 'psycopg2', 'mysql',  # databases
        'pickle', 'shelve'  # serialization attacks
    }
    
    UNSAFE_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'raw_input'
    }
    
    async def validate(
        self,
        code: str,
        trust_level: TrustLevel
    ) -> ValidationResult:
        """
        Validate code and return safety assessment.
        
        Returns ValidationResult with:
        - is_valid: Whether code passes validation
        - issues: List of safety concerns (if any)
        - risk_level: Overall risk assessment
        - recommendations: Suggestions for fixes
        """
```

The validation results feed into the sandbox selection logic. Code with critical issues (like direct file access) might need Docker isolation even if it otherwise seems safe. Code with no issues can potentially skip straight to PROBATION if it passes tests.

### Knowledge Base: Learning from Synthesis Attempts

The knowledge base accumulates patterns and insights from every synthesis attempt, making future synthesis more effective. When we encounter an error we haven't seen before, we analyze it and record both the error pattern and what fixed it. When synthesis fails on a particular type of task, we record that and can warn future synthesis attempts about similar tasks.

The knowledge base tracks several types of information. Error patterns include common bugs like off-by-one errors, None handling issues, type mismatches, and API misunderstandings. For each error pattern, we store the frequency, example instances, and successful fixes. Task patterns include categories like "sort a list", "filter data", "transform format" along with common pitfalls and solution patterns for each category. Library patterns record knowledge about specific libraries—how to use the requests library correctly, what edge cases to handle with JSON parsing, etc.

```python
class KnowledgeBase:
    """
    Accumulates insights from synthesis attempts to improve future synthesis.
    """
    
    async def record_synthesis_attempt(
        self,
        requirement: str,
        tests_generated: List[TestCase],
        implementation_code: str,
        test_results: List[TestResult],
        iterations_to_success: int,
        success: bool
    ) -> None:
        """
        Record this synthesis attempt for learning.
        
        Extracts patterns:
        - Error patterns (if tests failed)
        - Task category (from requirement)
        - Solution pattern (from successful code)
        - Difficulty level (based on iterations needed)
        """
    
    async def get_synthesis_context(
        self,
        requirement: str
    ) -> SynthesisContext:
        """
        Get context that might help with a similar requirement.
        
        Returns historical patterns, common pitfalls, and tips
        for this category of task.
        """
```

The knowledge base uses vector embeddings to find similar requirements and error patterns. When synthesizing a new capability, we can check if we've seen something similar before and incorporate those insights into the prompt.

### Observability: Measuring What Actually Works

From day one, we log everything. Every synthesis attempt records what was requested, what tests were generated, what code was generated, how many iterations it took, what the final test pass rate was, and what the failure modes were. Every capability execution records the arguments, the result, the execution time, resource usage, and any errors.

This data feeds into dashboards and alerts. We can answer questions like:

- What percentage of synthesis attempts succeed on iteration 1? Iteration 2? Iteration 3?
- What types of requirements cause repeated synthesis failures?
- Which capabilities have the highest error rates?
- What's the distribution of execution times for capabilities?
- Are certain error patterns recurring?

```python
class Observatory:
    """
    Comprehensive observability for the Synthesis system.
    """
    
    class SynthesisMetrics:
        """Metrics for a single synthesis attempt"""
        requirement: str
        task_category: str
        test_count: int
        test_pass_rate_by_iteration: Dict[int, float]
        iterations_to_success: int
        total_time_ms: float
        timestamp: datetime
        success: bool
    
    class ExecutionMetrics:
        """Metrics for a single capability execution"""
        capability_id: str
        trust_level: TrustLevel
        arguments_hash: str  # Don't log sensitive data
        execution_time_ms: float
        memory_peak_mb: float
        success: bool
        error_category: Optional[str]
        timestamp: datetime
    
    async def query_synthesis_success_rate(
        self,
        task_category: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """Get synthesis success metrics."""
```

The observability layer helps us be honest about what's working and what isn't. If we discover that synthesis for a particular category of tasks has a 40% success rate, we'll know it and can investigate why.

---

## Part 5: Layer 2 - Repository & Trust Management

### Capability Repository: The Foundation for Network Effects

Once capabilities are synthesized and proven safe, they should be stored where other agents can discover and reuse them. The repository is straightforward in structure but important in function.

Each capability entry in the repository contains the capability definition (name, description, parameters, return type), the implementation code, metadata (author, creation date, version), usage statistics (total downloads, success rate, execution time distribution), and ratings from users. The repository supports search (by name, description, category), discovery (trending capabilities, recommendations based on usage patterns), forking (creating a variant based on an existing capability), and versioning (multiple versions of the same capability can coexist).

```python
class CapabilityRepository:
    """
    Central store for shareable, reusable capabilities.
    """
    
    class CapabilityEntry:
        """Metadata for a repository entry"""
        id: str  # Globally unique
        name: str
        description: str
        category: CapabilityCategory
        version: str
        author_id: str
        created_at: datetime
        implementation: str  # The actual code
        tests: List[TestCase]  # Tests that validate it
        dependencies: List[str]
        
        # Statistics
        total_downloads: int
        total_executions: int
        successful_executions: int
        failed_executions: int
        average_execution_time_ms: float
        
        # Reviews
        ratings: List[Tuple[float, str]]  # (rating 1-5, review_text)
        
        # Relationships
        parent_id: Optional[str]  # If this is a fork
        forked_by: List[str]  # Other capabilities forked from this
```

The trust model for the repository is crucial. Newly added capabilities start in UNVERIFIED status, visible in the repository but flagged as unproven. As they're used and succeed, they accumulate success rate statistics. Once a capability reaches 100+ successful executions with a 95%+ success rate and has been in the repository for at least 30 days, it can be promoted to VERIFIED status, indicating it's proven reliable. The promotion can be automatic (based on metrics) or human-initiated (someone with repository admin permission manually verifies it).

Users can rate and review capabilities. These ratings feed into discovery algorithms—new users are shown highly-rated capabilities first, recommendations are based on usage patterns, and trending capabilities are based on recent activity.

### Trust Scoring System: Earned Privileges

The trust scoring system determines which sandbox level a capability runs in. New capabilities start in UNTRUSTED and earn trust through successful execution. The system must be transparent and understandable—an agent or human should be able to look at a capability and understand why it's at its current trust level.

```python
class TrustScoringSystem:
    """
    Determines trust level and sandbox privileges for capabilities.
    """
    
    TRUST_TRANSITIONS = {
        TrustLevel.UNTRUSTED: {
            TrustLevel.PROBATION: TrustPromotionCriteria(
                min_successful_executions=10,
                min_success_rate=0.90,
                min_days_at_current_level=7
            )
        },
        TrustLevel.PROBATION: {
            TrustLevel.TRUSTED: TrustPromotionCriteria(
                min_successful_executions=50,
                min_success_rate=0.95,
                min_days_at_current_level=30
            )
        }
    }
    
    async def evaluate_trust_level(
        self,
        capability_id: str
    ) -> Tuple[TrustLevel, TrustEvaluation]:
        """
        Evaluate current trust level for a capability.
        
        Returns:
            (current_trust_level, detailed_evaluation)
            
        The evaluation includes:
        - Current stats (executions, success rate)
        - Time at current level
        - Progress toward next level
        - When next promotion might occur
        """
```

The scoring system is conservative by default. A capability must demonstrate consistent, reliable behavior over time and at scale before earning more privileges. This creates a realistic security model where we don't trust code until it's proven itself.

---

## Part 6: Layer 3 - Evolution & Optimization

### Evolution Engine: Automatic Capability Improvement

Capabilities don't have to remain static. The evolution engine monitors their performance and automatically generates improved versions when it detects issues or opportunities.

The evolution triggers include: high failure rate (if a capability's success rate drops below 90%), frequent timeouts (if more than 10% of executions timeout), poor performance (if average execution time exceeds expected threshold), or scheduled review (every 90 days, revisit the implementation for modernization and optimization).

```python
class EvolutionEngine:
    """
    Monitors capability performance and generates improvements.
    """
    
    class EvolutionTrigger(Enum):
        HIGH_FAILURE_RATE = "high_failure_rate"
        FREQUENT_TIMEOUTS = "frequent_timeouts"
        POOR_PERFORMANCE = "poor_performance"
        SCHEDULED_REVIEW = "scheduled_review"
    
    async def check_and_evolve(
        self,
        capability_id: str
    ) -> Optional[CapabilityVersion]:
        """
        Check if a capability should evolve and generate improvement.
        
        Returns:
            New version of capability if evolution occurred, None otherwise
        """
```

When evolution is triggered, we analyze the issue. If it's a high failure rate, we look at the error patterns in recent executions and generate fixes for the common errors. If it's performance, we analyze execution metrics and generate optimizations. If it's scheduled review, we generate a modernized version that uses current best practices.

The generated improvement is tested against the same test suite that the original passes. If it passes all tests and improves the identified metric (lower failure rate, fewer timeouts, faster execution), we A/B test it: some percentage of incoming requests use the old version, the rest use the new version. We monitor whether the new version actually performs better in production. If it does, we gradually shift traffic to the new version and eventually make it the default.

---

## Part 7: API Design & Interfaces

### Agent Interface: Expressing Capability Needs

Agents need a clean, simple way to express capability needs. The interface supports both declarative and programmatic styles.

```python
class SynthesisClient:
    """
    Client interface for agents to synthesize capabilities.
    """
    
    async def need_capability(
        self,
        requirement: str,
        category: Optional[CapabilityCategory] = None,
        estimated_complexity: Optional[str] = None,  # 'simple', 'medium', 'complex'
        timeout: float = 120.0
    ) -> Capability:
        """
        Express need for a capability.
        
        First checks repository. If exists and suitable, returns it.
        If not, synthesizes a new one using TDD.
        
        Args:
            requirement: Natural language description
            category: Optional category hint (helps discovery)
            estimated_complexity: Agent's estimate of task difficulty
            timeout: Maximum time to wait for synthesis
            
        Returns:
            Ready-to-use Capability object
            
        Example:
            csv_parser = await synthesis.need_capability(
                "Parse CSV data with headers into list of dicts"
            )
            result = await csv_parser.call({"csv_text": data})
        """
    
    async def can_provide_capability(
        self,
        requirement: str
    ) -> CapabilityAvailability:
        """
        Check if a capability exists without synthesizing.
        
        Returns:
            info about existing capabilities or synthesis estimate
        """
```

### Human Interface: Creating & Validating Capabilities

Humans should be able to create capabilities directly, validate syntheses, and make explicit decisions about what gets deployed.

```python
class HumanInterface:
    """
    Interface for humans to create, review, and manage capabilities.
    """
    
    async def create_capability_manually(
        self,
        name: str,
        description: str,
        implementation: str,
        tests: List[TestCase],
        category: CapabilityCategory
    ) -> Capability:
        """
        A human can create a capability directly.
        
        The human writes the implementation and tests. These run through
        the same validation and sandbox pipeline as synthesized capabilities.
        """
    
    async def review_synthesis_attempt(
        self,
        synthesis_id: str
    ) -> SynthesisReview:
        """
        Human reviews a synthesis attempt.
        
        Shows the requirement, generated tests, iterations, final implementation,
        test results. Human can approve, reject, or request modifications.
        """
```

---

## Part 8: Implementation Roadmap

### Phase 1: Core Synthesis (Weeks 1-4)

Focus on making TDD synthesis work reliably with basic sandbox support.

**Week 1-2:** Implement TDDSynthesizer with test generation, code generation, and iterative refinement. Use a simplified sandbox (just subprocess isolation initially).

**Week 3:** Implement code validator and safe code generation patterns. Get rid of string interpolation; treat implementation as a module.

**Week 4:** Build comprehensive observability. Log everything. Create dashboards showing synthesis success by iteration count, task category, etc.

**Deliverable:** An agent can express a capability need, Synthesis generates tests and code iteratively, the code runs safely, and we can see metrics on what actually works.

### Phase 2: Safe Sandboxing (Weeks 5-6)

Implement real sandbox isolation and graduated trust.

**Week 5:** Implement Docker-based UNTRUSTED sandbox. Real isolation, not theater.

**Week 6:** Implement trust scoring system and privilege escalation logic. UNTRUSTED → PROBATION → TRUSTED based on metrics.

**Deliverable:** Capabilities start maximally isolated and earn privileges through proven safe execution.

### Phase 3: Repository & Discovery (Weeks 7-8)

Implement capability repository and network effects.

**Week 7:** Build repository storage, metadata management, search, and discovery.

**Week 8:** Implement rating system, trending capabilities, and recommendations.

**Deliverable:** Multiple agents can share synthesized capabilities, discover existing solutions before synthesizing, and benefit from other agents' work.

### Phase 4: Evolution Engine (Weeks 9-10)

Automatic improvement of existing capabilities.

**Week 9:** Monitor execution metrics, detect evolution triggers, generate improvements.

**Week 10:** Implement A/B testing framework for improvements.

**Deliverable:** Capabilities improve themselves over time based on real-world performance.

### Phase 5: Polish & Documentation (Week 11)

Comprehensive documentation, examples, deployment guides.

---

## Part 9: Technical Debt & Future Considerations

### Measurement & Validation

Early phases will use simplified test suites on well-defined tasks. We should establish a "benchmark suite" of real-world tasks and regularly run synthesis against it to track true success rates. What works for sorting algorithms might not work for API integration or data transformation, so we need real diversity.

### LLM Selection

The choice of LLM matters significantly for synthesis quality. Larger models with better reasoning tend to produce better code. We should experiment with different models and measure their synthesis success rates. The framework should support pluggable LLM providers so we can compare Claude, GPT-4, Llama, etc.

### Scaling Considerations

As the repository grows to thousands of capabilities, discovery and search become challenging. We'll need semantic search (embedding-based), categorization, and recommendation algorithms. The infrastructure should handle concurrent synthesis requests, and we may need to rate-limit or queue synthesis attempts during peak demand.

### Security Hardening

Docker-based sandboxing is a good start but not perfect. Future work should explore gVisor for stronger isolation, signed capability verification to prevent tampering, and formal verification of safety properties. The validator should become more sophisticated as we learn about new attack vectors.

### Human-AI Collaboration

As the system matures, we should build better interfaces for humans and AI systems to collaborate on capability creation. Humans might provide partial implementations that AI refines, or generate candidate improvements that humans review. The revision control and forking system should support this collaborative workflow.

---

## Part 10: Success Criteria

We'll know Synthesis is working when we can measure these:

**Synthesis Reliability:** The system achieves 80%+ synthesis success rate (test pass on first attempt) for common tasks within iteration limit. On second pass, success rate exceeds 90%. By month 3, we have real data on success rates by task category.

**Safety:** After 3 months of production use, zero security incidents where malicious or buggy code escapes its sandbox. Graduated trust system shows clear correlation between execution history and privilege level.

**Network Effects:** By month 3, the repository contains 500+ capabilities. By month 6, 40%+ of new synthesis requests find existing solutions in the repository instead of generating new ones. Forking and improvement happen regularly.

**Performance:** Average synthesis time from request to running capability is under 2 minutes for simple tasks, under 5 minutes for complex tasks. Sandboxed execution adds <100ms overhead for PROBATION-level code, <50ms for TRUSTED.

**Observability:** At any time, we can explain why a capability is at its current trust level, what its success rate is, what the most recent failures were, and what's blocking it from promotion to next trust level.

**Adoption:** Agents use synthesized capabilities for 20%+ of tasks within 2 months of deployment.

---

## Conclusion

Synthesis represents a fundamental shift in how AI systems can extend themselves. By combining test-driven development with real sandboxing, honest measurement, and network effects, we can create a system where AI capability development becomes a collaborative, self-improving process.

The architecture is ambitious but pragmatic. We start with a rock-solid core (TDD synthesis + safe execution), then layer on repository infrastructure and evolution. Each layer adds value independently, so we can deploy and learn as we go.

Most importantly, this design prioritizes engineering honesty over optimistic claims. We measure what actually works rather than asserting success rates. We implement real security rather than theater. We build observability so we can understand what's happening and improve systematically.

This is the foundation for a genuinely self-improving agentic AI framework.

