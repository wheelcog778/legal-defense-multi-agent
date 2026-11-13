#!/usr/bin/env python3
"""开工前自检：一条命令回答"这包能不能直接跑，缺什么"。

杀掉三处本该由人自己做的比对：
  1. assignee 前提（板上有 researcher/analyst/verifier/writer 吗）
  2. 版本同源（SKILL 版本 / 包目录名 / 测试说明标题）
  3. 案例完整性（有没有 meta.json、有没有原件 PDF）

用法：
  python preflight.py                     # 自检当前目录（包根或 legal-defense/）
  python preflight.py --kanban            # 追加检查 kanban assignee（需 hermes CLI）
退出码：0 = 全部可跑；1 = 有阻断项（会把原因逐条列出来）
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

STAGES = 11
TABLE_A, TABLE_B = 26, 12
ASSIGNEES = ["researcher", "analyst", "verifier", "writer"]

try:                                                          # 中文 Windows 控制台默认 GBK
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:                                             # noqa: BLE001
    pass

ok, warn, bad = [], [], []


def find_root() -> Path:
    """包根（含 legal-defense/ 与 测试案例/）或 legal-defense/ 本身都认。"""
    for cand in (Path.cwd(), *Path.cwd().parents):
        if (cand / "legal-defense" / "SKILL.md").exists():
            return cand
        if (cand / "SKILL.md").exists() and (cand / "roles").exists():
            return cand.parent if (cand.parent / "测试案例").exists() else cand
    sys.exit("找不到 SKILL.md：请在包根或 legal-defense/ 目录下运行")


def check_files(root: Path):
    base = root / "legal-defense" if (root / "legal-defense").exists() else root
    need = ["SKILL.md", "checklist.md", "build_case.py", "run.sh", "roles", "references"]
    missing = [n for n in need if not (base / n).exists()]
    if missing:
        bad.append(f"缺文件：{', '.join(missing)}（在 {base}）")
    roles = list((base / "roles").glob("*.md")) if (base / "roles").exists() else []
    if len(roles) == STAGES:
        ok.append(f"岗位卡 {len(roles)}/{STAGES}")
    else:
        bad.append(f"岗位卡 {len(roles)} 张，应为 {STAGES} 张")

    stray = [p.name for p in base.glob("*.md") if re.match(r"^\d{2}_", p.name)]
    if stray:
        bad.append("包根有岗位卡副本（应只在 roles/ 里）：" + "、".join(stray))
    else:
        ok.append("包根无岗位卡副本")

    cl = base / "checklist.md"
    if cl.exists():
        t = cl.read_text(encoding="utf-8")
        na, nb = len(re.findall(r"^\|\s*\d+\s*\|", t, re.M)), len(re.findall(r"^\|\s*M\d+\s*\|", t, re.M))
        if (na, nb) == (TABLE_A, TABLE_B):
            ok.append(f"门禁表 A {na} 项 / 表 B {nb} 项")
        else:
            bad.append(f"门禁项数不符：表 A {na}（应 {TABLE_A}）/ 表 B {nb}（应 {TABLE_B}）")
    return base


def check_version(root: Path, base: Path):
    m = re.search(r"^version:\s*(\S+)", (base / "SKILL.md").read_text(encoding="utf-8"), re.M)
    skill_ver = m.group(1) if m else "?"
    # 包目录名 / 测试说明标题里的版本号（没有就跳过这一路，不算不同源）
    pkg = next((p.name for p in [root, *root.parents] if re.search(r"v\d+\.\d+", p.name)), "")
    m2 = re.search(r"v(\d+\.\d+(?:\.\d+)?)", pkg)
    pkg_ver = m2.group(1) if m2 else "?"
    readme = next(iter(root.glob("00-测试说明.md")), None)
    doc_ver = "?"
    if readme:
        m3 = re.search(r"v(\d+\.\d+(?:\.\d+)?)", readme.read_text(encoding="utf-8"))
        doc_ver = m3.group(1) if m3 else "?"
    vers = {skill_ver, pkg_ver, doc_ver} - {"?"}
    if len(vers) <= 1:
        ok.append(f"版本同源：{skill_ver}")
    else:
        bad.append(f"版本不同源：SKILL {skill_ver} / 包名 {pkg_ver} / 说明 {doc_ver}")


def check_cases(root: Path):
    dirs = sorted((root / "测试案例").glob("*")) if (root / "测试案例").exists() else []
    if not dirs:
        warn.append("没有 测试案例/ 目录，只跑自带案子")
        return
    ok_n, no_pdf = 0, []
    for d in dirs:
        if not d.is_dir():
            continue
        has_meta = (d / "meta.json").exists()
        inputs = [p for p in (d / "input").glob("*") if p.is_file()] if (d / "input").exists() else []
        if not (has_meta and inputs):
            bad.append(f"{d.name}：缺 meta.json 或 input/ 为空")
            continue
        ok_n += 1
        if not any(p.suffix.lower() == ".pdf" for p in inputs):
            no_pdf.append(d.name)
    ok.append(f"案例可用 {ok_n} 个")
    if no_pdf:
        warn.append("以下案例无原件 PDF，40 岗引用核验只能对 md 做（该案 #12/#13 应判 blocked）："
                    + "、".join(no_pdf))


def check_kanban():
    if not shutil.which("hermes"):
        warn.append("没有 hermes CLI，跳过 assignee 检查（非 Hermes 环境用手册路径即可）")
        return
    try:                                                      # 先探活：CLI 本身坏了就别装作能查
        v = subprocess.run(["hermes", "--version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=20)
        if v.returncode != 0 or not (v.stdout or v.stderr).strip():
            warn.append(f"hermes CLI 不可用（--version 退出码 {v.returncode}，无输出），assignee 未检查")
            return
    except Exception as e:                                    # noqa: BLE001
        warn.append(f"hermes CLI 不可用（{type(e).__name__}），assignee 未检查")
        return
    try:
        p = subprocess.run(["hermes", "kanban", "list", "--json"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        if p.returncode != 0:
            warn.append(f"kanban list 失败（hermes 可执行但查询出错）：{(p.stderr or p.stdout).strip()[:120] or '无输出'}")
            return
        data = json.loads(p.stdout[p.stdout.find("{"):]) if "{" in p.stdout else {}
        have = set()
        for card in (data.get("tasks") or data.get("items") or []):
            a = card.get("assignee") or card.get("owner")
            if a:
                have.add(a)
        miss = [a for a in ASSIGNEES if a not in have]
        if miss:
            bad.append("板上缺 assignee：" + "、".join(miss) + "（改 build_case.py 第 13~24 行，或在板上建同名）")
        else:
            ok.append("四个 assignee 都在板上")
    except Exception as e:                                   # noqa: BLE001
        warn.append(f"kanban 查询异常：{type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kanban", action="store_true", help="追加检查 kanban assignee")
    args = ap.parse_args()

    root = find_root()
    print(f"包根：{root}\n")
    base = check_files(root)
    check_version(root, base)
    check_cases(root)
    if args.kanban:
        check_kanban()

    for line in ok:
        print(f"  [OK]   {line}")
    for line in warn:
        print(f"  [WARN] {line}")
    for line in bad:
        print(f"  [BAD]  {line}")
    print("\n结论：" + ("可跑" if not bad else f"有 {len(bad)} 项阻断，先修再跑"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())