from src.actions.base import BaseAction, ActionSpec
from src.backend.database import DBSessionMixin
from src.util.logging import Logger
from src.models.base import Asset
from sqlalchemy import update

class DeleteEmbeddingsAction(BaseAction, DBSessionMixin):
    """Action to delete all embeddings"""
    
    spec = ActionSpec(
        name="delete_embeddings",
        description="Delete all embeddings from assets",
        arguments=[]
    )
    
    def __init__(self):
        super().__init__()
        DBSessionMixin.__init__(self)
        self.logger = Logger("DeleteEmbeddings")
    
    async def execute(self) -> str:
        """Execute the embedding deletion"""
        try:
            with self.get_session() as session:
                # Count assets with embeddings
                count = session.query(Asset).filter(Asset.embedding.isnot(None)).count()
                
                if count == 0:
                    return "No embeddings found in database."
                
                # Update all assets to set embedding to NULL
                stmt = update(Asset).values(embedding=None)
                session.execute(stmt)
                session.commit()
                
                return f"Successfully deleted embeddings from {count} assets."
                
        except Exception as e:
            self.logger.error(f"Failed to delete embeddings: {str(e)}")
            raise 