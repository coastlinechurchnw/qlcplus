#!/bin/bash
# Sign only after deployment, install-name changes and resource pruning are done.
# May also be used to repair an already deployed local bundle.
# Bash 3 treats expansion of an empty array as unset under `set -u`.
set -eo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 <app_bundle> [identity|-] [entitlements]" >&2
    exit 1
fi

APP_DIR=${1%/}
IDENTITY=${2:--}
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ENTITLEMENTS=${3:-$SCRIPT_DIR/qlcplus.entitlements}
if [ ! -d "$APP_DIR/Contents" ] || [ ! -f "$ENTITLEMENTS" ]; then
    echo "Missing bundle Contents directory or entitlements file" >&2
    exit 1
fi

SIGN_ARGS=(--force --sign "$IDENTITY")
APP_ARGS=()
if [ "$IDENTITY" = "-" ]; then
    SIGN_ARGS+=(--timestamp=none)
else
    SIGN_ARGS+=(--timestamp)
    APP_ARGS+=(--options runtime --entitlements "$ENTITLEMENTS")
fi

# Use a manifest rather than a pipeline so traversal/signing errors propagate.
# Do not follow symlinks: framework aliases must not be signed a second time.
MANIFEST=$(mktemp "${TMPDIR:-/tmp}/qlcplus-sign.XXXXXX")
trap 'rm -f "$MANIFEST"' EXIT
# PlistBuddy predates macOS 10.13; unlike plutil's raw extraction it does not
# require a recent macOS. Keep PATH overrides available for packaging tests.
PATH="$PATH:/usr/libexec"
export PATH
if ! command -v PlistBuddy >/dev/null; then
    echo "PlistBuddy is required to identify bundle executables" >&2
    exit 1
fi
BUNDLE_EXECUTABLES=()
find "$APP_DIR/Contents" -type f -name Info.plist -print0 > "$MANIFEST"
while IFS= read -r -d '' plist; do
    case "$plist" in
        *.app/Contents/Info.plist|*.xpc/Contents/Info.plist|\
        *.appex/Contents/Info.plist|*.bundle/Contents/Info.plist)
            executable_dir=${plist%/Info.plist}/MacOS ;;
        *.framework/Resources/Info.plist|*.framework/Versions/*/Resources/Info.plist)
            executable_dir=${plist%/Resources/Info.plist} ;;
        *.bundle/Info.plist|*.xpc/Info.plist|*.appex/Info.plist)
            executable_dir=${plist%/Info.plist} ;;
        *) continue ;;
    esac
    # Malformed metadata is an error; a valid resource-only bundle may omit
    # CFBundleExecutable. Never interpolate plist data into a command string.
    plutil -lint "$plist"
    if ! executable=$(PlistBuddy -c 'Print :CFBundleExecutable' "$plist" 2>/dev/null); then
        continue
    fi
    case "$executable" in
        ''|.|..|*/*)
            echo "Invalid CFBundleExecutable in $plist" >&2
            exit 1 ;;
    esac
    BUNDLE_EXECUTABLES+=("$executable_dir/$executable")
done < "$MANIFEST"

MACHO_FILES=()
find "$APP_DIR/Contents" -type f -print0 > "$MANIFEST"
while IFS= read -r -d '' path; do
    description=$(file -b "$path")
    case "$description" in
        *Mach-O*)
            MACHO_FILES+=("$path")
            # Signing a CFBundleExecutable directly may sign its containing
            # bundle too. Defer it until all that bundle's nested code is signed.
            is_bundle_executable=false
            for executable in "${BUNDLE_EXECUTABLES[@]}"; do
                if [ "$path" = "$executable" ]; then
                    is_bundle_executable=true
                    break
                fi
            done
            if [ "$is_bundle_executable" = true ]; then
                continue
            fi
            case "$path" in
                */Contents/MacOS/*)
                    codesign "${SIGN_ARGS[@]}" "${APP_ARGS[@]}" "$path"
                    ;;
                *) codesign "${SIGN_ARGS[@]}" "$path" ;;
            esac
            ;;
    esac
done < "$MANIFEST"

# Seal nested code containers inside-out, but not resource-only .bundle dirs.
find "$APP_DIR/Contents" -depth -type d \( -name '*.framework' \
    -o -name '*.app' -o -name '*.xpc' -o -name '*.appex' \
    -o -name '*.bundle' \) -print0 > "$MANIFEST"
while IFS= read -r -d '' container; do
    has_code=false
    for path in "${MACHO_FILES[@]}"; do
        case "$path" in "$container"/*) has_code=true; break ;; esac
    done
    if [ "$has_code" = true ]; then
        case "$container" in
            *.app|*.xpc|*.appex)
                codesign "${SIGN_ARGS[@]}" "${APP_ARGS[@]}" "$container"
                ;;
            *) codesign "${SIGN_ARGS[@]}" "$container" ;;
        esac
    fi
done < "$MANIFEST"

# Never modify nested code after sealing the outer application.
codesign "${SIGN_ARGS[@]}" "${APP_ARGS[@]}" "$APP_DIR"
# Check additional executables explicitly, not only CFBundleExecutable.
for path in "${MACHO_FILES[@]}"; do
    case "$path" in
        "$APP_DIR"/Contents/MacOS/*)
            codesign --verify --strict --verbose=2 "$path"
            ;;
    esac
done
codesign --verify --deep --strict --verbose=2 "$APP_DIR"
