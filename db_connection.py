"""
Database connection and query module for client process monitoring
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Tuple
import os
from dotenv import load_dotenv

load_dotenv()


class DatabaseConnection:
    """Handles PostgreSQL database connections and queries"""
    
    def __init__(self):
        self.connection_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD')
        }
        self.conn = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
            print("✅ Database connection established")
            return self.conn
        except psycopg2.Error as e:
            print(f"❌ Database connection failed: {e}")
            raise
    
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("🔌 Database connection closed")
    
    def get_last_24h_processes(self) -> List[Dict[str, Any]]:
        """
        Retrieve all processes from last 24 hours using the processes_dashboard view
        Returns list of process dictionaries with all relevant information
        """
        query = """
        SELECT
            u.name,
            u.api_key,
            (SELECT name FROM process_status ps WHERE ps.id = p.status_id) AS status_name,
            p.start_time,
            p.ping_time,
            p.stop_time,
            ROUND(EXTRACT(EPOCH FROM (p.ping_time - p.start_time)) / 60, 1) AS elapsed_time_min,
            s.uri AS source_uri,
            s.alias AS source_alias,
            s.uuid AS source_uuid,
            p.uuid AS process_uuid,
            p.user_configuration
        FROM
            process p
            JOIN source s ON p.source_id = s.id
            JOIN "USER" u ON u.id = s.user_id
        WHERE
            p.start_time > now() - interval '24 hours'
            AND u.role_id = 2
        ORDER BY
            p.start_time DESC;
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                # Convert to list of dicts
                processes = [dict(row) for row in results]
                
                print(f"📊 Retrieved {len(processes)} processes from last 24h")
                return processes
                
        except psycopg2.Error as e:
            print(f"❌ Query failed: {e}")
            raise
    
    def get_user_apikey_mapping(self) -> Dict[str, str]:
        """
        Get mapping of user API keys to client names from database
        This replaces the folders_2_client.txt file
        """
        query = """
        SELECT
            u.api_key,
            u.name as client_name
        FROM
            "USER" u
        WHERE
            u.role_id = 2  -- Only clients
            AND u.api_key IS NOT NULL;
        """
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                
                # Build mapping dict
                mapping = {row['api_key']: row['client_name'] for row in results}
                
                print(f"🗂️  Loaded {len(mapping)} client API key mappings")
                return mapping
                
        except psycopg2.Error as e:
            print(f"❌ Failed to load API key mapping: {e}")
            # Return empty dict instead of failing
            return {}
    
    def categorize_processes(self, processes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize processes by status: finished, failed, running, etc.
        """
        categorized = {
            'finished': [],
            'failed': [],
            'running': [],
            'other': []
        }
        
        for process in processes:
            status = process['status_name'].lower()
            
            if 'finish' in status or 'complete' in status:
                categorized['finished'].append(process)
            elif 'fail' in status or 'error' in status:
                categorized['failed'].append(process)
            elif 'running' in status or 'processing' in status:
                categorized['running'].append(process)
            else:
                categorized['other'].append(process)
        
        print(f"📋 Categorized processes:")
        print(f"   ✅ Finished: {len(categorized['finished'])}")
        print(f"   ❌ Failed: {len(categorized['failed'])}")
        print(f"   ⏳ Running: {len(categorized['running'])}")
        print(f"   ℹ️  Other: {len(categorized['other'])}")
        
        return categorized


# Standalone functions for convenience
def get_db_connection() -> DatabaseConnection:
    """Create and return a database connection"""
    db = DatabaseConnection()
    db.connect()
    return db


def fetch_processes_last_24h() -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Fetch and categorize processes from last 24 hours
    Returns: (all_processes, categorized_processes)
    """
    db = get_db_connection()
    try:
        processes = db.get_last_24h_processes()
        categorized = db.categorize_processes(processes)
        return processes, categorized
    finally:
        db.disconnect()


if __name__ == "__main__":
    # Test the database connection
    print("Testing database connection...\n")
    
    db = get_db_connection()
    try:
        processes = db.get_last_24h_processes()
        print(f"\nSample process data:")
        if processes:
            print(processes[0])
        
        categorized = db.categorize_processes(processes)
        
        mapping = db.get_user_apikey_mapping()
        print(f"\nAPI Key Mapping: {mapping}")
        
    finally:
        db.disconnect()