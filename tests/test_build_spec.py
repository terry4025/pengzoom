"""pengzoom.spec 가 런타임이 요구하는 데이터 파일을 실제로 동봉하는지 검증한다.

이 검사가 필요한 이유는 브랜치를 합칠 때 조용히 깨지는 조합이 있기 때문이다.
빌드 스펙은 UI 브랜치에서, `boss_debuff_assets/` 는 보스 디버프 브랜치에서 왔다.
둘을 합치면 소스 실행은 멀쩡하고 테스트도 전부 통과하지만, 패키징한 exe 에서는
`assets_root()` 가 빈 폴더를 가리켜 아이콘 템플릿을 못 찾고 감지 기능만 죽는다.

그래서 스펙을 문자열로 검사하지 않고, 선언된 `datas` 를 임시 폴더에 PyInstaller
규칙대로 펼친 뒤 `sys._MEIPASS` 를 그쪽으로 돌려놓고 런타임 로더를 직접 호출한다.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC_PATH = ROOT / "pengzoom.spec"


class _SpecCall:
    """Analysis/PYZ/EXE 호출 인자를 붙잡아 두는 스텁.

    스펙은 `PYZ(a.pure)` 처럼 Analysis 결과의 속성을 다시 꺼내 쓴다. 그 속성이
    무엇인지는 이 검사에서 중요하지 않으므로 자리표시자를 돌려준다.
    """

    def __init__(self, name="spec"):
        self.name = name
        self.args = ()
        self.kwargs = {}

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return f"<{self.name}.{item}>"


def load_spec():
    """pengzoom.spec 을 PyInstaller 없이 실행해 선언 내용을 읽는다."""
    analysis = _SpecCall("Analysis")
    pyz = _SpecCall("PYZ")
    exe = _SpecCall("EXE")
    namespace = {
        "__file__": str(SPEC_PATH),
        "SPECPATH": str(ROOT),
        "Analysis": analysis,
        "PYZ": pyz,
        "EXE": exe,
    }
    exec(compile(SPEC_PATH.read_text(encoding="utf-8"), str(SPEC_PATH), "exec"), namespace)
    return namespace, analysis, exe


def materialize(datas, target: Path):
    """PyInstaller 의 datas 규칙대로 임시 폴더에 펼친다.

    (src_dir, dest_dir) -> dest_dir 아래에 src_dir 의 *내용*이 들어간다.
    (src_file, dest_dir) -> dest_dir 아래에 파일이 들어간다.
    """
    for source, destination in datas:
        source = Path(source)
        dest = target / destination
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest / source.name)


class BuildSpecDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.namespace, self.analysis, self.exe = load_spec()
        self.datas = self.namespace["datas"]

    def test_every_bundled_source_exists(self):
        for source, _ in self.datas:
            self.assertTrue(Path(source).exists(), f"동봉 대상이 없습니다: {source}")

    def test_entry_script_and_icon_are_wired(self):
        self.assertEqual(self.analysis.args[0], ["magnifier.py"])
        self.assertTrue(Path(self.exe.kwargs["icon"]).exists())

    def test_exe_name_tracks_app_version(self):
        version = self.namespace["APP_VERSION"]
        source = (ROOT / "magnifier.py").read_text(encoding="utf-8")
        self.assertIn(f'APP_VERSION = "{version}"', source)
        self.assertIn(version, self.exe.kwargs["name"])

    def test_dev_only_assets_are_not_shipped(self):
        # reference/ 와 samples/ 는 템플릿 제작용 원본이라 감지 경로에서 읽지 않는다.
        # 400KB 넘는 PNG 들이므로 배포본에 들어가면 순수 낭비다.
        destinations = [str(d).replace("\\", "/") for _, d in self.datas]
        for leaked in ("boss_debuff_assets/reference", "boss_debuff_assets/samples"):
            self.assertNotIn(leaked, destinations)
        self.assertNotIn("boss_debuff_assets", destinations,
                         "폴더를 통째로 넣으면 개발용 원본까지 따라 들어갑니다.")

    def test_qt_websocket_backend_is_kept(self):
        # 파티 연동은 QtWebSockets 로 붙는다. PyInstaller 가 정적 분석으로
        # 잡지 못하는 모듈이라 hiddenimports 에서 빠지면 런타임에만 터진다.
        self.assertIn("PyQt6.QtWebSockets", self.namespace["hiddenimports"])

    def test_excludes_do_not_drop_a_used_module(self):
        used = set()
        for path in ROOT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for name in self.namespace["excludes"]:
                if f"import {name}" in text:
                    used.add(name)
        self.assertEqual(used, set(), f"제외 목록에 실제로 쓰는 모듈이 있습니다: {used}")


class FrozenLayoutTests(unittest.TestCase):
    """스펙대로 펼친 폴더에서 런타임 로더가 정말 자원을 찾는지 확인한다."""

    @classmethod
    def setUpClass(cls):
        namespace, _, _ = load_spec()
        cls.bundle = Path(tempfile.mkdtemp(prefix="pengzoom_frozen_"))
        materialize(namespace["datas"], cls.bundle)
        # 사용자 폴더(APPDATA)의 학습 결과가 섞이면 번들 검증이 무의미해진다.
        cls.appdata = Path(tempfile.mkdtemp(prefix="pengzoom_appdata_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.bundle, ignore_errors=True)
        shutil.rmtree(cls.appdata, ignore_errors=True)

    def setUp(self):
        self._saved_meipass = getattr(sys, "_MEIPASS", None)
        self._saved_appdata = os.environ.get("APPDATA")
        sys._MEIPASS = str(self.bundle)
        os.environ["APPDATA"] = str(self.appdata)

    def tearDown(self):
        if self._saved_meipass is None:
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS
        else:
            sys._MEIPASS = self._saved_meipass
        if self._saved_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._saved_appdata

    def test_boss_debuff_icon_templates_are_found(self):
        import boss_debuff_detector as bdd

        self.assertEqual(bdd.assets_root(), self.bundle / "boss_debuff_assets")
        templates = bdd.load_icon_templates()
        self.assertTrue(templates, "번들에 아이콘 템플릿이 없어 감지가 동작하지 않습니다.")

    def test_boss_debuff_banner_icon_is_found(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        self.addCleanup(app.processEvents)
        import boss_debuff_panel

        pixmap = boss_debuff_panel._icon_pixmap(
            __import__("boss_debuff_detector").DEFAULT_DEBUFF_ID, 24)
        self.assertFalse(pixmap.isNull(), "번들 아이콘으로 배너를 그릴 수 없습니다.")

    def test_bundled_timer_profile_loads(self):
        import boss_debuff_detector as bdd

        # load_for() 는 아무것도 못 찾으면 빈 프로파일을 돌려주는데 그것도
        # version 은 PROFILE_VERSION 이다. 버전만 보면 누락을 놓치므로
        # 실제로 씨앗 글리프가 실려 왔는지를 본다.
        profile = bdd.TimerGlyphProfile.load_for()
        self.assertEqual(profile.version, bdd.PROFILE_VERSION)
        self.assertTrue(profile.glyphs, "번들 숫자 프로파일이 동봉되지 않았습니다.")
        self.assertEqual(len(profile.glyphs), len(profile.labels))
        self.assertTrue(profile.suffix_glyphs, "'초' 접미 글리프가 빠졌습니다.")

    def test_bundled_ocr_profile_loads(self):
        import cooldown_ocr

        path = cooldown_ocr._resource_path(f"ocr_profiles/{cooldown_ocr.DEFAULT_PROFILE_ID}.json")
        self.assertTrue(path.exists(), f"번들 OCR 프로파일이 없습니다: {path}")


if __name__ == "__main__":
    unittest.main()
