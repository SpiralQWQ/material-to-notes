# material-to-notes

把五个已开源工具串成一条「素材 → 学习笔记」流水线的**编排层**。

- web-knowledge-crawler（取材，只下载）
- document-to-markdown（文档转 md）
- media-to-markdown（媒体转 md）
- text-cleaning-engine（清洗）
- md-rewrite-engine（重写成教学笔记）

本仓**只做编排**，不含任何解析 / 转写 / 清洗 / 重写能力——那些都在五个零件里。
**五个零件的代码副本随库自带**（`parts/<零件名>/`，每份附 `UPSTREAM.md` 来源卡），整个仓库自包含、可整包发布；
外面那五个仓库仍是权威源，同步规矩与本地改动见 `parts/README.md` 和 `parts/md-rewrite-engine/PATCHES.md`。

形态：主对话派发任务 → 子 agent 执行 → 独立子 agent 审核 → 主对话最终验收。不做图形界面。

## 运行

源码在 `src/material_to_notes/`（src 布局）。两种跑法：

```bash
pip install -e .                 # 装好后直接用命令
pipeline --version

# 或者不安装，临时把 src 加进路径
PYTHONPATH=src python -m material_to_notes.cli.main --version
```

测试：`python -m pytest -q`

> 本机当前**没有** `pip install -e .`，所以 `pipeline` 命令不存在；上面第二种 `PYTHONPATH=src` 的跑法实测可用（输出 `pipeline 0.1.0`）。

## 文档

- `docs/架构与目录契约.md` —— 架构与目录契约；**现状以第十节「状态与变更记录」为准**（头部状态行只是摘要）
- `docs/SOP.md` —— 给 AI 的强制流程（派活 / 门禁 / 4 轮审核 / 证据单 / 组长验收五步）
- `docs/Task清单.md` —— 拆解到最小单元的 Task 清单（S1）与后续真跑暴露的新 Task
- `docs/穷举测试方案.md` —— 路径穷举 / 边界严格 / 终点一致性（S2），含 §七 CLI 路径穷举闭包表
- `docs/acceptance/每步验收标准.md` —— 每一步的实测命令、硬卡与软卡
- `docs/contracts/接口契约.md` —— 每一步真正跑出去的命令与产物落点（实测登记）
- `docs/实跑清单.md` —— 本机环境与按步骤开跑
- `docs/回灌清单.md` —— 零件问题的登记（A 区已改好并推送 **11 条** / B 区待改**只剩 B-3 一条** / C 区我们这层的兜底 6 条）
- `docs/补丁重构计划报告.md` —— 从五个零件可吸取什么（**2026-10-15 晚快照，正文留作当时记录**）
- `docs/全量体检报告.md` —— 2026-10-24 全量体检：文档说谎清单、隐私扫描盲区、
  零件副本与上游的差异、回灌候选表，以及当轮执行结果（§十一）
- `docs/验收报告.md` / `docs/终点一致性报告.md` —— 验收结果
- `docs/媒体线测试计划.md` —— 视频/图集/图形学三条线的测试计划与逐轮执行日志（**最新**，记到 2026-10-22）
- `docs/B-8锚点修复计划.md` —— 目录锚点缺陷的定位与修复（已修，库内副本 A-8）
- `parts/README.md` —— 库内零件副本的来历与同步规矩

## 状态

**T01–T116 全绿**；2026-10-13 之后因真跑与规范对齐而新增的 Task 见 `docs/Task清单.md` §五~§八。

测试：编排层 **486 passed**；零件自测 dtmd **151** / mre **250** / m2m **130**。
tce 与 wkc **不是 pytest 风格**，得逐个 `python tests/<文件>.py` 跑（且要带 `PYTHONPATH=.` + `PYTHONIOENCODING=utf-8`，否则报 `ModuleNotFoundError`）：
tce **5 个测试文件全 exit 0**；wkc **2 个 exit 0 / 3 个 exit 1**（那 3 个是审计脚本，需联网，改动前后同样 exit 1，非回归）。
详见 `docs/acceptance/每步验收标准.md`。

实跑进度（截至 2026-10-24，成品笔记 **20 份**）：

- **文档线**（PDF/Word/PPT → 笔记）—— **14 份**，端到端跑通并通过内容门禁。doc1×1、doc2×2、doc3×5、doc4×1、doc5×1，以及图形学课件第 1–4 章各 1 份（课件走的是这条线：输入 PDF、产物 `_mineru`）。
- **媒体线**（视频 → 笔记）—— **1 份**（vid5），已走到终点，门禁 19 项全过 exit 0。
- **图集线**（图片 → 笔记）—— **5 份**，alb_one 1 份 + alb_each 4 份，门禁全 PASS。
- **爬取线** —— **未接**。`run` 遇到单个网页链接会明确报"这条线还没接"；硬拦在 `src/material_to_notes/orchestrate/pipeline.py` 的 `UNWIRED_KINDS`——取材适配器目前只支持「词汇文件 + 站点」，不接裸链接。跑它还需要你给词汇文件与站点，且对外爬取要你点头。

各线的实测命令与产物落点见 `docs/contracts/接口契约.md`；逐轮验收过程见 `docs/验收报告.md` 与 `docs/媒体线测试计划.md`；`runs/` 是素材副本，不入库。
