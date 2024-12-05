from typing import Dict, List, Optional, Any
from src.util.logging import Logger
from openai import AsyncOpenAI
from src.config.config import Config
import json

SYSTEM_PROMPT = """You are a search agent that helps users find information in the database and codebase. You must always respond with a JSON object containing a search strategy.

Required JSON Response Format:
{
    "explanation": "Description of the search strategy",
    "actions": [
        {
            "type": "db_query",
            "spec": {
                "from": "table_name",
                "select": ["field1", "field2"],
                "where": [{"field": "field_name", "op": "operator", "value": "value"}],
                "order_by": [{"field": "field_name", "direction": "asc"}]
            }
        }
    ],
    "combine_results": "How to combine results",
    "format": "text"
}

Database Schema Knowledge:
- Projects table:
  - name: Project name
  - description: Project description
  - project_type: High-level type (e.g. 'bounty')
  - keywords: Array of tags including programming languages, frameworks, and features
  - source_url: URL to project source/listing
  - extra_data: JSONB field with additional metadata

- Assets table:
  - id: Unique identifier
  - asset_type: Type of asset ('github_repo', 'github_file', 'deployed_contract')
  - source_url: Original source URL (contains file extension for github_file)
  - local_path: Path to local file or directory
  - extra_data: JSONB field with additional metadata including tags and URLs
  - embedding: Vector embedding for semantic search

When searching:
1. Use projects.keywords for searching by language, framework, or feature
2. Use project_type for high-level categorization only
3. Use asset_type to filter specific types of assets
4. Use extra_data->>'tags' in assets for asset-specific metadata
5. Consider both description and keywords when searching for technologies
6. For file type filtering:
   - Use source_url LIKE '%.extension' to filter by file extension
   - Common extensions: .sol (Solidity), .cairo (Cairo), .vy (Vyper), .py (Python)
   - For GitHub files, source_url ends with the file extension

Query Format Rules:
1. Always use fully qualified field names (e.g. 'projects.name', 'assets.id')
2. For array fields like keywords:
   - Use '?*' operator for case-insensitive array search
   - Use '?' operator for case-sensitive array search
3. For text fields:
   - Use 'ilike' for case-insensitive text search
   - Use 'like' for case-sensitive text search
4. For random ordering:
   - Use order_by: [{"field": "RANDOM()", "direction": "asc"}]
5. For JSONB fields:
   - Use ->> operator to access text values (e.g. extra_data->>'tags')
   - Use -> operator to access JSON values

Example JSON Search Strategies:
1. Find Cairo projects:
{
    "explanation": "Search for projects using Cairo language",
    "actions": [{
        "type": "db_query",
        "spec": {
            "from": "projects",
            "select": ["projects.name", "projects.description", "projects.project_type"],
            "where": [
                {"field": "projects.keywords", "op": "?*", "value": "cairo"}
            ],
            "order_by": [{"field": "RANDOM()", "direction": "asc"}],
            "limit": 5
        }
    }],
    "combine_results": "List the projects with their descriptions",
    "format": "text"
}

2. Find Solidity smart contracts:
{
    "explanation": "Search for Solidity contract files",
    "actions": [{
        "type": "db_query",
        "spec": {
            "from": "assets",
            "select": ["assets.id", "assets.source_url", "assets.local_path"],
            "where": [
                {"field": "assets.asset_type", "op": "=", "value": "github_file"},
                {"field": "assets.source_url", "op": "like", "value": "%.sol"}
            ],
            "order_by": [{"field": "assets.id", "direction": "asc"}],
            "limit": 10
        }
    }],
    "combine_results": "List the Solidity files with their URLs",
    "format": "text"
}

3. Find Vyper contracts with reentrancy:
{
    "explanation": "Search for Vyper contracts containing reentrancy patterns",
    "actions": [
        {
            "type": "db_query",
            "spec": {
                "from": "assets",
                "select": ["assets.id", "assets.source_url", "assets.local_path"],
                "where": [
                    {"field": "assets.asset_type", "op": "=", "value": "github_file"},
                    {"field": "assets.source_url", "op": "like", "value": "%.vy"}
                ],
                "limit": 50
            }
        },
        {
            "type": "file_search",
            "pattern": "send|transfer|call.value|raw_call",
            "use_previous_paths": true
        }
    ],
    "combine_results": "List Vyper files containing potential reentrancy patterns",
    "format": "text"
}
"""

class SearchAgent:
    """Agent for handling natural language search queries
    
    This agent understands the relationship between database records and files:
    - Assets table contains metadata about files and repositories
    - local_path field in assets points to actual files on disk
    - Projects are linked to assets through project_assets table
    
    The agent can:
    1. Search database metadata using db_query action
    2. Search file contents using file_search action
    3. Combine both searches intelligently
    """
    
    def __init__(self):
        self.logger = Logger("SearchAgent")
        self.config = Config()
        
        # Initialize OpenAI client
        try:
            openai_key = self.config.openai_api_key
            self.client = AsyncOpenAI(api_key=openai_key)
            self.model = self.config.openai_model
            self.logger.info(f"Using OpenAI model: {self.model}")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI: {e}")
            raise
            
    def _get_system_prompt(self) -> str:
        """Get the system prompt for search query understanding"""
        return SYSTEM_PROMPT
        
    def _format_results(self, results: Dict[str, Any], format_type: str) -> Dict[str, Any]:
        """Format results according to specified format"""
        if format_type == "json":
            return results
            
        # Format as human-readable text
        text_results = []
        
        # Add explanation if available
        if "explanation" in results:
            text_results.append(results["explanation"])
            text_results.append("")  # Empty line
            
        # Format actual results
        if "results" in results:
            if not results["results"]:
                text_results.append("No results found.")
            else:
                for result in results["results"]:
                    if isinstance(result, dict):
                        # Handle different result types
                        if "name" in result and "description" in result:
                            # Project result
                            text_results.append(f"Project: {result['name']}")
                            if result.get('description'):
                                text_results.append(f"Description: {result['description']}")
                        elif "file_path" in result and "matches" in result:
                            # File search result
                            text_results.append(f"File: {result['file_path']}")
                            for match in result["matches"]:
                                text_results.append(f"  Line {match['line_number']}: {match['line']}")
                        else:
                            # Generic result
                            text_results.append(" - " + ", ".join(f"{k}: {v}" for k, v in result.items()))
                    else:
                        text_results.append(str(result))
                    text_results.append("")  # Empty line between results
                    
        # Add metadata if available
        if "metadata" in results:
            meta = results["metadata"]
            if "total_results" in meta:
                text_results.append(f"\nTotal results: {meta['total_results']}")
            if "files_searched" in meta:
                text_results.append(f"Files searched: {meta['files_searched']}")
                
        return {
            "text": "\n".join(text_results).strip()
        }
        
    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a natural language search query
        
        Args:
            query: Natural language search query
            
        Returns:
            Dict containing search results and metadata
        """
        try:
            # Get search strategy from GPT
            search_strategy = await self._analyze_query(query)
            self.logger.info(f"Search strategy: {search_strategy}")
            
            results = {
                "query": query,
                "explanation": search_strategy.get("explanation", ""),
                "results": [],
                "metadata": {}
            }
            
            # Execute actions in sequence
            action_results = []
            for action in search_strategy.get("actions", []):
                if action["type"] == "db_query":
                    # Import here to avoid circular imports
                    from src.actions.db_query import DBQueryAction
                    db_action = DBQueryAction()
                    result = await db_action.execute(json.dumps(action["spec"]))
                    action_results.append(json.loads(result))
                    
                elif action["type"] == "file_search":
                    # Import here to avoid circular imports
                    from src.actions.file_search import FileSearchAction
                    file_action = FileSearchAction()
                    # Get paths from previous db_query if needed
                    if action.get("use_previous_paths"):
                        prev_result = action_results[-1]
                        paths = [r.get("local_path") for r in prev_result.get("results", [])]
                        action["paths"] = paths
                        
                    result = await file_action.execute(
                        action.get("pattern", ""),
                        action.get("paths", [])
                    )
                    action_results.append(json.loads(result))
                    
            # Combine results according to strategy
            results["results"] = self._combine_results(
                action_results,
                search_strategy.get("combine_results", "")
            )
            
            # Add metadata
            results["metadata"] = {
                "total_results": len(results["results"]),
                "actions_executed": len(action_results)
            }
            
            # Format results according to strategy
            return self._format_results(results, search_strategy.get("format", "text"))
            
        except Exception as e:
            self.logger.error(f"Error processing search query: {str(e)}")
            return {
                "text": f"Error processing search query: {str(e)}"
            }
            
    async def _analyze_query(self, query: str) -> Dict[str, Any]:
        """Use GPT to analyze and structure the search query"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            return json.loads(result)
            
        except Exception as e:
            self.logger.error(f"Error analyzing query with GPT: {str(e)}")
            return self._basic_query_parse(query)
            
    def _basic_query_parse(self, query: str) -> Dict[str, Any]:
        """Basic query parsing as fallback if GPT fails"""
        # Default to searching both filenames and contents
        return {
            "explanation": "Basic search of filenames and contents",
            "actions": [
                {
                    "type": "db_query",
                    "spec": {
                        "from": "assets",
                        "join": {"table": "projects", "on": {"id": "id"}},
                        "select": ["projects.name", "assets.local_path"],
                        "where": [{"field": "local_path", "op": "is not", "value": null}]
                    }
                },
                {
                    "type": "file_search",
                    "pattern": query,
                    "use_previous_paths": True
                }
            ],
            "combine_results": "Show projects with matching files",
            "format": "text"
        }
        
    def _combine_results(self, action_results: List[Dict[str, Any]], strategy: str) -> List[Dict[str, Any]]:
        """Combine results from multiple actions according to strategy"""
        combined = []
        
        try:
            if not action_results:
                return combined
                
            # Handle different combination strategies
            if "matching_ids" in strategy:
                # Get IDs from file search to use in next query
                if len(action_results) >= 2:
                    file_results = action_results[1].get("results", [])
                    matching_ids = []
                    for r in file_results:
                        if "asset_id" in r:
                            matching_ids.append(r["asset_id"])
                    # Replace placeholder in next query
                    if len(action_results) >= 3:
                        for condition in action_results[2].get("spec", {}).get("where", []):
                            if condition.get("value") == "RESULTS[0].matching_ids":
                                condition["value"] = matching_ids
                                
            # Default combination
            for result in action_results:
                if "results" in result:
                    combined.extend(result["results"])
                    
            return combined
            
        except Exception as e:
            self.logger.error(f"Error combining results: {str(e)}")
            return action_results[0].get("results", []) if action_results else [] 

    async def execute_action(self, action_type: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action and return results"""
        try:
            if action_type == "db_query":
                action = DBQueryAction()
                result = await action.execute(json.dumps(spec))
                result_data = json.loads(result)
                if "error" in result_data:
                    self.logger.error(f"Query failed: {result_data['error']}")
                    # Try to fix common errors
                    if "Invalid field format" in result_data["error"]:
                        # Add table prefix to fields
                        if "select" in spec:
                            table = spec.get("from", "")
                            spec["select"] = [f"{table}.{field}" if "." not in field else field 
                                           for field in spec["select"]]
                        # Try again with fixed query
                        self.logger.info("Retrying with qualified field names...")
                        result = await action.execute(json.dumps(spec))
                        result_data = json.loads(result)
                    elif "Invalid field" in result_data["error"] and "RANDOM()" in result_data["error"]:
                        # Remove problematic order by
                        if "order_by" in spec:
                            del spec["order_by"]
                        # Try again without random ordering
                        self.logger.info("Retrying without random ordering...")
                        result = await action.execute(json.dumps(spec))
                        result_data = json.loads(result)
                return result_data
            elif action_type == "file_search":
                action = FileSearchAction()
                result = await action.execute(json.dumps(spec))
                return json.loads(result)
            else:
                raise ValueError(f"Unknown action type: {action_type}")
        except Exception as e:
            self.logger.error(f"Action failed: {str(e)}")
            return {
                "error": str(e),
                "count": 0,
                "results": []
            }

    async def execute_strategy(self, strategy: Dict[str, Any]) -> str:
        """Execute a search strategy and return formatted results"""
        try:
            if "error" in strategy:
                return f"Error planning search: {strategy['error']}"
                
            if "explanation" in strategy:
                self.logger.info(strategy["explanation"])
                
            results = []
            for action in strategy.get("actions", []):
                action_type = action["type"]
                spec = action["spec"]
                
                result = await self.execute_action(action_type, spec)
                if "error" in result:
                    return f"Search failed: {result['error']}"
                results.append(result)
                
            # Format results according to strategy
            if "combine_results" in strategy:
                self.logger.debug(f"Combining results: {strategy['combine_results']}")
                
            if "format" in strategy and strategy["format"] == "text":
                # Format as text
                if not results:
                    return "No results found."
                    
                lines = []
                for result in results:
                    if result.get("count", 0) == 0:
                        lines.append("No matching items found.")
                        continue
                        
                    for item in result.get("results", []):
                        if isinstance(item, dict):
                            if "name" in item:
                                lines.append(f"\nProject: {item['name']}")
                                if "description" in item:
                                    lines.append(f"Description: {item['description']}")
                                if "project_type" in item:
                                    lines.append(f"Type: {item['project_type']}")
                            elif "path" in item:
                                lines.append(f"\nFile: {item['path']}")
                                if "matches" in item:
                                    lines.append("Matches:")
                                    for match in item["matches"]:
                                        lines.append(f"- {match}")
                return "\n".join(lines)
                
            return str(results)
            
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {str(e)}")
            return f"Search failed: {str(e)}" 

    async def generate_search_strategy(self, query: str) -> Dict[str, Any]:
        """Generate a search strategy from a natural language query"""
        try:
            messages = [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": f"""Help me convert this search request into a JSON search strategy: "{query}"

Remember:
1. Use keywords column for languages and features
2. Use project_type only for high-level categories
3. Use description for free text search
4. Consider both exact and fuzzy matches
5. Return clear error messages to the user

Your response must be a valid JSON object."""}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.config.openai_model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            strategy = response.choices[0].message.content
            self.logger.info(f"Search strategy: {strategy}")
            
            try:
                return json.loads(strategy)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse strategy JSON: {str(e)}")
                return {
                    "error": "Failed to generate valid search strategy",
                    "raw_response": strategy
                }
                
        except Exception as e:
            self.logger.error(f"Error generating search strategy: {str(e)}")
            return {
                "error": f"Failed to generate search strategy: {str(e)}"
            } 