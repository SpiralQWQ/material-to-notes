# 更新日志

本项目的所有重要变更都记录在本文档中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

## [1.0.0] - 2026-10-25

首个公开发布，双轨授权：AGPL-3.0 开源 + 商业授权。

### 新增

- **`scripts/setup_parts.py`** —— 首次使用时拉取五个零件，锁定到已验证可用的 commit。
  `--check` 只报缺谁、`--update` 按锁表重新对位、`--mirror` 走国内镜像。
- **`scripts/setup_engines.py`** —— 为每个引擎建独立虚拟环境，并把路径写进 `.env`，
  按管线分线安装而非一次全装：`--line document` 约 0.1 GB（解析走 MinerU 云 API）、
  `--line fetch` 约 0.7 GB、`--line clean` 约 1.4 GB、`--line media` 约 3.7 GB、
  `--all` 约 7 GB。本地 MinerU 按需开启且标明不推荐；ffmpeg 只检测不下载——
  在安装脚本里从互联网抓可执行文件是供应链风险。
  主管线环境是「一个引擎一个环境」的唯一例外：适配器是用 `sys.executable`
  启动所有零件的，所以这些包装进那个解释器，而不是装进一个没人会读的 venv。
- **`pyproject.toml` 声明了主管线真正的依赖。** 原先是一张空表，
  于是 `pip install -e .` 之后连 `import yaml` 都不行。现在有测试锁死这份列表与
  `setup_engines.py` 里的管线包列表是同一件事，两者不能再各自漂移。
- **`scripts/privacy_check.py`** —— 扫描绝对路径、用户名、内部代号与密钥，已接入 CI。
  它同时读 git 与一次有界磁盘走查，所以没人 add 过的文件也照扫；
  在没有 git 的 `git archive` 导出物上同样能跑。
- **`docs/UPSTREAM.md`** —— 五个零件的来源、锁定版本、许可，
  以及升锁表前必须遵守的两条规矩。
- **`THIRD_PARTY.md`** —— 第三方组件与许可索引。其中三件要留意：
  mineru 用自定义（非 OSI）许可、pymupdf 是 AGPL 与 Artifex 商业双轨、
  torch 的许可里含 BSL-1.0。
- **社区文件** —— `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md`、
  issue 与 PR 模板，以及 CI。
- **`.env.example` 列全了流水线会读的每一个键**，包括 `MINERU_API_TOKEN`。
  原先偏偏漏了默认文档线缺了就跑不动的那一个 token，用户照 README 配完，
  一跑就撞「未设置 MINERU_API_TOKEN」，而模板里根本没有这一行可抄。
- **526 条测试**（单元 + 端到端 + 穷举）。只需要 `pytest` 与 `pyyaml`：
  测试只读零件的文件、不 import 零件，所以跑测试不必装任何引擎。

### 变更

- **五个零件改为拉取，不再随库发布。** 复制进来会造成两份权威副本悄悄分叉，
  而且让仓库读起来像聚合站而不是一个项目。改由锁表加 `docs/UPSTREAM.md` 代替副本。
- **命令统一为 `material-to-notes`** —— 仓库名、发行名、CLI 命令、导入名四者同一，
  与这一家族的其他仓库一致。

### 说明

- **本变更日志只覆盖本仓库。** 对五个零件的改动归各自的变更日志管，
  本仓库通过锁定 commit 消费它们。内部开发流水账不随本仓库发布。
- **发布前用全新克隆端到端验过一遍**：克隆 → `setup_parts.py` → `pytest -q`
  → 526 passed，退出码 0。有四个"照 README 三步走完仍然跑不起来"的断点是这么跑出来的，
  不是读代码看出来的：主管线环境装进了没人读的 venv、上面那张空依赖表、
  `.env` 缺的那个键，以及一个在一切正常时才报红的 CI 退出码守卫。
- **测试套件绝不会不看作答就报绿。** `parts/` 缺失时它全 skip、
  打印一条能直接照着敲的命令，然后退 1——什么都没验的一次运行，
  不该被任何只看退出码的人读成"一切正常"。
- 文档线默认走 MinerU **云 API**。本地引擎可用（`--mode local`），但刻意不推荐。
- **写笔记这一步故意不做成自动。** 见 README 的「它是半自动的，不是全自动」一节
  与 [`docs/SOP.md`](docs/SOP.md)。

## [0.1.0] - 2026-10-07

内部首个版本，从未对外发布：契约层、适配层、编排层、门禁层、记录层，加 188 个测试。
留在这里只为交代来历；要知道这个项目现在是什么，看上面的 1.0.0。

[未发布]: https://github.com/SpiralQWQ/material-to-notes/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v1.0.0
[0.1.0]: https://github.com/SpiralQWQ/material-to-notes/releases/tag/v0.1.0
