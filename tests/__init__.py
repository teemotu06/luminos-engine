import os


# Force a local SQLite configuration before app modules import DATABASE_URL.
os.environ["DATABASE_URL"] = "sqlite:////tmp/luminos_engine_test_bootstrap.db"
