#!/usr/bin/env python3
"""Exercise the real dependency helper without Homebrew or Mach-O tools.

cp and chmod are real commands (also when wrapped for failure injection). Mode
bits, rather than os.access(), are checked so these tests also work as root.
"""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "fix_dylib_deps.sh"
STUB = r'''
import json
import os
from pathlib import Path
import subprocess
import sys

tool, args = Path(sys.argv[0]).name, sys.argv[1:]
with open(os.environ["TEST_LOG"], "a") as log:
    log.write(json.dumps([tool, args]) + "\n")
if os.environ.get("TEST_FAIL") == tool + (args[0] if tool == "otool" else ""):
    print("injected failure: " + tool, file=sys.stderr)
    sys.exit(79)
if tool == "brew":
    print(os.environ["TEST_PREFIX"])
elif tool == "otool":
    print(args[1] + ":")
    install_id = os.environ.get("TEST_ID", "")
    if args[0] == "-D":
        if install_id:
            print(install_id)
    else:
        entries = ([install_id] if install_id else []) + json.loads(os.environ["TEST_DEPS"])
        for entry in entries:
            print("\t" + entry + " (compatibility version 1.0.0, current version 2.0.0)")
elif tool in ("cp", "chmod"):
    sys.exit(subprocess.call([os.environ["TEST_REAL_" + tool.upper()], *args]))
'''


class FixDylibDepsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="qlc dylib tests ")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "stub tools"
        self.bin.mkdir()
        self.home = self.root / "temporary home"
        self.frameworks = self.home / "QLC+.app/Contents/Frameworks"
        self.frameworks.mkdir(parents=True)
        self.prefix = self.root / "Homebrew prefix with spaces"
        self.source = self.frameworks / "libsndfile.1.dylib"
        self.source.write_bytes(b"Mach-O fixture\n")
        self.log = self.root / "calls.jsonl"
        self.env = os.environ.copy()
        self.env.update(
            HOME=str(self.home), TEST_PREFIX=str(self.prefix),
            TEST_LOG=str(self.log), TEST_DEPS="[]", TEST_ID="", TEST_FAIL="",
            TEST_REAL_CP=shutil.which("cp"), TEST_REAL_CHMOD=shutil.which("chmod"),
            PATH=str(self.bin) + os.pathsep + self.env.get("PATH", ""),
        )
        for tool in ("brew", "otool", "install_name_tool", "cp", "chmod"):
            path = self.bin / tool
            path.write_text("#!" + sys.executable + "\n" + STUB)
            path.chmod(0o755)

    def library(self, name):
        path = self.prefix / "opt/audio/lib" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"read-only Homebrew library\n")
        path.chmod(0o444)
        return path

    def run_helper(self, dependencies, install_id="", failure=""):
        self.log.unlink(missing_ok=True)
        env = dict(self.env, TEST_DEPS=json.dumps(list(map(str, dependencies))),
                   TEST_ID=str(install_id), TEST_FAIL=failure)
        result = subprocess.run(
            ["bash", str(HELPER), str(self.source)], cwd=self.root, env=env,
            text=True, capture_output=True, timeout=30,
        )
        self.calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return result

    def calls_for(self, name):
        return [args for tool, args in self.calls if tool == name]

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_writable_copy(self, original, content=None):
        copied = self.frameworks / original.name
        self.assertTrue(copied.stat().st_mode & stat.S_IWUSR)
        self.assertEqual(stat.S_IMODE(original.stat().st_mode), 0o444)
        self.assertEqual(copied.read_bytes(), original.read_bytes() if content is None else content)

    def assert_rewrites(self, dependencies):
        self.assertEqual(self.calls_for("install_name_tool"), [
            ["-change", str(dep), "@executable_path/../Frameworks/" + Path(dep).name,
             str(self.source)] for dep in dependencies
        ])

    def test_readonly_ogg_and_vorbis_copies_are_writable_without_changing_homebrew(self):
        dependencies = [self.library("libogg.0.dylib"), self.library("libvorbis.0.dylib")]
        self.assert_success(self.run_helper(dependencies))
        for dep in dependencies:
            self.assert_writable_copy(dep)
        self.assert_rewrites(dependencies)
        self.assertEqual(self.calls_for("otool"), [
            ["-L", str(self.source)], ["-D", str(self.source)],
        ])

    def test_install_id_is_not_copied_or_rewritten(self):
        own_id = self.library(self.source.name)
        dependency = self.library("libogg.0.dylib")
        self.assert_success(self.run_helper([dependency], own_id))
        self.assert_rewrites([dependency])
        copies = self.calls_for("cp")
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0][0], str(dependency))
        self.assertIn(Path(copies[0][1]),
                      (self.frameworks, self.frameworks / dependency.name))
        self.assertEqual(self.calls_for("chmod"), [["u+w", str(self.frameworks / dependency.name)]])
        self.assertEqual(self.source.read_bytes(), b"Mach-O fixture\n")
        self.assertEqual(stat.S_IMODE(own_id.stat().st_mode), 0o444)

    def test_existing_readonly_copy_is_made_writable_not_replaced(self):
        dependency = self.library("libvorbis.0.dylib")
        copied = self.frameworks / dependency.name
        copied.write_bytes(b"existing bundled library\n")
        copied.chmod(0o444)
        self.assert_success(self.run_helper([dependency]))
        self.assert_writable_copy(dependency, b"existing bundled library\n")
        self.assertFalse(self.calls_for("cp"))
        self.assert_rewrites([dependency])

    def test_loader_path_resolves_relative_to_image_and_repairs_existing_copy(self):
        image_dir = self.root / "actual image directory"
        image_dir.mkdir()
        self.source = self.source.rename(image_dir / self.source.name)
        dependency = image_dir / "libogg.0.dylib"
        dependency.write_bytes(b"read-only local sibling\n")
        dependency.chmod(0o444)
        own_id = "@rpath/" + self.source.name
        reference = "@loader_path/" + dependency.name
        for existing in (False, True):
            with self.subTest(existing=existing):
                copied = self.frameworks / dependency.name
                if existing:
                    copied.chmod(0o444)
                self.assert_success(self.run_helper([reference], own_id))
                self.assert_writable_copy(dependency)
                self.assert_rewrites([reference])
                self.assertEqual(bool(self.calls_for("cp")), not existing)

    def test_loader_path_prefers_actual_sibling_over_conflicting_homebrew_sibling(self):
        image_dir = self.root / "actual image directory"
        image_dir.mkdir()
        self.source = self.source.rename(image_dir / self.source.name)
        homebrew_id = self.library(self.source.name)
        homebrew_dependency = self.library("libogg.0.dylib")
        dependency = image_dir / homebrew_dependency.name
        dependency.write_bytes(b"actual image sibling, not Homebrew sibling\n")
        dependency.chmod(0o444)
        reference = "@loader_path/" + dependency.name
        for own_id in ("@rpath/" + self.source.name, str(homebrew_id)):
            with self.subTest(install_id=own_id):
                (self.frameworks / dependency.name).unlink(missing_ok=True)
                self.assert_success(self.run_helper([reference], own_id))
                self.assert_writable_copy(dependency)
                self.assert_rewrites([reference])
                self.assertEqual(homebrew_dependency.read_bytes(), b"read-only Homebrew library\n")
                self.assertEqual(stat.S_IMODE(homebrew_dependency.stat().st_mode), 0o444)
                self.assertEqual(stat.S_IMODE(homebrew_id.stat().st_mode), 0o444)

    def test_external_dependency_symlink_is_materialized_without_changing_homebrew(self):
        dependency = self.library("libvorbis.0.dylib")
        original_bytes = dependency.read_bytes()
        copied = self.frameworks / dependency.name
        copied.symlink_to(dependency)
        self.assert_success(self.run_helper([dependency]))
        self.assertFalse(copied.is_symlink())
        self.assertFalse(copied.samefile(dependency))
        self.assert_writable_copy(dependency)
        self.assertEqual(dependency.read_bytes(), original_bytes)
        self.assert_rewrites([dependency])

    def test_internal_dependency_alias_remains_usable(self):
        dependency = self.library("libvorbis.0.dylib")
        target = self.frameworks / "libvorbis.0.4.9.dylib"
        target.write_bytes(b"existing bundled alias target\n")
        target.chmod(0o444)
        alias = self.frameworks / dependency.name
        alias.symlink_to(target.name)
        self.assert_success(self.run_helper([dependency]))
        # Keeping an internal alias or materializing it are both valid, provided
        # the dependency retains its contents and becomes editable in the bundle.
        self.assertTrue(alias.is_file())
        self.assert_writable_copy(dependency, b"existing bundled alias target\n")
        self.assertEqual(target.read_bytes(), b"existing bundled alias target\n")
        self.assertEqual(dependency.read_bytes(), b"read-only Homebrew library\n")
        self.assert_rewrites([dependency])

    def test_tool_failures_propagate_and_stop_dependency_processing(self):
        dependencies = [self.library("libogg.0.dylib"), self.library("libvorbis.0.dylib")]
        for failure in ("otool-L", "otool-D", "cp", "chmod", "install_name_tool"):
            with self.subTest(failure=failure):
                for dep in dependencies:
                    (self.frameworks / dep.name).unlink(missing_ok=True)
                result = self.run_helper(dependencies, failure=failure)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("injected failure", result.stderr)
                self.assertFalse((self.frameworks / dependencies[1].name).exists())
                for dep in dependencies:
                    self.assertEqual(stat.S_IMODE(dep.stat().st_mode), 0o444)
                if failure != "install_name_tool":
                    self.assertFalse(self.calls_for("install_name_tool"))

    def test_missing_loader_path_dependency_fails(self):
        result = self.run_helper(["@loader_path/missing.dylib"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Resolved path does not exist", result.stderr)
        self.assertFalse(self.calls_for("install_name_tool"))


if __name__ == "__main__":
    unittest.main()
