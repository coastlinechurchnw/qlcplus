#!/usr/bin/env python3
"""Run the complete macOS CMake install file on Linux with fake dependencies.

The production CMakeLists and plist templates are copied unchanged to a small
checkout. Only variables.cmake is replaced: no Qt detection, compiler output or
macOS libraries are required. All install() and configure_file() calls are real;
empty framework/plugin fixtures satisfy unrelated installation rules.
"""

import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest


MACOS = Path(__file__).resolve().parents[1]
CMAKE = shutil.which("cmake")
PROJECT = r'''
cmake_minimum_required(VERSION 3.16)
project(plist_regression NONE)
add_subdirectory(platforms/macos)

# Use the framework list evaluated by the actual macOS file, not a second copy
# of its Qt5/Qt6/QML conditional logic.
get_directory_property(frameworks DIRECTORY platforms/macos DEFINITION QT_FRAMEWORK_NAMES)
foreach(framework IN LISTS frameworks)
    file(MAKE_DIRECTORY "$ENV{QTDIR}/lib/${framework}.framework")
endforeach()
'''
VARIABLES = r'''
set(INSTALLROOT "$ENV{HOME}/QLC+.app/Contents")
set(DATADIR Resources)
set(LIBSDIR Frameworks)
set(PLUGINDIR PlugIns)
set(QT_MAJOR_VERSION 6)
set(FFTW3_LIBDIR "$ENV{TEST_SUPPORT_LIBS}")
set(LIBFTDI1_libftdi1_LIBDIR "$ENV{TEST_SUPPORT_LIBS}")
set(LIBUSB1_LIBDIR "$ENV{TEST_SUPPORT_LIBS}")
set(SNDFILE_LIBDIR "$ENV{TEST_SUPPORT_LIBS}")
'''


@unittest.skipUnless(CMAKE, "cmake is required for real configure/install tests")
class PlistInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="qlc plist tests ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.checkout = self.root / "minimal checkout"
        self.macos = self.checkout / "platforms/macos"
        self.macos.mkdir(parents=True)
        for name in ("CMakeLists.txt", "Info.plist", "Info.plist.qmlui", "qt.conf",
                     "qlcplus.entitlements"):
            shutil.copy2(MACOS / name, self.macos / name)
        self.write(self.checkout / "CMakeLists.txt", PROJECT)
        self.write(self.checkout / "variables.cmake", VARIABLES)
        self.write(self.checkout / "resources/icons/qlcplus.icns", "icon fixture")
        self.home = self.root / "temporary home"
        self.home.mkdir()
        self.contents = self.home / "QLC+.app/Contents"
        self.qt = self.root / "Qt installation with spaces"
        for name in (
            "imageformats/libqgif.dylib", "imageformats/libqjpeg.dylib",
            "imageformats/libqsvg.dylib", "multimedia/libdarwinmediaplugin.dylib",
            "multimedia/libffmpegmediaplugin.dylib", "platforms/libqcocoa.dylib",
            "styles/libqmacstyle.dylib", "geometryloaders/libdefaultgeometryloader.dylib",
            "renderers/libopenglrenderer.dylib", "sceneparsers/libassimpsceneimport.dylib",
        ):
            self.write(self.qt / "plugins" / name, "plugin fixture")
        self.support = self.root / "support libraries"
        for name in ("libfftw3.3.dylib", "libftdi1.2.dylib", "libftdi1.2.5.0.dylib",
                     "libusb-1.0.0.dylib", "libsndfile.1.dylib", "libsndfile.1.0.37.dylib"):
            self.write(self.support / name, "library fixture")
        self.build = self.root / "build tree"
        self.generated = self.build / "platforms/macos/Info.plist"
        self.env = dict(os.environ, HOME=str(self.home), QTDIR=str(self.qt),
                        TEST_SUPPORT_LIBS=str(self.support))
        # A caller's staging root must not redirect these real installs.
        self.env.pop("DESTDIR", None)

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def cmake(self, *args):
        result = subprocess.run([CMAKE, *map(str, args)], cwd=self.root,
                                env=self.env, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def check_variant(self, qml):
        template = self.macos / ("Info.plist.qmlui" if qml else "Info.plist")
        originals = {p: p.read_bytes() for p in self.macos.glob("Info.plist*")}
        expected = plistlib.loads(template.read_bytes())
        expected_executable = "qlcplus-qml" if qml else "qlcplus-launcher"
        self.assertEqual(expected["CFBundleExecutable"], expected_executable)
        for version in ("9.8.7", "9.8.8"):
            with self.subTest(version=version):
                self.cmake("-S", self.checkout, "-B", self.build,
                           "-Dqmlui=" + ("ON" if qml else "OFF"),
                           "-DAPPVERSION=" + version)
                # A configured file must exist before installation: merely fixing
                # the installed file afterwards with sed is not sufficient.
                expected["CFBundleShortVersionString"] = version
                self.assertEqual(plistlib.loads(self.generated.read_bytes()), expected)
                if version == "9.8.7":
                    self.assertFalse(self.contents.exists())
                else:
                    # CMake's install up-to-date check has second-level mtime
                    # resolution. Age the prior install rather than sleeping.
                    os.utime(self.contents / "Info.plist", (1, 1))
                self.cmake("--install", self.build)
                installed = self.contents / "Info.plist"
                self.assertEqual(plistlib.loads(installed.read_bytes()), expected)
                self.assertEqual(installed.read_bytes(), self.generated.read_bytes())
                # BSD sed -i/-e accidentally left this extra file in the signed
                # bundle; test the bundle, not CMake source spelling.
                self.assertEqual(sorted(p.name for p in self.contents.glob("Info.plist*")),
                                 ["Info.plist"])
                self.assertEqual({p: p.read_bytes() for p in originals}, originals)

    def test_widget_plist_is_configured_then_installed_without_sed_backup(self):
        self.check_variant(qml=False)

    def test_qml_plist_is_configured_then_installed_without_sed_backup(self):
        self.check_variant(qml=True)

    def test_configure_preserves_dollar_brace_literals(self):
        # Add a probe only to the sandbox template to distinguish @ONLY from
        # unrestricted configure_file substitution, without matching CMake text.
        template = self.macos / "Info.plist"
        data = plistlib.loads(template.read_bytes())
        data["RegressionLiteral"] = "${APPVERSION}"
        template.write_bytes(plistlib.dumps(data))
        self.cmake("-S", self.checkout, "-B", self.build,
                   "-Dqmlui=OFF", "-DAPPVERSION=9.8.7")
        configured = plistlib.loads(self.generated.read_bytes())
        self.assertEqual(configured["CFBundleShortVersionString"], "9.8.7")
        self.assertEqual(configured["RegressionLiteral"], "${APPVERSION}")
        self.cmake("--install", self.build)
        self.assertEqual(plistlib.loads((self.contents / "Info.plist").read_bytes()),
                         configured)


if __name__ == "__main__":
    unittest.main()
