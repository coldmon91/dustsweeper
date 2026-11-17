import os
import sys
from pathlib import Path

raw = sys.stdin.read()
dest = os.environ.get("FAKE_STDIN_PATH")
if dest:
    Path(dest).write_text(raw)
sys.stdout.write("정체를 규칙으로 확정하지 못했다.\n")
