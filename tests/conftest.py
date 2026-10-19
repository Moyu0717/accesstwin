import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ACCESSTWIN_MOCK", "1")
# Tests never touch the real demo database.
os.environ["ACCESSTWIN_DB"] = str(Path(tempfile.mkdtemp(prefix="accesstwin_test_")) / "test.db")
os.environ["GEMINI_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
