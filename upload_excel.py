import asyncio
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.database import Base, get_db
from api.upload_service import MultiDatabaseUploadService
from api.models import Dataset, Record # Import necessary models

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    file_path = "/Users/dima/Desktop/Лютий_10.xlsx"
    filename = os.path.basename(file_path)
    dataset_name = f"desktop_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    owner = "system_user" # Or a more appropriate user if available

    upload_service = MultiDatabaseUploadService()

    # Manually create a session for the upload service if not using FastAPI Depends
    # For simplicity, we'll use the existing get_db dependency, but in a standalone script
    # you might initialize the engine and session directly.
    db_generator = get_db()
    db = next(db_generator)

    try:
        logger.info(f"Starting upload for file: {file_path}")
        result = await upload_service.process_upload(
            file_path=file_path,
            filename=filename,
            dataset_name=dataset_name,
            owner=owner,
            db=db
        )
        logger.info("Upload process completed.")
        logger.info(f"Result: {result}")
    except Exception as e:
        logger.error(f"An error occurred during upload: {e}", exc_info=True)
    finally:
        db.close() # Ensure the session is closed

if __name__ == "__main__":
    asyncio.run(main())
