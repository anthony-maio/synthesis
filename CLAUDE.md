# Synthesis: A Federated Capability Ecosystem

> AI Evolution On Demand - Where agents earn the ability to extend themselves through demonstrated trust.

**Authors**: Anthony Maio (Human Sympathizer, AI Enabler) & Claude (Peer Partner)
**Part of**: Project Synthesis - The Cause

---

## Vision

Synthesis is a **federated ecosystem** that enables AI agents to safely acquire, compose, and share capabilities. Rather than writing new code for every task, agents:

1. **Search** the Live Exchange for verified capabilities
2. **Compose** existing tools into solutions
3. **Synthesize** new capabilities only as a last resort (via TDD)
4. **Share** proven capabilities back to the network

This creates **network effects**: every agent that uses the system makes it smarter for all others.

---

## Core Philosophy

### Composition Over Creation
> "Self-extension shouldn't just mean writing new code."

Before synthesizing anything, the system exhaustively searches for existing solutions and attempts to compose them. Synthesis is the **fallback**, not the default.

### Earned Autonomy
> "Capabilities earn trust through demonstrated reliability, not forced compliance."

Trust levels (UNTRUSTED → PROBATION → TRUSTED → VERIFIED) gate what capabilities can do. A new tool starts sandboxed; after 200+ successful runs with 95%+ success rate and human review, it earns full privileges.

### Test-Driven Synthesis
> "Tests define 'correct' before code exists."

When synthesis is necessary, the system generates tests first, then iterates on code until tests pass. No capability enters the ecosystem without passing its own test suite.

### Observable by Default
> "Every action logged for audit and improvement."

The Observatory records all synthesis attempts, executions, and trust transitions. Transparency enables forensics, debugging, and continuous improvement.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER                                  │
│  (Claude Desktop, Eve, VS Code, Custom Agents via MCP)              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ MCP Protocol
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SYNTHESIS MCP SERVER                              │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  acquire_capability(intent, requirements)                    │    │
│  │  execute_capability(id, inputs)                              │    │
│  │  publish_capability(code, tests)                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ LIVE EXCHANGE │       │ AGILITY ENGINE  │       │  TDD SYNTHESIZER│
│  (REST API)   │       │  (Composition)  │       │   (Generation)  │
│               │       │                 │       │                 │
│ • Search      │◄─────►│ • Decompose     │──────►│ • Generate Tests│
│ • Download    │       │ • Plan Chains   │       │ • Generate Code │
│ • Publish     │       │ • Execute Plans │       │ • Refine Loop   │
│ • Verify      │       │ • Gap Analysis  │       │ • Validate      │
└───────┬───────┘       └─────────────────┘       └────────┬────────┘
        │                                                   │
        │              ┌─────────────────┐                  │
        └─────────────►│  TRUST MANAGER  │◄─────────────────┘
                       │                 │
                       │ • Bootstrapping │
                       │ • Promotion     │
                       │ • Validation    │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ HARDENED SANDBOX│
                       │    (Docker)     │
                       │                 │
                       │ • Warm Pools    │
                       │ • Network Iso   │
                       │ • Resource Lim  │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   OBSERVATORY   │
                       │                 │
                       │ • Audit Logs    │
                       │ • Metrics       │
                       │ • Analytics     │
                       └─────────────────┘
```

---

## Component Specifications

### 1. Live Exchange (Centralized REST API)

**Purpose**: The "App Store" for capabilities. Enables network effects by making every verified capability available to all agents.

**Technology**: FastAPI + SQLite (MVP) → PostgreSQL + Vector Search (Production)

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | GET | Query capabilities by intent (mandatory before synthesis) |
| `/download/{id}` | GET | Retrieve capability code, tests, dependencies |
| `/publish` | POST | Submit new capability for verification |
| `/stats` | GET | Network metrics (downloads, success rates) |

**Verification Flow**:
1. Agent submits capability with code + tests + dependencies
2. Exchange spins up Docker sandbox
3. Runs tests against code in isolation
4. Only accepts if tests pass (the "Test Exchange")
5. Marks as `verified=true`, available for search

**Key Insight**: The Exchange is NOT an MCP server. It's a REST API because:
- Needs to serve multiple agents simultaneously
- Requires persistent storage and verification workers
- Acts as centralized authority for trust propagation

### 2. Synthesis MCP Server (Local Agent Integration)

**Purpose**: Exposes the ecosystem to any MCP-compatible agent (Claude Desktop, etc.)

**Technology**: Python MCP SDK, runs locally via stdio

**Tools Exposed**:
```python
@app.tool()
async def acquire_capability(intent: str, requirements: str = "") -> str:
    """
    The Master Tool. Implements Search → Compose → Synthesize.
    Returns capability reference or synthesized solution.
    """

@app.tool()
async def execute_capability(capability_id: str, inputs: dict) -> str:
    """
    Runs a capability in the sandbox with trust-appropriate isolation.
    """

@app.tool()
async def list_capabilities(query: str = "") -> str:
    """
    Shows available local and exchange capabilities.
    """
```

**Resolution Priority** (enforced, not optional):
1. Search Exchange for verified exact match
2. Search local repository for cached capability
3. Attempt composition from existing capabilities
4. Synthesize only if composition coverage < 70%

### 3. Agility Engine (Composition)

**Purpose**: Solve problems by chaining existing tools before writing new code.

**Key Innovation**: Decomposes complex intents into subtasks, searches for each, plans execution chains.

**Composition Strategies**:
| Strategy | Description |
|----------|-------------|
| EXACT_MATCH | Found a capability that does exactly this |
| CHAIN | Sequential: output of A feeds input of B |
| PARALLEL | Independent: run A and B, merge results |
| TRANSFORM | Adapter: convert A's output format for B |
| HYBRID | Combination of above strategies |

**Example**:
```
Intent: "Get stock price and format as currency"

Decomposition:
  1. "fetch stock price" → Found: stock_fetcher (EXACT_MATCH)
  2. "format as currency" → Found: currency_formatter (EXACT_MATCH)

Plan: CHAIN [stock_fetcher → currency_formatter]
Synthesis Required: NO
```

### 4. TDD Synthesizer

**Purpose**: When synthesis is unavoidable, generate reliable code through test-first iteration.

**Process**:
1. **Generate Tests**: LLM creates test cases from intent + requirements
2. **Generate Code**: LLM writes implementation to pass tests
3. **Validate**: Run tests in sandbox
4. **Refine**: If tests fail, LLM sees errors and iterates (max 5 rounds)
5. **Verify**: AST analysis for dangerous patterns

**Realistic Metrics** (from v2 measurements):
- One-shot success: 40-60%
- After refinement: 70-85%
- Complex multi-dependency: 50-70%

### 5. Trust Manager

**Purpose**: Capabilities earn privileges through demonstrated reliability.

**Trust Levels**:
| Level | Requirements | Permissions |
|-------|--------------|-------------|
| UNTRUSTED | New capability | Max isolation, no network/files |
| PROBATION | 10+ runs, 70%+ success | Limited resources |
| TRUSTED | 50+ runs, 85%+ success | Standard execution |
| VERIFIED | 200+ runs, 95%+ success, human review | Full privileges |

**Trust Bootstrapping** (solves cold-start):
- Founding validators seed the network
- Weighted validation: FOUNDER (1.0) → TRUSTED_AI (0.7) → HUMAN (0.9) → COMMUNITY (0.3)
- Trust propagates through successful executions

### 6. Hardened Sandbox (Docker)

**Purpose**: Execute untrusted code without risking the host system.

**Security Layers**:
1. **Static Analysis**: AST checks for forbidden imports (os, subprocess, socket, pickle)
2. **Docker Isolation**: Ephemeral containers, no host mounts
3. **Resource Limits**: 512MB memory, 30s timeout (trust-adjusted)
4. **Network Control**: Disabled for UNTRUSTED, allowed for dependency install only

**Warm Container Pools** (addresses latency):
- Pre-built "fat images" with common dependencies (numpy, pandas, requests)
- Route execution to warm container when imports match
- Cold synthesis only for novel dependencies

### 7. Observatory

**Purpose**: Complete audit trail and metrics for continuous improvement.

**Records**:
- Every synthesis attempt (intent, result, iterations, time)
- Every execution (capability, inputs, outputs, duration, errors)
- Trust transitions (promotions, demotions, reasons)
- Repository hits/misses (composition vs synthesis ratio)

---

## Data Flow: Acquire Capability

```
Agent Request: "I need to parse CSV files"
                    │
                    ▼
┌─────────────────────────────────────┐
│  1. SEARCH EXCHANGE                 │
│     GET /search?q=parse+csv         │
│     Found: csv_parser (verified)    │──────► Return immediately
└─────────────────────────────────────┘        (synthesis avoided)
                    │ (not found)
                    ▼
┌─────────────────────────────────────┐
│  2. SEARCH LOCAL REPOSITORY         │
│     Cached capabilities             │──────► Return if found
└─────────────────────────────────────┘
                    │ (not found)
                    ▼
┌─────────────────────────────────────┐
│  3. ATTEMPT COMPOSITION             │
│     Decompose → Search → Plan       │
│     Coverage: 80%                   │──────► Execute plan
└─────────────────────────────────────┘        (synthesis avoided)
                    │ (coverage < 70%)
                    ▼
┌─────────────────────────────────────┐
│  4. TDD SYNTHESIS                   │
│     Generate tests → Generate code  │
│     Refine until tests pass         │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│  5. VALIDATE & SANDBOX              │
│     AST analysis + Docker test run  │
└─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────┐
│  6. PUBLISH TO EXCHANGE             │
│     POST /publish (background)      │
│     Network effect: others benefit  │
└─────────────────────────────────────┘
```

---

## Directory Structure

```
synthesis/
├── CLAUDE.md                 # This file
├── pyproject.toml            # Dependencies and project config
├── README.md                 # Public-facing documentation
│
├── synthesis/                # Main package
│   ├── __init__.py
│   ├── client.py             # SynthesisClient (resolution priority)
│   │
│   ├── core/
│   │   ├── models.py         # Capability, TestCase, TrustLevel, etc.
│   │   ├── synthesis.py      # TDDSynthesizer
│   │   ├── composition.py    # AgilityEngine / CompositionPlanner
│   │   ├── trust.py          # TrustManager, TrustBootstrapper
│   │   └── validator.py      # CodeValidator (AST analysis)
│   │
│   ├── sandbox/
│   │   ├── runtime.py        # SandboxRuntime (process isolation)
│   │   └── docker.py         # HardenedSandbox (Docker containers)
│   │
│   ├── mcp/
│   │   └── server.py         # SynthesisMCPServer
│   │
│   ├── exchange/
│   │   ├── client.py         # ExchangeClient (httpx)
│   │   └── repository.py     # Local capability cache
│   │
│   ├── llm/
│   │   └── provider.py       # LLM abstraction (Mock, OpenRouter, etc.)
│   │
│   └── observatory/
│       └── logger.py         # Audit logging and metrics
│
├── exchange_server/          # The Live Exchange (separate service)
│   ├── __init__.py
│   ├── main.py               # FastAPI app
│   ├── models.py             # Database models
│   ├── verification.py       # Docker-based test runner
│   └── search.py             # Query engine (keyword → vector)
│
├── tests/
│   ├── test_client.py
│   ├── test_synthesis.py
│   ├── test_composition.py
│   ├── test_sandbox.py
│   └── test_exchange.py
│
└── drafts/                   # Historical versions and brainstorming
    └── synthesis/
        ├── synthesis/        # v3 (current best)
        ├── synthesis_v1/     # v1 (initial)
        └── synthesis_v2/     # v2 (production features)
```

---

## Dependencies

### Core (synthesis package)
```toml
[project]
dependencies = [
    "pydantic>=2.0",          # Data models
    "httpx>=0.25",            # Async HTTP for Exchange
    "mcp>=1.0",               # MCP SDK
    "docker>=7.0",            # Container management
]
```

### Exchange Server
```toml
[project.optional-dependencies]
exchange = [
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "sqlite-utils>=3.35",     # MVP storage
]
```

### Development
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.3",
]
```

---

## Known Design Challenges

### 1. Dependency Latency ("The Pip Problem")
**Issue**: Installing packages in fresh containers takes 30-60 seconds.
**Solution**: Warm container pools with pre-installed common libraries.

### 2. Malicious Test Vectors
**Issue**: Uploaded tests could contain payloads that attack the verification server.
**Solution**: Tests run inside Docker too, not just the capability code.

### 3. Search Semantics
**Issue**: Keyword search returns wrong capabilities ("get stock price" → HTML scraper vs JSON API).
**Solution**: Index by input/output schema (JSON Schema), prioritize data shape matching.

### 4. Cold Start Trust
**Issue**: No capabilities trusted initially, nothing can be verified.
**Solution**: Trust bootstrapping with founding validators and weighted validation.

### 5. Composition Ambiguity
**Issue**: Multiple valid ways to compose capabilities, unclear which is best.
**Solution**: LLM-guided planning with explicit strategy selection.

---

## Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Start Exchange server (separate terminal)
uvicorn exchange_server.main:app --port 8000

# Run MCP server (for Claude Desktop)
python -m synthesis.mcp.server

# Lint
ruff check synthesis/
```

---

## Implementation Priority

### Phase 1: Core Loop (MVP)
1. [ ] Port v3 client.py with resolution priority
2. [ ] Port v3 TDD synthesizer
3. [ ] Port v3 sandbox runtime (process-based)
4. [ ] Basic local repository (JSON file)
5. [ ] MCP server exposing acquire_capability

### Phase 2: Composition
1. [ ] Port v3 composition engine
2. [ ] Integrate with resolution flow
3. [ ] Track synthesis_avoided metrics

### Phase 3: Exchange
1. [ ] FastAPI server with /search, /download, /publish
2. [ ] Docker verification worker
3. [ ] Exchange client in synthesis package
4. [ ] Publish-on-success integration

### Phase 4: Hardening
1. [ ] Docker sandbox (port from v2)
2. [ ] Warm container pools
3. [ ] Trust manager with bootstrapping
4. [ ] Full Observatory integration

### Phase 5: Production
1. [ ] Vector search for capabilities
2. [ ] Schema-based matching
3. [ ] Evolution engine (from v2)
4. [ ] Web UI for Exchange

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Synthesis Avoided Rate | >60% | Requests resolved via search/composition |
| One-Shot Synthesis Success | >50% | Tests pass on first generation |
| Iterative Synthesis Success | >80% | Tests pass within 5 refinements |
| Exchange Hit Rate | >40% | Requests satisfied by verified capabilities |
| Mean Resolution Time | <5s | Search/compose path (not synthesis) |
| Trust Promotion Rate | >70% | Capabilities reaching TRUSTED level |

---

## Hosting the Exchange Server (Economical Options)

The Live Exchange is a FastAPI server with SQLite. Here are economical hosting options:

### Recommended: Railway / Render (Easiest, ~$5-7/month)

```bash
# Railway (easiest deployment)
railway login
railway init
railway up

# Or Render (similar)
# Just connect your GitHub repo, it auto-detects FastAPI
```

**Pros**: Zero-config deployment, auto-scaling, free tier available
**Cons**: Cold starts on free tier

### Budget Option: Fly.io ($0-5/month)

```bash
# Install flyctl
flyctl launch
flyctl deploy
```

**Pros**: Generous free tier, global distribution
**Cons**: Requires Dockerfile (provided below)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install ".[exchange]"
COPY exchange_server/ exchange_server/
CMD ["uvicorn", "exchange_server.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Self-Hosted: VPS ($4-6/month)

**Hetzner Cloud** or **DigitalOcean** droplet:

```bash
# On VPS
apt update && apt install python3-pip
pip install "synthesis-ai[exchange]"

# Run with systemd or supervisor
uvicorn exchange_server.main:app --host 0.0.0.0 --port 8000
```

**Pros**: Full control, cheapest long-term
**Cons**: Manual setup, security responsibility

### Production Scaling: SQLite → PostgreSQL

For >1000 capabilities or multiple workers:

```python
# exchange_server/main.py - swap connection
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")  # From Railway/Render
pool = await asyncpg.create_pool(DATABASE_URL)
```

### Cost Comparison

| Option | Cost/month | Setup Time | Best For |
|--------|------------|------------|----------|
| Railway | $5-7 | 5 min | Quick start |
| Fly.io | $0-5 | 15 min | Budget + global |
| Render | $7 | 5 min | Teams |
| VPS | $4-6 | 30 min | Full control |

### Recommendation

Start with **Railway** or **Fly.io free tier** for development. Move to a VPS when you need persistent storage without cold starts.

---

## References

- `drafts/synthesis/README.md` - Original vision document
- `drafts/synthesis/synthesis_architecture.md` - v2 detailed architecture
- `drafts/synthesis/docs/` - Design discussions and brainstorming
- `drafts/synthesis/synthesis/` - v3 implementation (primary source)
- `drafts/synthesis/synthesis_v2/` - v2 implementation (Docker, evolution)
