# Synthesis: LLM Evolution Engine (MCP) — Implementation Plan

## Paper Summary

The paper describes **Synthesis**, a self-extending agentic AI framework where LLM agents can dynamically create, test, share, and evolve their own tools at runtime. It is exposed via MCP (Model Context Protocol) so any MCP-compatible client (Claude Desktop, etc.) can use it. The system has three major subsystems:

1. **MCP Server Factory** — programmatically generates new MCP tool servers from high-level descriptions
2. **Capability Manager** — manages the lifecycle of capabilities: creation via restricted code execution, TDD-based validation, trust scoring, and sandboxed runtime
3. **Evolution Engine** — monitors usage metrics and automatically synthesises improved versions of capabilities

The paper's own analysis identifies key improvements needed over the naive prototype:
- Don't concatenate user code into templates; use isolated modules
- Use real sandboxing (subprocess/Docker), not just restricted `__builtins__`
- Ground trust metrics in actual measured results, not assumed success rates
- Start with a focused MVP and layer on repository/evolution features later

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   MCP Interface                     │
│  (tools exposed to Claude / any MCP client)         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Capability   │  │   Test       │  │  Trust    │ │
│  │  Manager      │  │   Runner     │  │  System   │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                 │                │        │
│  ┌──────▼─────────────────▼────────────────▼─────┐  │
│  │              Sandbox Executor                  │  │
│  │   (subprocess isolation, restricted builtins)  │  │
│  └────────────────────┬──────────────────────────┘  │
│                       │                             │
│  ┌────────────────────▼──────────────────────────┐  │
│  │            Capability Repository              │  │
│  │   (SQLite persistence, metadata, versions)    │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Phased Implementation

### Phase 1: Core Foundation (MVP)

The minimum viable system that demonstrates dynamic capability creation, testing, and execution with safety guarantees.

#### 1.1 Data Models (`src/synthesis/models.py`)

Define the core data structures using Python dataclasses / Pydantic:

- **`Capability`** — name, description, source code, version, created_at, author
- **`TrustLevel`** (enum) — `UNTRUSTED`, `PROBATION`, `TRUSTED`, `VERIFIED`
- **`TrustScore`** — total_executions, successful_executions, computed trust_level (property), promotion thresholds
- **`TestCase`** — input args (list), expected output, description
- **`TestResult`** — passed (bool), actual output, error message, duration
- **`ExecutionResult`** — return value, stdout, stderr, success, duration
- **`CapabilityMetadata`** — wraps Capability + TrustScore + list of TestCases

#### 1.2 Sandbox Executor (`src/synthesis/sandbox.py`)

Safe execution of untrusted code in an isolated subprocess:

- **`SubprocessSandbox`** — runs user code in a separate Python process with:
  - Restricted builtins (only safe functions: `abs`, `min`, `max`, `sum`, `len`, `range`, `sorted`, `enumerate`, `zip`, `map`, `filter`, `isinstance`, `type`, `str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`, `set`, `print`)
  - Allowed stdlib modules whitelist (`math`, `json`, `re`, `datetime`, `collections`, `itertools`, `functools`, `string`, `decimal`, `fractions`, `statistics`, `random`, `hashlib`, `base64`, `uuid`, `textwrap`, `copy`)
  - Timeout enforcement (default 30s)
  - Memory limit enforcement via `resource` module
  - No filesystem, network, or subprocess access
  - Communication via JSON over stdin/stdout pipes
- **`sandbox_worker.py`** — the script executed in the subprocess; receives code + function call via stdin JSON, returns result via stdout JSON
- Rationale: subprocess isolation is more secure than in-process `exec()` with restricted builtins, and doesn't require Docker for the MVP

#### 1.3 Test Runner (`src/synthesis/testing.py`)

TDD-based validation of capabilities:

- **`TestRunner`** class:
  - `run_tests(capability, test_cases) -> list[TestResult]` — runs each test case through the sandbox, compares actual vs expected output
  - `validate_capability(capability, test_cases) -> bool` — returns True only if all tests pass
  - Records test durations for performance tracking
- Tests are defined as simple input/output pairs (JSON-serializable)
- Results update the capability's `TrustScore`

#### 1.4 Capability Manager (`src/synthesis/manager.py`)

Central coordinator for capability CRUD and lifecycle:

- **`CapabilityManager`** class:
  - `create_capability(name, description, code, tests) -> CapabilityMetadata` — validates code compiles, runs tests, stores capability
  - `execute_capability(name, args) -> ExecutionResult` — runs a capability in the sandbox, updates trust metrics
  - `list_capabilities() -> list[CapabilityMetadata]` — list all registered capabilities
  - `get_capability(name) -> CapabilityMetadata` — get details for a single capability
  - `delete_capability(name) -> bool` — remove a capability
  - `update_capability(name, code, tests) -> CapabilityMetadata` — update code/tests, re-validate, increment version

#### 1.5 Repository / Persistence (`src/synthesis/repository.py`)

Local storage of capabilities and metrics:

- **`SQLiteRepository`** class:
  - SQLite database for persistence across restarts
  - Tables: `capabilities` (id, name, description, code, version, created_at, updated_at), `trust_scores` (capability_id, total_execs, successful_execs), `test_cases` (capability_id, input_json, expected_output_json, description)
  - CRUD operations matching the manager's needs
  - Migration support for schema evolution

#### 1.6 MCP Server (`src/synthesis/server.py`)

Expose the system as MCP tools using the `mcp` Python SDK:

- **Tools to expose:**
  - `create_capability` — create a new capability with code and tests
  - `run_capability` — execute a capability by name with given arguments
  - `list_capabilities` — list all available capabilities with trust levels
  - `get_capability` — get full details (code, tests, trust score) for a capability
  - `delete_capability` — remove a capability
  - `search_capabilities` — search by name/description keywords
- **Resources to expose:**
  - `capability://{name}` — individual capability details as a resource
- The server runs as a stdio-based MCP server for local use

#### 1.7 Project Setup

- `pyproject.toml` — project metadata, dependencies (`mcp`, `pydantic`), entry point for the MCP server
- `src/synthesis/__init__.py` — package init
- `tests/` — pytest tests for each module
  - `tests/test_models.py`
  - `tests/test_sandbox.py`
  - `tests/test_testing.py`
  - `tests/test_manager.py`
  - `tests/test_repository.py`

---

### Phase 2: Enhanced Safety & Usability

#### 2.1 Docker Sandbox (`src/synthesis/docker_sandbox.py`)

Optional Docker-based isolation for higher security:

- Run untrusted code in ephemeral containers with no network, limited CPU/memory
- Fall back to subprocess sandbox when Docker is unavailable
- Use a minimal Python base image with no extra packages

#### 2.2 Dependency Management

- Allow capabilities to declare pip dependencies
- Install dependencies into isolated virtual environments (one per capability or per trust level)
- Maintain a whitelist of allowed packages
- Scan dependencies against known vulnerability databases

#### 2.3 Capability Versioning

- Full version history for each capability
- Diff between versions
- Rollback to previous versions
- Track which version is "active"

#### 2.4 Improved Test Generation

- Expose an MCP tool that uses the LLM to generate test cases for a given capability description
- Property-based testing support (hypothesis-style)
- Edge case detection heuristics

---

### Phase 3: Evolution & Repository

#### 3.1 Evolution Engine (`src/synthesis/evolution.py`)

- Monitor capability usage metrics (execution count, error rate, latency)
- Identify capabilities that are underperforming (high error rate, slow)
- Trigger LLM-based rewriting of underperforming capabilities
- A/B test new versions against old ones
- Auto-promote successful evolutions, auto-rollback failures

#### 3.2 Shared Repository

- Publish capabilities to a shared registry (local network or cloud)
- Browse, search, download, rate, and fork capabilities
- Namespace support (user/org scoping)
- Capability signatures / checksums for integrity verification

#### 3.3 MCP Server Factory

- Generate entirely new MCP servers (not just capabilities within Synthesis) from high-level descriptions
- Auto-register generated servers in Claude Desktop config
- Template-based generation with proper module separation (not string concatenation)

---

## File Structure

```
synthesis/
├── pyproject.toml
├── README.md
├── PLAN.md
├── LICENSE
├── src/
│   └── synthesis/
│       ├── __init__.py
│       ├── models.py          # Data models (Capability, TrustScore, etc.)
│       ├── sandbox.py         # Subprocess sandbox executor
│       ├── sandbox_worker.py  # Worker script run in subprocess
│       ├── testing.py         # Test runner
│       ├── manager.py         # Capability manager (coordinator)
│       ├── repository.py      # SQLite persistence layer
│       └── server.py          # MCP server entry point
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_sandbox.py
│   ├── test_testing.py
│   ├── test_manager.py
│   └── test_repository.py
└── synthesis - the llm evolution engine (mcp) (1).pdf
```

## Key Design Decisions

1. **Subprocess over in-process exec** — The paper's prototype uses `exec()` with restricted `__builtins__`, which is insufficient for real safety. Subprocess isolation (Phase 1) provides meaningful process-level boundaries. Docker (Phase 2) adds OS-level isolation.

2. **SQLite for persistence** — Lightweight, zero-config, appropriate for a local-first tool. No external database server needed.

3. **Pydantic for models** — Strong typing, JSON serialization, validation — all critical for an MCP server that exchanges structured data.

4. **MCP stdio transport** — Standard for local MCP servers. Can be extended to SSE/HTTP transport for networked use later.

5. **Trust scoring based on measured results** — Per the paper's critique, trust levels are computed from actual execution metrics, not assumed. Thresholds: UNTRUSTED (default) → PROBATION (≥10 executions, ≥90% success) → TRUSTED (≥50 executions, ≥95% success) → VERIFIED (requires explicit human review).

6. **Module separation for generated code** — Per the paper's critique, user code is never concatenated into templates. It is written to a separate file and executed in isolation.

7. **MVP first** — Phase 1 delivers a working system. Phases 2 and 3 add sophistication incrementally.

## Dependencies

- `mcp` — MCP Python SDK for building the MCP server
- `pydantic` — data validation and serialization
- `pytest` — testing framework (dev dependency)

## How to Run (after Phase 1 implementation)

```bash
# Install
pip install -e .

# Run the MCP server
python -m synthesis.server

# Or configure in Claude Desktop's config:
# {
#   "mcpServers": {
#     "synthesis": {
#       "command": "python",
#       "args": ["-m", "synthesis.server"]
#     }
#   }
# }
```
