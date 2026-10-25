# 第三方组件与许可 · THIRD PARTY

> 本文件登记 `material-to-notes` 依赖的外部组件及其许可。
> **许可信息以各组件自己的仓库与发布物为准**，这里是一份索引与提示，不是法律意见。
> 下表标注「已核」的，是 2026-10-25 从 PyPI 元数据或组件自身 `LICENSE` 读到的原值。

---

## 一、五个零件（被编排调用的独立项目）

五个零件**不随本仓库发布**，由 `scripts/setup_parts.py` 按锁表拉取。它们各自是独立仓库，
双轨授权（AGPL-3.0 开源 + 商业授权），版权归 `Spiral QWQ`。
仓库地址、锁定版本与入口见 [docs/UPSTREAM.md](docs/UPSTREAM.md)。

| 零件 | 许可 |
|---|---|
| `web-knowledge-crawler` | AGPL-3.0 + 商业（`COMMERCIAL.md`） |
| `document-to-markdown` | AGPL-3.0 + 商业 |
| `media-to-markdown` | AGPL-3.0 + 商业 |
| `text-cleaning-engine` | AGPL-3.0 + 商业 |
| `md-rewrite-engine` | AGPL-3.0 + 商业 |

---

## 二、Python 依赖

按零件分组的 `requirements.txt` 汇总。`setup_engines.py` 会为每个引擎建独立环境安装。

### 文档线 · document-to-markdown

| 包 | 许可 | 用途 |
|---|---|---|
| `mineru` | **`LicenseRef-MinerU-Open-Source-License`**（自定义，非 OSI 标准） | 文档解析引擎。⚠️ 见下方「需要特别注意的三件事」 |
| `pymupdf` | **AGPL-3.0 或 Artifex 商业许可（双轨）** | PDF 切片/渲染。⚠️ 见下方「需要特别注意的三件事」 || `mistune` | BSD-3-Clause | Markdown 语法门禁 |
| `camelot-py` | MIT | 表格复核 |
| `pikepdf` | MPL-2.0 | 坏 PDF 急救 |
| `requests` | Apache-2.0 | 云端 API 上传/轮询 |

### 媒体线 · media-to-markdown

| 包 | 许可 | 用途 |
|---|---|---|
| `torch` | Apache-2.0 / BSD / BSL-1.0 等**混合** | 深度学习底座。⚠️ 见下方「需要特别注意的三件事」 |
| `funasr` | MIT | 语音转写 |
| `rapidocr-onnxruntime` | Apache-2.0 | 图片 OCR |
| `opencv-python` | Apache-2.0 | 图像处理 |
| `rapidfuzz` | MIT | 模糊匹配 |
| `numpy` | BSD-3-Clause（捆绑多种宽松许可） | 数值计算 |
| `soundfile` | BSD-3-Clause | 音频读写 |
| `pypinyin` | MIT | 拼音处理 |
| `python-dotenv` | BSD-3-Clause | `.env` 读取 |

### 取材线 · web-knowledge-crawler

| 包 | 许可 | 用途 |
|---|---|---|
| `crawl4ai` | Apache-2.0 | 网页抓取 |
| `playwright` | Apache-2.0 | 浏览器自动化（crawl4ai 依赖） |

### 清洗线 · text-cleaning-engine

| 包 | 许可 | 用途 |
|---|---|---|
| `presidio-analyzer` | MIT | 个人信息识别与脱敏 |
| `spacy` | MIT | 自然语言处理底座 |
| `trafilatura` | Apache-2.0 | 正文提取 |
| `clean-text` | Apache-2.0 | 文本清洗 |
| `snownlp` | MIT | 中文情感/分词 |
| `sentencex` | MIT | 句子切分归一化 |
| `jsonschema` | MIT | 配置校验 |
| `PyYAML` | MIT | YAML 读取 |

### 编排层自身

| 包 | 许可 | 用途 |
|---|---|---|
| `PyYAML` | MIT | 读取 `configs/pipeline.yaml` |
| `requests` | Apache-2.0 | 子进程之外的少量 HTTP |

编排层 `pyproject.toml` 的 `dependencies` 为空——它不直接依赖第三方包，只通过
`subprocess` 调用零件。

---

## 三、需要特别注意的三件事

### ① `mineru` 用的是自定义许可

PyPI 上它的许可表达式是 `LicenseRef-MinerU-Open-Source-License`，**不是** MIT / Apache / BSD
这类标准许可，也不在 OSI 批准清单里。意思是：能不能商用、要不要开源改动，得去读它自己仓库里
那份许可的原文，不能按"看起来开源"推断。

本仓库的文档线**默认走 MinerU 云端 API**，本地 MinerU 只在 `--mode local` 时才需要。
云端模式同样受 MinerU 服务条款约束，需要自备 API token。

### ② `pymupdf` 是 AGPL 与商业的双轨

它有两种选择：按 AGPL-3.0 用（那就得满足 AGPL 的全部义务，包括网络场景下的源码开放），
或者向 Artifex 买商业许可。本仓库整体是 AGPL-3.0，走第一条路是自洽的；
但**如果你买了 `material-to-notes` 的商业授权，PyMuPDF 这一层仍要单独处理**——
买我们的授权不附带 Artifex 的授权。

**它不能像本地 MinerU 那样跳过。** 常见误会是把 pymupdf 当成"本地模型"，
其实它是一个 PDF 工具箱（MuPDF 这个 C 库的 Python 绑定）——不下载模型、不跑推理、
纯 CPU。云端路径照样需要它：MinerU 云 API 单个文件有 200 页上限，
上传前必须把大 PDF 物理切成小文件，这个切割就是 pymupdf 干的
（`dtmd/convert/base.py::make_slice`，`cloud.py` 每个块都会调）。
装出来约 54 MB，和 mineru 那种 GB 级不是一回事。

### ③ `torch` 的许可是混合的

它的许可表达式是一串 `AND`：Apache-2.0、BSD-2-Clause、BSD-3-Clause、BSL-1.0、MIT 等。
其中 **BSL-1.0（Business Source License）不是 OSI 认可的开源许可**，它带"到期后自动转为
开放许可"的条款。分发包含 torch 的产物时，这一条要看清。

---

## 四、非 Python 外部工具

这些由 `setup_engines.py` 安装或引导安装，**不随本仓库分发**，所以本仓库不继承它们的分发义务；
但你在自己机器上装来用时，各自的条款对你生效。

| 工具 | 许可 | 说明 |
|---|---|---|
| `ffmpeg` | LGPL-2.1+ **或** GPL-2.0+，取决于构建时开的选项 | 音视频处理。⚠️ 网上大部分 Windows 预编译包是 **GPL** 版本，自己分发它会连带 GPL 义务 |
| `yt-dlp` | Unlicense（公共领域） | 视频下载。无义务，但**下载什么内容是站点条款的问题**，与本项目无关 |
| `git` | GPL-2.0 | 拉取零件用 |

### 模型文件

语音、OCR、NLP 模型是运行时下载的，**每个模型有自己的许可**，安装时看它自己包里的元数据：

- FunASR / SenseVoice 系列模型（ModelScope）
- RapidOCR 的 ONNX 模型
- spaCy 的 `*_core_web_*` 模型

这些不在上表的 Python 包许可覆盖范围内。

---

## 五、外部服务（需自备凭证）

本仓库不含任何密钥。用到的服务都要你自己注册并遵守各自条款：

| 服务 | 用在哪 | 说明 |
|---|---|---|
| MinerU 云 API | 文档线云端模式 | 需 API token |
| 智谱 GLM | 媒体线画面理解 / mre 质检评分 | 需 API key |
| DeepSeek | 可选的评分通路 | 需 API key |
| Anthropic Claude | 可选的评分通路 | 需 API token |
| ModelScope | 下载 FunASR 等模型 | 一般无需凭证 |

---

## 六、复核方式

上表「已核」项的来源：2026-10-25 读 PyPI JSON API 的 `license_expression` 字段
（PEP 639 的新标准字段），以及本机已装环境的 `.dist-info/METADATA`。
PyPI 的旧 `license` 自由文本字段对很多包是空的，所以没有采信它。
