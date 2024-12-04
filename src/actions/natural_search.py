from src.actions.base import BaseAction, ActionSpec, ActionArgument
from src.jobs.natural_search import NaturalSearchJob
import json
from src.util.logging import Logger

class NaturalSearchAction(BaseAction):
    """Action for natural language search across database and files
    
    This action provides a natural language interface to search:
    1. Database metadata (projects, assets)
    2. File contents
    
    Example queries:
    - "List all projects with files that have 'Uniswap' in the filename"
    - "List all projects that have files that contain the keyword 'Redstone'"
    - "Find all files containing 'reentrancy' in project:example"
    """
    
    spec = ActionSpec(
        name="search",
        description="Natural language search across projects and files",
        arguments=[
            ActionArgument(
                name="query",
                description="Natural language search query",
                required=True
            )
        ]
    )
    
    def __init__(self):
        self.logger = Logger("NaturalSearchAction")
        
    async def execute(self, query: str) -> str:
        """Execute the natural language search
        
        Args:
            query: Natural language search query
            
        Returns:
            Human-readable text response
        """
        try:
            # Import JobManager here to avoid circular imports
            from src.jobs.manager import JobManager
            
            # Create and submit search job
            job = NaturalSearchJob()
            job.query = query
            
            job_manager = JobManager()
            job_id = await job_manager.submit_job(job)
            
            # Wait for initial results
            await job.start()
            
            # Format and return results
            if "text" in job.results:
                return f"Search completed (Job ID: {job_id})\n\n{job.results['text']}"
                
            # Format results as text if not already formatted
            text_lines = [f"Search completed (Job ID: {job_id})\n"]
            
            # Add explanation if available
            if "explanation" in job.results:
                text_lines.append(job.results["explanation"])
                text_lines.append("")
                
            # Add results
            if not job.results.get("results"):
                text_lines.append("No results found.")
            else:
                for result in job.results["results"]:
                    if isinstance(result, dict):
                        # Format different result types
                        if "name" in result and "description" in result:
                            text_lines.append(f"Project: {result['name']}")
                            if result.get('description'):
                                text_lines.append(f"Description: {result['description']}")
                        elif "file_path" in result and "matches" in result:
                            text_lines.append(f"File: {result['file_path']}")
                            for match in result["matches"]:
                                text_lines.append(f"  Line {match['line_number']}: {match['line']}")
                        else:
                            text_lines.append(" - " + ", ".join(f"{k}: {v}" for k, v in result.items()))
                    else:
                        text_lines.append(str(result))
                    text_lines.append("")
                    
            # Add metadata
            meta = job.results.get("metadata", {})
            if "total_results" in meta:
                text_lines.append(f"\nTotal results: {meta['total_results']}")
            if "files_searched" in meta:
                text_lines.append(f"Files searched: {meta['files_searched']}")
                
            return "\n".join(text_lines).strip() or "No results found."
            
        except Exception as e:
            self.logger.error(f"Error executing natural search: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}" 