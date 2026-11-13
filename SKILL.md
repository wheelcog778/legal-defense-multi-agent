---
name: legal-defense-multi-agent
description: "Use when defending an administrative penalty with a crew."
version: 1.5.1
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [legal, multi-agent, kanban, defense, administrative-penalty]
    category: productivity
    related_skills: [kanban-multi-agent-team, grounded-citations, pdf]
---

# Legal Defense Multi-Agent

行政处罚 / 诉讼辩护的十道工序 kanban 流水线：事实 → 有利法源 → **不利法源** → **类案** → **规范冲突** → **沿革与不确定概念** → 抗辩构建 → **红队** → **引用核验** → 成稿 → 门禁。

**先判阶段再动手**：收到告知书＝申辩阶段（出申辩意见书）；收到决定书＝复议或诉讼阶段（出复议申请书／起诉状）；两期均已过＝救济窗口关闭，不出文书，先出窗口说明。阶段判错，整份文书白写。

工作目录：`<你的 legal-multi-agent 项目根目录>`（builder、roles、checklist、cases）。

## When to Use

- 行政处罚陈述申辩、行政复议申请、行政诉讼起诉状的理由部分。
- 任何“引错一条就全废”的文书。
- 已经有一份稿子，只需要挑毛病、不想从零跑流水线时：按 `references/reviewing-an-existing-brief.md` 的八项过一遍，别启动整套 DAG。
- 要把这套工序搬到别的规则域（病案编码、合同审查、税务申报）：按 `references/framework-porting.md` 的四步走，只搬骨架、不搬话术。
- 不适用：法律常识问答、简单一页信。

## 为什么多三道工序

单链 agent 只朝有利方向检索，而真实败诉来自你没读到的那一条。三个阶段不可省：

1. **11 不利法源检索** — 通读整部规范，列出对方能换用的每一条。
   实例：《暂行规定》第六条的申辩，漏了《实施办法》第十二条 + 第二十二条第三款（对个人罚 5000 元）。对方换个依据，全文作废。
2. **12 类案与裁判倾向** — 查这类案子实际怎么判、撤销理由分布。理论强不等于能突破，排序靠它。
3. **15 规范冲突与定义审查** — 先定“哪一条说了算”：定义、效力、新旧、竞合四类逐类过。
4. **16 沿革与不确定概念** — 旧法/新法概念变迁（从旧兼从轻，处罚法 37 条）+ 不确定概念清单（明确性质则、判断余地、裁量基准）——这是扩张辩护空间的主战场。
5. **30 红队** — 扮演机关法制审核人：文义 / 体系 / 目的 / 类案四路攻击，加“换条不换事”与概念替换。
6. **40 引用核验** — 逐条对官方原文与效力状态，核不上的从正文删除。

## Procedure

```bash
cd /path/to/legal-defense-multi-agent
python3 preflight.py --kanban   # 开工自检（Windows 用 py -3）
mkdir -p cases/<slug>/input cases/<slug>/out   # 告知书、聊天记录、陈述放 input/
py -3 build_case.py cases/<slug>              # 建 DAG（幂等；非 Windows 用 python3）
bash run.sh cases/<slug>                       # 跑到底；或反复 hermes kanban dispatch
```

卡图：

```
00 facts (researcher)
├─ 10 sources_pro (researcher) ─┐
├─ 11 sources_con (analyst)   ──┤
└─ 12 case_law (analyst)      ──┤
                                 ├─ 15 conflicts (verifier) ─┐
                                 └─ 16 concepts (verifier)  ─┴─ 20 arguments (analyst)
                                                                  ├─ 30 redteam (verifier)
                                                                  └─ 40 citations (verifier)
                                                                      └─ 50 draft (writer)
                                                                          └─ 60 gate (verifier)
```

## 对外交付（可转发版）

给别人用时出三个东西，不是一个：

1. **零依赖手册**（`manual/行政处罚申辩十道工序.pdf`）——十段提示词，任何 AI 都能跑，不需要 Hermes。收件人只有 ChatGPT/DeepSeek 也能用。
2. **便携包**——`build_case.py` + `roles/` + `checklist.md` + 手册；解压后两条命令跑完。
3. **测试包**（给别的 agent 试跑用）——流水线 + 几个真实公开决定书当输入 + `00-测试说明.md` + 回报清单。选案、取数、清理、打包、回报问法见 `references/public-cases-as-test-inputs.md`。

规矩：

- 手册里每段提示词必须自包含（角色 + 输入 + 输出格式 + 铁律），不能写“参见上一步”。
- 附材料清单和 26 项门禁（另附窗口说明 12 项），收件人不需要回头问你。
- 手册用 `render.py`（零依赖 md→打印版 HTML）+ Edge headless `--print-to-pdf`；页数用 `b'/Type\s*/Page[^s]'` 数，排版必须截图看过再交。
- 分发 zip **必须**用 `_分发/build_zip.py` 打（arcname 取相对包根），打完它会自检“无盘符/无绝对路径/无重复”；发布前再用 `Expand-Archive` 解一次。手写 `z.write(p, '前缀/'+p.absolute())` 会把 `C:/...` 嵌进条目名，收件人双击就报“无法处理无效的存档条目”——这个错犯过三次。
- 打包排除 `cases/` 和 `.card_bodies/`——案件材料不进转发包。
- 分发 zip 用 Python `zipfile` 生成；用 shell zip 或资源管理器压中文目录，收件人解出来是乱码文件名。

## 跨域移植

骨架不依赖法律。只要目标域满足三条就值得搬：**有官方原文**（能逐字核）、**引错一条会全废**（对抗性真实存在）、**结果可判定**（能进清单，不靠审美）。

法律 → 病案编码的映射：事实包→病历结构化；有利法源→官方规则源（ICD、清单规范、分组方案）；不利法源→病历中不支持该编码的表述；类案→同组病例与入组结果；规范冲突→版本冲突（临床版/医保版、2.0/3.0）；沿革→编码沿革；论证→编码选择理由（落到病历行）；红队→医保审核员视角；引用核验→规则原文核验；成稿→质控报告。映射表、四步法与三个失效信号见 `references/framework-porting.md`。

## Gates

- **阻断行只在“全部主渠道均已届满”时打。** 复议关了、起诉还开（剩余 >7 日）**不挂 B1**，改在第一行写 `【仅存渠道：起诉，剩余 N 天】` 并在表 B 的 M11 判 pass。把这种状态标成“窗口已关闭”，等于把唯一还开着的路说死——它是最该催“赶紧递”的状态。
- **公告送达不能拿落款日当送达日**：自公告发布之日起经 30 日视为送达，申辩／听证期从视为送达日起算；视为送达日在未来时写“未起算”，不许写“已届满”或“剩 60 日”。
- **表 B（窗口说明）有盲区要堵**：走这条出口时 12 岗类案、40 岗引用核验没有 A 表项可打勾，容易被静默跳过。M12 要求逐项披露未执行／blocked 的岗位及影响。
- `checklist.md` 是“可提交”的唯一定义，**两张表按产出选**：文书类用表 A（26 项），救济窗口说明用表 B（12 项，M1–M12）。选错表＝整张门禁作废（拿 A 表检窗口说明，#4 全文通读、#22 附件会全 fail）。
- **判定四种**：pass / fail / n/a / blocked。n/a 只限“材料本包没有”“公开件已遮蔽”；blocked 只限“靠外部原文或检索，而通道确实不可用”。靠外部通道的项（A#4、6、9、11、12、13、15）通道不可用时**统一判 blocked**，不许有的判 n/a、有的判 fail。
- **期限要算到天，不只核规则。** #21 分三件：规则没核＝fail；只核规则不算日历＝fail；**算出来已届满判 pass**，届满事实交阻断项 B1——已届满不是错误，判 fail 会造出一条“无回改空间”的 fail，破坏“fail＝可改”的契约。
- **结论行只许有结论**：`结论：可提交（fail 0，阻断 0，blocked 0）` 或 `结论：不可提交（fail n，阻断 B1/0，blocked k）`。**fail 0 但 blocked > 0 仍是不可提交**（未核＝未证）。禁止“可先作为初稿递交”“基本可提交”这类软着陆尾巴。
- **blocked 必须带明细并分两类**：`blocked k：#4 #6 #9 …`，每项标**环境性**（无网／无 key／包内缺原件，换环境可补）还是**实质性**（该核而材料本身没有，必须做）。不分类的 blocked 会让结论行永远一样长，看不出到底缺什么。
- 主张排序按**可突破性**：类案采纳频次 > 规范强度 > 论证美感。无类案支持的争点必须显式标注。
- `sources_con.md` **第一行必须点名漏项**（前稿漏了哪一条／机关没引但可换用的哪一条），岗位卡里写死了。只列法条不点名＝对抗性归零。
- 类案岗检索通道不可用时，输出 `本岗不可执行（检索通道不可用：<原因>）`，门禁 #11 判 **blocked**，不得折算成“无类案支持”混过去。
- 每条引用必须带：逐字原文、效力状态、修订文号、来源 URL。无原文 = 无引用。
- 成稿只能用 `citations.md` 判定为**准确**的条目。
- `redteam.md` 列出的自认句，一律改写为假设性表述（“即使假定……”）。

## Pitfalls

- **`input/` 里只有模板或前稿时，流水线照跑，而且会交出几十万字 + 成稿 docx**。产物齐全不等于案子成立——那是方法演练。判定“真实案例”的唯一标准是 `input/` 里有原始告知书/决定书（含文号与落款）；没有就在 `meta.json` 标题里写“待补告知书”，并在一切对外场合标“模板演练”，不得用作样张、报价依据或“办成过”。00 facts 卡的材料清点必须把缺的写成【待补：…】，绝不能用通用模板补位；一个 `文件数=1 且为模板` 的 case，在评审和客户面前都是负资产。
- **无人值守 worker 用不了 `execute_code`**（提示 not allowed in an unattended session）。必须走 `terminal`；读 .docx 用 `unzip -p f.docx word/document.xml`，或落一个 .py 脚本再跑。
- **workspace 必须 `dir:<绝对路径>`**，不能用 scratch——scratch 完成后会被删除，产物一起没。
- 卡体先写到 `cases/<slug>/.card_bodies/<stage>.md`，用 `--body-file` 传入，避免中文换行被 shell 弄坏。
- `hermes kanban dispatch` 显示 `Spawned: 0` 但 `runs <id>` 显示 running，说明 worker 已经起来了——计数只反映本轮。
- **`hermes kanban block` 的签名是 `block <task_id> <reason...>`**，批量靠 `--ids id1 id2`。把多个 id 连写成位置参数，每个都返回 `cannot block`。另外依赖未满足的 todo 卡本身 block 不了——想停链要在上游动手（改父卡、archive），别在下游卡上反复试。
- claim lock 显示为 `<hostname>:<pid>`，无害。解析 CLI 输出前先去掉 `\r`。
- **并行跑多案会撞上下文天花板**：4 路并行 × 每路 11 份长产物，实测 3/4 路在写出任何文件前就崩掉；限篇幅（单篇 ≤80 行）后 4/4 跑通。要并行就限篇幅，要质量就一案一 agent 串行。
- 时长：检索岗 4–6 分钟；核验岗重取官方法条可 15 分钟以上。先看 `hermes kanban log <id>` 再判断卡死。
- **政府网站 PDF 不要交给网页抓取工具直接吃**：gov 站 PDF 常 404、读超时，或那个 `.pdf` 地址实际返回站点导航页。用 `curl -sS -L -A "Mozilla/5.0"` 落盘、`file` 验成 PDF、再本地用 pypdf 抽；抽取结果必带页码与全角标点错，清理和验收口径见 `references/public-cases-as-test-inputs.md`。

## Verification

- `hermes kanban show <root>` 的 children 与上图一致。
- `cases/<slug>/out/` 十一件产物齐全（按阶段，含 `gate.md`）。
- `facts.md` 的“材料清点”表里，实际文件数与来源要经得起问：1 个通用模板 + 0 份原始文书 = 演练，不是案例（无论 out/ 里有多少字）。
- `gate.md` 结论行只有“可提交 / 不可提交”两种；其他字样说明门禁岗没按契约执行。
- `sources_con.md` 第一行应当直接点名“前一稿漏了哪一条”。只罗列法条而不指名漏项，说明这一岗退化成了普通检索，本次运行的对抗性等于零。
