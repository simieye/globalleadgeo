#!/usr/bin/env bash
# 打包 macOS DMG 安装包：GlobalEagleGEO.app（内含完整源码 + 离线 wheel）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/packaging/macos"
VERSION="1.0.0"
DIST="$ROOT/dist"
STAGE="$DIST/dmg_stage"
APP="$STAGE/GlobalEagleGEO.app"
RES="$APP/Contents/Resources"

echo "==> 清理并创建目录结构"
rm -rf "$DIST"
mkdir -p "$APP/Contents/MacOS" "$RES/app" "$RES/wheels"

echo "==> 写入 App Bundle"
cp "$PKG/Info.plist" "$APP/Contents/Info.plist"
cp "$PKG/GlobalEagleGEO" "$APP/Contents/MacOS/GlobalEagleGEO"
chmod 755 "$APP/Contents/MacOS/GlobalEagleGEO"

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
