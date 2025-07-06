# 1) Read environment
import logging
import os
import boto3
from sqlalchemy import create_engine, event
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker, scoped_session

STAGE = os.getenv("STAGE", "local").lower()
AWS_REGION = os.getenv("REGION", "us-east-1")
if STAGE in ["dev", "prod"]:
    DSQL_ARN = os.getenv("DSQL_ENDPOINT")
    if not DSQL_ARN:
        raise RuntimeError("DSQL_ENDPOINT must be set")
    DSQL_ENDPOINT = f"{DSQL_ARN.split('/')[-1]}.dsql.{AWS_REGION}.on.aws"

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_PW = os.getenv("POSTGRES_PASSWORD", "")  # only used for local dev


def make_base_url() -> str:
    """
    Build connection URL for Aurora DSQL or local PostgreSQL.
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
    elif STAGE in ["dev", "prod"]:
        # Aurora DSQL connection - will use IAM authentication
        url = URL.create(
            drivername="postgresql+psycopg2",
            username=POSTGRES_USER,
            password="",
            host=DSQL_ENDPOINT,
            port=5432,
            database=POSTGRES_DB,
        )
        return url.render_as_string(hide_password=False)
    else:
        raise ValueError(f"Unknown STAGE: {STAGE}. Expected 'local', 'dev', or 'prod'.")


def make_connect_args() -> dict:
    """
    For local: use password.
    For dev/prod: use Aurora DSQL IAM authentication.
    """
    if STAGE == "local":
        return {"sslmode": "disable"}
    else:
        dsql = boto3.client("dsql", region_name=AWS_REGION)
        # If you're connecting as the built-in "admin":
        token = dsql.generate_db_connect_admin_auth_token(
            Hostname=DSQL_ENDPOINT,
            Region=AWS_REGION,
        )
        # If you have a custom role instead of "admin", use:
        # token = dsql.generate_db_connect_auth_token(
        #     Hostname=DSQL_ENDPOINT,
        #     DBUser=POSTGRES_USER,
        #     Region=AWS_REGION,
        # )
        return {"password": token, "sslmode": "require"}


# Build the SQLAlchemy engine and session
_engine = create_engine(
    make_base_url(),
    connect_args=make_connect_args(),
    pool_pre_ping=True,
    future=True,
)

# In dev, refresh DSQL IAM token on each new connection
if STAGE == "dev":

    @event.listens_for(_engine, "do_connect")
    def _inject_fresh_token(dialect, conn_rec, cargs, cparams):
        fresh = boto3.client("dsql", region_name=AWS_REGION).generate_db_auth_token(
            DBHostname=f"{DSQL_ENDPOINT.split('/')[-1]}.dsql.{AWS_REGION}.on.aws",
            Port=5432,
            DBUsername=POSTGRES_USER,
            Region=AWS_REGION,
        )
        cparams["password"] = fresh
        return dialect.connect(*cargs, **cparams)


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
