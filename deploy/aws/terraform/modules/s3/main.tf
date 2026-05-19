resource "aws_s3_bucket" "books" {
  bucket = "bookforge-books-${var.account_id}"
}

resource "aws_s3_bucket_versioning" "books" {
  bucket = aws_s3_bucket.books.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "books" {
  bucket = aws_s3_bucket.books.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "books" {
  bucket                  = aws_s3_bucket.books.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "books" {
  bucket = aws_s3_bucket.books.id

  rule {
    id     = "archive-old-versions"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}
