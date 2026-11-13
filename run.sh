#!/usr/bin/env bash
# 建 DAG 并反复派发，直到全部完成或超过次数。
# 用法: bash run.sh cases/<slug>
set -uo pipefail
cd "$(dirname "$0")"

CASE="${1:?用法: bash run.sh cases/<slug>}"
MAX="${2:-40}"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

"$PY" build_case.py "$CASE" --dispatch || exit 1

for i in $(seq 1 "$MAX"); do
  done_n=$(hermes kanban list 2>/dev/null | grep -c " done " || true)
  ready_n=$(hermes kanban list 2>/dev/null | grep -cE " (ready|todo) " || true)
  echo "[$i] done=$done_n ready_or_todo=$ready_n"
  if [ "$ready_n" -eq 0 ]; then
    echo "没有待办卡了。检查 out/gate.md 的结论。"
    break
  fi
  hermes kanban dispatch >/dev/null 2>&1 || true
  sleep 20
done

echo
echo "产物目录: $CASE/out/"
ls -1 "$CASE/out/" 2>/dev/null || true
