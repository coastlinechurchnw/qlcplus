#!/usr/bin/env python3
"""Linux regression tests for the actual Bash signing/packaging entry points.

Run with: python3 -m unittest discover -s platforms/macos/tests -p '*_test.py' -v
The command doubles model tool outcomes, not Apple's signature validation. No
host build tools, Qt installation, macOS utilities, or real HOME are touched.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[3]
HELPER = SOURCE / "platforms/macos/sign_bundle.sh"
PRUNED = (
    "QtQuick/Controls/FluentWinUI3",
    "QtQuick/Controls/Imagine",
    "QtQuick/Controls/iOS",
    "QtQuick/Controls/Material",
    "QtQuick/Controls/Universal",
    "QtQuick/Particles",
)

# One stand-alone executable is installed under each stubbed command name. It
# records argv without shell parsing, so spaces and signing flags are tested.
STUB = r'''
import json
import os
from pathlib import Path
import sys

tool = Path(sys.argv[0]).name
args = sys.argv[1:]
app = Path(os.environ["TEST_APP"])
phase = ""
if tool == "codesign":
    phase = "verify" if "--verify" in args else "sign"
elif tool == "make":
    phase = "install" if "install/fast" in args else "build"
entry = {"tool": tool, "args": args, "phase": phase}
if tool == "codesign":
    qml = app / "Contents/Resources/qml"
    entry["unpruned"] = [p for p in json.loads(os.environ["TEST_PRUNED"])
                         if (qml / p).exists()]
with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps(entry) + "\n")
if (os.environ.get("TEST_FAIL_TOOL") == tool
        and os.environ.get("TEST_FAIL_PHASE", phase) == phase
        and (not os.environ.get("TEST_FAIL_TARGET")
             or (args and args[-1] == os.environ["TEST_FAIL_TARGET"]))):
    print("injected failure: " + tool + " " + phase, file=sys.stderr)
    sys.exit(79)

if tool == "file":
    path = Path(args[-1])
    print("Mach-O 64-bit arm64 executable" if path.read_bytes().startswith(b"MACHO")
          else "ASCII text")
elif tool == "sysctl":
    print("2")
elif tool == "make" and phase == "install":
    for relative, content in json.loads(os.environ["TEST_INSTALL"]).items():
        path = app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
elif tool == "macdeployqt":
    # Deployment adds QML modules; signing must observe pruning afterwards.
    qml = app / "Contents/Resources/qml"
    for relative in json.loads(os.environ["TEST_PRUNED"]) + ["QtQuick/KeepMe"]:
        path = qml / relative / "qmldir"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("module fixture\n")
'''


class SigningHarness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="qlc signing tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "stub tools"
        self.bin.mkdir()
        self.log = self.root / "calls.jsonl"
        self.app = self.root / "Application with spaces.app"
        self.env = os.environ.copy()
        # Never inherit a developer's signing identity or Qt installation.
        for name in ("SIGNATURE", "QTDIR"):
            self.env.pop(name, None)
        self.env.update(
            PATH=str(self.bin) + os.pathsep + self.env.get("PATH", ""),
            TEST_APP=str(self.app),
            TEST_LOG=str(self.log),
            TEST_PRUNED=json.dumps(PRUNED),
            TEST_INSTALL="{}",
        )
        for name in ("file", "codesign", "cmake", "make", "sysctl", "macdeployqt",
                     "fix_dylib_deps.sh", "create-dmg"):
            path = self.bin / name
            path.write_text("#!" + sys.executable + "\n" + STUB)
            path.chmod(0o755)

    def write(self, relative, content="resource\n"):
        path = self.app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def run_script(self, script, *args, overrides=None, cwd=None):
        self.log.unlink(missing_ok=True)
        env = self.env.copy()
        env.update(overrides or {})
        result = subprocess.run(
            ["bash", str(script), *map(str, args)],
            cwd=cwd or self.root, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        self.calls = ([json.loads(line) for line in self.log.read_text().splitlines()]
                      if self.log.exists() else [])
        return result

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def calls_for(self, tool, phase=None):
        return [c for c in self.calls if c["tool"] == tool
                and (phase is None or c["phase"] == phase)]


class SignBundleTests(SigningHarness):
    def setUp(self):
        super().setUp()
        self.machos = [
            "Contents/MacOS/qlcplus",
            "Contents/MacOS/qlcplus-main",
            "Contents/MacOS/qlcplus-fixtureeditor",
            "Contents/Frameworks/lib sound.1.dylib",
            "Contents/PlugIns/platforms/libqcocoa.dylib",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Test Kit",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Helpers/Worker.app/Contents/MacOS/worker",
            "Contents/XPCServices/Service.xpc/Contents/MacOS/service",
            "Contents/PlugIns/Extension.appex/Contents/MacOS/extension",
            "Contents/PlugIns/Code.bundle/Contents/MacOS/plugin",
        ]
        self.containers = [
            "Contents/Frameworks/Test Kit.framework",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Helpers/Worker.app",
            "Contents/XPCServices/Service.xpc",
            "Contents/PlugIns/Extension.appex",
            "Contents/PlugIns/Code.bundle",
        ]
        for relative in self.machos:
            self.write(relative, "MACHO fixture\n")
        self.resources = [
            "Contents/Info.plist", "Contents/Resources/read me.txt",
            "Contents/Resources/Styles.bundle/theme.css",
            "Contents/MacOS/not-a-mach-o",
        ]
        for relative in self.resources:
            self.write(relative)
        (self.app / self.resources[-1]).chmod(0o755)
        framework = self.app / self.containers[0]
        (framework / "Versions/Current").symlink_to("A", target_is_directory=True)
        (framework / "Test Kit").symlink_to("Versions/Current/Test Kit")
        (self.app / "Contents/MacOS/launcher alias").symlink_to("qlcplus")
        (self.app / "Contents/Frameworks/framework alias").symlink_to(
            "Test Kit.framework", target_is_directory=True)

    def test_ad_hoc_signs_only_real_code_inside_out_and_verifies(self):
        # A different working directory also exercises helper-relative defaults.
        result = self.run_script(HELPER, str(self.app) + "/")
        self.assert_success(result)
        signed = self.calls_for("codesign", "sign")
        targets = [c["args"][-1] for c in signed]
        expected = [str(self.app / p) for p in self.machos + self.containers]
        expected.append(str(self.app))
        self.assertCountEqual(targets, expected)
        self.assertEqual(targets[-1], str(self.app))
        for container in self.containers:
            enclosing = str(self.app / container)
            for target in targets:
                if target.startswith(enclosing + os.sep):
                    self.assertLess(targets.index(target), targets.index(enclosing))
        for call in signed:
            args = call["args"]
            self.assertEqual(args[args.index("--sign") + 1], "-")
            self.assertIn("--force", args)
            self.assertIn("--timestamp=none", args)
            self.assertNotIn("--timestamp", args)
            self.assertNotIn("--options", args)
            self.assertNotIn("--entitlements", args)
        inspected = [Path(c["args"][-1]) for c in self.calls_for("file")]
        self.assertTrue(all(not path.is_symlink() for path in inspected))
        self.assertCountEqual(inspected, [self.app / p for p in self.machos + self.resources])
        verified = self.calls_for("codesign", "verify")
        self.assertCountEqual([c["args"][-1] for c in verified],
                              [str(self.app / p) for p in self.machos
                               if p.startswith("Contents/MacOS/")] + [str(self.app)])
        for call in verified:
            self.assertIn("--strict", call["args"])
        self.assertEqual(verified[-1]["args"][-1], str(self.app))
        self.assertIn("--deep", verified[-1]["args"])
        code_calls = self.calls_for("codesign")
        self.assertEqual(code_calls[:len(signed)], signed)

    def test_identity_preserves_runtime_and_custom_entitlements(self):
        entitlements = self.root / "custom signing.entitlements"
        entitlements.write_text("<plist/>\n")
        identity = "Developer ID Application: Test Team (123456)"
        result = self.run_script(HELPER, self.app, identity, entitlements)
        self.assert_success(result)
        for call in self.calls_for("codesign", "sign"):
            args = call["args"]
            self.assertEqual(args[args.index("--sign") + 1], identity)
            self.assertIn("--timestamp", args)
            self.assertNotIn("--timestamp=none", args)
            target = args[-1]
            executable_or_app = ("/Contents/MacOS/" in target
                                 or target.endswith((".app", ".xpc", ".appex")))
            if executable_or_app:
                self.assertEqual(args[args.index("--options") + 1], "runtime")
                self.assertEqual(args[args.index("--entitlements") + 1], str(entitlements))
            else:
                self.assertNotIn("--options", args)
                self.assertNotIn("--entitlements", args)

    def test_identity_defaults_to_helper_relative_entitlements(self):
        result = self.run_script(HELPER, self.app, "Test Identity")
        self.assert_success(result)
        args = self.calls_for("codesign", "sign")[-1]["args"]
        self.assertEqual(Path(args[args.index("--entitlements") + 1]),
                         HELPER.with_name("qlcplus.entitlements"))

    def test_signing_and_verification_failures_propagate(self):
        for phase, target in (
            ("sign", str(self.app / self.machos[3])),
            ("sign", str(self.app / self.containers[0])),
            ("sign", str(self.app / self.containers[1])),
            ("sign", str(self.app)),
            ("verify", str(self.app / self.machos[0])),
            ("verify", str(self.app)),
        ):
            with self.subTest(phase=phase, target=target):
                result = self.run_script(HELPER, self.app, overrides={
                    "TEST_FAIL_TOOL": "codesign", "TEST_FAIL_PHASE": phase,
                    "TEST_FAIL_TARGET": target,
                })
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("injected failure", result.stderr)
                self.assertEqual(self.calls_for("codesign")[-1]["args"][-1], target)
                self.assertEqual(self.calls_for("codesign")[-1]["phase"], phase)
                if phase == "sign":
                    self.assertFalse(self.calls_for("codesign", "verify"))

    def test_missing_inputs_fail_before_signing(self):
        for args in ((), (self.root / "Missing.app",),
                     (self.app, "-", self.root / "missing.entitlements")):
            with self.subTest(args=args):
                result = self.run_script(HELPER, *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.calls_for("codesign"))


class CreateDmgTests(SigningHarness):
    def setUp(self):
        super().setUp()
        self.checkout = self.root / "minimal checkout"
        macos = self.checkout / "platforms/macos"
        (macos / "dmg").mkdir(parents=True)
        (self.checkout / "engine/src").mkdir(parents=True)
        (self.checkout / "engine/src/qlcconfig.h").write_text('#define APPVERSION "5.0 Test"\n')
        shutil.copy2(SOURCE / "create-dmg.sh", self.checkout / "create-dmg.sh")
        shutil.copy2(HELPER, macos / "sign_bundle.sh")
        shutil.copy2(HELPER.with_name("qlcplus.entitlements"), macos / "qlcplus.entitlements")
        shutil.copy2(self.bin / "fix_dylib_deps.sh", macos / "fix_dylib_deps.sh")
        shutil.copy2(self.bin / "create-dmg", macos / "dmg/create-dmg")
        self.home = self.root / "fake home"
        self.home.mkdir()
        self.app = self.home / "QLC+.app"
        qt = self.root / "fake Qt"
        (qt / "bin").mkdir(parents=True)
        shutil.copy2(self.bin / "macdeployqt", qt / "bin/macdeployqt")
        self.install = {
            "Contents/MacOS/qlcplus": "MACHO main\n",
            "Contents/MacOS/qlcplus-fixtureeditor": "MACHO editor\n",
            "Contents/Frameworks/libsndfile.1.dylib": "MACHO dependency\n",
            "Contents/Info.plist": "resource\n",
        }
        self.env.update(HOME=str(self.home), QTDIR=str(qt), TEST_APP=str(self.app),
                        TEST_INSTALL=json.dumps(self.install))

    def package(self, *args, overrides=None):
        return self.run_script(self.checkout / "create-dmg.sh", *args,
                               overrides=overrides, cwd=self.checkout)

    def test_widget_deployment_includes_both_executables_then_signs_before_dmg(self):
        for signature in (None, "-"):
            with self.subTest(signature=signature):
                overrides = {} if signature is None else {"SIGNATURE": signature}
                result = self.package(overrides=overrides)
                self.assert_success(result)
                self.assertIn("Using ad-hoc signing", result.stdout)
                deploy = self.calls_for("macdeployqt")
                self.assertEqual(len(deploy), 1)
                self.assertEqual(deploy[0]["args"], [
                    str(self.app),
                    "-executable=" + str(self.app / "Contents/MacOS/qlcplus"),
                    "-executable=" + str(self.app / "Contents/MacOS/qlcplus-fixtureeditor"),
                ])
                signs = self.calls_for("codesign", "sign")
                # Exact targets also exclude a separate DMG signing request,
                # including when SIGNATURE is the nonempty ad-hoc identity.
                self.assertCountEqual([c["args"][-1] for c in signs],
                                      [str(self.app / p) for p in self.install
                                       if p != "Contents/Info.plist"] + [str(self.app)])
                for call in signs:
                    args = call["args"]
                    self.assertEqual(args[args.index("--sign") + 1], "-")
                    self.assertIn("--timestamp=none", args)
                    self.assertNotIn("--timestamp", args)
                    self.assertNotIn("--options", args)
                self.assertEqual(signs[-1]["args"][-1], str(self.app))
                dmg = self.calls_for("create-dmg")
                self.assertEqual(len(dmg), 1)
                self.assertLess(self.calls.index(deploy[0]), self.calls.index(signs[0]))
                self.assertLess(self.calls.index(self.calls_for("codesign", "verify")[-1]),
                                self.calls.index(dmg[0]))

    def test_qml_pruning_precedes_real_signing_helper(self):
        install = dict(self.install)
        del install["Contents/MacOS/qlcplus"]
        del install["Contents/MacOS/qlcplus-fixtureeditor"]
        install["Contents/MacOS/qlcplus-qml"] = "MACHO qml\n"
        result = self.package("qmlui", overrides={"TEST_INSTALL": json.dumps(install)})
        self.assert_success(result)
        self.assertEqual(self.calls_for("macdeployqt")[0]["args"],
                         [str(self.app), "-qmldir=qmlui/qml"])
        signs = self.calls_for("codesign", "sign")
        self.assertTrue(signs)
        for call in signs:
            self.assertEqual(call["unpruned"], [])
        self.assertTrue((self.app / "Contents/Resources/qml/QtQuick/KeepMe/qmldir").is_file())
        self.assertEqual(len(self.calls_for("create-dmg")), 1)

    def test_failed_build_deploy_or_signing_never_creates_dmg(self):
        for tool, phase in (("cmake", ""), ("make", "build"), ("make", "install"),
                            ("macdeployqt", ""), ("codesign", "sign"),
                            ("codesign", "verify")):
            with self.subTest(tool=tool, phase=phase):
                result = self.package(overrides={
                    "TEST_FAIL_TOOL": tool, "TEST_FAIL_PHASE": phase,
                })
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("injected failure", result.stderr)
                self.assertFalse(self.calls_for("create-dmg"))
                if tool in ("cmake", "make", "macdeployqt"):
                    self.assertFalse(self.calls_for("codesign"))


if __name__ == "__main__":
    unittest.main()
