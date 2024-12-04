from sqlalchemy import text, select, func
from typing import List, Any, Dict, Optional
from src.models.base import Project, Asset, project_assets

class SQLQueryBuilder:
    """Build SQL queries from natural language"""
    
    def build_query(self, query: str) -> text:
        """Build a SQL query from natural language"""
        query = query.lower().strip()
        
        # Handle count queries
        if "how many" in query or "count" in query:
            if "asset" in query:
                return text("SELECT COUNT(*) FROM assets")
            elif "project" in query:
                return text("SELECT COUNT(*) FROM projects")
                
        # Handle listing queries
        if "list" in query or "show" in query or "get" in query:
            if "asset" in query:
                return text("""
                    SELECT 
                        a.id, 
                        a.asset_type,
                        a.file_url,
                        a.repo_url,
                        a.explorer_url,
                        array_agg(p.name) as project_names
                    FROM assets a
                    LEFT JOIN project_assets pa ON a.id = pa.asset_id
                    LEFT JOIN projects p ON pa.project_id = p.id
                    GROUP BY 
                        a.id,
                        a.asset_type,
                        a.file_url,
                        a.repo_url,
                        a.explorer_url
                    ORDER BY a.id
                """)
            elif "project" in query:
                return text("""
                    SELECT 
                        p.id,
                        p.name,
                        p.description,
                        p.project_type,
                        COUNT(a.id) as asset_count
                    FROM projects p
                    LEFT JOIN project_assets pa ON p.id = pa.project_id
                    LEFT JOIN assets a ON pa.asset_id = a.id
                    GROUP BY p.id, p.name, p.description, p.project_type
                    ORDER BY p.name
                """)
        
        # Default to listing assets
        return text("""
            SELECT 
                a.id, 
                a.asset_type,
                a.file_url,
                a.repo_url,
                a.explorer_url,
                array_agg(p.name) as project_names
            FROM assets a
            LEFT JOIN project_assets pa ON a.id = pa.asset_id
            LEFT JOIN projects p ON pa.project_id = p.id
            GROUP BY 
                a.id,
                a.asset_type,
                a.file_url,
                a.repo_url,
                a.explorer_url
            ORDER BY a.id
        """)
    
    def build_count_query(self, query: str) -> text:
        """Build a count query from natural language"""
        query = query.lower().strip()
        
        if "asset" in query:
            return text("SELECT COUNT(*) FROM assets")
        elif "project" in query:
            return text("SELECT COUNT(*) FROM projects")
            
        # Default to counting assets
        return text("SELECT COUNT(*) FROM assets")