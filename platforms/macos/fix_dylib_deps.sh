#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <source_dylib>"
    exit 1
fi

HOMEBREW_PREFIX=$(brew --prefix) || exit 1
SRC_DYLIB="$1"
FRAMEWORKS_DIR=~/QLC+.app/Contents/Frameworks

echo "Processing $SRC_DYLIB... (Homebrew at $HOMEBREW_PREFIX)"

# Ensure Frameworks directory exists
mkdir -p "$FRAMEWORKS_DIR" || exit 1

# Only chmod independent bundle files, never a dependency symlink's target.
# Materialize internal aliases too: each dependency keeps its installed name.
copy_dependency()
{
    local source="$1"
    local destination="$FRAMEWORKS_DIR/$2"
    local temporary

    if [ -L "$destination" ]; then
        temporary=$(mktemp "$FRAMEWORKS_DIR/.qlcplus-dylib.XXXXXX") || return 1
        if ! cp -pL "$destination" "$temporary"; then
            rm -f "$temporary"
            return 1
        fi
        if ! mv -f "$temporary" "$destination"; then
            rm -f "$temporary"
            return 1
        fi
    elif [ ! -e "$destination" ]; then
        cp "$source" "$destination" || return 1
    elif [ ! -f "$destination" ]; then
        echo "Error: Dependency destination is not a regular file: $destination" >&2
        return 1
    fi

    # Homebrew libraries can be read-only; only the bundle copy must be editable.
    chmod u+w "$destination" || return 1
}

# Capture tool output separately so a failed otool cannot be hidden by a pipe.
dependencies=$(otool -L "$SRC_DYLIB") || exit 1
install_ids=$(otool -D "$SRC_DYLIB") || exit 1
# Executables have no install ID. A dylib's ID is not a dependency.
dylib_full_path=$(printf '%s\n' "$install_ids" | awk 'NR == 2 {sub(/^[[:space:]]+/, ""); print; exit}')
dylib_dir=$(dirname "$SRC_DYLIB")

echo "Source dylib full path: $dylib_full_path"
echo "Source dylib directory: $dylib_dir"

# Process each dependency reported by otool
while IFS= read -r line; do
    # Dependency entries are indented; ignore file/architecture headers.
    case "$line" in
        [[:space:]]*) ;;
        *) continue ;;
    esac
    dep="${line#"${line%%[![:space:]]*}"}"
    dep="${dep% (compatibility version *}"
    [ -n "$dep" ] || continue
    [ "$dep" != "$dylib_full_path" ] || continue
    subst=$(basename "$dep")

    if [[ "$dep" == "$HOMEBREW_PREFIX/"* ]]; then
        echo "Found Homebrew library: $dep ($subst)"

        copy_dependency "$dep" "$subst" || exit 1

        # Update the source dylib's reference to the dependency
        install_name_tool -change "$dep" "@executable_path/../Frameworks/$subst" "$SRC_DYLIB" || exit 1
    
    elif [[ "$dep" == @loader_path/* ]]; then
        echo "Found @loader_path reference: $dep ($subst)"
        
        # Resolve the actual path based on the source dylib's directory
        resolved_path="$dylib_dir/${dep#@loader_path/}"
        # A copied Homebrew image may still need its original siblings. Only
        # use an absolute Homebrew install ID as a fallback, never @rpath IDs.
        if [ ! -f "$resolved_path" ] && [[ "$dylib_full_path" == "$HOMEBREW_PREFIX/"* ]]; then
            resolved_path="$(dirname "$dylib_full_path")/${dep#@loader_path/}"
        fi

        echo "Resolved path for @loader_path: $resolved_path"

        if [ -f "$resolved_path" ]; then
            copy_dependency "$resolved_path" "$subst" || exit 1

            # Update the source dylib's reference to the dependency
            install_name_tool -change "$dep" "@executable_path/../Frameworks/$subst" "$SRC_DYLIB" || exit 1
        else
            echo "Error: Resolved path does not exist: $resolved_path" >&2
            exit 1
        fi
    fi
done <<< "$dependencies"
