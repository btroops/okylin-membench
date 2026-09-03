#!/usr/bin/env bash
# 构建 membench 的 .deb 软件包（在 openKylin / Debian 系环境上直接运行）。
# 用法:  bash packaging/build_deb.sh [输出目录，默认 dist/]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.1.0-1"
OUT_DIR="${1:-$ROOT/dist}"
STAGE="$(mktemp -d /tmp/membench_deb.XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

PKG_DIR="$STAGE/membench_${VERSION}_all"
mkdir -p "$PKG_DIR/DEBIAN" \
         "$PKG_DIR/usr/bin" \
         "$PKG_DIR/usr/lib/membench" \
         "$PKG_DIR/usr/share/doc/membench"

# 1) 源码与数据
cp -r "$ROOT/membench"          "$PKG_DIR/usr/lib/membench/"
cp -r "$ROOT/cases"             "$PKG_DIR/usr/lib/membench/"
cp -r "$ROOT/agents"            "$PKG_DIR/usr/lib/membench/"
cp -r "$ROOT/examples"          "$PKG_DIR/usr/lib/membench/"
cp -r "$ROOT/tests"             "$PKG_DIR/usr/lib/membench/"
cp    "$ROOT/batch_agents.json" "$PKG_DIR/usr/lib/membench/" 2>/dev/null || true
find "$PKG_DIR/usr/lib/membench" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# 2) CLI 入口
cat > "$PKG_DIR/usr/bin/membench" <<'EOF'
#!/bin/sh
# membench 命令行入口
export PYTHONPATH="/usr/lib/membench${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m membench.cli "$@"
EOF
chmod 755 "$PKG_DIR/usr/bin/membench"

# 3) 控制文件与文档
cp "$ROOT/packaging/control" "$PKG_DIR/DEBIAN/control"
cp "$ROOT/README.md"         "$PKG_DIR/usr/share/doc/membench/"
for f in "$ROOT/docs"/*.md; do
    [ -e "$f" ] && cp "$f" "$PKG_DIR/usr/share/doc/membench/"
done
cat > "$PKG_DIR/usr/share/doc/membench/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: membench
Source: https://gitee.com/openkylin/membench

Files: *
Copyright: 2026 openKylin membench contributors
License: GPL-2.0-or-later
 membench 以 GPL-2.0-or-later 许可发布，服务于 openKylin 社区。
EOF

# 4) 构建
mkdir -p "$OUT_DIR"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$OUT_DIR/membench_${VERSION}_all.deb"
echo "构建完成: $OUT_DIR/membench_${VERSION}_all.deb"
