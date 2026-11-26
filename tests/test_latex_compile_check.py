"""latex_compile_check.py 回归：源集哈希判重语义（无需真实 LaTeX 环境）。"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "skills" / "latex-guard" / "scripts" / "latex_compile_check.py"

sys.path.insert(0, str(TOOL.parent))
import latex_compile_check as lcc  # noqa: E402


class HashSemanticsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tex = Path(self._tmp.name) / "tex"
        self.build = Path(self._tmp.name) / "build"
        self.tex.mkdir()
        self.build.mkdir()
        (self.tex / "main.tex").write_text(
            "\\documentclass{ctexart}\n\\begin{document}\nHello\n\\end{document}\n", encoding="utf-8")
        (self.tex / "ref.bib").write_text('@book{k, title={T}}\n', encoding="utf-8")
        (self.tex / "sections").mkdir()
        (self.tex / "sections" / "s1.tex").write_text("Chapter one.\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _hash(self):
        return lcc.compute_source_hash(self.tex)

    def _stamp(self, source_hash: str, pdf_name: str = "main.pdf"):
        (self.build / lcc.STAMP_NAME).write_text(
            json.dumps({"source_sha256": source_hash, "pdf": pdf_name}), encoding="utf-8")

    def test_fresh_dir_needs_recompile(self):
        needed, info = lcc.needs_recompile(self.tex, self.build, self._hash())
        self.assertTrue(needed)
        self.assertEqual(info["reason"], "hash_mismatch_or_no_stamp")

    def test_unchanged_skips_recompile(self):
        h = self._hash()
        # 先落最新源时间，再写 PDF，保证 PDF mtime 严格晚于全部源
        (self.tex / "sections" / "s1.tex").write_text("Chapter one.\n", encoding="utf-8")
        time.sleep(0.01)
        pdf = self.build / "main.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        self._stamp(h, "main.pdf")
        needed, info = lcc.needs_recompile(self.tex, self.build, self._hash())
        self.assertFalse(needed, f"源未变应跳过重编译: {info}")

    def test_source_change_triggers_recompile(self):
        h = self._hash()
        (self.tex / "main.tex").write_text(
            "\\documentclass{ctexart}\n\\begin{document}\nHello world!\\end{document}\n",
            encoding="utf-8")
        self._stamp(h, "main.pdf")
        needed, info = lcc.needs_recompile(self.tex, self.build, self._hash())
        self.assertTrue(needed)
        self.assertEqual(info["reason"], "hash_mismatch_or_no_stamp")

    def test_pdf_missing_triggers_recompile(self):
        self._stamp(self._hash(), "main.pdf")  # stamp 声称有 pdf 但 build 里没有
        needed, info = lcc.needs_recompile(self.tex, self.build, self._hash())
        self.assertTrue(needed)
        self.assertEqual(info["reason"], "pdf_missing")

    def test_pdf_older_than_source_triggers_recompile(self):
        h = self._hash()
        pdf = self.build / "main.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        old = time.time() - 1000
        os_utime = __import__("os").utime
        os_utime(pdf, (old, old))
        (self.tex / "sections" / "s1.tex").write_text("Chapter one.\n", encoding="utf-8")
        os_utime(self.tex / "sections" / "s1.tex", (time.time(), time.time()))
        self._stamp(h, "main.pdf")
        needed, info = lcc.needs_recompile(self.tex, self.build, self._hash())
        self.assertTrue(needed)
        self.assertEqual(info["reason"], "pdf_older_than_sources")

    def test_source_hash_ignores_read_order(self):
        h1 = self._hash()
        # 追加一个与现有内容无关的新文件也应改变哈希？不——新文件加入源集即改变集合。
        (self.tex / "extra.tex").write_text("appendix\n", encoding="utf-8")
        h2 = self._hash()
        self.assertNotEqual(h1, h2, "源集变化必须改变哈希")

    def test_check_cli_prints_decision(self):
        import subprocess
        r = subprocess.run([sys.executable, str(TOOL), "--tex-dir", str(self.tex),
                            "--build-dir", str(self.build), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("NEEDS_RECOMPILE", r.stdout)


if __name__ == "__main__":
    unittest.main()