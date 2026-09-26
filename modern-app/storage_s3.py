"""Invoice attachment storage on S3, replacing local disk uploads."""
import boto3

import config

_s3 = boto3.client("s3", region_name=config.AWS_REGION)


def upload_attachment(file_storage, stored_filename):
    _s3.upload_fileobj(file_storage.stream, config.UPLOAD_BUCKET, stored_filename)


def presigned_download_url(stored_filename, original_filename, expires_in=300):
    return _s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": config.UPLOAD_BUCKET,
            "Key": stored_filename,
            "ResponseContentDisposition": f'attachment; filename="{original_filename}"',
        },
        ExpiresIn=expires_in,
    )
