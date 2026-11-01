"""Read-only verification of the two repositories' pinned motor contract."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def Bridge_Verify(consumer: Path) -> dict:
    owner = Path(__file__).resolve().parents[3]
    manifest = json.loads((consumer / "contracts/motor-test-package/v1/PROVENANCE.json")
                          .read_text(encoding="utf-8"))
    rows = []
    for relative, identity in manifest["files"].items():
        owner_bytes = (owner / identity["owner_path"]).read_bytes()
        consumer_bytes = (consumer / relative).read_bytes()
        digest = hashlib.sha256(owner_bytes).hexdigest()
        assert owner_bytes == consumer_bytes, relative
        assert digest == identity["sha256"], relative
        rows.append({"consumer_path": relative, "owner_path": identity["owner_path"],
                     "sha256": digest, "byte_identical": True})
    output = owner / ".work/0.1.0-software-completion-20261101/motor.tdmotor.json"
    golden = owner / "tests/fixtures/motor_test_package/v1/valid_positive.tdmotor.json"
    assert output.read_bytes() == golden.read_bytes()
    checked = subprocess.run([str(consumer / ".venv/Scripts/python.exe"), "-m",
                              "treediagram", "check",
                              ".test-tmp/software-completion-20261101/motor-imported.json"],
                             cwd=consumer, capture_output=True, text=True, check=True)
    validation = json.loads(checked.stdout)
    assert validation["structurally_valid"] and validation["runnable"]
    assert not validation["issues"]
    return {
        "scope": ("Synthetic owner export, exact pinned contract, real consumer CLI validation; "
                  "no hardware evidence"),
        "owner_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=owner,
                                               text=True).strip(),
        "consumer_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=consumer,
                                                  text=True).strip(),
        "contract_owner_commit": manifest["owner_commit"],
        "files": rows,
        "export_matches_existing_golden": True,
        "export_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "consumer_check_command": checked.args,
        "consumer_check_exit": checked.returncode,
        "consumer_check_result": validation,
    }


if __name__ == "__main__":
    report = Bridge_Verify(Path(sys.argv[1]).resolve())
    target = Path(__file__).with_name("bridge-verification.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(report['files'])} exact files, deterministic export, consumer CLI")
