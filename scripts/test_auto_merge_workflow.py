from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
AUTO_MERGE_WORKFLOW = WORKFLOWS / "auto-merge.yml"


class TestAutoMergeWorkflow(unittest.TestCase):
    def test_auto_merge_workflow_is_removed(self) -> None:
        if AUTO_MERGE_WORKFLOW.exists():
            self.fail(".github/workflows/auto-merge.yml should not queue PR merges")

    def test_no_workflow_queues_auto_merge(self) -> None:
        blocked_patterns = (
            "gh pr merge --auto",
            "enable-auto-merge",
            "automerge",
            "auto-merge",
        )

        violations: list[str] = []
        for path in WORKFLOWS.glob("*.yml"):
            workflow = path.read_text().lower()
            violations.extend(
                f"{path.relative_to(ROOT)} contains {pattern}"
                for pattern in blocked_patterns
                if pattern in workflow
            )

        if violations:
            self.fail("Auto-merge workflow references found:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
