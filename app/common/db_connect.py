# Database connection for Aurora Serverless RDS and local PostgreSQL
import logging
import os
import boto3
import json
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker, scoped_session

STAGE = os.getenv("STAGE", "local").lower()
AWS_REGION = os.getenv("REGION", "us-east-1")

# Aurora Serverless RDS configuration
if STAGE in ["dev", "prod"]:
    RDS_ENDPOINT = os.getenv("RDS_ENDPOINT")
    if not RDS_ENDPOINT:
        raise RuntimeError("RDS_ENDPOINT must be set")

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_PW = os.getenv("POSTGRES_PASSWORD", "")  # only used for local dev


def get_rds_master_password() -> str:
    """
    Retrieve Aurora Serverless master password from Secrets Manager.
    """
    secrets_client = boto3.client("secretsmanager", region_name=AWS_REGION)
    # Get secret ARN from RDS cluster
    secret_arn = os.getenv("RDS_SECRET_ARN")
    if not secret_arn:
        raise RuntimeError("RDS_SECRET_ARN must be set for RDS connections")

    response = secrets_client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])
    return secret["password"]


def make_base_url() -> str:
    """
    Build connection URL for Aurora Serverless RDS or local PostgreSQL.
    """
    if STAGE == "local":
        # Local development with Docker PostgreSQL
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=POSTGRES_USER,
            password=POSTGRES_PW,
            host="localhost",
            port=5432,
            database=POSTGRES_DB,
        )
        return url.render_as_string(hide_password=False)
    else:
        # Aurora Serverless RDS connection
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=POSTGRES_USER,
            password="",
            host=RDS_ENDPOINT,
            port=5432,
            database=POSTGRES_DB,
        )
        return url.render_as_string(hide_password=False)


def make_connect_args() -> dict:
    """
    For local: use password.
    For dev/prod: use master password from Secrets Manager (same as bastion host).
    """
    if STAGE == "local":
        return {"sslmode": "disable"}
    else:
        password = get_rds_master_password()
        return {"password": password, "sslmode": "require"}


# Build the SQLAlchemy engine and session
_engine = create_engine(
    make_base_url(),
    connect_args=make_connect_args(),
    pool_pre_ping=True,
    future=True,
)


SessionLocal = scoped_session(
    sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
)


# set SQLAlchemy logs to only error
logging.basicConfig()
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
