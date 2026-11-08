#!/usr/bin/env python3
"""Linux regression tests for the actual Bash signing/packaging entry points.

Run with: python3 -m unittest discover -s platforms/macos/tests -p '*_test.py' -v
The command doubles model tool outcomes, not Apple's signature validation. No
host build tools, Qt installation, macOS utilities, or real HOME are touched.
"""

import json
import os
from pathlib import Path
import plistlib
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
import plistlib
import sys
from xml.parsers.expat import ExpatError

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

if (tool == "codesign" and phase == "sign"
        and os.environ.get("TEST_REJECT_DIRECT_CFEXEC") == "1"
        and args[-1] in json.loads(os.environ.get("TEST_CFEXEC", "[]"))):
    print("direct CFBundleExecutable signing rejected: " + args[-1], file=sys.stderr)
    sys.exit(80)

if tool in ("plutil", "PlistBuddy"):
    expected = ["-lint"] if tool == "plutil" else ["-c", "Print :CFBundleExecutable"]
    if args[:-1] != expected:
        print("unexpected plist command: " + repr(args), file=sys.stderr)
        sys.exit(81)
    try:
        with open(args[-1], "rb") as source:
            metadata = plistlib.load(source)
    except (ValueError, OSError, plistlib.InvalidFileException, ExpatError) as error:
        print("invalid plist: " + str(error), file=sys.stderr)
        sys.exit(1)
    if tool == "PlistBuddy":
        if "CFBundleExecutable" not in metadata:
            sys.exit(1)
        print(metadata["CFBundleExecutable"])
elif tool == "file":
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
            TEST_REJECT_DIRECT_CFEXEC="1",
            TEST_CFEXEC="[]",
        )
        for name in ("file", "codesign", "cmake", "make", "sysctl", "macdeployqt",
                     "fix_dylib_deps.sh", "create-dmg", "plutil", "PlistBuddy"):
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
            "Contents/MacOS/qlcplus-launcher",
            "Contents/MacOS/qlcplus",
            "Contents/MacOS/qlcplus-fixtureeditor",
            "Contents/Frameworks/lib sound.1.dylib",
            "Contents/PlugIns/platforms/libqcocoa.dylib",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Test Kit",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Helpers/Worker.app/Contents/MacOS/worker",
            "Contents/XPCServices/Service.xpc/Contents/MacOS/service",
            "Contents/PlugIns/Extension.appex/Contents/MacOS/extension",
            "Contents/PlugIns/Code.bundle/Contents/MacOS/plugin",
            "Contents/PlugIns/Raw Plugin.bundle/rawplugin",
        ]
        self.containers = [
            "Contents/Frameworks/Test Kit.framework",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Helpers/Worker.app",
            "Contents/XPCServices/Service.xpc",
            "Contents/PlugIns/Extension.appex",
            "Contents/PlugIns/Code.bundle",
            "Contents/PlugIns/Raw Plugin.bundle",
        ]
        for relative in self.machos:
            self.write(relative, "MACHO fixture\n")
        self.resources = [
            "Contents/Resources/read me.txt",
            "Contents/Resources/Styles.bundle/theme.css",
            "Contents/MacOS/not-a-mach-o",
        ]
        for relative in self.resources:
            self.write(relative)
        (self.app / self.resources[-1]).chmod(0o755)
        self.entrypoints = [self.machos[i] for i in (0, 5, 6, 7, 8, 9)]
        self.plists = {
            "Contents/Info.plist": "qlcplus-launcher",
            "Contents/Frameworks/Test Kit.framework/Versions/A/Resources/Info.plist": "Test Kit",
            self.containers[1] + "/Contents/Info.plist": "worker",
            self.containers[2] + "/Contents/Info.plist": "service",
            self.containers[3] + "/Contents/Info.plist": "extension",
            self.containers[4] + "/Contents/Info.plist": "plugin",
            self.containers[5] + "/Info.plist": None,
            "Contents/Resources/Styles.bundle/Info.plist": None,
        }
        for relative, executable in self.plists.items():
            metadata = {"CFBundleIdentifier": "org.qlcplus.test"}
            if executable is not None:
                metadata["CFBundleExecutable"] = executable
            self.write(relative, plistlib.dumps(metadata).decode())
        self.resources.extend(self.plists)
        self.env["TEST_CFEXEC"] = json.dumps([str(self.app / p) for p in self.entrypoints])
        framework = self.app / self.containers[0]
        (framework / "Versions/Current").symlink_to("A", target_is_directory=True)
        (framework / "Test Kit").symlink_to("Versions/Current/Test Kit")
        (framework / "Resources").symlink_to("Versions/Current/Resources", target_is_directory=True)
        (self.app / "Contents/MacOS/launcher alias").symlink_to("qlcplus-launcher")
        (self.app / "Contents/Frameworks/framework alias").symlink_to(
            "Test Kit.framework", target_is_directory=True)

    def test_ad_hoc_signs_only_real_code_inside_out_and_verifies(self):
        # A different working directory also exercises helper-relative defaults.
        result = self.run_script(HELPER, str(self.app) + "/")
        self.assert_success(result)
        signed = self.calls_for("codesign", "sign")
        targets = [c["args"][-1] for c in signed]
        expected = [str(self.app / p) for p in self.machos + self.containers
                    if p not in self.entrypoints]
        expected.append(str(self.app))
        self.assertCountEqual(targets, expected)
        self.assertEqual(targets[-1], str(self.app))
        for entrypoint in self.entrypoints:
            self.assertNotIn(str(self.app / entrypoint), targets)
        for tool in ("plutil", "PlistBuddy"):
            metadata_calls = self.calls_for(tool)
            self.assertCountEqual([c["args"][-1] for c in metadata_calls],
                                  [str(self.app / p) for p in self.plists])
            self.assertTrue(all(self.calls.index(c) < self.calls.index(signed[0])
                                for c in metadata_calls))
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

    def test_malformed_bundle_metadata_fails_before_any_signing(self):
        for relative in ("Contents/Info.plist",
                         "Contents/Frameworks/Test Kit.framework/Versions/A/Resources/Info.plist",
                         "Contents/Resources/Styles.bundle/Info.plist"):
            with self.subTest(plist=relative):
                path = self.app / relative
                original = path.read_bytes()
                try:
                    path.write_text("<plist><dict>malformed")
                    result = self.run_script(HELPER, self.app)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("invalid plist", result.stderr)
                    self.assertFalse(self.calls_for("codesign"))
                finally:
                    path.write_bytes(original)


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
            "Contents/MacOS/qlcplus-launcher": "MACHO launcher\n",
            "Contents/MacOS/qlcplus": "MACHO main\n",
            "Contents/MacOS/qlcplus-fixtureeditor": "MACHO editor\n",
            "Contents/Frameworks/libsndfile.1.dylib": "MACHO dependency\n",
            "Contents/Info.plist": plistlib.dumps({"CFBundleExecutable": "qlcplus-launcher"}).decode(),
        }
        self.env.update(HOME=str(self.home), QTDIR=str(qt), TEST_APP=str(self.app),
                        TEST_INSTALL=json.dumps(self.install),
                        TEST_CFEXEC=json.dumps([str(self.app / "Contents/MacOS/qlcplus-launcher")]))

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
                                       if p not in ("Contents/Info.plist", "Contents/MacOS/qlcplus-launcher")]
                                      + [str(self.app)])
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
        del install["Contents/MacOS/qlcplus-launcher"]
        del install["Contents/MacOS/qlcplus"]
        del install["Contents/MacOS/qlcplus-fixtureeditor"]
        install["Contents/MacOS/qlcplus-qml"] = "MACHO qml\n"
        install["Contents/Info.plist"] = plistlib.dumps({"CFBundleExecutable": "qlcplus-qml"}).decode()
        result = self.package("qmlui", overrides={
            "TEST_INSTALL": json.dumps(install),
            "TEST_CFEXEC": json.dumps([str(self.app / "Contents/MacOS/qlcplus-qml")]),
        })
        self.assert_success(result)
        self.assertEqual(self.calls_for("macdeployqt")[0]["args"],
                         [str(self.app), "-qmldir=qmlui/qml"])
        signs = self.calls_for("codesign", "sign")
        self.assertTrue(signs)
        for call in signs:
            self.assertEqual(call["unpruned"], [])
        self.assertTrue((self.app / "Contents/Resources/qml/QtQuick/KeepMe/qmldir").is_file())
        self.assertEqual(len(self.calls_for("create-dmg")), 1)

    def test_malformed_installed_metadata_prevents_signing_and_dmg(self):
        install = dict(self.install)
        install["Contents/Info.plist"] = "<plist><dict>malformed"
        result = self.package(overrides={"TEST_INSTALL": json.dumps(install)})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid plist", result.stderr)
        self.assertEqual(len(self.calls_for("macdeployqt")), 1)
        self.assertFalse(self.calls_for("codesign"))
        self.assertFalse(self.calls_for("create-dmg"))

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
