# 更新日志

本项目的所有重要变更都记录在本文档中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

## [1.0.0] - 2026-10-25

首个公开发布，双轨授权：AGPL-3.0 开源 + 商业授权。

### 新增

- **`scripts/setup_parts.py`** —— 首次使用时拉取五个零件，锁定到已验证可用的 commit。
  `--check` 只报缺谁、`--update` 按锁表重新对位、`--force` 丢掉副本重克、
  `--mirror` 走国内镜像（`gh-proxy` 预设于 2026-10-25 实测可用；这类站点寿命都不长，
  失效时传完整 URL 前缀即可）。
- **`scripts/setup_engines.py`** —— 为每个引擎建独立虚拟环境，并把路径写进 `.env`。
  按管线分线安装，不一次全装：`--line document` 约 0.1 GB（解析走 MinerU 云 API）、
  `--line fetch` 约 0.7 GB、`--line clean` 约 1.4 GB、`--line media` 约 3.7 GB、
  `--all` 约 7 GB。本地 MinerU 刻意设为按需（`--line document-local`）并标明不推荐。
  ffmpeg 只检测不下载——在安装脚本里从互联网抓可执行文件是供应链风险。
- **`docs/UPSTREAM.md`** —— 五个零件的来源、锁定版本、许可，以及升锁表前必须遵守的两条规矩。
- **`THIRD_PARTY.md`** —— 第三方组件与许可索引，以及三件需要特别注意的事：
  mineru 用自定义（非 OSI）许可、pymupdf 是 AGPL 与 Artifex 商业双轨、
  torch 的许可里含 BSL-1.0。
- **社区文件** —— `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md`、
  issue 与 PR 模板，以及一个会先拉零件、再跑测试、再跑隐私扫描的 CI。
- **`tests/conftest.py`** —— 一道预检：把「零件没拉」从 39 个 `FileNotFoundError`
  变成一条跳过，并指明该跑什么命令；全跳过时强制退出码非零，
  让"什么都没验到"的跑测不会被报成绿色。
- **测试套件 514 条**（单元 + 端到端 + 穷举）。只需要 `pytest` 与 `pyyaml`——
  它只读零件的文件、不 import 零件，所以跑测试不需要装任何引擎。

### 变更

- **五个零件改为拉取，不再随库发布。** 复制进来会造成两份权威副本悄悄分叉，
  而且让仓库读起来像聚合站而不是一个项目。改由 `setup_parts.py` 的锁表
  加 `docs/UPSTREAM.md` 代替副本。
- **`privacy_check.py` 不再有两个会让它说谎的盲区。** 它原来的文件清单只来自
  `git ls-files`，于是没人 add 过的文件——正是没人注意到的泄露的住处——一个都不扫，
  而脚本照样打印 `clean`。现在 git 与有界磁盘走查并用，
  这也让它在没有 git 的 `git archive` 导出物上同样能跑。
  它也不再在 GBK 控制台上崩死：报告要原样打印文件内容，
  遇到控制台编码不了的字符会抛 `UnicodeEncodeError`，然后以一个与隐私无关的原因退出非零。
- **模式集更宽。** 原来只查四类形态，漏掉内部代号、本地目录树、以及非 `C:` 盘上的用户目录。
  现已覆盖；绝对路径规则也改为要求至少两级路径，
  免得 Python 字符串字面量里的转义 `\n` 被当成路径报出来。
- **命令统一为 `material-to-notes`。** 仓库名、发行名、CLI 命令、导入名四者同一，
  与这一家族的其他仓库一致。

### 修复

- 门禁消息与派活单让用户去跑 `pipeline toc`、`pipeline step`、`pipeline gate`、
  `pipeline run`、`pipeline checklist`——改名后这些命令已经不存在了。
  所有这些字符串现在都是真实命令名。
- `argparse` 在用法文本与 `--version` 里仍自称 `pipeline`。
- `setup_engines.py` 的 `write_env` 会改 `.env`，而那里面是真实的 API 密钥。
  现在改为原地改行、只追加真正的新键，而不是从解析结果重写整个文件——
  后者会丢掉注释和任何它没识别出来的键，那就是让人丢掉没备份的密钥的方式。
- 绝对路径规则原来会把 GitHub 仓库名里的 `Di` + `sk-` 当成密钥
  （例如 `Acronis-Disk-Director-...`），让报告里塞满没人能清的命中。现已要求词边界。

### 说明

- **本变更日志的范围仅限本仓库。** 它不记录对五个零件做的改动：
  那些归各自的变更日志管，本仓库通过锁定 commit 消费它们。
  详细的内部开发流水账（含逐个零件的修复，以及产出它们的 51 轮验收）
  留在源项目里，不随本仓库发布。
- 文档线默认走 MinerU **云 API**。本地引擎可用（`--mode local`），但刻意不推荐。
- 写笔记这一步故意不做成自动。见 README 的「它是半自动的，不是全自动」一节
  与 [`docs/SOP.md`](docs/SOP.md)。

## [0.1.0] - 2026-10-07

首个版本：把五个已开源工具串成一条「素材 → 学习笔记」流水线的编排层。

### 新增

- **契约层** `contract/` —— 步骤定义（单一事实源）、工作目录布局、产物校验、外部命令运行器。
- **执行适配层** `steps/` —— 五个零件各一个薄适配器（wkc / dtmd / m2m / tce / mre）。
- **编排层** `orchestrate/` —— 工作台初始化、选路、串行 runner、断点续跑、失败处理、装配。
- **门禁层** `gates/` —— 机器门禁（保留原始证据）、审核检查单
  （含语义保真 / 幻觉 / 成本三条全局项）。
- **记录层** `report/` —— 总进度单、JSONL 运行日志。
- **命令行入口** `cli/` —— `init` / `route` / `gate` / `checklist`。
- **文档** `docs/` —— 架构与目录契约、穷举测试方案、SOP。
- **测试** —— 单元 + 端到端 + 穷举，共 188 个。

### 说明

- 五个零件保持独立；本工具只通过「文件接力 + 命令行调用」使用它们。
- 对真实零件实跑需本机环境；当时未覆盖项记录在源项目里，不在此公布。

[未发布]: https://github.com/SpiralQWQ/material-to-notes/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v1.0.0
[0.1.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v0.1.0
