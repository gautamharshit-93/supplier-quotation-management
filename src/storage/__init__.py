"""
Picks the active storage backend based on config.STORAGE_BACKEND, exposing
the same function names either way: save_uploaded_file, save_record,
list_records, delete_all_records.
"""
import config

if config.STORAGE_BACKEND == "azure":
    from .azure_storage import (
        save_uploaded_file,
        save_record,
        list_records,
        delete_all_records,
    )
else:
    from .local_storage import (
        save_uploaded_file,
        save_record,
        list_records,
        delete_all_records,
    )
