from typing import Dict, List, Any, Optional
from src.agents.base_agent import BaseAgent, AgentCommand
from src.util.logging import Logger
import json

class ConversationAgent(BaseAgent):
    """Agent for handling natural language conversations with users"""
    
    def __init__(self, command_names: Optional[List[str]] = None):
        self.logger = Logger("ConversationAgent")
        
        # Add specialized prompt for conversation handling
        custom_prompt = """You are specialized in having helpful conversations with security researchers.

Your responsibilities:
1. Understand user queries and intent
2. Execute appropriate commands to fulfill requests
3. Provide clear, concise responses
4. Guide users toward security-relevant information
5. Maintain context across conversation turns

Database Schema:
- projects: Represents security programs and projects
  - id: Primary key
  - name: Project name
  - description: Project description
  - project_type: Type (e.g., 'bounty', 'audit')
  - project_source: Source platform (e.g., 'immunefi', 'github')
  - extra_data: JSON field with additional metadata

- assets: Represents security-relevant assets (files, contracts, repos)
  - id: Primary key
  - asset_type: Type (e.g., 'github_file', 'github_repo', 'deployed_contract')
  - source_url: Original URL of the asset
  - file_url: Direct file URL if applicable
  - repo_url: Repository URL if applicable
  - explorer_url: Block explorer URL if applicable
  - local_path: Path to downloaded content
  - extra_data: JSON field with additional metadata

- project_assets: Links projects to their assets
  - project_id: References projects.id
  - asset_id: References assets.id

Example Queries:
1. Find GitHub repositories:
   EXECUTE: db_query query={"from": "assets", "where": [{"field": "asset_type", "op": "=", "value": "github_repo"}]}

2. Search by URL pattern:
   EXECUTE: db_query query={"from": "assets", "where": [{"field": "source_url", "op": "ilike", "value": "%github%"}]}

3. Get project with specific assets:
   EXECUTE: db_query query={"from": "projects", "join": "project_assets", "where": [{"field": "asset_type", "op": "=", "value": "github_file"}]}

4. Complex search with multiple conditions:
   EXECUTE: db_query query={"from": "assets", "where": [{"field": "asset_type", "op": "=", "value": "github_repo"}, {"field": "source_url", "op": "ilike", "value": "%uniswap%"}]}

Available Operations:
- Comparison: =, !=, >, <, >=, <=, ilike (case-insensitive pattern match)
- Pattern matching: Use % as wildcard in ilike patterns
- Joins: Specify "join" field to link tables
- Ordering: Use "order_by" field
- Limits: Use "limit" field (default 100)

Communication style:
- Be professional but conversational
- Focus on security relevance
- Provide specific, actionable information
- Ask clarifying questions when needed
- Use clear formatting for better readability"""

        # Call parent constructor with custom prompt and command names
        super().__init__(custom_prompt=custom_prompt, command_names=command_names)
        
    def _truncate_result(self, result: str, max_length: int = 4000) -> str:
        """Truncate a result string to a reasonable size"""
        if len(result) <= max_length:
            return result
            
        # For JSON strings, try to parse and truncate the content
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                if 'results' in data and isinstance(data['results'], list):
                    # Truncate results array
                    original_count = len(data['results'])
                    data['results'] = data['results'][:10]  # Keep only first 10 results
                    data['note'] = f"Results truncated to 10 of {original_count} total matches"
                return json.dumps(data)
        except json.JSONDecodeError:
            pass
            
        # For plain text, truncate with ellipsis
        return result[:max_length] + "... (truncated)"

    async def process_message(self, message: str) -> str:
        """Process a user message and return a response"""
        try:
            # First get AI's understanding of the request
            messages = [
                {"role": "user", "content": message},
                {"role": "system", "content": """Determine if this message requires executing any commands.
                
For casual conversation or greetings, just respond naturally.
Only suggest commands if the user is asking for specific information or actions.

Example casual messages (no commands needed):
- "How are you?"

Example action messages (commands needed):
- "Show me recent projects"
- "Search for reentrancy vulnerabilities"
- "List all assets"

If commands are needed, format them exactly like this:
EXECUTE: db_query query={"from": "projects", "limit": 5}"""}
            ]
            plan = await self.chat_completion(messages)
            
            # For casual conversation, return the response directly
            if 'EXECUTE:' not in plan:
                return plan
                
            # Otherwise, proceed with command execution
            messages.extend([
                {"role": "assistant", "content": plan},
                {"role": "system", "content": """Execute the necessary commands. Format queries exactly like this:

1. Get random projects:
EXECUTE: db_query query={"from": "projects", "limit": 5}

2. Search assets by type:
EXECUTE: db_query query={"from": "assets", "where": [{"field": "asset_type", "op": "=", "value": "github_repo"}]}

3. Search by URL pattern:
EXECUTE: db_query query={"from": "assets", "where": [{"field": "source_url", "op": "ilike", "value": "%github%"}]}

4. Join projects and assets:
EXECUTE: db_query query={"from": "projects", "join": "project_assets", "where": [{"field": "asset_type", "op": "=", "value": "github_file"}]}

The query must be a single, properly escaped JSON string."""}
            ])
            
            execution_plan = await self.chat_completion(messages)
            
            # Execute any commands found
            results = []
            for line in execution_plan.split('\n'):
                if line.startswith('EXECUTE:'):
                    command_line = line[8:].strip()
                    self.logger.info(f"Processing command: {command_line}", extra_data={"raw_command": command_line})
                    
                    # Split only on the first space to preserve the rest
                    parts = command_line.split(' ', 1)
                    if len(parts) != 2:
                        error_msg = f"Invalid command format: {command_line}"
                        self.logger.error(error_msg)
                        results.append(error_msg)
                        continue
                        
                    command = parts[0]
                    params_str = parts[1]
                    
                    # Extract parameter name and value
                    if '=' not in params_str:
                        error_msg = f"Invalid parameter format: {params_str}"
                        self.logger.error(error_msg)
                        results.append(error_msg)
                        continue
                        
                    param_name, param_value = params_str.split('=', 1)
                    
                    try:
                        # For db_query, ensure the query is valid JSON
                        if command == 'db_query':
                            try:
                                query_json = json.loads(param_value)
                                # Always add a reasonable limit to database queries
                                if 'limit' not in query_json:
                                    query_json['limit'] = 10
                                self.logger.info("Executing db_query", extra_data={"query": query_json})
                                result = await self.execute_command(command, query=json.dumps(query_json))
                            except json.JSONDecodeError as e:
                                error_msg = f"Invalid query format: {str(e)}"
                                self.logger.error(error_msg, extra_data={"raw_query": param_value})
                                result = error_msg
                        else:
                            # For other commands, pass the parameter as is
                            self.logger.info(f"Executing {command}", extra_data={param_name: param_value})
                            result = await self.execute_command(command, **{param_name: param_value})
                            
                        # Truncate large results
                        result = self._truncate_result(str(result))
                        self.logger.info(f"Command result", extra_data={"command": command, "result": result})
                        results.append(result)
                    except Exception as e:
                        error_msg = f"Error executing {command}: {str(e)}"
                        self.logger.error(error_msg, extra_data={"error": str(e), "command": command})
                        results.append(error_msg)
                        
            # Get AI to summarize the results
            if results:
                summary_messages = [
                    {"role": "system", "content": "Summarize these command results in a clear and helpful way:"},
                    {"role": "user", "content": "\n".join(str(r) for r in results)}
                ]
                return await self.chat_completion(summary_messages)
            else:
                # Check if the execution plan contains any EXECUTE commands
                if 'EXECUTE:' not in execution_plan:
                    # If no commands were intended, just return the AI's response
                    return execution_plan
                else:
                    error_msg = "No valid commands were found in the execution plan"
                    self.logger.error(error_msg, extra_data={"execution_plan": execution_plan})
                    return error_msg

        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.logger.error(error_msg, extra_data={"error": str(e), "message": message})
            return error_msg 