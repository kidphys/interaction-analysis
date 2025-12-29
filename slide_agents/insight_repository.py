"""
Repository for managing InsightItem persistence in DuckDB.
Provides functionality to:
- Generate IDs based on item content
- Persist items to DuckDB
- Load items from DuckDB
"""

import hashlib
import json
from typing import Optional
import duckdb
from slide_agents.query_node import InsightItem


class InsightRepository:
    """
    Repository for managing InsightItem persistence in DuckDB.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        """
        Initialize the repository with a DuckDB connection.

        Args:
            conn: DuckDB connection object
        """
        self.conn = conn
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Create the insight_items table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS insight_items (
                id VARCHAR PRIMARY KEY,
                content_hash VARCHAR UNIQUE,
                item_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _generate_content_hash(self, item: InsightItem) -> str:
        """
        Generate a hash based on the item's content (message + visualization).

        Args:
            item: The InsightItem to hash

        Returns:
            A hexadecimal hash string
        """
        # Create a dictionary representation without the ID
        item_dict = item.model_dump(exclude={'id'})
        # Sort keys for consistent hashing
        content_str = json.dumps(item_dict, sort_keys=True)
        # Generate SHA256 hash
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    def _generate_id_from_content(self, item: InsightItem) -> str:
        """
        Generate an ID for an item based on its content.
        Uses the first 16 characters of the content hash as the ID.

        Args:
            item: The InsightItem to generate an ID for

        Returns:
            A unique ID string
        """
        content_hash = self._generate_content_hash(item)
        # Use first 16 characters of hash as ID (can be adjusted)
        return content_hash[:16]

    def add_id(self, item: InsightItem) -> str:
        """
        Add an ID to an existing item based on its content.
        If the item already has an ID, it will be returned.
        Otherwise, a new ID will be generated and assigned.

        Args:
            item: The InsightItem to add an ID to

        Returns:
            The ID of the item
        """
        if item.id is not None:
            return item.id

        # Always generate a new ID (don't reuse existing IDs)
        item.id = self._generate_id_from_content(item)
        return item.id

    def save(self, item: InsightItem) -> str:
        """
        Persist an item to DuckDB.
        If the item doesn't have an ID, one will be generated based on content.
        If an item with the same content already exists, it will be deleted and replaced.

        Args:
            item: The InsightItem to persist

        Returns:
            The ID of the persisted item
        """
        # Ensure item has an ID
        item_id = self.add_id(item)

        # Generate content hash
        content_hash = self._generate_content_hash(item)

        # Delete any existing item with the same content_hash
        self.conn.execute(
            "DELETE FROM insight_items WHERE content_hash = ?",
            (content_hash,)
        )

        # Serialize item to JSON
        item_json = item.model_dump_json()

        # Insert the new item
        self.conn.execute("""
            INSERT INTO insight_items (id, content_hash, item_json)
            VALUES (?, ?, ?)
        """, (item_id, content_hash, item_json))

        return item_id

    def load(self, item_id: str) -> Optional[InsightItem]:
        """
        Load an item from DuckDB by ID.

        Args:
            item_id: The ID of the item to load

        Returns:
            The InsightItem if found, None otherwise
        """
        result = self.conn.execute(
            "SELECT item_json FROM insight_items WHERE id = ?",
            (item_id,)
        ).fetchone()

        if result is None:
            return None

        item_json = result[0]
        return InsightItem.model_validate_json(item_json)

    def load_by_content_hash(self, content_hash: str) -> Optional[InsightItem]:
        """
        Load an item from DuckDB by content hash.

        Args:
            content_hash: The content hash of the item to load

        Returns:
            The InsightItem if found, None otherwise
        """
        result = self.conn.execute(
            "SELECT item_json FROM insight_items WHERE content_hash = ?",
            (content_hash,)
        ).fetchone()

        if result is None:
            return None

        item_json = result[0]
        return InsightItem.model_validate_json(item_json)

    def find_by_content(self, item: InsightItem) -> Optional[InsightItem]:
        """
        Find an item in the database that matches the content of the given item.

        Args:
            item: The InsightItem to search for

        Returns:
            The matching InsightItem if found, None otherwise
        """
        content_hash = self._generate_content_hash(item)
        return self.load_by_content_hash(content_hash)

    def list_all(self) -> list[InsightItem]:
        """
        Load all items from DuckDB.

        Returns:
            A list of all InsightItems in the database
        """
        results = self.conn.execute(
            "SELECT item_json FROM insight_items ORDER BY created_at DESC"
        ).fetchall()

        items = []
        for result in results:
            item_json = result[0]
            items.append(InsightItem.model_validate_json(item_json))

        return items

    def delete(self, item_id: str) -> bool:
        """
        Delete an item from DuckDB by ID.

        Args:
            item_id: The ID of the item to delete

        Returns:
            True if the item was deleted, False if it didn't exist
        """
        cursor = self.conn.execute(
            "DELETE FROM insight_items WHERE id = ?",
            (item_id,)
        )
        return cursor.rowcount > 0
