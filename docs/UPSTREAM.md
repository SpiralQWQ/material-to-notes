# 零件来源卡 · UPSTREAM

> 本文件说明 `material-to-notes` 驱动的五个零件从哪来、锁在哪个版本、许什么愿。
> **零件代码不随本仓库发布。** 首次使用前先跑一条命令把它们取回来：
>
> ```bash
> python scripts/setup_parts.py
> ```
>
> 取回来的东西落在 `parts/<零件名>/`，那个目录被 `.gitignore` 排除，不入库。

---

## 一、为什么零件不入库

本仓库只放**编排层**——把五个零件串成一条线的那层代码。零件本身是五个独立的开源仓库，
各有自己的版本节奏、CHANGELOG、README 和许可。把它们复制进本仓库会造成同一个项目存在
两份权威副本：上游改了、副本忘了同步，两边行为就会分叉，而且分叉是静默的。

所以这里只存一个**锁表**：锁到哪个 commit、入口文件在哪、许可是什么。`setup_parts.py`
照这张表把零件取回来，`docs/架构与目录契约.md` 讲它们怎么被调用。

---

## 二、五个零件

| 零件 | 干什么 | 上游仓库 | 锁定 commit | 分支 | 入口 |
|---|---|---|---|---|---|
| `web-knowledge-crawler` | 取材：按词汇 + 站点爬网页 | [SpiralQWQ/web-knowledge-crawler](https://github.com/SpiralQWQ/web-knowledge-crawler) | `637115d5` | `main` | `app/crawl_all.py` |
| `document-to-markdown` | 文档线：PDF/Word/PPT → Markdown | [SpiralQWQ/document-to-markdown](https://github.com/SpiralQWQ/document-to-markdown) | `ce7d42a6` | `master` | `python -m dtmd` |
| `media-to-markdown` | 媒体线：视频/音频/图集 → Markdown | [SpiralQWQ/media-to-markdown](https://github.com/SpiralQWQ/media-to-markdown) | `6c09e200` | `master` | `python -m media_to_markdown` |
| `text-cleaning-engine` | 清洗：剥水印、去噪、归一化 | [SpiralQWQ/text-cleaning-engine](https://github.com/SpiralQWQ/text-cleaning-engine) | `aa44c14d` | `master` | `python -m cleaner.clean_md` |
| `md-rewrite-engine` | 写笔记：教学笔记格式规范 + 门禁 | [SpiralQWQ/md-rewrite-engine](https://github.com/SpiralQWQ/md-rewrite-engine) | `bbc8de76` | `master` | `python -m md_rewrite_engine` |

**许可**：五个零件都是**双轨**——AGPL-3.0 开源 + 商业授权（`COMMERCIAL.md`）。
版权归 `Spiral QWQ`。完整条款以各零件仓库里的 `LICENSE` 与 `COMMERCIAL.md` 为准。
（`web-knowledge-crawler` 的 `LICENSE` 表头是 AGPL 单栏格式，与另四个的双栏表头写法不同，
但同样是双轨。）

> **完整 40 位 SHA 在 `scripts/setup_parts.py` 的锁表里，那里是唯一事实源。**
> 上表写 8 位短前缀只是为了好看；要精确复现，以脚本为准，别照上表抄。

**为什么锁 commit 而不是追最新 master**：零件是会动的，而本仓库对零件有三个硬假设——
适配器写死了入口（`python -m dtmd`、`app/crawl_all.py`）；
`orchestrate/spec.py` 直接从 `md-rewrite-engine` 读笔记规范与门禁标签；
各零件的目录布局决定 `PYTHONPATH` 怎么拼。零件一改名、一挪目录、一改规范，
流水线不会报错，只会**静默地产出错东西**。所以锁，而且升级要当一件事来办。

---

## 三、两条硬规矩

### 规矩一：升级零件版本，必须先跑端到端

改 `scripts/setup_parts.py` 里的 commit 之前，先问自己一遍"我怎么知道换了之后还是对的"。
顺序是固定的：

1. 在上游仓库看清楚那个 commit 改了什么（尤其有没有动入口文件、目录布局、`configs/note_style_spec.yaml`、`scripts/gate_check.py`）
2. 改锁表 → `python scripts/setup_parts.py --update`
3. 跑全量测试：`python -m pytest -q`（当前基线 **514 passed**）
4. 用一份真实素材端到端跑一条线，确认产物形状没变
5. 上面四步全过，才提交

### 规矩二：零件的问题回灌上游，不在 `parts/` 里就地改

`parts/` 是取回来的快照，改它等于改一份没人会合并的副本。发现零件有问题：

1. 去那个零件的仓库提 issue 或 PR
2. 修合并、推送后，把新的 commit 号填进 `scripts/setup_parts.py` 的锁表
3. 按规矩一重新验证

---

## 四、常用命令

```bash
python scripts/setup_parts.py --check     # 只看缺谁，什么都不拉
python scripts/setup_parts.py             # 补齐缺失的
python scripts/setup_parts.py --update    # 全部重拉并按锁表对位
python scripts/setup_parts.py --force     # 丢掉现有副本，从头克隆
python scripts/setup_parts.py --mirror gh-proxy   # 走国内镜像
```

`--mirror` 收两种值：preset 名（目前只有 `gh-proxy`，2026-10-25 实测可用），
或者任意完整 URL 前缀。镜像站寿命都不长，preset 失效时直接传 URL 即可。

---

## 五、修改记录

| 日期 | 变动 |
|---|---|
| 2026-10-25 | 建立本文件。锁表全部对齐上游 master 顶点；`document-to-markdown` 由 `143d262` 升至 `ce7d42a6`（上游的「genericize local directory names」隐私加固提交，升级后全量仍 486 passed） |
