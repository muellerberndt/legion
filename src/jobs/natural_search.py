from typing import Dict, Any, Optional
from src.jobs.base import Job, JobType
from src.agents.search_agent import SearchAgent
from src.util.logging import Logger

class NaturalSearchJob(Job):
    """Job for handling natural language search queries
    
    This job uses the SearchAgent to process natural language queries and return
    results from multiple sources (database and file contents).
    
    Example queries:
    - "List all projects with files that have 'Uniswap' in the filename"
    - "List all projects that have files that contain the keyword 'Redstone'"
    - "Find all files containing 'reentrancy' in project:example"
    """
    
    def __init__(self):
        super().__init__(job_type=JobType.AGENT)
        self.logger = Logger("NaturalSearchJob")
        self.query: Optional[str] = None
        self.results: Dict[str, Any] = {}
        
    async def start(self) -> None:
        """Start the natural language search"""
        if not self.query:
            raise ValueError("Search query not set")
            
        try:
            agent = SearchAgent()
            self.results = await agent.process_query(self.query)
            
        except Exception as e:
            self.logger.error(f"Error in natural search: {str(e)}")
            self.results = {
                "error": str(e),
                "query": self.query
            }
            
    async def stop(self) -> None:
        """Stop the job - nothing to do for search"""
        pass