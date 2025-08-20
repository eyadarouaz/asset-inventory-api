from minio import Minio
from django.conf import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False
)

def upload_to_minio(bucket_name, file_path, object_name):
    # Create bucket if it doesn't exist
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    # Upload
    minio_client.fput_object(bucket_name, object_name, file_path)
    return f"{bucket_name}/{object_name}"

def get_file_from_minio(bucket_name, object_name):
    response = minio_client.get_object(bucket_name, object_name)
    return response.read().decode("utf-8")