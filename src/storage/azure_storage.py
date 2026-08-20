"""
OPTIONAL UPGRADE PATH — not used unless STORAGE_BACKEND=azure in .env.

This mirrors local_storage.py's function signatures exactly (save_uploaded_file,
save_record, list_records, delete_all_records) so storage/__init__.py can pick
whichever backend is configured without any other file needing to change.

To activate:
  1. pip install azure-storage-blob azure-cosmos
  2. Fill in AZURE_STORAGE_CONNECTION_STRING, AZURE_COSMOS_ENDPOINT,
     AZURE_COSMOS_KEY etc. in .env
  3. Set STORAGE_BACKEND=azure in .env

This file is intentionally left as a clear, minimal implementation guide
rather than a fully wired module, since it depends on credentials/resources
this project cannot create or verify on your behalf.
"""
from typing import Dict, List, Optional
import config


def _get_blob_container():
    from azure.storage.blob import BlobServiceClient
    service = BlobServiceClient.from_connection_string(config.AZURE_STORAGE_CONNECTION_STRING)
    container = service.get_container_client(config.AZURE_BLOB_CONTAINER)
    if not container.exists():
        container.create_container()
    return container


def _get_cosmos_container():
    from azure.cosmos import CosmosClient, PartitionKey
    client = CosmosClient(config.AZURE_COSMOS_ENDPOINT, credential=config.AZURE_COSMOS_KEY)
    database = client.create_database_if_not_exists(config.AZURE_COSMOS_DATABASE)
    container = database.create_container_if_not_exists(
        id=config.AZURE_COSMOS_CONTAINER,
        partition_key=PartitionKey(path="/record_type"),
    )
    return container


def save_uploaded_file(file_bytes: bytes, filename: str) -> str:
    container = _get_blob_container()
    blob_client = container.get_blob_client(filename)
    blob_client.upload_blob(file_bytes, overwrite=True)
    return blob_client.url


def save_record(record: Dict) -> Dict:
    import uuid
    from datetime import datetime, timezone
    container = _get_cosmos_container()
    record = dict(record)
    record.setdefault("id", str(uuid.uuid4()))
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    record.setdefault("record_type", record.get("record_type", "document"))
    container.upsert_item(record)
    return record


def list_records(record_type: Optional[str] = None) -> List[Dict]:
    container = _get_cosmos_container()
    if record_type:
        query = "SELECT * FROM c WHERE c.record_type = @rt"
        params = [{"name": "@rt", "value": record_type}]
        return list(container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
    return list(container.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))


def delete_all_records() -> None:
    container = _get_cosmos_container()
    for item in list(container.query_items(query="SELECT * FROM c", enable_cross_partition_query=True)):
        container.delete_item(item, partition_key=item.get("record_type"))
