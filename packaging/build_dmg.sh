#!/usr/bin/env bash
# 打包 macOS DMG 安装包：GlobalEagleGEO.app（原生窗口壳 + 完整源码 + 离线 wheel）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/packaging/macos"
VERSION="1.1.0"
DIST="$ROOT/dist"
STAGE="$DIST/dmg_stage"
APP="$STAGE/GlobalEagleGEO.app"
RES="$APP/Contents/Resources"

echo "==> 清理并创建目录结构"
rm -rf "$DIST"
mkdir -p "$APP/Contents/MacOS" "$RES/app" "$RES/wheels"

echo "==> 写入 App Bundle"
cp "$PKG/Info.plist" "$APP/Contents/Info.plist"
cp "$PKG/server.sh" "$RES/server.sh"
chmod 755 "$RES/server.sh"

echo "==> 生成应用图标"
if python3 "$PKG/make_icon.py" >/dev/null 2>&1 && [ -f "$PKG/AppIcon.icns" ]; then
  cp "$PKG/AppIcon.icns" "$RES/AppIcon.icns"
else
  echo "    [warn] 图标生成失败，使用系统默认图标"
fi

echo "==> 编译原生窗口壳（Swift + WKWebView）"
BIN="$APP/Contents/MacOS/GlobalEagleGEO"
SRC="$PKG/native/GlobalEagleGEO.swift"
BUILD="$DIST/native_build"
mkdir -p "$BUILD"
compiled=0
if command -v swiftc >/dev/null 2>&1 && [ -f "$SRC" ]; then
  host_arch="$(uname -m)"
  if swiftc -O -swift-version 5 -target "${host_arch}-apple-macos11.0" \
      -o "$BUILD/GlobalEagleGEO_${host_arch}" "$SRC" >/dev/null 2>&1; then
    if [ "$host_arch" = "arm64" ] && swiftc -O -swift-version 5 -target x86_64-apple-macos11.0 \
        -o "$BUILD/GlobalEagleGEO_x86_64" "$SRC" >/dev/null 2>&1; then
      lipo -create -output "$BUILD/GlobalEagleGEO_universal" \
        "$BUILD/GlobalEagleGEO_arm64" "$BUILD/GlobalEagleGEO_x86_64" >/dev/null 2>&1 \
        && cp "$BUILD/GlobalEagleGEO_universal" "$BIN" && compiled=1
    fi
    if [ "$compiled" -eq 0 ]; then
      cp "$BUILD/GlobalEagleGEO_${host_arch}" "$BIN" && compiled=1
    fi
  fi
fi
if [ "$compiled" -eq 1 ]; then
  chmod 755 "$BIN"
  echo "    [ok] 原生窗口壳已编译"
else
  echo "    [warn] Swift 编译不可用，退化为浏览器版启动器"
  cp "$PKG/GlobalEagleGEO" "$BIN"
  chmod 755 "$BIN"
fi

echo "==> 复制应用源码（backend / frontend / requirements / run.sh / README）"
(cd "$ROOT" && tar --exclude='__pycache__' --exclude='*.pyc' --exclude='backend/data' \
  -cf - backend frontend requirements.txt run.sh README.md) | (cd "$RES/app" && tar -xf -)

echo "==> 下载离线依赖 wheel（失败则退化为首次运行时联网安装）"
if ! python3 -m pip download -r "$ROOT/requirements.txt" -d "$RES/wheels" >/dev/null 2>&1; then
  echo "    [warn] wheel 下载失败，将依赖首次运行时联网安装"
fi

echo "==> 附加 DMG 内容（使用说明 / 停止服务 / Applications 快捷方式）"
cp "$PKG/使用说明.txt" "$STAGE/使用说明.txt"
cp "$PKG/停止服务.command" "$STAGE/停止服务.command"
chmod 755 "$STAGE/停止服务.command"
ln -s /Applications "$STAGE/Applications"

echo "==> 尝试 ad-hoc 签名（失败不影响使用）"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "    [warn] 跳过签名"

echo "==> 生成 DMG"
hdiutil create -volname "Global Eagle GEO" -srcfolder "$STAGE" -ov \
  -format UDZO "$DIST/GlobalEagleGEO-${VERSION}.dmg" >/dev/null

SIZE=$(du -h "$DIST/GlobalEagleGEO-${VERSION}.dmg" | cut -f1 | tr -d ' ')
echo "==> 完成：$DIST/GlobalEagleGEO-${VERSION}.dmg ($SIZE)"
