#!/bin/sh
set -u

IMPORT_DIR="/import"
STATE_FILE="/state/imported.txt"

mkdir -p /books /state
touch "$STATE_FILE"

echo "监听 $IMPORT_DIR 中..."

while true; do
  find "$IMPORT_DIR" -type f -name "*.epub" | while read -r f; do
    name=$(basename "$f")
    if grep -qxF "$name" "$STATE_FILE"; then
      continue
    fi
    echo "发现新书: $name"
    if calibredb add --with-library /books "$f" >/dev/null 2>&1; then
      echo "$name" >> "$STATE_FILE"
      echo "导入成功: $name"
    else
      echo "导入失败: $name"
    fi
  done
  sleep 15
done
