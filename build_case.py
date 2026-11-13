#!/usr/bin/env python3
"""在 Hermes kanban 板上搭出法律申辩的 DAG。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases"

# (stage, role_file, assignee, deps, output, title)
STAGES = [
    ("00", "00_intake.md",         "researcher", [],            "facts.md",           "00 案情事实包"),
    ("10", "10_sources_pro.md",    "researcher", ["00"],        "sources_pro.md",     "10 有利法源检索"),
    ("11", "11_sources_con.md",    "analyst",    ["00"],        "sources_con.md",     "11 不利法源检索（对抗性）"),
    ("12", "12_case_law.md",        "analyst",    ["00"],        "case_law.md",        "12 类案与裁判倾向"),
    ("15", "15_conflict_review.md", "verifier",  ["10", "11"], "conflicts.md",       "15 规范冲突与定义审查"),
    ("16", "16_concept_genealogy.md", "verifier", ["10", "11"], "concepts.md",        "16 沿革与不确定概念"),
    ("20", "20_arguments.md",      "analyst",    ["12", "15", "16"], "arguments.md",  "20 抗辩路径构建"),
    ("30", "30_redteam.md",        "verifier",   ["20"],        "redteam.md",         "30 红队：对方会怎么打"),
    ("40", "40_citation_check.md", "verifier",   ["20", "30"], "citations.md",       "40 引用逐条核验"),
    ("50", "50_draft.md",          "writer",     ["40"],        "陈述申辩意见书.md",  "50 文书成稿"),
    ("60", "60_gate.md",           "verifier",   ["50"],        "gate.md",            "60 提交前检查"),
]

BODY_TAIL = """
## 案件上下文

- 案件目录（绝对路径）：{case}
- 输入材料：{case}/input/ —— 先全部读完再动手
- 已产出：{case}/out/
- 本卡必须落盘：**{out}**

## 完成要求

1. 结论必须写进上面那个文件，不能只写在完成摘要里。
2. 用 kanban_complete 提交时，摘要写明：产出文件绝对路径 + 行数 + 一句话结论。
3. 材料不够就写【待补：xxx】，不许编造事实、不许凭记忆引用法条。

## 上下文与续跑规则（成本约束，必须遵守）

1. **先读摘要**：上游产物同目录下有 `<文件名>.summary.md`（≤200 字结论 + 小节清单）。先只读摘要；
   要细节时按小节标题用 grep 定位、再用 offset/limit 读那一段——**不许整份读上游长文**，>20KB 的尤其禁止。
2. **自己也要写摘要**：本卡落盘 `{out}` 之后，再写 `{out}.summary.md`：≤200 字结论 + 全部 `##` 小节标题（一行一个）。
3. **重试续跑**：若已存在 `{out}.partial.md`，先读它并从断点继续；每写完一节就追加进 partial，全部写完后合并成 `{out}`。
   不要因为一次失败就把整张卡从零重写。
4. **长产物不占上下文**：正文超过 20KB 的内容只写进文件，上下文里只留路径 + 小节列表，不要把全文贴回来复述。
"""


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").replace("\r", ""), (p.stderr or "").replace("\r", "")


def parse_id(stdout):
    try:
        data = json.loads(stdout.strip())
    except json.JSONDecodeError:
        start = stdout.find("{")
        if start < 0:
            return None
        data = json.loads(stdout[start:])
    for key in ("id", "task_id", "taskId"):
        if isinstance(data, dict) and data.get(key):
            return data[key]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", help="cases/<slug>")
    ap.add_argument("--dispatch", action="store_true", help="建完立即派发一次")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不调 hermes")
    args = ap.parse_args()

    case = Path(args.case)
    if not case.is_absolute():
        case = (ROOT / case).resolve()
    if not case.is_dir():
        sys.exit(f"案件目录不存在: {case}")

    meta_path = case / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    title = meta.get("title") or case.name
    slug = case.name

    (case / "out").mkdir(exist_ok=True)
    (case / "input").mkdir(exist_ok=True)
    bodies = case / ".card_bodies"
    bodies.mkdir(exist_ok=True)

    ids = {}
    for stage, role_file, assignee, deps, out, card_title in STAGES:
        body = (ROOT / "roles" / role_file).read_text(encoding="utf-8")
        body += BODY_TAIL.format(case=case.as_posix(), out=out)
        body_path = bodies / f"{stage}.md"
        body_path.write_text(body, encoding="utf-8")

        cmd = [
            "hermes", "kanban", "create",
            f"[{slug}] {card_title}",
            "--assignee", assignee,
            "--workspace", f"dir:{case.as_posix()}",
            "--body-file", body_path.as_posix(),
            "--idempotency-key", f"{slug}-{stage}",
            "--json",
        ]
        for d in deps:
            if d in ids:
                cmd += ["--parent", ids[d]]

        if args.dry_run:
            print(f"  {stage}  {card_title:<24} -> {assignee:<10} deps={deps or '-'}  out={out}")
            ids[stage] = f"dry-{stage}"
            continue

        rc, out_s, err_s = run(cmd)
        if rc != 0:
            print(f"[fail] {stage}: {err_s.strip()[:300]}")
            sys.exit(1)
        tid = parse_id(out_s)
        if not tid:
            print(f"[fail] {stage}: 无法解析 id，输出为:\n{out_s[:400]}")
            sys.exit(1)
        ids[stage] = tid
        print(f"  {stage}  {tid}  {card_title:<24} -> {assignee:<10} deps={deps or '-'}")

    graph = {"case": slug, "root_id": ids.get("00"), "cards": ids}
    (case / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n图已保存: {(case / 'graph.json').as_posix()}")

    if args.dispatch and not args.dry_run:
        print("\n派发一次 …")
        rc, out_s, err_s = run(["hermes", "kanban", "dispatch"])
        print(out_s.strip()[-800:] or err_s.strip()[:400])
    elif not args.dry_run:
        print("未派发。执行：hermes kanban dispatch")


if __name__ == "__main__":
    main()
