# Idempotent Set actions for Virtual Console buttons

## Objective

Make repeated MIDI control messages activate a Virtual Console button without
switching it off, while preserving exclusive selection inside a solo frame.
The target show uses Peach, Peach-Cyan, Peach-Indigo, and Peach-Salmon buttons
controlled by ProPresenter. Mouse, keyboard, and external input must all perform
the same action: **Set function → On** always activates; **Set function → Off**
always stops the assigned function.

## Initial approach

1. Check out `mcallegari/qlcplus` at the `QLC+_4.14.4` release tag on a local
   feature branch. Inspect repository instructions, button/input handling,
   solo-frame behavior, tests, and the supplied show archive.
2. Review the linked discussions and kpr0th implementation for useful context.
   Choose the smallest compatible design, preserving existing behavior by
   default and documenting how the target buttons opt into activation-only
   behavior if configuration is needed.
3. Implement the feature and meaningful regression coverage for repeated
   activation, release messages, and switching between solo-frame buttons.
4. Build and run appropriate tests, review the diff, document show setup and
   verification results, and commit locally without pushing.

## Investigation findings

- Baseline: upstream `QLC+_4.14.4`, commit
  `027e6d4fdb0680ce6fc6f1fd2c6d0eebe1d08c94`; local branch
  `midi-activate-only-buttons`.
- The initial workspace contained only `coastline-show.tar.gz`. The source
  checkout is in `source/`; this plan was written before cloning and then moved
  into the checkout. No repository `AGENTS.md` was found.
- `qlcplus/main-show.qxw` contains the four Toggle buttons in the Color Picker
  solo frame (ID 30, mixing disabled):

  | Button | Widget ID | Scene ID | Input universe / channel |
  | --- | --- | --- | --- |
  | Peach | 47 | 1059 | 1 / 128 |
  | Peach-Cyan | 48 | 1057 | 1 / 129 |
  | Peach-Indigo | 49 | 1058 | 1 / 130 |
  | Peach-Salmon | 50 | 1047 | 1 / 131 |

- These scenes have 25-second fades and are also controlled by the Color Fade
  speed dial. The included ProPresenter profile defines channels 128–131 as
  slider controls. The same inputs also control Loop 1–4 playback sliders;
  this overlap must be accounted for in show verification.
- The show declares MIDI universe 1 but does not embed an input-plugin/profile
  assignment. Device/network setup remains an installation-time configuration.
- The kpr0th release includes value-state behavior (nonzero = on, zero = off),
  cuelist changes, and monitoring-policy changes. Value-state behavior differs
  from the requested latch: MIDI NoteOff must not immediately clear a look.
- The initial implementation explored an external-input-only option. User
  feedback redirected the design to an ordinary button action so mouse,
  keyboard, and external signals share the same behavior. The external-only
  setting was removed before committing.

## Implementation details

- Added **Set function** to the existing **On button press…** action group, with
  an **On / Off** combo enabled when Set is selected. Function association is
  available in both modes; intensity adjustment is available for On.
- Internally the two choices are appended `VCButton::SetOn` / `SetOff` actions.
  This preserves existing action ordinals and reuses the existing copy and XML
  mechanism, without adding a separate setting or an input-specific code path.
  Persistence is `<Action>SetOn</Action>` or `<Action>SetOff</Action>`. Existing
  workspaces keep their original action; new buttons still default to Toggle.
- All input methods use `pressFunction()`. Set On uses the shared startup helper
  only when the button is not Active or its function has a pending stop. It does
  not restart a selected function or its fades/chaser steps on repeated presses.
  Releases have no effect on Set actions; external zero values retain the
  existing feedback refresh.
- Set On participates in function-state monitoring and the existing solo-frame
  exclusion alongside Toggle. Set Off is an unlatched stop command, including
  for functions started elsewhere; it does not claim solo selection or stop its
  attachment in response to an unrelated solo selection.
- Regression investigation exposed a rapid-selection race: solo A → B removes
  A's function ownership immediately, but the button remains Active until its
  asynchronous stop completes. A → B → A before the next timer tick therefore
  needs explicit reactivation rather than an Active-state-only guard.
- Ignore stale running notifications for already stopped functions and
  intermediate stopped notifications during a restart. These checks apply to
  Toggle and Set On: otherwise a cancelled queued Toggle start could clear a
  newer Set On selection in a mixed frame. Valid monitored-function and solo
  notifications keep their existing policy; no engine changes are required.
- The 25-second scene fade-out is handled by faders after the scene's stop,
  rather than keeping the scene function running for 25 seconds. Regression
  tests therefore check real pending-stop/queued-start transitions and ownership
  instead of relying on a long wall-clock sleep.

## Build discoveries

- User installed Qt 6.10.2 development tools and the Linux build/test
  prerequisites. Build directory: `/tmp/opencode/qlcplus-build`.
- Configuration uses Unix Makefiles, Debug, `qmlui=OFF`,
  `QT_DIR=/usr/lib/x86_64-linux-gnu/cmake/Qt6`, and
  `QT_QMAKE_EXECUTABLE=/usr/bin/qmake6`.
- A baseline build defect captured `qmake -query` trailing newlines in generated
  C++ path strings. Added `OUTPUT_STRIP_TRAILING_WHITESPACE` to its three CMake
  queries. This independent three-line build fix is a separate commit from the
  feature and its regression coverage.
- `make -j4 qlcplus vcbutton_test` builds successfully. Initial new XML
  round-trip tests exposed a test setup issue: the existing appearance reader
  needs a device-backed XML reader. The fixture now uses QBuffer.
- Qt translation tools are installed under `/usr/lib/qt6/bin`, which must be on
  PATH. The fixture tool expects `python`; a temporary virtual environment with
  system-site-packages provides that alias and the installed lxml without
  further system changes.
- The standard Linux `check` harness skips UI tests for this headless user;
  run the VCButton and related UI tests explicitly as well.

## Reference notes

- https://forum.qlcplus.org/viewtopic.php?t=10965 — repeated solo-button triggers
  still toggle off the selected button.
- https://www.qlcplus.org/forum/viewtopic.php?f=18&t=11044 — earlier approaches
  and loopback/slider workarounds.
- https://www.qlcplus.org/forum/viewtopic.php?t=16864 — automation use cases and
  reports about the kpr0th build.
- https://github.com/kpr0th/qlcplus/releases/tag/qlcplus-kpr0th-2023-12-31 —
  inspiration only; no release-wide cherry-pick planned. Core value-state change
  is commit `1bbc034b5d936179cd35ab948a3a193b7d1164de`.

## Verification results

### Build and standard checks

```sh
cmake -S /home/captain/projects/qlcplus/source \
  -B /tmp/opencode/qlcplus-build -G "Unix Makefiles" \
  -Dqmlui=OFF -DCMAKE_BUILD_TYPE=Debug \
  -DQT_DIR=/usr/lib/x86_64-linux-gnu/cmake/Qt6 \
  -DQT_QMAKE_EXECUTABLE=/usr/bin/qmake6
python3 -m venv --without-pip --system-site-packages /tmp/opencode/qlcplus-test-env
```

Run from `/tmp/opencode/qlcplus-build`:

```sh
PATH=/tmp/opencode/qlcplus-test-env/bin:/usr/lib/qt6/bin:$PATH make -j4
PATH=/tmp/opencode/qlcplus-test-env/bin:/usr/lib/qt6/bin:$PATH \
  QT_QPA_PLATFORM=offscreen make check
```

- Full application, plugins, and test binaries built successfully.
- `make check`: **passed**; 64 engine/plugin Qt suites, 3,132 passing cases,
  no failures, one expected EFX duplicate-fixture skip.
- Fixture schema: **1,710 definitions valid**; Python fixture tool: **zero
  errors**; fixtures map: **OK**.
- Logs: `/tmp/opencode/qlcplus-full-build.log` and
  `/tmp/opencode/qlcplus-make-check.log`.
- The top-level check script can conceal a nested failure through its final
  `popd`; results above were verified from actual suite output, not just exit
  status. Initial attempts exposed missing PATH entries / python alias, resolved
  by the environment commands above.

### Button regression tests

From `source/ui/test/vcbutton` (existing tests require resource-relative cwd):

```sh
QT_QPA_PLATFORM=offscreen \
  /tmp/opencode/qlcplus-build/ui/test/vcbutton/vcbutton_test -silent
```

**36 passed, 0 failed.** Coverage includes repeated mouse, keyboard and external
presses; queued startup without restart; releases; Set Off for running/monitored
functions; repeated Off without solo side effects; monitoring takeover; normal
and rapid solo reselection with 25-second fade configured; mixed Toggle/Set On
queued selection; shared-attachment restart notifications; uninterrupted fade-in
progress across repeated cues; legacy actions, copy, XML roundtrips, and
properties accept/cancel/enablement.

All **28 UI suites** were also executed explicitly headlessly from their own
build test directories with:

```sh
QT_QPA_PLATFORM=offscreen \
  LD_LIBRARY_PATH=/tmp/opencode/qlcplus-build/engine/src:/tmp/opencode/qlcplus-build/ui/src \
  ./<name>_test
```

That run passed **268 cases, 0 failures, 0 skips**. The final VCButton-only run
above adds the shared-attachment restart case and strengthens fade/visual-state
assertions. Full UI log: `/tmp/opencode/qlcplus-ui-tests.log`.

The built application reports **QLC+ 4.14.4** via `--help`. Independent Sol code
review found no remaining blockers after the mixed-mode lifecycle fix.
`git diff --check` passes.

## Configuring the supplied show

1. Open `main-show.qxw` with this build and enter Design mode.
2. For each of Peach, Peach-Cyan, Peach-Indigo, and Peach-Salmon, open Button
   Properties, select **Set function**, and choose **On**. Keep the current
   function/input assignments and save the workspace. In XML, change just these
   four buttons' `<Action>Toggle</Action>` to `<Action>SetOn</Action>`.
3. Configure universe 1's MIDI input and supplied ProPresenter input profile on
   the installation machine. The action is a normal workspace button action and
   works identically for mouse, keyboard, MIDI, and other external input.
4. In Operate mode, send positive cues repeatedly, then zero/NoteOff: the look
   remains selected. Cue a different color: the old scene stops and the new
   scene starts using the existing solo behavior and configured fades. Test
   quick A → B → A as well as normal song-length spacing.
5. Repeat clicks/keyboard presses as well: Set On also stays on with those input
   methods. To explicitly stop a look, use a separate button assigned to that
   function with **Set function → Off**, select another solo look, or use the
   existing Stop All control. Zero/release intentionally does not clear it.
6. Check the overlapping Loop 1–4 input mappings during live verification.

Older official builds do not implement SetOn/SetOff and interpret unknown action
strings as Toggle. Use this build when opening/saving the configured workspace.
Live ProPresenter/network/MIDI hardware verification must be performed on the
installation machine; automated tests exercise the same VC input path and
function/solo lifecycle locally.

## Local delivery

Delivery uses two independently scoped commits: the CMake path-output fix
(`f1ce2da80`), then the Set action implementation together with its tests and
this living plan.
All work is on `midi-activate-only-buttons` in
`/home/captain/projects/qlcplus/source`; the built executable is
`/tmp/opencode/qlcplus-build/main/qlcplus`. Commits are local; no push requested.

## Apple Silicon packaging follow-up

### Report and investigation

On the target Mac, the launcher opens but selecting either QLC+ or the Fixture
Definition Editor exits without a visible application. Running either packaged
program directly produces `killed`, while `./build/main/qlcplus` runs normally.
The supplied `build.log` shows successful compilation, installation and DMG
creation, with no explicit deployment error.

The user verified both packaged executables and the build-tree executable with
`codesign --verify --strict --verbose=4`: all are valid on disk. This rules out
the initial hypothesis of invalid signatures on the primary executables. It
does not verify loaded libraries. The subsequently supplied launcher crash
report establishes `EXC_BAD_ACCESS / SIGKILL (Code Signature Invalid)`,
`CODESIGNING`, code 2, `Invalid Page`, while Qt loads platform integration.
It confirms native ARM64 and Qt 6.10.2, but the offending mapped library has no
pathname in the report; neither libogg/libvorbis nor the platform plugin can be
identified as the exact failed image from that report alone.

Source inspection identified concrete packaging omissions:

- The app entry point is the launcher, but `macdeployqt` was not explicitly
  given the two child executables for dependency deployment.
- Final signing was conditional on a certificate identity and did not cover
  local builds explicitly. The certificate branch signed resources as code and
  modified child signatures after sealing the outer app.
- Deployment/signing failures could be followed by DMG creation, and some
  compiler/install failures incorrectly returned success.

### Packaging correction

`create-dmg.sh` now deploys both child executables explicitly and invokes
`platforms/macos/sign_bundle.sh` after dependency rewriting and resource pruning.
The helper signs actual Mach-O files, then nested code containers inside-out,
and seals the outer app last. It checks the extra executables individually and
the complete app with deep/strict verification. Symlinks and plain resources
are not individually signed. Local builds use ad-hoc signing; certificate builds
retain their identity, timestamp and application entitlements. A failed build,
deployment, signing or verification step prevents DMG creation.

The next target build exposed two concrete blockers and an ordering defect:

- BSD `sed -i -e` created `Contents/Info.plist-e`. Signing rejected that unexpected
  bundle subcomponent. CMake now uses `configure_file(... @ONLY)` to generate the
  selected v4/v5 Info.plist in the build tree before installation; no backup is
  created and the source templates remain unchanged.
- Homebrew codec libraries copied with `cp` retained read-only permissions.
  `macdeployqt` reported permission errors while stripping libogg and libvorbis.
  The dependency helper now makes independent bundle copies owner-writable,
  including existing copies. Existing symlink aliases are materialized before
  chmod so their original targets are not modified. It also skips a dylib's own
  install ID, resolves loader-relative paths from the actual image first, and
  propagates dependency-tool errors.
- Signing a bundle's `CFBundleExecutable` directly can inspect the enclosing
  bundle before the remaining nested code is signed. The signing helper now
  reads actual plist metadata, defers these main executables to their container
  signing pass, and still signs additional standalone programs individually.
  This includes versioned Qt frameworks without traversing their aliases.

Warnings that `install_name_tool` invalidates signatures are expected during
deployment mutations; signing must complete afterward. Permission failures and
the `Info.plist-e` rejection are actual blockers, not ignorable warnings.

### Repair and target-machine validation

Copy the updated changes to the Mac checkout; the signing helper uses the
adjacent existing `qlcplus.entitlements`. From the checkout root, repair the
existing user bundle without rebuilding. Remove only the known generated plist
backup, repair the regular bundled dylib permissions, rerun Qt deployment, and
finally sign:

```sh
(
  set -e
  APP="$HOME/QLC+.app"
  rm -f "$APP/Contents/Info.plist-e"
  find "$APP/Contents/Frameworks" -type f -name '*.dylib' -exec chmod u+w {} +
  "$QTDIR/bin/macdeployqt" "$APP" \
    "-executable=$APP/Contents/MacOS/qlcplus" \
    "-executable=$APP/Contents/MacOS/qlcplus-fixtureeditor"
  bash platforms/macos/sign_bundle.sh "$APP"
)
QT_DEBUG_PLUGINS=1 "$HOME/QLC+.app/Contents/MacOS/qlcplus"
```

Then test the Fixture Definition Editor and both launcher choices. Rebuilding
with the updated `create-dmg.sh` also includes the corrected deployment step.
The signing helper repairs signatures, not missing libraries or incorrect load
paths. If the repaired program still gets killed, capture its newest report
under `~/Library/Logs/DiagnosticReports` and inspect the termination reason and
named image before making further deployment changes.

### Verification completed locally

- `bash -n create-dmg.sh platforms/macos/sign_bundle.sh`: passed.
- `bash -n platforms/macos/fix_dylib_deps.sh`: passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s platforms/macos/tests -p '*_test.py' -v`:
  **22 tests passed**: 10 signing/packaging tests, 9 dependency tests, and 3 native
  CMake plist-generation/install tests. These execute the real scripts/CMake
  rules with isolated fixtures and command stubs where Apple tools are needed.
  Coverage includes metadata-aware inside-out signing, standalone executables,
  read-only library copies, symlink materialization, original-file preservation,
  install IDs, loader-relative resolution, version/template substitution,
  space-containing paths, local/certificate modes, QML pruning, and failure
  propagation before DMG creation.
- Independent Sol review found no remaining packaging-code blockers.
- Actual Apple signing acceptance and repaired-bundle launch are still pending
  on the target Mac. Linux-side tests verify orchestration, not macOS runtime
  behavior; the confirmed signature kill is not yet confirmed resolved.
