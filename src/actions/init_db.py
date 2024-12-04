from sqlalchemy import text
from src.backend.database import db, Base
from src.util.logging import Logger, LogConfig

class InitDBAction:
    """Initialize the database schema"""
    description = "Initialize database schema"
    
    def __init__(self):
        # Temporarily disable database logging
        LogConfig.set_db_logging(False)
        self.logger = Logger("InitDB")
    
    def execute(self):
        """Create all database tables if not already initialized"""
        try:
            if db.is_initialized():
                LogConfig.set_db_logging(True)
                return
                        
            # Create tables
            Base.metadata.create_all(db.get_engine())
            
            # Create array to vector conversion function
            with db.session() as session:
                session.execute(text('''
                    CREATE OR REPLACE FUNCTION array_to_vector(array double precision[])
                    RETURNS vector
                    AS $$
                    SELECT array::vector
                    $$
                    LANGUAGE SQL
                    IMMUTABLE
                    PARALLEL SAFE;
                '''))
                
                # Create vector similarity search index
                session.execute(text('''
                    CREATE INDEX IF NOT EXISTS asset_embedding_idx 
                    ON assets 
                    USING ivfflat ((embedding::vector) vector_cosine_ops)
                    WITH (lists = 100);
                '''))
                session.commit()
                        
            # Re-enable database logging now that tables exist
            LogConfig.set_db_logging(True)
            
        except Exception as e:
            raise
