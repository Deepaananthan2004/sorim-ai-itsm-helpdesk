from backend.app.knowledge import KnowledgeService
from backend.app.storage import get_store
if __name__=="__main__":
    print("Knowledge ingestion:",KnowledgeService().ingest_directory())
    print("Storage:",getattr(get_store(),"base","MongoDB Atlas"))
