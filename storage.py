from __future__ import annotations
import os
import boto3

S3_BUCKET = os.environ.get('AWS_S3_BUCKET')
S3_REGION = os.environ.get('AWS_S3_REGION', 'us-east-1')


def _s3():
    return boto3.client(
        's3',
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    )


def save_upload(file_obj, filename: str, upload_folder: str) -> str:
    """Save an uploaded file. Returns the stored path/key for the DB.

    - S3 active (AWS_S3_BUCKET set): uploads to bucket, returns the S3 key.
    - S3 not configured: saves to local upload_folder, returns the local path.
    """
    if S3_BUCKET:
        key = f"uploads/{filename}"
        _s3().upload_fileobj(file_obj, S3_BUCKET, key)
        return key
    else:
        local_path = os.path.join(upload_folder, filename)
        file_obj.save(local_path)
        return local_path


def presigned_url(stored_path: str, expiry: int = 3600) -> str | None:
    """Return a presigned S3 URL for the stored path, or None if using local storage.

    stored_path is exactly what was returned by save_upload and persisted in the DB.
    """
    if S3_BUCKET:
        # Normalise: if stored_path is a local-style path like "uploads/foo.jpg" it
        # already matches the S3 key we write; pass it through as-is.
        return _s3().generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': stored_path},
            ExpiresIn=expiry,
        )
    return None
