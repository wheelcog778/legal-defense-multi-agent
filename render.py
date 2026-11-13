#!/usr/bin/env python3
"""极简 Markdown → 打印版 HTML（零依赖）。

支持：# 标题、表格、``` 代码块、**粗体**、`行内码`、*斜体*、--- 分隔线。
"""
import html
import re
import sys
from pathlib import Path

CSS = """
@page { size: A4; margin: 18mm 16mm 16mm 16mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  margin: 0; color: #1e1e1e; background: #fff;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 10pt; line-height: 1.75;
}
.page { max-width: 700px; margin: 0 auto; padding: 28px 26px 40px; }
h1 { font-size: 21pt; margin: 0 0 6px; letter-spacing: .5px; }
h1 + p { color: #666; font-size: 10pt; margin-top: 0; }
h2 {
  font-size: 13pt; margin: 26px 0 9px; padding: 5px 0 5px 10px;
  border-left: 4px solid #1e1e1e; line-height: 1.45;
}
h3 { font-size: 11pt; margin: 18px 0 6px; }
p { margin: 7px 0; }
ul, ol { margin: 6px 0; padding-left: 20px; }
li { margin: 4px 0; }
strong { font-weight: 700; }
hr { border: 0; border-top: 1px solid #ddd; margin: 22px 0; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 9pt; }
th { background: #f4f4f2; text-align: left; padding: 6px 8px; border-bottom: 1.5px solid #bbb; }
td { padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
code {
  font-family: Consolas, "Courier New", monospace; font-size: 8.6pt;
  background: #f2f2ef; padding: 1px 4px; border-radius: 2px;
}
pre {
  background: #faf9f6; border: 1px solid #e4e0d6; border-left: 3px solid #b99a4e;
  padding: 11px 13px; overflow-wrap: break-word; white-space: pre-wrap;
  font-size: 8.7pt; line-height: 1.6; margin: 9px 0 14px; page-break-inside: avoid;
}
pre code { background: none; padding: 0; font-size: inherit; }
h2, h3 { page-break-after: avoid; }
table { page-break-inside: avoid; }
@media print { .page { padding: 0; max-width: none; } }
"""


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
    return text


def convert(md: str) -> str:
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if re.match(r"^-{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            head, body = cells[0], cells[2:]
            t = ["<table><thead><tr>"] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
            for r in body:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        if not line.strip():
            i += 1
            continue

        # 列表：连续的 - / * 或 1. 行
        if re.match(r"^([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\d+\.\s+", line))
            pat = r"^\d+\.\s+" if ordered else r"^[-*]\s+"
            items = []
            while i < len(lines) and re.match(pat, lines[i]):
                items.append(re.sub(pat, "", lines[i]).strip())
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<" + tag + ">" + "".join("<li>" + inline(x) + "</li>" for x in items) + "</" + tag + ">")
            continue

        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|-{3,}\s*$|\|)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if not buf:                      # 兜底：无法归类的行，强行当段落输出，避免死循环
            out.append("<p>" + inline(lines[i].strip()) + "</p>")
            i += 1
            continue
        out.append("<p>" + inline(" ".join(buf)) + "</p>")

    return "\n".join(out)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("用法: python3 render.py <input.md> [output.html]   # 零依赖 md → 打印版 HTML")
        print("示例: python3 render.py manual/行政处罚申辩十道工序.md")
        return
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".html")
    body = convert(src.read_text(encoding="utf-8"))
    dst.write_text(
        f'<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{html.escape(src.stem)}</title><style>{CSS}</style></head>"
        f'<body><div class="page">{body}</div></body></html>',
        encoding="utf-8",
    )
    print(dst.as_posix())


if __name__ == "__main__":
    main()
