#!/bin/bash
#VERSION=$(head -1 debian/changelog | sed 's/.*(\(.*\)).*/\1/')
#VERSION=$(grep -m 1 APPVERSION variables.pri | cut -d '=' -f 2 | sed -e 's/^[[:space:]]*//' | tr ' ' _ | tr -d '\r\n')
APP_DIR=~/QLC+.app
BIN_DIR=$APP_DIR/Contents/MacOS
QML_DIR=$APP_DIR/Contents/Resources/qml

if [ "$1" == "qmlui" ]; then
    OPTS="-Dqmlui=on"
fi

# cleanup previous builds
rm -rf "$APP_DIR"
rm *.dmg
rm rw.*

rm -rf build
mkdir build || exit 1
cd build || exit 1

if [ -z "$SIGNATURE" ] || [ "$SIGNATURE" = "-" ]; then
    echo "Using ad-hoc signing for local use. Export SIGNATURE for identity signing."
fi

# Build
if [ -n "$QTDIR" ]; then
    CMAKE_OSX_DEPLOYMENT_TARGET=12.0
    [ -d "$QTDIR/lib/cmake/Qt5Core" ] && CMAKE_OSX_DEPLOYMENT_TARGET=10.13
    cmake -DCMAKE_PREFIX_PATH="$QTDIR/lib/cmake" -DCMAKE_OSX_DEPLOYMENT_TARGET=$CMAKE_OSX_DEPLOYMENT_TARGET $OPTS .. || exit 1
else
    echo "QTDIR not set. Aborting."
    exit 1
fi

NUM_CPUS=`sysctl -n hw.ncpu` || true
if [ -z "$NUM_CPUS" ]; then
    NUM_CPUS=4
fi

if ! make -j$NUM_CPUS; then
    echo Compiler error. Aborting package creation.
    exit 1
fi

# Install to ~/QLC+.app/
if ! make install/fast; then
    echo Installation error. Aborting package creation.
    exit 1
fi

cd .. || exit 1

# Extract VERSION from engine/src/qlcconfig.h
VERSION=$(grep -E '^#define APPVERSION' engine/src/qlcconfig.h | sed -E 's/^#define APPVERSION[[:space:]]+"([^"]+)".*/\1/' | tr ' ' '-')

echo "Fix non-Qt dependencies..."
platforms/macos/fix_dylib_deps.sh "$APP_DIR/Contents/Frameworks/libsndfile.1.dylib" || exit 1
if [ -f "$BIN_DIR/qlcplus" ]; then
    platforms/macos/fix_dylib_deps.sh "$BIN_DIR/qlcplus" || exit 1
    platforms/macos/fix_dylib_deps.sh "$BIN_DIR/qlcplus-fixtureeditor" || exit 1
else
    platforms/macos/fix_dylib_deps.sh "$BIN_DIR/qlcplus-qml" || exit 1
fi

echo "Run macdeployqt..."
if [ "$1" == "qmlui" ]; then
    "$QTDIR/bin/macdeployqt" "$APP_DIR" -qmldir=qmlui/qml || exit 1

    # Remove uneeded QML stuff
    rm -rf "$QML_DIR/QtQuick/Controls/FluentWinUI3" \
        "$QML_DIR/QtQuick/Controls/Imagine" \
        "$QML_DIR/QtQuick/Controls/iOS" \
        "$QML_DIR/QtQuick/Controls/Material" \
        "$QML_DIR/QtQuick/Controls/Universal" \
        "$QML_DIR/QtQuick/Particles" || exit 1
else
    "$QTDIR/bin/macdeployqt" "$APP_DIR" \
        "-executable=$BIN_DIR/qlcplus" \
        "-executable=$BIN_DIR/qlcplus-fixtureeditor" || exit 1
fi

# Sign after every bundle mutation, including QML pruning. The helper also
# covers custom libraries and extra executables macdeployqt may not sign.
echo "Signing and verifying application bundle..."
bash platforms/macos/sign_bundle.sh "$APP_DIR" "${SIGNATURE:--}" || exit 1

# Create Apple Disk iMaGe from ~/QLC+.app/
OUTDIR=$PWD
cd platforms/macos/dmg || exit 1
./create-dmg --volname "Q Light Controller Plus $VERSION" \
    --volicon "$OUTDIR/resources/icons/qlcplus.icns" \
    --background background.png \
    --window-size 400 300 \
    --window-pos 200 100 \
    --icon-size 64 \
    --icon "QLC+" 0 150 \
    --app-drop-link 200 150 \
    "$OUTDIR/QLC+_$VERSION.dmg" \
    "$APP_DIR" || exit 1
cd -

if [ -n "$SIGNATURE" ] && [ "$SIGNATURE" != "-" ]; then
    codesign --sign "$SIGNATURE" --timestamp "$OUTDIR/QLC+_$VERSION.dmg" || exit 1
fi
