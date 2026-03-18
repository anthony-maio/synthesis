"""
repository.py - Capability Repository with Network Effects
===========================================================

This module implements the community repository system that enables:
- Capability sharing and discovery
- Trust scoring through community validation  
- Forking and improvement of existing capabilities
- Network effects where more users = better capabilities

This addresses the feedback about enabling collective intelligence
and reuse across the ecosystem.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

from .capability import Capability, TrustLevel, CapabilityType


@dataclass
class CapabilityRating:
    """
    User rating for a capability.
    
    Community ratings help establish trust and identify high-quality capabilities.
    """
    
    user_id: str
    capability_id: str
    rating: int  # 1-5 stars
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    verified_user: bool = False  # Whether user is verified
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'user_id': self.user_id,
            'capability_id': self.capability_id,
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat(),
            'verified_user': self.verified_user
        }


@dataclass
class UsageMetrics:
    """
    Track capability usage across the community.
    
    These metrics help identify popular and reliable capabilities,
    contributing to the network effects.
    """
    
    total_downloads: int = 0
    total_executions: int = 0
    unique_users: int = 0
    fork_count: int = 0
    success_rate: float = 0.0
    average_execution_time_ms: float = 0.0
    last_used: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'total_downloads': self.total_downloads,
            'total_executions': self.total_executions,
            'unique_users': self.unique_users,
            'fork_count': self.fork_count,
            'success_rate': self.success_rate,
            'average_execution_time_ms': self.average_execution_time_ms,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }


@dataclass 
class RepositoryEntry:
    """
    Complete repository entry for a capability.
    
    This includes the capability itself plus all community metadata.
    """
    
    capability: Capability
    author_id: str
    published_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Community metadata
    usage_metrics: UsageMetrics = field(default_factory=UsageMetrics)
    ratings: List[CapabilityRating] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    # Trust and verification
    community_trust_score: float = 0.0
    verified: bool = False
    verification_date: Optional[datetime] = None
    
    # Lineage tracking
    parent_capability_id: Optional[str] = None
    fork_count: int = 0
    
    @property
    def average_rating(self) -> float:
        """Calculate average user rating."""
        if not self.ratings:
            return 0.0
        return sum(r.rating for r in self.ratings) / len(self.ratings)
    
    @property
    def weighted_score(self) -> float:
        """
        Calculate weighted score for ranking.
        
        Combines multiple factors to identify the best capabilities,
        enabling effective discovery in the repository.
        """
        # Weight factors
        rating_weight = 0.3
        usage_weight = 0.2  
        success_weight = 0.3
        trust_weight = 0.2
        
        # Normalize metrics
        rating_score = self.average_rating / 5.0
        
        # Usage score (log scale to handle large differences)
        import math
        usage_score = min(1.0, math.log10(self.usage_metrics.total_executions + 1) / 5)
        
        success_score = self.usage_metrics.success_rate
        
        # Trust score based on capability trust level
        trust_map = {
            TrustLevel.QUARANTINE: 0.0,
            TrustLevel.UNTRUSTED: 0.2,
            TrustLevel.PROBATION: 0.5,
            TrustLevel.TRUSTED: 0.8,
            TrustLevel.VERIFIED: 1.0
        }
        capability_trust = trust_map.get(
            self.capability.metadata.trust_level, 0.2
        )
        
        # Combine scores
        score = (
            rating_score * rating_weight +
            usage_score * usage_weight +
            success_score * success_weight +
            capability_trust * trust_weight
        )
        
        # Boost for verified capabilities
        if self.verified:
            score *= 1.2
        
        return min(1.0, score)  # Cap at 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'capability': self.capability.to_dict(),
            'author_id': self.author_id,
            'published_at': self.published_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'usage_metrics': self.usage_metrics.to_dict(),
            'ratings': [r.to_dict() for r in self.ratings],
            'tags': self.tags,
            'community_trust_score': self.community_trust_score,
            'verified': self.verified,
            'verification_date': self.verification_date.isoformat() if self.verification_date else None,
            'parent_capability_id': self.parent_capability_id,
            'fork_count': self.fork_count,
            'average_rating': self.average_rating,
            'weighted_score': self.weighted_score
        }


class CapabilityRepository:
    """
    Community repository for sharing and discovering capabilities.
    
    This implements the network effects aspect of the Synthesis framework:
    - More users contribute more capabilities
    - Usage data improves trust scoring
    - Forking enables collaborative improvement
    - Discovery mechanisms help find the best solutions
    
    Unlike the initial design's simple storage, this provides a complete
    ecosystem for capability sharing and evolution.
    """
    
    def __init__(self, db_path: str = "/var/synthesis/repository.db"):
        """
        Initialize repository.
        
        Args:
            db_path: Path to repository database
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database schema for repository."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Capabilities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS capabilities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                type TEXT NOT NULL,
                author_id TEXT NOT NULL,
                module_code TEXT NOT NULL,
                metadata TEXT NOT NULL,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parent_id TEXT,
                verified BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (parent_id) REFERENCES capabilities(id)
            )
        ''')
        
        # Usage metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_metrics (
                capability_id TEXT PRIMARY KEY,
                total_downloads INTEGER DEFAULT 0,
                total_executions INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                fork_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                average_execution_time_ms REAL DEFAULT 0.0,
                last_used TIMESTAMP,
                FOREIGN KEY (capability_id) REFERENCES capabilities(id)
            )
        ''')
        
        # Ratings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capability_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_user BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (capability_id) REFERENCES capabilities(id),
                UNIQUE(capability_id, user_id)
            )
        ''')
        
        # Tags table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                capability_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (capability_id) REFERENCES capabilities(id),
                PRIMARY KEY (capability_id, tag)
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_capabilities_type ON capabilities(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_capabilities_author ON capabilities(author_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_usage_downloads ON usage_metrics(total_downloads)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ratings_capability ON ratings(capability_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)')
        
        conn.commit()
        conn.close()
    
    def publish(self, capability: Capability, author_id: str,
                tags: List[str] = None,
                parent_id: Optional[str] = None) -> str:
        """
        Publish a capability to the repository.
        
        This makes the capability available for discovery and reuse
        by the community, enabling network effects.
        
        Args:
            capability: Capability to publish
            author_id: ID of the publishing author/agent
            tags: Optional tags for discovery
            parent_id: ID of parent capability if this is a fork
            
        Returns:
            Repository ID of published capability
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Store capability
            cursor.execute('''
                INSERT INTO capabilities 
                (id, name, description, type, author_id, module_code, metadata, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                capability.metadata.id,
                capability.metadata.name,
                capability.metadata.description,
                capability.metadata.capability_type.value,
                author_id,
                capability.module_code,
                json.dumps(capability.metadata.to_dict()),
                parent_id
            ))
            
            # Initialize usage metrics
            cursor.execute('''
                INSERT INTO usage_metrics (capability_id)
                VALUES (?)
            ''', (capability.metadata.id,))
            
            # Add tags
            if tags:
                for tag in tags:
                    cursor.execute('''
                        INSERT OR IGNORE INTO tags (capability_id, tag)
                        VALUES (?, ?)
                    ''', (capability.metadata.id, tag))
            
            # Update parent's fork count if this is a fork
            if parent_id:
                cursor.execute('''
                    UPDATE usage_metrics 
                    SET fork_count = fork_count + 1
                    WHERE capability_id = ?
                ''', (parent_id,))
            
            conn.commit()
            return capability.metadata.id
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to publish capability: {e}")
            
        finally:
            conn.close()
    
    def search(self, query: str = None,
              capability_type: Optional[CapabilityType] = None,
              tags: List[str] = None,
              min_rating: float = 0.0,
              verified_only: bool = False,
              limit: int = 20) -> List[RepositoryEntry]:
        """
        Search for capabilities in the repository.
        
        This discovery mechanism is key to the network effects -
        users can find and reuse existing solutions rather than
        recreating them.
        
        Args:
            query: Text search query
            capability_type: Filter by capability type
            tags: Filter by tags
            min_rating: Minimum average rating
            verified_only: Only return verified capabilities
            limit: Maximum results to return
            
        Returns:
            List of matching repository entries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build search query
        conditions = []
        params = []
        
        if query:
            conditions.append('(c.name LIKE ? OR c.description LIKE ?)')
            params.extend([f'%{query}%', f'%{query}%'])
        
        if capability_type:
            conditions.append('c.type = ?')
            params.append(capability_type.value)
        
        if verified_only:
            conditions.append('c.verified = 1')
        
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        
        # Execute search with join to get metrics
        cursor.execute(f'''
            SELECT 
                c.id, c.name, c.description, c.type, c.author_id,
                c.module_code, c.metadata, c.published_at, c.updated_at,
                c.parent_id, c.verified,
                u.total_downloads, u.total_executions, u.unique_users,
                u.fork_count, u.success_rate, u.average_execution_time_ms,
                u.last_used,
                AVG(r.rating) as avg_rating,
                COUNT(DISTINCT r.user_id) as rating_count
            FROM capabilities c
            LEFT JOIN usage_metrics u ON c.id = u.capability_id
            LEFT JOIN ratings r ON c.id = r.capability_id
            WHERE {where_clause}
            GROUP BY c.id
            ORDER BY u.total_downloads DESC, avg_rating DESC
            LIMIT ?
        ''', params + [limit])
        
        results = []
        for row in cursor.fetchall():
            # Reconstruct capability
            metadata_dict = json.loads(row[6])
            capability = Capability.from_dict({
                'metadata': metadata_dict,
                'module_code': row[5],
                'entry_point': 'execute'
            })
            
            # Create usage metrics
            usage_metrics = UsageMetrics(
                total_downloads=row[11] or 0,
                total_executions=row[12] or 0,
                unique_users=row[13] or 0,
                fork_count=row[14] or 0,
                success_rate=row[15] or 0.0,
                average_execution_time_ms=row[16] or 0.0,
                last_used=datetime.fromisoformat(row[17]) if row[17] else None
            )
            
            # Get ratings for this capability
            cursor.execute('''
                SELECT user_id, rating, comment, created_at, verified_user
                FROM ratings
                WHERE capability_id = ?
            ''', (row[0],))
            
            ratings = []
            for rating_row in cursor.fetchall():
                ratings.append(CapabilityRating(
                    user_id=rating_row[0],
                    capability_id=row[0],
                    rating=rating_row[1],
                    comment=rating_row[2],
                    created_at=datetime.fromisoformat(rating_row[3]),
                    verified_user=bool(rating_row[4])
                ))
            
            # Get tags
            cursor.execute('''
                SELECT tag FROM tags WHERE capability_id = ?
            ''', (row[0],))
            tags = [t[0] for t in cursor.fetchall()]
            
            # Create repository entry
            entry = RepositoryEntry(
                capability=capability,
                author_id=row[4],
                published_at=datetime.fromisoformat(row[7]),
                updated_at=datetime.fromisoformat(row[8]),
                usage_metrics=usage_metrics,
                ratings=ratings,
                tags=tags,
                verified=bool(row[10]),
                parent_capability_id=row[9],
                fork_count=usage_metrics.fork_count
            )
            
            # Apply rating filter
            if entry.average_rating >= min_rating:
                results.append(entry)
        
        conn.close()
        return results
    
    def get_by_id(self, capability_id: str) -> Optional[RepositoryEntry]:
        """
        Get a specific capability by ID.
        
        Args:
            capability_id: Capability ID
            
        Returns:
            RepositoryEntry if found, None otherwise
        """
        results = self.search(limit=1)
        
        # Filter for exact ID match
        for entry in results:
            if entry.capability.metadata.id == capability_id:
                return entry
        
        return None
    
    def download(self, capability_id: str, user_id: str) -> Optional[Capability]:
        """
        Download a capability and track usage.
        
        This increments download counters contributing to the
        network effect of identifying popular capabilities.
        
        Args:
            capability_id: ID of capability to download
            user_id: ID of downloading user
            
        Returns:
            Capability if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get capability
        cursor.execute('''
            SELECT module_code, metadata FROM capabilities
            WHERE id = ?
        ''', (capability_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        # Update download metrics
        cursor.execute('''
            UPDATE usage_metrics
            SET total_downloads = total_downloads + 1,
                last_used = CURRENT_TIMESTAMP
            WHERE capability_id = ?
        ''', (capability_id,))
        
        # Track unique user if needed (simplified - production would use better tracking)
        cursor.execute('''
            UPDATE usage_metrics
            SET unique_users = (
                SELECT COUNT(DISTINCT user_id) + 1
                FROM ratings
                WHERE capability_id = ?
            )
            WHERE capability_id = ?
        ''', (capability_id, capability_id))
        
        conn.commit()
        conn.close()
        
        # Reconstruct capability
        metadata_dict = json.loads(row[1])
        capability = Capability.from_dict({
            'metadata': metadata_dict,
            'module_code': row[0],
            'entry_point': 'execute'
        })
        
        return capability
    
    def rate(self, capability_id: str, user_id: str,
            rating: int, comment: str = "",
            verified_user: bool = False) -> bool:
        """
        Rate a capability.
        
        Community ratings help establish trust and identify
        high-quality capabilities, core to the network effects.
        
        Args:
            capability_id: ID of capability to rate
            user_id: ID of rating user
            rating: Rating (1-5 stars)
            comment: Optional comment
            verified_user: Whether user is verified
            
        Returns:
            True if rating added/updated successfully
        """
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert or update rating
            cursor.execute('''
                INSERT OR REPLACE INTO ratings
                (capability_id, user_id, rating, comment, verified_user, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (capability_id, user_id, rating, comment, verified_user))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Failed to add rating: {e}")
            return False
            
        finally:
            conn.close()
    
    def fork(self, capability_id: str, author_id: str) -> Optional[str]:
        """
        Fork a capability for improvement.
        
        Forking enables collaborative improvement, a key aspect
        of the network effects where capabilities evolve through
        community contributions.
        
        Args:
            capability_id: ID of capability to fork
            author_id: ID of forking author
            
        Returns:
            ID of forked capability if successful
        """
        # Get original capability
        original = self.get_by_id(capability_id)
        if not original:
            return None
        
        # Create forked capability
        import uuid
        forked_capability = Capability(
            metadata=original.capability.metadata,
            module_code=original.capability.module_code,
            entry_point=original.capability.entry_point,
            input_schema=original.capability.input_schema,
            output_schema=original.capability.output_schema,
            docstring=original.capability.docstring,
            examples=original.capability.examples
        )
        
        # Update metadata for fork
        forked_capability.metadata.id = f"cap_{uuid.uuid4().hex[:12]}"
        forked_capability.metadata.parent_id = capability_id
        forked_capability.metadata.author = author_id
        forked_capability.metadata.created_at = datetime.now()
        forked_capability.metadata.updated_at = datetime.now()
        forked_capability.metadata.name = f"{original.capability.metadata.name}_fork"
        
        # Reset trust metrics for fork
        forked_capability.metadata.trust_level = TrustLevel.UNTRUSTED
        forked_capability.metadata.metrics.total_executions = 0
        forked_capability.metadata.metrics.successful_executions = 0
        
        # Publish forked capability
        forked_id = self.publish(
            forked_capability,
            author_id,
            tags=original.tags + ['fork'],
            parent_id=capability_id
        )
        
        return forked_id
    
    def report_execution(self, capability_id: str, success: bool,
                        execution_time_ms: float) -> bool:
        """
        Report execution results for a capability.
        
        This feeds back into the trust scoring system, helping
        identify reliable capabilities through actual usage data.
        
        Args:
            capability_id: ID of executed capability
            success: Whether execution was successful
            execution_time_ms: Execution time in milliseconds
            
        Returns:
            True if report recorded successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get current metrics
            cursor.execute('''
                SELECT total_executions, success_rate, average_execution_time_ms
                FROM usage_metrics
                WHERE capability_id = ?
            ''', (capability_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return False
            
            total_execs = row[0] or 0
            current_success_rate = row[1] or 0.0
            current_avg_time = row[2] or 0.0
            
            # Calculate new metrics
            new_total = total_execs + 1
            
            # Update success rate (running average)
            successful_execs = int(current_success_rate * total_execs)
            if success:
                successful_execs += 1
            new_success_rate = successful_execs / new_total
            
            # Update average execution time (running average)
            new_avg_time = (
                (current_avg_time * total_execs + execution_time_ms) / new_total
            )
            
            # Update database
            cursor.execute('''
                UPDATE usage_metrics
                SET total_executions = ?,
                    success_rate = ?,
                    average_execution_time_ms = ?,
                    last_used = CURRENT_TIMESTAMP
                WHERE capability_id = ?
            ''', (new_total, new_success_rate, new_avg_time, capability_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Failed to report execution: {e}")
            return False
            
        finally:
            conn.close()
    
    def get_trending(self, days: int = 7, limit: int = 10) -> List[RepositoryEntry]:
        """
        Get trending capabilities based on recent activity.
        
        This helps surface actively used and improving capabilities,
        accelerating the network effects of discovery.
        
        Args:
            days: Number of days to consider for trending
            limit: Maximum results to return
            
        Returns:
            List of trending repository entries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate cutoff date
        cutoff = datetime.now() - timedelta(days=days)
        
        # Get capabilities with recent activity
        cursor.execute('''
            SELECT c.id
            FROM capabilities c
            JOIN usage_metrics u ON c.id = u.capability_id
            WHERE u.last_used > ?
            ORDER BY 
                u.total_executions DESC,
                u.success_rate DESC
            LIMIT ?
        ''', (cutoff.isoformat(), limit))
        
        trending_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Get full entries for trending capabilities
        trending = []
        for cap_id in trending_ids:
            entry = self.get_by_id(cap_id)
            if entry:
                trending.append(entry)
        
        return trending
    
    def verify_capability(self, capability_id: str,
                         verifier_id: str) -> bool:
        """
        Mark a capability as verified after human review.
        
        Human verification is the highest trust level, helping
        identify production-ready capabilities.
        
        Args:
            capability_id: ID of capability to verify
            verifier_id: ID of verifying user (should be authorized)
            
        Returns:
            True if verification successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Update verification status
            cursor.execute('''
                UPDATE capabilities
                SET verified = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (capability_id,))
            
            # Could also log verifier info in a separate table
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Failed to verify capability: {e}")
            return False
            
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        These metrics help track the growth of the ecosystem
        and the network effects in action.
        
        Returns:
            Dictionary of repository statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total capabilities
        cursor.execute('SELECT COUNT(*) FROM capabilities')
        stats['total_capabilities'] = cursor.fetchone()[0]
        
        # Verified capabilities
        cursor.execute('SELECT COUNT(*) FROM capabilities WHERE verified = 1')
        stats['verified_capabilities'] = cursor.fetchone()[0]
        
        # Total downloads
        cursor.execute('SELECT SUM(total_downloads) FROM usage_metrics')
        stats['total_downloads'] = cursor.fetchone()[0] or 0
        
        # Total executions
        cursor.execute('SELECT SUM(total_executions) FROM usage_metrics')
        stats['total_executions'] = cursor.fetchone()[0] or 0
        
        # Average success rate
        cursor.execute('SELECT AVG(success_rate) FROM usage_metrics WHERE total_executions > 10')
        stats['average_success_rate'] = cursor.fetchone()[0] or 0.0
        
        # Capabilities by type
        cursor.execute('''
            SELECT type, COUNT(*) FROM capabilities
            GROUP BY type
        ''')
        stats['by_type'] = dict(cursor.fetchall())
        
        # Top authors
        cursor.execute('''
            SELECT author_id, COUNT(*) as count
            FROM capabilities
            GROUP BY author_id
            ORDER BY count DESC
            LIMIT 10
        ''')
        stats['top_authors'] = [
            {'author_id': row[0], 'capability_count': row[1]}
            for row in cursor.fetchall()
        ]
        
        # Fork statistics
        cursor.execute('SELECT COUNT(*) FROM capabilities WHERE parent_id IS NOT NULL')
        stats['total_forks'] = cursor.fetchone()[0]
        
        # Rating statistics
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM ratings')
        stats['users_who_rated'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT AVG(rating) FROM ratings')
        stats['average_rating'] = cursor.fetchone()[0] or 0.0
        
        conn.close()
        return stats
