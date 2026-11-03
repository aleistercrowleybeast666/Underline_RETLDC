"""Record the exact tracked implementation inputs used for the candidate and check for drift."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
phase = sys.argv[1]
assert phase in ("start", "end")
label = sys.argv[2] if len(sys.argv) > 2 else ""
assert label in ("", "final", "release")
prefix = "source-" + (label + "-" if label else "")
out = here / (prefix + phase + ".json")
assert not out.exists()
paths = subprocess.check_output(
    ["git", "ls-files", "-z", "--", "src", "plugins", "contracts", "tests", "scripts",
     "main.py", "pyproject.toml", "打包.bat"], cwd=root,
).decode("utf8").split("\0")
files = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths if p}
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
record = {"commit": commit, "tracked_files": len(files),
          "implementation_bytes_sha256": files}
if phase == "end":
    first = json.loads((here / (prefix + "start.json")).read_text(encoding="utf8"))
    before = first["implementation_bytes_sha256"]
    record["changed"] = sorted(p for p in before.keys() | files.keys()
                               if before.get(p) != files.get(p))
    assert not record["changed"] and commit == first["commit"]
out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
print(commit, len(files), "files", phase)

