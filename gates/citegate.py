"""法镜 · 引用白名单门（确定性，不经模型）

为什么有这一道：40 岗写出 citations.md 之后，「成稿只用判为准确的引用」靠的是 50 岗
自觉。实测 05 案：核验表把《听证办法》第五条第二款判为「有偏差」、把处罚法 33/36/37/63
条判为「无法核实」，成稿里照样出现，而且附录一自报「已核原文准确」。

这一门不看模型怎么说，只做三件事：
  1. 从 citations.md 的表格里抽出所有「规范 + 条款 + 判定」，只留判定以「准确」开头的。
  2. 从成稿里抽出所有显式引用（《规范》第X条第Y款第Z项，含「及/、/和」并列）。
  3. 逐条比对。核验表里没有的 = 未核；核验表判否的 = 越权引用。两者都算 fail。

刻意不做的事（写在这里，免得后人以为漏了）：
  - 不解析「该条例」「该办法」这类简称指代 —— 只在表格里按后缀唯一匹配（《条例》）。
  - 不判断引用内容是否逐字正确 —— 那是 40 岗的事，这一门只查「有没有资格引用」。
  - 不把转述对方援引（贵局告知公告援引……）判 fail —— 那不是我方主张，记 context。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

CN_NUM = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
          "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
NUM_CH = r"[0-9〇零一二三四五六七八九十百两]"
ART = rf"第\s*({NUM_CH}+)\s*条"
KUAN = rf"第\s*({NUM_CH}+)\s*款"
XIANG = rf"第\s*({NUM_CH}+)\s*项"
CLAUSE_RE = re.compile(rf"{ART}(?:\s*{KUAN})?(?:\s*{XIANG})?")
NAME_RE = re.compile(r"《([^》]{2,40})》")
DOCNO_RE = re.compile(rf"([\u4e00-\u9fa5]{{0,12}}〔\d{{4}}〕\s*\d+\s*号)")
VERDICT_RE = re.compile(r"^(准确|有偏差|无法核实|失效)")
OK_PREFIX = "准确"

OPPONENT = re.compile(r"(?:贵局|告知公告|告知书|决定书|对方).{0,30}(?:援引|引用|载明)"
                       r"|(?:援引|引用|载明).{0,30}(?:贵局|告知公告|告知书|决定书|对方)")
HEDGE = re.compile(r"(待核|未核|不作原文引用|原文未载|未获原文)")
UNRESOLVED = re.compile(r"(?:该|本)(?:条例|办法|规定|法)第[0-9〇零一二三四五六七八九十百两]+条")

DRAFT_CANDIDATES = (
    "陈述申辩意见书.md",
    "行政复议申请书.md",
    "行政起诉状.md",
    "救济窗口说明.md",
)


def stage_from_facts(out_dir: Path) -> str:
    """从 facts.md 的「阶段／产出文书」行解析程序阶段，返回对应文件名。

    不能只看目录里哪个文件先存在：旧申辩稿会盖住新复议稿，导出和引用门就都对着错稿。
    解析不出阶段时返回空串，由调用方 fail-closed，不拿默认稿冒充。
    """
    p = Path(out_dir) / "facts.md"
    if not p.is_file():
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    line = ""
    for ln in text.splitlines():
        s = ln.strip().lstrip("*#- ").strip()
        for head in ("程序阶段：", "阶段：", "程序阶段:", "阶段:"):
            if s.startswith(head):
                line = s[len(head):].strip()
                break
        if line:
            break
    if not line:
        for ln in text.splitlines():
            s = ln.strip().lstrip("*#- ").strip()
            for head in ("产出文书：", "产出文书=", "产出文书＝", "产出文书:"):
                if s.startswith(head):
                    line = s[len(head):].strip()
                    break
            if line:
                break
    if re.search(r"救济窗口|两期均已过|窗口已届满", line):
        return "救济窗口说明.md"
    if "复议" in line and "诉讼" not in line:
        return "行政复议申请书.md"
    if "诉讼" in line or "起诉" in line:
        return "行政起诉状.md"
    if "申辩" in line or "告知" in line:
        return "陈述申辩意见书.md"
    return ""


def draft_path(out_dir: Path, name: str = "") -> Path:
    """当前阶段唯一成稿路径；不按「谁先存在」猜，旧阶段稿不得被选中。"""
    out = Path(out_dir)
    name = name or stage_from_facts(out)
    if not name:
        return out / DRAFT_CANDIDATES[0]
    return out / name




def cn2int(s: str) -> int | None:
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total = 0
    for ch in s:
        if ch in "零〇":
            continue
        if ch == "十":
            total = (total or 1) * 10 if total < 10 else total + 10
        elif ch == "百":
            total = (total or 1) * 100
        elif ch in CN_NUM:
            total = total * 10 + CN_NUM[ch] if total and total % 10 else total + CN_NUM[ch]
        else:
            return None
    return total or None


def norm_name(s: str) -> str:
    s = s.strip().strip("《》")
    s = s.replace("中华人民共和国", "")
    return re.sub(r"\s+", "", s)


@dataclass
class Entry:
    """citations.md 里的一行核验结论。"""
    name: str
    art: int
    kuan: int | None
    xiang: int | None
    ok: bool
    qualified: bool
    verdict: str
    raw: str

    @property
    def key(self):
        return (self.name, self.art, self.kuan, self.xiang)


def _leading_clauses(window: str) -> list[re.Match]:
    """书名号之后紧贴的条款串：第X条（第Y款）（第Z项），可带「及/、/和」并列。"""
    # 表格把「规范名」和「条款」放在相邻两格：允许开头跨一个 | 再取条款
    s = re.sub(r"^\s*\|?\s*", "", window)
    out, pos = [], 0
    while True:
        m = CLAUSE_RE.match(s, pos)
        if not m:
            break
        out.append(m)
        pos = m.end()
        sep = re.match(r"\s*(?:[、，,]|及|和|与|或者)\s*", s[pos:])
        if not sep:
            break
        pos += sep.end()
        if not re.match(rf"第\s*{NUM_CH}+\s*条", s[pos:]):
            break
    return out


def extract_refs(text: str) -> list[tuple[str, int, int | None, int | None, int, str]]:
    """抽显式引用：返回 (规范名, 条, 款, 项, 行号, 原文片段)。同一行同一条只留一次。"""
    out, seen = [], set()
    names = list(NAME_RE.finditer(text))
    for i, m in enumerate(names):
        start = m.end()
        stop = names[i + 1].start() if i + 1 < len(names) else len(text)
        window = text[start:min(stop, start + 80)]
        for c in _leading_clauses(window):
            art = cn2int(c.group(1))
            kuan = cn2int(c.group(2)) if c.group(2) else None
            xiang = cn2int(c.group(3)) if c.group(3) else None
            if art is None:
                continue
            line = text.count("\n", 0, m.start()) + 1
            key = (norm_name(m.group(1)), art, kuan, xiang, line)
            if key in seen:
                continue
            seen.add(key)
            out.append((*key, text[m.start():start + c.end()].replace("\n", " ")[:80]))
    return out


def parse_citations(text: str) -> list[Entry]:
    """只认表格行里判定的那一列；判定以「准确」开头 = 可引用。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        vi = next((i for i, c in enumerate(cells) if VERDICT_RE.match(c)), None)
        if vi is None or vi < 2:
            continue
        spec = cells[1]
        if "《" not in spec and not DOCNO_RE.search(spec):
            continue
        verdict = cells[vi]
        ok = verdict.startswith(OK_PREFIX)
        qualified = ok and ("（）" in verdict or "(" in verdict)
        for name, art, kuan, xiang, _ln, _raw in extract_refs(spec):
            out.append(Entry(name, art, kuan, xiang, ok, qualified, verdict, spec))
        if "《" not in spec:
            m = DOCNO_RE.search(spec)
            for c in _leading_clauses(spec[m.end():] if m else ""):
                art = cn2int(c.group(1))
                if art:
                    out.append(Entry(norm_name(m.group(1)), art,
                                     cn2int(c.group(2)) if c.group(2) else None,
                                     cn2int(c.group(3)) if c.group(3) else None,
                                     ok, qualified, verdict, spec))
    return out


def resolve(name: str, known: set[str]) -> str | None:
    if name in known:
        return name
    if len(name) < 2:
        return None
    hits = [k for k in known if k.endswith(name)]
    return hits[0] if len(hits) == 1 else None


def judge(entries: list[Entry], name: str, art: int, kuan: int | None,
          xiang: int | None) -> tuple[str, Entry | None]:
    """allow / deny / unverified。"""
    cands = [e for e in entries if e.name == name and e.art == art]
    if not cands:
        return "unverified", None
    for e in cands:
        if kuan is not None and e.kuan is not None and e.kuan != kuan:
            continue
        if xiang is not None and e.xiang is not None and e.xiang != xiang:
            continue
        if e.ok:
            return "allow", e
    return "deny", cands[0]


def _segments(text: str) -> tuple[list[tuple[int, str]], str]:
    """切成「正文段」与「附录一对照表」。

    附录一是一张状态表（第 3 列本来就写「已核／待核」），按自报冲突查；
    附录二、附录三仍是实质内容（救济途径里真引条文），按正文严格查。
    返回 ([(起始行号, 文本)], 对照表文本)。
    """
    m1 = re.search(r"(?m)^##\s*附录一", text)
    if not m1:
        return [(1, re.split(r"(?m)^##\s*黑板要点", text)[0])], ""
    body1 = re.split(r"(?m)^##\s*黑板要点", text[:m1.start()])[0]
    rest = text[m1.start():]
    m2 = re.search(r"(?m)^##\s*附录二", rest)
    table = rest[:m2.start()] if m2 else rest
    body2 = rest[m2.start():] if m2 else ""
    body2 = re.split(r"(?m)^##\s*黑板要点", body2)[0]
    segs = [(1, body1)]
    if body2.strip():
        segs.append((body1.count("\n") + table.count("\n") + 1, body2))
    return segs, table


def _spec(name: str, art: int, kuan: int | None, xiang: int | None) -> str:
    s = f"《{name}》第{art}条"
    if kuan:
        s += f"第{kuan}款"
    if xiang:
        s += f"第{xiang}项"
    return s


def run(out_dir: Path) -> dict:
    out = Path(out_dir)
    cit_p = out / "citations.md"
    draft_p = draft_path(out)
    report = ["# 引用白名单门（引擎判定，不经模型）", ""]

    if not cit_p.is_file():
        body = ("结论：BLOCKED —— 引用核验表 `citations.md` 不存在，本门无法判定。\n\n"
                "未核＝未证：不得据此放行。")
        (out / "citegate.md").write_text(report[0] + "\n\n" + body + "\n", encoding="utf-8")
        return {"status": "blocked", "fails": 0, "allowed": 0, "denied": [],
                "unverified": [], "conflicts": [], "context": []}
    if not draft_p.is_file() or draft_p.stat().st_size < 200:
        body = f"结论：BLOCKED —— 成稿 `{draft_p.name}` 不存在或过短，本门无对象。\n"
        (out / "citegate.md").write_text(report[0] + "\n\n" + body + "\n", encoding="utf-8")
        return {"status": "blocked", "fails": 0, "allowed": 0, "denied": [],
                "unverified": [], "conflicts": [], "context": []}

    cit_txt = cit_p.read_text(encoding="utf-8", errors="ignore")
    draft_txt = draft_p.read_text(encoding="utf-8", errors="ignore")
    entries = parse_citations(cit_txt)
    if not entries:
        body = ("结论：BLOCKED —— 引用核验表存在，但没有解析出任何可判定的条款。"
                + chr(10) + chr(10)
                + "空表/畸形表不等于没有引用问题：未核＝未证，不得据此放行。")
        (out / "citegate.md").write_text(report[0] + chr(10) + chr(10) + body + chr(10), encoding="utf-8")
        return {"status": "blocked", "fails": 0, "allowed": 0, "denied": [],
                "unverified": [], "conflicts": [], "context": [], "unresolved": 0}
    known = {e.name for e in entries}
    segs, appendix = _segments(draft_txt)
    unresolved = len(UNRESOLVED.findall(draft_txt))

    allowed: list[tuple] = []
    denied: list[tuple] = []
    unverified: list[tuple] = []
    context: list[tuple] = []

    # 一、正文（含附录二/三）：严格判。核验表判否 = 越权；核验表没有 = 未核。两者都 fail。
    for off, seg in segs:
        rows = seg.splitlines()
        for name, art, kuan, xiang, line, _raw in extract_refs(seg):
            gline = line + off - 1
            real = resolve(name, known)
            if real is None:
                verdict, hit = "unverified", None
            else:
                verdict, hit = judge(entries, real, art, kuan, xiang)
            if verdict == "allow":
                allowed.append((name, art, kuan, xiang, gline, bool(hit and hit.qualified)))
                continue
            row = rows[line - 1] if 0 <= line - 1 < len(rows) else ""
            i = next((m.start() for m in NAME_RE.finditer(row)
                      if norm_name(m.group(1)) == name), -1)
            before = row[max(0, i - 24):i] if i >= 0 else ""
            after = row[i:i + 120] if i >= 0 else row
            item = (name, art, kuan, xiang, gline, hit.verdict if hit else "未在核验表中出现")
            if OPPONENT.search(before):
                context.append((*item[:5], "转述对方援引"))
            elif HEDGE.search(after):
                context.append((*item[:5], "原文自带待核标记"))
            else:
                (denied if verdict == "deny" else unverified).append(item)

    # 二、附录一「法律依据对照表」：只抓自报冲突——同一行自称准确/已核，核验表却判否。
    conflicts: list[tuple] = []
    t_off = len(draft_txt.splitlines()) - len(appendix.splitlines()) + 1
    for ln, row in enumerate(appendix.splitlines(), t_off):
        if not re.search(r"(准确|已核|已核实)", row):
            continue
        if re.search(r"(有误|错位|不符|待核|无法核实|失效|不得|删|未核)", row):
            continue                      # 这一行本身就在如实标注问题，不算自报造假
        for name, art, kuan, xiang, _l, _r in extract_refs(row):
            real = resolve(name, known)
            if real is None:
                conflicts.append((name, art, kuan, xiang, ln, "自报已核，核验表无此条"))
                continue
            verdict, hit = judge(entries, real, art, kuan, xiang)
            if verdict != "allow":
                conflicts.append((real, art, kuan, xiang, ln,
                                  f"自报已核，核验表判「{hit.verdict if hit else '否'}」"))

    fails = len(denied) + len(unverified) + len(conflicts)
    status = "blocked" if unresolved else ("pass" if fails == 0 else "fail")
    n_ok = sum(1 for e in entries if e.ok)
    report = [
        "# 引用白名单门（引擎判定，不经模型）", "",
        f"核验表：`{cit_p.name}` —— 判为「准确」的条目 {n_ok} 条 / 全部 {len(entries)} 条",
        f"成稿：`{draft_p.name}` —— 正文显式引用 {len(allowed) + len(denied) + len(unverified) + len(context)} 处",
        "",
        f"结论：{status.upper()} —— 越权引用 {len(denied)} 处，"
        f"未核引用 {len(unverified)} 处，附录自报冲突 {len(conflicts)} 处，语境豁免 {len(context)} 处，"
        f"未解析简称 {unresolved} 处",
        "",
    ]

    def table(items, problem_col: str) -> list[str]:
        rows = ["", f"| 行 | 引用 | {problem_col} |", "|---|---|---|"]
        for name, art, kuan, xiang, line, why in items:
            rows.append(f"| {line} | {_spec(name, art, kuan, xiang)} | {why} |")
        return rows

    if denied:
        report += ["## 一、越权引用（核验表判否仍写入正文）"] + table(denied, "核验表判定")
    if unverified:
        report += ["## 二、未核引用（核验表里根本没有这一条）"] + table(unverified, "核验表判定")
    if conflicts:
        report += ["## 三、附录自报冲突（自称已核，核验表判否）"] + table(conflicts, "冲突")
    if context:
        report += ["", "## 四、语境豁免（不计 fail，供律师目视）", "",
                   "| 行 | 引用 | 原因 |", "|---|---|---|"]
        for name, art, kuan, xiang, line, why in context:
            report.append(f"| {line} | {_spec(name, art, kuan, xiang)} | {why} |")
    if unresolved:
        report += ["", "## 五、未解析简称（需律师目视）", "",
                   f"正文有 {unresolved} 处「该条例/该办法/本法＋第X条」未解析；"
                   "本门不判 fail，但按未核处理，不得显示可提交。", ""]
    report += ["", f"统计：可引用 {len(allowed)} / 越权 {len(denied)} / 未核 {len(unverified)} / "
                   f"自报冲突 {len(conflicts)} / 未解析 {unresolved}，本门 fail 数 = {fails}", ""]
    (out / "citegate.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"status": status, "fails": fails,
            "allowed": len(allowed), "denied": denied, "unverified": unverified,
            "conflicts": conflicts, "context": context, "unresolved": unresolved}


if __name__ == "__main__":
    d = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    r = run(d / "out" if (d / "out").is_dir() else d)
    print(f"status={r['status']} fails={r['fails']} allowed={r['allowed']}")
    for it in r["denied"] + r["unverified"]:
        print("  ", it)
