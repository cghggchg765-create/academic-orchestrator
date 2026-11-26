import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf_render_pages.py"
STATE = ROOT / "shared" / "state-engine" / "state_utils.py"


class PdfRenderPagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mm_pdf_"))
        self.pdf = self.tmp / "fake.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 fake")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, *args):
        return subprocess.run(["python", str(SCRIPT), *args],
                              capture_output=True, text=True)

    def test_fake_engine_writes_manifest_and_pages(self):
        out = self.tmp / "pages"
        r = self.run_script(str(self.pdf), "--out", str(out), "--engine", "fake",
                            "--fake-pages", "4", "--quiet")
        self.assertEqual(r.returncode, 0, r.stderr)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["page_count"], 4)
        self.assertEqual(manifest["engine"], "fake")
        self.assertEqual(len(manifest["pages"]), 4)
        self.assertEqual(manifest["pages"][0]["page"], 1)
        self.assertTrue((out / "page-0001.png").exists())
        self.assertIn("mm-pdf-vision", SCRIPT.read_text(encoding="utf-8") or (ROOT / "skills" / "mm-pdf-vision" / "SKILL.md").read_text(encoding="utf-8"))

    def test_cache_hit_reuses_existing_fake_render(self):
        out = self.tmp / "pages"
        first = self.run_script(str(self.pdf), "--out", str(out), "--engine", "fake",
                                "--fake-pages", "4", "--quiet")
        self.assertEqual(first.returncode, 0, first.stderr)
        image = out / "page-0001.png"
        before = image.stat().st_mtime_ns
        second = self.run_script(str(self.pdf), "--out", str(out), "--engine", "fake",
                                 "--fake-pages", "4")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("RENDER_CACHE_HIT", second.stdout)
        self.assertEqual(image.stat().st_mtime_ns, before)

    def test_cache_invalidates_when_fake_page_count_changes(self):
        out = self.tmp / "pages"
        self.assertEqual(self.run_script(str(self.pdf), "--out", str(out), "--engine", "fake",
                                         "--fake-pages", "2", "--quiet").returncode, 0)
        second = self.run_script(str(self.pdf), "--out", str(out), "--engine", "fake",
                                 "--fake-pages", "3", "--quiet")
        self.assertEqual(second.returncode, 0, second.stderr)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["page_count"], 3)
        self.assertFalse(manifest["cache_hit"])

    def test_missing_pdf_fails(self):
        r = self.run_script(str(self.tmp / "nope.pdf"), "--engine", "fake", "--quiet")
        self.assertEqual(r.returncode, 1)

    def test_skill_has_frontmatter_and_script_reference(self):
        skill = ROOT / "skills" / "mm-pdf-vision" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        # SKILL.md 的 name 使用裸名（插件命名空间由宿主按「插件名:组件名」注册，不写入文件）
        self.assertIn("name: mm-pdf-vision", text)
        self.assertIn("pdf_render_pages.py", text)
        self.assertIn("PENDING", text)


if __name__ == "__main__":
    unittest.main()