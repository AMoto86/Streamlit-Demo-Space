"""
Database module for Network Connectivity Dashboard.
Handles SQLite connections, table creation, and CRUD operations.
"""

import sqlite3
import os
from datetime import datetime

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "network.db")


def get_connection():
    """Create and return a database connection."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable dictionary-like access
        return conn
    except sqlite3.Error as e:
        raise RuntimeError(f"Database connection failed: {e}")


def initialize_database():
    """
    Create the required tables if they don't exist.
    
    Tables:
        - nodes: Stores network nodes (Sensors, Endpoints, Intermediaries)
        - edges: Stores pathways between nodes with status info
        - test_results: Stores history of connection tests
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('Sensor', 'Endpoint', 'Intermediary'))
            )
        """)

        # Create edges table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Down' CHECK(status IN ('Active', 'Down')),
                last_tested TEXT,
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            )
        """)

        # Create test_results table for audit trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Database initialization failed: {e}")


def seed_dummy_data():
    """
    Populate the database with sample data on first run.
    Creates a small network topology with sensors, endpoints, and pathways.
    """
    # Only seed if the database is empty
    if get_node_count() > 0:
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Insert sample nodes
        nodes = [
            ("Sensor A", "Sensor"),
            ("Sensor B", "Sensor"),
            ("Sensor C", "Sensor"),
            ("Endpoint A", "Endpoint"),
            ("Endpoint B", "Endpoint"),
            ("Gateway 1", "Intermediary"),
            ("Gateway 2", "Intermediary"),
        ]

        cursor.executemany(
            "INSERT OR IGNORE INTO nodes (name, type) VALUES (?, ?)", nodes
        )

        # Get node IDs for edge creation
        cursor.execute("SELECT id, name FROM nodes")
        node_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Insert sample edges (pathways)
        edges = [
            (node_map["Sensor A"], node_map["Gateway 1"], "Active"),
            (node_map["Sensor B"], node_map["Gateway 1"], "Active"),
            (node_map["Sensor C"], node_map["Gateway 2"], "Down"),
            (node_map["Gateway 1"], node_map["Endpoint A"], "Active"),
            (node_map["Gateway 1"], node_map["Gateway 2"], "Active"),
            (node_map["Gateway 2"], node_map["Endpoint B"], "Down"),
        ]

        cursor.executemany(
            "INSERT INTO edges (source_id, target_id, status) VALUES (?, ?, ?)", edges
        )

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to seed dummy data: {e}")


# ---------------------------------------------------------------------------
# Node CRUD Operations
# ---------------------------------------------------------------------------

def get_node_count():
    """Return the total number of nodes in the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM nodes")
        count = cursor.fetchone()["count"]
        conn.close()
        return count
    except sqlite3.Error:
        return 0


def get_all_nodes():
    """Return all nodes from the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM nodes")
        nodes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return nodes
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to fetch nodes: {e}")


def add_node(name: str, node_type: str) -> bool:
    """
    Add a new node to the database.
    
    Args:
        name: Unique name for the node.
        node_type: Type of node (Sensor, Endpoint, Intermediary).
    
    Returns:
        True if node was added, False if it already exists.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO nodes (name, type) VALUES (?, ?)", (name, node_type)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Node with this name already exists
        return False
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to add node: {e}")


# ---------------------------------------------------------------------------
# Edge CRUD Operations
# ---------------------------------------------------------------------------

def get_all_edges():
    """Return all edges with node names for display purposes."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                e.id,
                e.source_id,
                e.target_id,
                e.status,
                e.last_tested,
                n1.name AS source_name,
                n2.name AS target_name
            FROM edges e
            JOIN nodes n1 ON e.source_id = n1.id
            JOIN nodes n2 ON e.target_id = n2.id
        """)
        edges = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return edges
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to fetch edges: {e}")


def add_edge(source_name: str, target_name: str) -> bool:
    """
    Add a new edge (pathway) between two nodes.
    
    Args:
        source_name: Name of the source node.
        target_name: Name of the target node.
    
    Returns:
        True if edge was added, False if it already exists or nodes not found.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Look up node IDs
        cursor.execute("SELECT id FROM nodes WHERE name = ?", (source_name,))
        source_row = cursor.fetchone()
        cursor.execute("SELECT id FROM nodes WHERE name = ?", (target_name,))
        target_row = cursor.fetchone()

        if not source_row or not target_row:
            conn.close()
            return False

        source_id = source_row["id"]
        target_id = target_row["id"]

        # Check if edge already exists
        cursor.execute(
            "SELECT id FROM edges WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        )
        if cursor.fetchone():
            conn.close()
            return False

        # Insert new edge with default 'Down' status
        cursor.execute(
            "INSERT INTO edges (source_id, target_id, status) VALUES (?, ?, ?)",
            (source_id, target_id, "Down"),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to add edge: {e}")


def update_edge_status(source_name: str, target_name: str, status: str):
    """
    Update the status of an edge and set the last_tested timestamp.
    
    Args:
        source_name: Name of the source node.
        target_name: Name of the target node.
        status: New status ('Active' or 'Down').
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE edges 
            SET status = ?, last_tested = ?
            WHERE source_id = (SELECT id FROM nodes WHERE name = ?)
              AND target_id = (SELECT id FROM nodes WHERE name = ?)
            """,
            (status, datetime.now().isoformat(), source_name, target_name),
        )

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to update edge status: {e}")


def update_edges_status(edge_pairs: list, status: str):
    """
    Batch update the status of multiple edges.
    
    Args:
        edge_pairs: List of (source_name, target_name) tuples.
        status: New status ('Active' or 'Down').
    """
    timestamp = datetime.now().isoformat()
    try:
        conn = get_connection()
        cursor = conn.cursor()

        for source_name, target_name in edge_pairs:
            cursor.execute(
                """
                UPDATE edges 
                SET status = ?, last_tested = ?
                WHERE source_id = (SELECT id FROM nodes WHERE name = ?)
                  AND target_id = (SELECT id FROM nodes WHERE name = ?)
                """,
                (status, timestamp, source_name, target_name),
            )

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to batch update edge status: {e}")


# ---------------------------------------------------------------------------
# Test Results Operations
# ---------------------------------------------------------------------------

def record_test_result(source_name: str, target_name: str, result: str):
    """
    Record a test result in the audit trail.
    
    Args:
        source_name: Name of the source node.
        target_name: Name of the target node.
        result: Test outcome description.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO test_results (source_name, target_name, result, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (source_name, target_name, result, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to record test result: {e}")


def get_recent_tests(limit: int = 10):
    """
    Get the most recent test results.
    
    Args:
        limit: Maximum number of results to return.
    
    Returns:
        List of recent test result dictionaries.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM test_results 
            ORDER BY timestamp DESC 
            LIMIT ?
            """,
            (limit,),
        )
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to fetch test results: {e}")


# ---------------------------------------------------------------------------
# Summary / Health Statistics
# ---------------------------------------------------------------------------

def get_health_summary():
    """
    Calculate system health statistics.
    
    Returns:
        Dictionary with total_nodes, active_edges, down_edges, and total_edges.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM nodes")
        total_nodes = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM edges WHERE status = 'Active'")
        active_edges = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM edges WHERE status = 'Down'")
        down_edges = cursor.fetchone()["count"]

        conn.close()

        return {
            "total_nodes": total_nodes,
            "active_edges": active_edges,
            "down_edges": down_edges,
            "total_edges": active_edges + down_edges,
        }
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to calculate health summary: {e}")
