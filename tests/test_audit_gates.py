"""9.0 评分漏洞防护门禁测试（旧引擎产物 / 未人工确认收尾 / 评审对象非最终产物）。

覆盖：
- H 门禁一致性：N7 completed 但 H3 pending → audit 报违规；auto_passed（合法待追认）不误报；
- 引擎版本遗留：state 中出现 mm-*-writing@旧版本（如 1.3.0 < 当前 1.5.0）→ 标记 legacy，评审结论无效；
- 评审-产物时间线：审阅记录时间早于最终 main.pdf mtime → 评审对象非最终交付物，必须重评；
- 无 PDF / 无审阅记录 → 时间线检查不误报。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"


class AuditGatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_audit_"))
        self.project = self.tmp / "project"
        self.project.mkdir()
        subprocess.run(["python", str(STATE), "init", "--dir", str(self.project), "--name", "Test"],
                       check=True, capture_output=True, text=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def audit(self):
        r = subprocess.run(["python", str(STATE), "project-audit", "--dir", str(self.project)],
                           check=True, capture_output=True, text=True)
        return json.loads(r.stdout)

    def load_state(self):
        with (self.project / "state" / "decision_log.json").open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self, state):
        with (self.project / "state" / "decision_log.json").open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def mark_n7_completed(self, h3_status="pending"):
        state = self.load_state()
        state.setdefault("nodes", {})["N7"] = {"status": "completed"}
        state.setdefault("gates", {})["H3"] = {"status": h3_status}
        self.save_state(state)

    def test_h_gate_pending_on_completed_node_fails_audit(self):
        """N7 completed 但 H3 pending → audit 报'人工确认门禁未过即收尾'。"""
        self.mark_n7_completed("pending")
        report = self.audit()
        hits = [m for m in report["h_gate_consistency"] if m["node"] == "N7" and m["gate"] == "H3"]
        self.assertTrue(hits, f"应命中 N7→H3，实际 {report['h_gate_consistency']}")
        self.assertIn("人工确认门禁未过即收尾", " ".join(report["summary"]["issues"]))

    def test_h_gate_auto_passed_not_reported(self):
        """auto_passed 是合法待追认态（等 h-confirm），completed + auto_passed 不误报。"""
        self.mark_n7_completed("auto_passed")
        report = self.audit()
        self.assertFalse(report["h_gate_consistency"], f"auto_passed 不应报，实际 {report['h_gate_consistency']}")

    def test_engine_legacy_detected(self):
        """state 中出现旧版 skill 记录（mm-latex-writing@1.3.0）→ engine_legacy 命中且评审结论无效。"""
        agent_dir = self.project / "state" / "agents" / "writing"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "result.json").write_text(
            json.dumps({"skills_read": ["mm-latex-writing@1.3.0"]}, ensure_ascii=False),
            encoding="utf-8")
        report = self.audit()
        versions = {m["version"] for m in report["engine_legacy"]}
        self.assertIn("1.3.0", versions, f"应检测到 1.3.0 旧版引擎产物，实际 {report['engine_legacy']}")
        self.assertTrue(any("相关评审结论不可作为有效依据" in m["reason"] for m in report["engine_legacy"]))
        self.assertIn("旧版引擎产物混入", " ".join(report["summary"]["issues"]))

    def test_review_timeline_late_pdf_fails_audit(self):
        """审阅时间早于最终 main.pdf mtime → 评审对象非最终产物，必须重评。"""
        # 写入带旧时间戳（UTC）的审阅记录
        node_dir = self.project / "state" / "nodes" / "论文"
        node_dir.mkdir(parents=True, exist_ok=True)
        (node_dir / "dashboard.md").write_text(
            "| 2020-01-01T00:00:00Z | reviewer | mm-latex-writing | PASS | 终审 |\n", encoding="utf-8")
        # 造一个 mtime 明显晚于 2020 的最终 PDF
        pdf = self.project / "ReportPaper" / "LaTeX" / "build" / "main.pdf"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4 test")
        report = self.audit()
        self.assertTrue(report["review_timeline"], f"应命中时间线违规，实际 {report['review_timeline']}")
        self.assertTrue(any("必须对最终产物重新执行" in m["reason"] for m in report["review_timeline"]))
        self.assertIn("评审对象非最终产物", " ".join(report["summary"]["issues"]))

    def test_review_timeline_no_pdf_no_false_positive(self):
        """无 PDF / 无审阅记录 → 时间线检查不误报。"""
        report = self.audit()
        self.assertEqual(report["review_timeline"], [])

    def test_engine_legacy_no_false_positive(self):
        """干净项目（无旧版本记录）→ engine_legacy 为空。"""
        report = self.audit()
        self.assertEqual(report["engine_legacy"], [])


if __name__ == "__main__":
    unittest.main()
