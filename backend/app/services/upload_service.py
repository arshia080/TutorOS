import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.storage import get_storage

# Extension is derived from the allowlisted MIME type, never from the client-supplied
# filename -- that filename is only ever kept as display metadata.
EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


class UploadedFile:
    def __init__(self, storage_key: str, file_name: str, mime_type: str, file_size: int):
        self.storage_key = storage_key
        self.file_name = file_name
        self.mime_type = mime_type
        self.file_size = file_size


async def save_upload(file: UploadFile) -> UploadedFile:
    content_type = file.content_type or ""
    extension = EXTENSION_BY_MIME.get(content_type)
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type or 'unknown'}",
        )

    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large"
        )

    storage_key = f"{uuid.uuid4().hex}{extension}"
    get_storage().save(content, storage_key)

    display_name = (file.filename or storage_key).rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    return UploadedFile(
        storage_key=storage_key, file_name=display_name, mime_type=content_type, file_size=len(content)
    )
