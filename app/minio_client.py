import os
import logging
from pathlib import Path
from typing import Optional, List
from minio import Minio
from minio.error import S3Error
from django.conf import settings

logger = logging.getLogger(__name__)


def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL
    )


def ensure_bucket_exists(bucket_name: str) -> bool:
    try:
        client = get_minio_client()
        
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created MinIO bucket: {bucket_name}")
        
        return True
        
    except S3Error as e:
        logger.error(f"Error ensuring bucket exists: {e}")
        return False


def upload_to_minio(bucket_name: str, file_path: str, object_name: str) -> str:
    try:
        client = get_minio_client()
        
        # Ensure bucket exists
        ensure_bucket_exists(bucket_name)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Upload file
        client.fput_object(
            bucket_name,
            object_name,
            file_path
        )
        
        logger.info(f"Uploaded {file_path} to {bucket_name}/{object_name} ({file_size} bytes)")
        
        return object_name
        
    except S3Error as e:
        logger.error(f"Error uploading to MinIO: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading to MinIO: {e}")
        raise


def download_from_minio(bucket_name: str, object_name: str, file_path: str) -> str:
    try:
        client = get_minio_client()
        
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Download file
        client.fget_object(
            bucket_name,
            object_name,
            file_path
        )
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Downloaded {bucket_name}/{object_name} to {file_path} ({file_size} bytes)")
        
        return file_path
        
    except S3Error as e:
        logger.error(f"Error downloading from MinIO: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading from MinIO: {e}")
        raise


def list_objects(bucket_name: str, prefix: Optional[str] = None) -> List[str]:
    try:
        client = get_minio_client()
        
        objects = client.list_objects(
            bucket_name,
            prefix=prefix,
            recursive=True
        )
        
        object_names = [obj.object_name for obj in objects]
        
        logger.info(f"Listed {len(object_names)} objects from {bucket_name}")
        
        return object_names
        
    except S3Error as e:
        logger.error(f"Error listing objects from MinIO: {e}")
        return []


def delete_object(bucket_name: str, object_name: str) -> bool:
    try:
        client = get_minio_client()
        
        client.remove_object(bucket_name, object_name)
        
        logger.info(f"Deleted {bucket_name}/{object_name}")
        
        return True
        
    except S3Error as e:
        logger.error(f"Error deleting object from MinIO: {e}")
        return False


def delete_objects(bucket_name: str, object_names: List[str]) -> int:
    try:
        client = get_minio_client()
        
        # Remove objects
        errors = client.remove_objects(
            bucket_name,
            [obj for obj in object_names]
        )
        
        # Count errors
        error_count = sum(1 for _ in errors)
        success_count = len(object_names) - error_count
        
        logger.info(f"Deleted {success_count}/{len(object_names)} objects from {bucket_name}")
        
        return success_count
        
    except S3Error as e:
        logger.error(f"Error deleting objects from MinIO: {e}")
        return 0


def get_object_url(bucket_name: str, object_name: str, expires: int = 3600) -> Optional[str]:
    try:
        client = get_minio_client()
        
        url = client.presigned_get_object(
            bucket_name,
            object_name,
            expires=expires
        )
        
        logger.info(f"Generated presigned URL for {bucket_name}/{object_name}")
        
        return url
        
    except S3Error as e:
        logger.error(f"Error generating presigned URL: {e}")
        return None


def get_object_info(bucket_name: str, object_name: str) -> Optional[dict]:
    try:
        client = get_minio_client()
        
        stat = client.stat_object(bucket_name, object_name)
        
        info = {
            'object_name': stat.object_name,
            'size': stat.size,
            'last_modified': stat.last_modified,
            'etag': stat.etag,
            'content_type': stat.content_type,
        }
        
        return info
        
    except S3Error as e:
        logger.error(f"Error getting object info: {e}")
        return None


def copy_object(
    src_bucket: str,
    src_object: str,
    dst_bucket: str,
    dst_object: str
) -> bool:
    try:
        client = get_minio_client()
        
        from minio.commonconfig import CopySource
        
        client.copy_object(
            dst_bucket,
            dst_object,
            CopySource(src_bucket, src_object)
        )
        
        logger.info(f"Copied {src_bucket}/{src_object} to {dst_bucket}/{dst_object}")
        
        return True
        
    except S3Error as e:
        logger.error(f"Error copying object: {e}")
        return False


def archive_deployment(job_id: int, archive_bucket: str = "terraform-archive") -> bool:
    try:
        source_bucket = "terraform-jobs"
        source_prefix = f"job_{job_id}"
        
        # List all objects for this job
        objects = list_objects(source_bucket, prefix=source_prefix)
        
        if not objects:
            logger.warning(f"No objects found for job {job_id}")
            return False
        
        # Ensure archive bucket exists
        ensure_bucket_exists(archive_bucket)
        
        # Copy each object to archive
        for obj in objects:
            archive_obj = f"archived/{obj}"
            copy_object(source_bucket, obj, archive_bucket, archive_obj)
        
        logger.info(f"Archived {len(objects)} objects for job {job_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error archiving deployment: {e}")
        return False