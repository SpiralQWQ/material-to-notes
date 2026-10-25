# material-to-notes

<p align="center">
  <a href="README.md"><kbd>🇺🇸 English</kbd></a> · <kbd>🇨🇳 中文</kbd>
</p>

<p align="center">
  <a href="https://github.com/SpiralQWQ/material-to-notes/releases"><img src="https://img.shields.io/github/v/tag/SpiralQWQ/material-to-notes?label=version" alt="version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL%203.0%20%7C%20Commercial-blue" alt="license"></a>
  <a href="https://github.com/SpiralQWQ/material-to-notes/stargazers"><img src="https://img.shields.io/github/stars/SpiralQWQ/material-to-notes?style=social" alt="stars"></a>
</p>

## 目录

- [它是半自动的，不是全自动](#它是半自动的不是全自动)
- [安装](#安装)
- [跑起来](#跑起来)
- [文档](#文档)
- [许可](#许可)
- [贡献](#贡献)
- [更新日志](#更新日志)
- [打赏](#打赏)

---

把五个已开源工具串成一条「素材 → 学习笔记」流水线的**编排层**。

| 零件 | 干什么 |
|---|---|
| [web-knowledge-crawler](https://github.com/SpiralQWQ/web-knowledge-crawler) | 取材（按词汇 + 站点爬网页） |
| [document-to-markdown](https://github.com/SpiralQWQ/document-to-markdown) | 文档转 md（PDF/Word/PPT） |
| [media-to-markdown](https://github.com/SpiralQWQ/media-to-markdown) | 媒体转 md（视频/音频/图集） |
| [text-cleaning-engine](https://github.com/SpiralQWQ/text-cleaning-engine) | 清洗（剥水印、去噪） |
| [md-rewrite-engine](https://github.com/SpiralQWQ/md-rewrite-engine) | 重写成教学笔记 |

本仓**只做编排**，不含任何解析 / 转写 / 清洗 / 重写能力——那些都在五个零件里。

**五个零件的代码不随本仓库发布。** 它们各有版本节奏、CHANGELOG 和许可，
复制进来会造成两份权威副本悄悄分叉。所以这里只存一份**锁表**，首次使用时一条命令把它们取回来：

```bash
python scripts/setup_parts.py          # 拉到 parts/<零件名>/，锁定 commit
python scripts/setup_parts.py --check  # 只看缺谁，什么都不拉
```text
来源、锁定版本与许可见 [`docs/UPSTREAM.md`](docs/UPSTREAM.md)。

---

## 它是半自动的，不是全自动

这点必须先说清，否则装完会发现最后一步停住不动，以为项目是坏的。

```text
机器干的活（全自动）              人 / AI 干的活（必须有人在场）
─────────────────────────       ────────────────────────────
爬网页                            写笔记
转 md
清洗
按规范排版                        判断"教没教会人"
查格式 / 查结构 / 查字数            审核质量
                                  决定返工还是通过
```text
**写笔记那一步故意不做成自动的。** 格式能查、字数能查、结构能查，但"讲清楚了没有"
只有脑子能判。所以代码跑到这一步就停手，打印一句「`note` 交给子 agent 写，任务单在 XXX」，
然后由主对话接手：看任务单 → 派 agent → 收作业 → 审核。

规矩全在 [`docs/SOP.md`](docs/SOP.md)：主对话只做派发、交接、盯预警、定去留；
每一步一个执行子 agent、一个**独立**审核子 agent（不共享执行者上下文）；
每个 Task 走 4 轮审核 + 一张四要素证据单；3 次不过就停，交给人，代码不自己绕过去。

---

## 安装

三步，顺序不能换。

### 第 1 步：装引擎

```bash
python scripts/setup_engines.py --check    # 先看缺什么
```text
默认只装**主管线环境**（约 0.1 GB，一分钟内）。然后按你要跑的线加：

| 命令 | 加装什么 | 实测体积 |
|---|---|---|
| `--line document` | 只要主管线（文档解析走 MinerU **云 API**） | ~0.1 GB |
| `--line fetch` | crawl4ai + yt-dlp | ~0.7 GB |
| `--line clean` | trafilatura + presidio | ~1.4 GB |
| `--line media` | funasr + torch + rapidocr | ~3.7 GB |
| `--all` | 除本地 MinerU 外全部 | ~7.0 GB |

**丑话说前面**：全装完要下 **5–8 GB**，耗时 **20–40 分钟**，torch 是大头。
按线装能省掉绝大部分——只跑文档线的话 0.1 GB 就够。

为什么一个引擎一个独立环境，不装一起：torch/funasr 与 opencv 的 numpy 互相打架，
crawl4ai 要 playwright，presidio 要 spaCy 加模型。装一起解析出来的版本集谁都不满足。
零件本来就是这么设计的——重依赖各自走桥脚本，解释器由环境变量指定。

主管线环境是「一个引擎一个独立环境」的唯一例外：它装进**你运行这个脚本时用的那个解释器**，
因为适配器就是用同一个解释器启动所有零件的。`pip install -e .` 装的是同一套
（`pyproject.toml` 里声明了），两条路走完都能 `import yaml`。

**本地 MinerU 不推荐。** 文档线是照着 MinerU 云 API 设计的，本地引擎是几 GB 模型干同一件事。
真要 `--mode local`，用它：`--line document-local`（~4.6 GB，含 pix2text 公式 OCR）。

**ffmpeg 不自动下载。** 在安装脚本里从互联网抓可执行文件是供应链风险，所以只检测 PATH，
找不到就告诉你装（Windows：`winget install Gyan.FFmpeg`），装完自己设 `FFMPEG`。

密钥按需自备，写进 `.env`（该文件不入库）：MinerU 云 API token、智谱 GLM key，
可选 DeepSeek / Anthropic。模板见 [`.env.example`](.env.example)，**里面全是空值**。

`MINERU_API_TOKEN` 是默认文档线**缺了就跑不动**的那一个——[mineru.net](https://mineru.net/)
注册送的免费额度够试手。其余都是可选项，只在质检评分和画面理解时才用得上。

### 第 2 步：拉零件

```bash
python scripts/setup_parts.py
```text
国内网络慢就加镜像：`--mirror gh-proxy`（2026-10-25 实测可用；这类站点寿命都不长，
失效时直接传完整 URL 前缀）。

### 第 3 步：验证

```bash
python -m pytest -q        # 524 passed
```text
---

## 跑起来

```bash
pip install -e .                                   # 装完就有 material-to-notes 命令
material-to-notes --version

# 或者不安装，临时把 src 加进路径
PYTHONPATH=src python -m material_to_notes.cli.main --version
```text
十一条子命令：

| 命令 | 干什么 |
|---|---|
| `init` | 初始化一个工作目录 |
| `route` | 看一个输入会走哪条线 |
| `run` | 把一条线端到端跑起来（`note` 步交子 agent） |
| `step` | 只跑一步（供主对话派给子 agent） |
| `intake` | 看/写投料单 |
| `deliver` | 把笔记拷到投料单指定的交付目录 |
| `assign` | 打印某步的任务单（派发用，会先给上一版产物留底） |
| `snapshots` | 列出某步留底过的产物版本 |
| `gate` | 跑某步的机器门禁 |
| `toc` | 用零件给笔记补/刷新篇内目录 |
| `checklist` | 打印某步的审核检查单 |

---

## 文档

| 文件 | 看什么 |
|---|---|
| [`docs/SOP.md`](docs/SOP.md) | 给 AI 的强制流程：派活 / 门禁 / 4 轮审核 / 证据单 / 组长验收五步 |
| [`docs/架构与目录契约.md`](docs/架构与目录契约.md) | 架构与目录布局；**现状以第十节「状态与变更记录」为准** |
| [`docs/contracts/接口契约.md`](docs/contracts/接口契约.md) | 每一步真正跑出去的命令与产物落点 |
| [`docs/穷举测试方案.md`](docs/穷举测试方案.md) | 路径穷举 / 边界严格 / 终点一致性 |
| [`docs/acceptance/每步验收标准.md`](docs/acceptance/每步验收标准.md) | 每一步的实测命令、硬卡与软卡 |
| [`docs/UPSTREAM.md`](docs/UPSTREAM.md) | 五个零件的来源、锁定版本、许可、两条硬规矩 |
| [`THIRD_PARTY.md`](THIRD_PARTY.md) | 第三方组件与许可索引；三件需特别注意的事 |

---

> `docs/` 下的文档用中文写。`README.md`（英文）与 `README_zh.md`（中文）保持同步，
> 其余文档只有中文版。

## 许可

**双轨**：[AGPL-3.0](LICENSE) 开源 + [商业授权](COMMERCIAL.md)。Copyright (c) 2026 Spiral QWQ。

AGPL 的网络条款意味着：任何人拿这套代码改一改再发布，**包括搭成网站给别人用**，
他改过的东西也必须以 AGPL 公开。不想满足这个条件的，走商业授权。

第三方组件与许可见 [`THIRD_PARTY.md`](THIRD_PARTY.md)——其中 mineru 用自定义许可、
pymupdf 是 AGPL/Artifex 双轨，这两条买商业授权时也要单独处理。

---

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。本项目特有的两条：**不许改 `parts/` 里的任何东西**
（零件的问题回灌上游，修完推上去再升锁表）；**不许提交机器路径、用户名、内部代号或密钥**。

---

## 更新日志

[CHANGELOG_zh.md](CHANGELOG_zh.md)（中文）· [CHANGELOG.md](CHANGELOG.md)（English）.

## 打赏

如果这个项目帮到了你，欢迎请我喝杯咖啡。打赏完全是自愿的——项目永远免费开源。

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="微信支付" width="200">
  <img src="assets/donate_alipay.jpg" alt="支付宝" width="200">
</p>
