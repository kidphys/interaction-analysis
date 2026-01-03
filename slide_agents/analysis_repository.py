"""
Repository for managing Analysis persistence in DuckDB.
Provides functionality to:
- Generate IDs based on question and user_id
- Persist analysis data to DuckDB
- Load analysis data from DuckDB
"""

import hashlib
import json
from typing import Optional, Dict, Any
import duckdb


def create_analysis_repository_from_duckdb_file(duckdb_file: str) -> 'AnalysisRepository':
    """
    Create an analysis repository from a DuckDB file.
    """
    conn = duckdb.connect(duckdb_file)
    return AnalysisRepository(conn)


class AnalysisRepository:
    """
    Repository for managing Analysis persistence in DuckDB.
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
        """Create the analysis table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                question VARCHAR NOT NULL,
                sql TEXT NOT NULL,
                data TEXT NOT NULL,
                analysis TEXT NOT NULL,
                insight_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add insight_ids column if it doesn't exist (for existing tables)
        try:
            self.conn.execute("ALTER TABLE analysis ADD COLUMN insight_ids TEXT")
        except:
            # Column already exists, ignore
            pass

    def _generate_id(self, question: str, user_id: str) -> str:
        """
        Generate an ID by hashing the question and user_id.

        Args:
            question: The question string
            user_id: The user ID string

        Returns:
            A hexadecimal hash string (SHA256)
        """
        # Combine question and user_id for hashing
        content_str = f"{question}:{user_id}"
        # Generate SHA256 hash
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    def _extract_insight_ids(self, analysis: Any) -> list[str]:
        """
        Extract insight IDs from the analysis object.

        Args:
            analysis: The analysis object (InsightResponse or similar)

        Returns:
            A list of insight IDs
        """
        insight_ids = []

        try:
            # Handle Pydantic models
            if hasattr(analysis, 'items'):
                # InsightResponse has items attribute
                for item in analysis.items:
                    if hasattr(item, 'id') and item.id:
                        insight_ids.append(item.id)
            elif hasattr(analysis, 'model_dump'):
                # Try to get items from model_dump
                analysis_dict = analysis.model_dump()
                if 'items' in analysis_dict:
                    for item in analysis_dict['items']:
                        if isinstance(item, dict) and 'id' in item and item['id']:
                            insight_ids.append(item['id'])
                        elif hasattr(item, 'id') and item.id:
                            insight_ids.append(item.id)
            elif isinstance(analysis, dict):
                # Handle dict format
                if 'items' in analysis:
                    for item in analysis['items']:
                        if isinstance(item, dict) and 'id' in item and item['id']:
                            insight_ids.append(item['id'])
            elif isinstance(analysis, str):
                # Try to parse as JSON
                try:
                    analysis_dict = json.loads(analysis)
                    if 'items' in analysis_dict:
                        for item in analysis_dict['items']:
                            if isinstance(item, dict) and 'id' in item and item['id']:
                                insight_ids.append(item['id'])
                except:
                    pass
        except Exception as e:
            # If extraction fails, return empty list
            print(f"Warning: Could not extract insight IDs: {e}")
            pass

        return insight_ids

    def save(
        self,
        question: str,
        sql: str,
        data: str,
        analysis: Any,
        user_id: str
    ) -> str:
        """
        Persist an analysis to DuckDB.
        If an analysis with the same question and user_id already exists, it will be updated.

        Args:
            question: The question that was analyzed
            sql: The SQL query that was executed
            data: The data result (as string)
            analysis: The analysis result (will be serialized to JSON)
            user_id: The user ID

        Returns:
            The ID of the persisted analysis
        """
        # Generate ID from question and user_id
        analysis_id = self._generate_id(question, user_id)

        # Extract insight IDs from analysis
        insight_ids = self._extract_insight_ids(analysis)
        insight_ids_json = json.dumps(insight_ids) if insight_ids else None

        # Serialize analysis to JSON if it's not already a string
        if isinstance(analysis, str):
            analysis_json = analysis
        else:
            # Try to serialize as JSON (handles dict, Pydantic models, etc.)
            try:
                if hasattr(analysis, 'model_dump'):
                    # Pydantic model
                    analysis_json = json.dumps(analysis.model_dump())
                elif hasattr(analysis, 'dict'):
                    # Pydantic v1 or similar
                    analysis_json = json.dumps(analysis.dict())
                else:
                    # Regular dict or other JSON-serializable object
                    analysis_json = json.dumps(analysis)
            except (TypeError, AttributeError):
                # Fallback to string representation
                analysis_json = str(analysis)

        # Use INSERT OR REPLACE to handle updates
        self.conn.execute("""
            INSERT OR REPLACE INTO analysis (id, user_id, question, sql, data, analysis, insight_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (analysis_id, user_id, question, sql, data, analysis_json, insight_ids_json))

        return analysis_id

    def load(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Load an analysis from DuckDB by ID.

        Args:
            analysis_id: The ID of the analysis to load

        Returns:
            A dictionary with the analysis data if found, None otherwise
        """
        result = self.conn.execute(
            "SELECT user_id, question, sql, data, analysis, insight_ids, created_at FROM analysis WHERE id = ?",
            (analysis_id,)
        ).fetchone()

        if result is None:
            return None

        return {
            'id': analysis_id,
            'user_id': result[0],
            'question': result[1],
            'sql': result[2],
            'data': result[3],
            'analysis': json.loads(result[4]) if result[4] else None,
            'insight_ids': json.loads(result[5]) if result[5] else [],
            'created_at': result[6]
        }

    def load_by_question_and_user(self, question: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Load an analysis from DuckDB by question and user_id.

        Args:
            question: The question string
            user_id: The user ID string

        Returns:
            A dictionary with the analysis data if found, None otherwise
        """
        analysis_id = self._generate_id(question, user_id)
        return self.load(analysis_id)

    def list_by_user(self, user_id: str) -> list[Dict[str, Any]]:
        """
        Load all analyses for a specific user from DuckDB.

        Args:
            user_id: The user ID to filter by

        Returns:
            A list of analysis dictionaries
        """
        results = self.conn.execute(
            "SELECT id, user_id, question, sql, data, analysis, insight_ids, created_at FROM analysis WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()

        analyses = []
        for result in results:
            analyses.append({
                'id': result[0],
                'user_id': result[1],
                'question': result[2],
                'sql': result[3],
                'data': result[4],
                'analysis': json.loads(result[5]) if result[5] else None,
                'insight_ids': json.loads(result[6]) if result[6] else [],
                'created_at': result[7]
            })

        return analyses

    def list_all(self) -> list[Dict[str, Any]]:
        """
        Load all analyses from DuckDB.

        Returns:
            A list of all analysis dictionaries
        """
        results = self.conn.execute(
            "SELECT id, user_id, question, sql, data, analysis, insight_ids, created_at FROM analysis ORDER BY created_at DESC"
        ).fetchall()

        analyses = []
        for result in results:
            analyses.append({
                'id': result[0],
                'user_id': result[1],
                'question': result[2],
                'sql': result[3],
                'data': result[4],
                'analysis': json.loads(result[5]) if result[5] else None,
                'insight_ids': json.loads(result[6]) if result[6] else [],
                'created_at': result[7]
            })

        return analyses

    def load_by_insight_id(self, insight_id: str) -> list[Dict[str, Any]]:
        """
        Load all analyses that contain a specific insight ID.

        Args:
            insight_id: The insight ID to search for

        Returns:
            A list of analysis dictionaries that contain the insight ID
        """
        # Load all analyses and filter in Python for reliability
        # This is efficient enough for most use cases
        results = self.conn.execute("""
            SELECT id, user_id, question, sql, data, analysis, insight_ids, created_at
            FROM analysis
            WHERE insight_ids IS NOT NULL
            ORDER BY created_at DESC
        """).fetchall()

        analyses = []
        for result in results:
            insight_ids_list = json.loads(result[6]) if result[6] else []
            # Check if the insight_id is in the list
            if insight_id in insight_ids_list:
                analyses.append({
                    'id': result[0],
                    'user_id': result[1],
                    'question': result[2],
                    'sql': result[3],
                    'data': result[4],
                    'analysis': json.loads(result[5]) if result[5] else None,
                    'insight_ids': insight_ids_list,
                    'created_at': result[7]
                })

        return analyses

    def delete(self, analysis_id: str) -> bool:
        """
        Delete an analysis from DuckDB by ID.

        Args:
            analysis_id: The ID of the analysis to delete

        Returns:
            True if the analysis was deleted, False if it didn't exist
        """
        cursor = self.conn.execute(
            "DELETE FROM analysis WHERE id = ?",
            (analysis_id,)
        )
        return cursor.rowcount > 0

    def delete_by_question_and_user(self, question: str, user_id: str) -> bool:
        """
        Delete an analysis from DuckDB by question and user_id.

        Args:
            question: The question string
            user_id: The user ID string

        Returns:
            True if the analysis was deleted, False if it didn't exist
        """
        analysis_id = self._generate_id(question, user_id)
        return self.delete(analysis_id)

