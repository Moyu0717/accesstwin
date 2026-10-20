import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ACCESSTWIN_MOCK", "1")
# Page tests share one DB with the test process; the per-session sandbox has its own tests.
os.environ.setdefault("ACCESSTWIN_SESSION_SANDBOX", "0")
# Tests never touch the real demo database.
os.environ["ACCESSTWIN_DB"] = str(Path(tempfile.mkdtemp(prefix="accesstwin_test_")) / "test.db")
os.environ["GROQ_API_KEY"] = ""
os.environ["ACCESSTWIN_STATE_DIR"] = str(Path(os.environ["ACCESSTWIN_DB"]).parent)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
