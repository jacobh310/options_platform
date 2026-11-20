import os
import tempfile

# Must be set before `app` is imported anywhere: the engine is created at import time.
_tmp = tempfile.mkdtemp(prefix="options_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
