import time
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv  # Load environment variables

load_dotenv()

def initialize_qdrant():
    retries = 5
    for _ in range(retries):
        try:
            client = QdrantClient(
                "https://fb8eb5f5-ed8f-46ba-92be-012584859271.eu-west-1-0.aws.cloud.qdrant.io:6333",
                api_key=os.getenv("QDRANT_API_KEY", None),
            )
            client.get_collections()
            return client
        except Exception as e:
            print(f"Retrying connection to Qdrant: {e}")
            time.sleep(2)
    raise Exception("Failed to connect to Qdrant after multiple retries")

qdrant_client = initialize_qdrant()
