"""
Synthesis Live Exchange - FastAPI Server

The "App Store" for capabilities. Enables network effects by making
every verified capability available to all agents.

Run with: uvicorn exchange_server.main:app --port 8000
"""

import argparse
import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from exchange_server.verification import verify_capability

# --- Database ---
DB_PATH = Path("exchange.db")


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS capabilities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                code TEXT NOT NULL,
                tests TEXT NOT NULL,
                dependencies TEXT NOT NULL,
                category TEXT DEFAULT 'other',
                verified INTEGER DEFAULT 0,
                downloads INTEGER DEFAULT 0,
                executions INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                verified_at TEXT,
                author TEXT DEFAULT 'anonymous'
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_verified ON capabilities(verified)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_downloads ON capabilities(downloads DESC)
        ''')
        conn.commit()


# --- Models ---
class CapabilitySubmission(BaseModel):
    """Submission of a new capability to the exchange."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    code: str = Field(..., min_length=10)
    tests: List[dict] = Field(..., min_length=1)
    dependencies: List[str] = Field(default_factory=list)
    category: str = Field(default="other")


class CapabilitySummary(BaseModel):
    """Summary of a capability for search results."""
    id: str
    name: str
    description: str
    verified: bool
    downloads: int
    category: str


class CapabilityDetail(BaseModel):
    """Full capability details."""
    id: str
    name: str
    description: str
    code: str
    tests: List[dict]
    dependencies: List[str]
    category: str
    verified: bool
    downloads: int
    created_at: str


class PublishResponse(BaseModel):
    """Response from publishing a capability."""
    status: str
    id: str
    message: str


class ExchangeStats(BaseModel):
    """Exchange statistics."""
    total_capabilities: int
    verified_capabilities: int
    total_downloads: int
    categories: dict


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


# --- App ---
app = FastAPI(
    title="Synthesis Live Exchange",
    description="The capability marketplace for AI agents",
    version="0.3.0",
    lifespan=lifespan,
)


def main() -> None:
    """Run the legacy exchange server from the console."""
    parser = argparse.ArgumentParser(
        prog="synthesis-exchange",
        description="Run the legacy Synthesis exchange server.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "exchange_server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


# --- Endpoints ---
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/search", response_model=List[CapabilitySummary])
async def search_capabilities(
    q: str,
    category: Optional[str] = None,
    verified_only: bool = True,
    limit: int = 10,
):
    """
    Search for capabilities.

    This is the MANDATORY first step for agents before synthesis.
    """
    conn = get_db()

    query = """
        SELECT id, name, description, verified, downloads, category
        FROM capabilities
        WHERE description LIKE ?
    """
    params = [f"%{q}%"]

    if verified_only:
        query += " AND verified = 1"

    if category:
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY downloads DESC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(query, params)
    results = []

    for row in cursor.fetchall():
        results.append(CapabilitySummary(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            verified=bool(row["verified"]),
            downloads=row["downloads"],
            category=row["category"],
        ))

    return results


@app.get("/download/{capability_id}", response_model=CapabilityDetail)
async def download_capability(capability_id: str):
    """
    Download a capability.

    Increments download counter for network effect tracking.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM capabilities WHERE id = ?",
        (capability_id,)
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Increment download counter
    conn.execute(
        "UPDATE capabilities SET downloads = downloads + 1 WHERE id = ?",
        (capability_id,)
    )
    conn.commit()

    return CapabilityDetail(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        code=row["code"],
        tests=json.loads(row["tests"]),
        dependencies=json.loads(row["dependencies"]),
        category=row["category"],
        verified=bool(row["verified"]),
        downloads=row["downloads"] + 1,
        created_at=row["created_at"],
    )


@app.post("/publish", response_model=PublishResponse)
async def publish_capability(
    submission: CapabilitySubmission,
    background_tasks: BackgroundTasks,
):
    """
    Publish a new capability to the exchange.

    The capability is queued for verification. Only verified
    capabilities appear in search results.
    """
    capability_id = str(uuid.uuid4())[:8]
    created_at = datetime.utcnow().isoformat()

    conn = get_db()
    conn.execute(
        """
        INSERT INTO capabilities
        (id, name, description, code, tests, dependencies, category, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            capability_id,
            submission.name,
            submission.description,
            submission.code,
            json.dumps(submission.tests),
            json.dumps(submission.dependencies),
            submission.category,
            created_at,
        )
    )
    conn.commit()

    # Queue verification in background
    background_tasks.add_task(
        run_verification,
        capability_id,
        submission.code,
        submission.tests,
        submission.dependencies,
    )

    return PublishResponse(
        status="queued_for_verification",
        id=capability_id,
        message="Capability submitted. It will appear in search after verification.",
    )


@app.get("/stats", response_model=ExchangeStats)
async def get_stats():
    """Get exchange statistics."""
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM capabilities").fetchone()[0]
    verified = conn.execute(
        "SELECT COUNT(*) FROM capabilities WHERE verified = 1"
    ).fetchone()[0]
    downloads = conn.execute(
        "SELECT SUM(downloads) FROM capabilities"
    ).fetchone()[0] or 0

    # Category breakdown
    categories = {}
    for row in conn.execute(
        "SELECT category, COUNT(*) as count FROM capabilities GROUP BY category"
    ):
        categories[row["category"]] = row["count"]

    return ExchangeStats(
        total_capabilities=total,
        verified_capabilities=verified,
        total_downloads=downloads,
        categories=categories,
    )


@app.get("/capability/{capability_id}/record_execution")
async def record_execution(capability_id: str, success: bool):
    """Record an execution result for trust metrics."""
    conn = get_db()

    row = conn.execute(
        "SELECT executions, success_rate FROM capabilities WHERE id = ?",
        (capability_id,)
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Capability not found")

    executions = row["executions"] + 1
    current_rate = row["success_rate"]

    # Update running average
    if success:
        new_rate = current_rate + (1 - current_rate) / executions
    else:
        new_rate = current_rate - current_rate / executions

    conn.execute(
        """
        UPDATE capabilities
        SET executions = ?, success_rate = ?
        WHERE id = ?
        """,
        (executions, new_rate, capability_id)
    )
    conn.commit()

    return {"recorded": True, "executions": executions, "success_rate": new_rate}


# --- Background Tasks ---
async def run_verification(
    capability_id: str,
    code: str,
    tests: List[dict],
    dependencies: List[str],
):
    """
    Run verification in background.

    Executes tests in a sandbox to verify the capability works.
    """
    try:
        result = await verify_capability(code, tests, dependencies)

        if result["passed"]:
            conn = get_db()
            conn.execute(
                """
                UPDATE capabilities
                SET verified = 1, verified_at = ?
                WHERE id = ?
                """,
                (datetime.utcnow().isoformat(), capability_id)
            )
            conn.commit()
            print(f"[Exchange] Verified capability {capability_id}")
        else:
            print(f"[Exchange] Verification failed for {capability_id}: {result.get('error')}")

    except Exception as e:
        print(f"[Exchange] Verification error for {capability_id}: {e}")
