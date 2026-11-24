# 群消息待办整理 Agent

把刷屏的校园群聊整理成一张可执行的清单：**本地分类器判断「是不是待办」→ 大模型抽取「要做什么、什么时候截止」→ 时间归一化与过期判定 → 导出 Excel / Word**。

![界面预览](results/shot_main.png)

课程：《机器学习》期末项目 · 个人完成

---

## 1. 它解决什么问题

学生群每天几十上百条消息，作业、材料、缴费、开会通知和闲聊、表情包、游戏战报混在一起。人工翻记录的成本高、漏 DDL 的代价大。
本 Agent 的输入是一段（或多条）群消息，输出是结构化待办清单：事项、原文时间、归一化截止时间、分类、置信度、是否需要人工确认。

**成功标准**（可量化）：在 60 条人工标注的测试消息上，待办检测 F1、截止时间抽取准确率、单条处理成本与延迟。

## 2. 快速开始

### 2.0 前置要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（`启动.bat` 是 Windows 批处理；macOS / Linux 用 2.4 的命令行方式） |
| Python | 3.10 及以上（本项目在 3.12.14 上测试） |
| 磁盘 | 依赖装好后约 120 MB（scikit-learn 及其依赖占主要部分） |
| 网络 | 首次 `pip install` 需要联网；不填 API Key 也能运行（见 2.5 离线模式） |

### 2.1 获取代码（访问者必做的第一步）

```bash
git clone https://github.com/no-Ccarp/msg2todo.git
cd msg2todo
```

不会用 git 的话：在仓库页面点绿色 **Code → Download ZIP**，解压到任意本地目录。

> ⚠️ **必须先把代码下载到本地磁盘。** 在 GitHub 网页上点开 `启动.bat` 只会显示它的源码，
> 浏览器不能执行本地脚本；也没有任何在线服务能在你本地启动一个服务。这一步没有捷径。

### 2.2 安装依赖

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS / Linux
```

首次安装约 1–3 分钟。依赖清单见 `requirements.txt`（scikit-learn / numpy / joblib / matplotlib / openpyxl / python-docx）。

### 2.3 配置 API Key（可选）

```bash
copy .env.example .env        # Windows；macOS/Linux 用 cp
```

编辑 `.env`，把 `LLM_API_KEY` 换成你自己的 DeepSeek Key。**不配也能启动**，只是抽取质量下降，见 2.5。

### 2.4 启动

```bat
:: Windows：双击，或在项目目录执行
启动.bat

:: 任意平台：命令行等价写法
.venv\Scripts\python train.py          :: 首次会训练并生成 models/clf.pkl
.venv\Scripts\python -m app.main       :: 启动本地服务
```

浏览器打开 <http://127.0.0.1:8000>，粘贴消息 → 点「开始分析」。
`启动.bat` 会自动检查虚拟环境、缺依赖就装、缺模型就训练，然后启动服务并打开浏览器；
**那个命令行窗口要保持开着**，关掉服务就停。

### 2.5 离线模式（没有 API Key 也能跑）

未配置 `LLM_API_KEY` 时，系统自动降级：分类器照常判断「是不是待办」，截止时间由规则从原文摘取，
不调用任何外部服务。此时界面会显示「离线模式」标记，抽取字段比完整模式粗糙（比如不会把一句话
改写成简洁的任务描述），但**整条链路仍可跑通、可演示、可复现**。

配置 Key 后无需改代码，重启服务即切换到完整模式。

## 3. 目录结构

```
msg2todo/
├─ 启动.bat              # 双击启动
├─ .env.example          # 密钥模板（真实 .env 不入库）
├─ requirements.txt
├─ core/                 # 与界面无关的核心逻辑
│  ├─ parse.py           # 聊天记录解析 + 脱敏（手机号/学号/昵称/链接）
│  ├─ rules.py           # 关键词规则基线
│  ├─ timeparse.py       # 中文时间表达归一化（明天/本周日/9.27/中午十二点…）
│  ├─ llm.py             # DeepSeek 调用：重试、磁盘缓存、并发、token 统计
│  └─ pipeline.py        # 分类器门控 → 大模型抽取 → 校验 → 过期分组
├─ app/
│  ├─ main.py            # 标准库 http.server（3 个接口 + 静态文件）
│  └─ static/            # 单页前端（原生 HTML/CSS/JS，无构建）
├─ models/               # clf.pkl（待办分类器）、cat.pkl（类别模型）
├─ data/                 # messages.jsonl / labels.jsonl / split.json；raw/ 为原始记录（不入库）
├─ results/              # 实验指标、图表、错误分析、缓存
├─ train.py              # 训练 + 交叉验证 + 跨群测试 + 规则基线
├─ cli.py                # 批量实验 / 单条分析 / 数据统计
├─ prepare_data.py       # 金标准固化与数据划分
├─ label.py              # 大模型按规范预标注（结果经人工复核）
├─ ablation_features.py  # 特征表示消融（word vs char vs char_wb）
├─ analyze_results.py    # 出图 + 错误案例
└─ tests/test_basic.py   # 20 项离线自检（不调用模型）
```

## 4. 复现实验

```bat
.venv\Scripts\python core\parse.py           :: 解析 + 脱敏 → data/messages.jsonl
.venv\Scripts\python label.py                :: 预标注（需 API，可用缓存）
.venv\Scripts\python prepare_data.py         :: 人工复核固化 + 数据划分
.venv\Scripts\python train.py                :: 分类器指标 → results/clf_metrics.json
.venv\Scripts\python cli.py experiment       :: 5 组对照 → results/experiment.json
.venv\Scripts\python ablation_features.py    :: 特征消融
.venv\Scripts\python analyze_results.py      :: 图表与错误分析
.venv\Scripts\python tests\test_basic.py     :: 自检
```

## 5. 主要结果（60 条测试集，16 条待办）

| 方案 | 精确率 | 召回率 | F1 | 成本(元) |
|---|---|---|---|---|
| A 关键词规则 | 0.786 | 0.688 | 0.733 | 0 |
| B 纯大模型零样本 | 0.765 | 0.812 | 0.788 | 0.034 |
| C 规则门控+大模型 | 0.769 | 0.625 | 0.690 | 0.009 |
| **D 分类器门控+大模型（本方案）** | **0.867** | **0.812** | **0.839** | **0.014** |
| E 消融：去掉分类器门控 | 0.765 | 0.812 | 0.788 | 0.034 |

分类器本体（离线、CPU）：随机分层测试集 F1 0.889 / AUC 0.965；跨群测试 F1 0.538（域偏移明显，详见课程提交的报告 PDF）。

> **关于可重复性**：大模型的输出即使 `temperature=0` 也并非严格确定。同一配置重复运行时，D 组 F1 在 0.80–0.84、C 组在 0.64–0.69 之间浮动（一次运行内约 ±1–2 条样本）。上表是一次完整运行的结果；多次运行中「D 组最优、门控把成本降约六成」的结论保持一致。想自己复现：`python cli.py experiment`（会真实调用模型，约 ¥0.2）。

## 6. 数据与隐私

- 数据来自本人所在三个微信群各 100 条，共 300 条；已在解析阶段脱敏：昵称→`[成员N]`、群名→`[群N]`、手机号→`[手机号]`、学号→`[学号]`、长链接→`[链接]`、微信附件文件名→删除。
- `data/raw/` 含原始记录，已在 `.gitignore` 中排除，不随仓库发布。
- 仅脱敏后的消息正文会发送给模型服务；密钥只从环境变量读取，不写入任何文件。

## 7. 复用组件

| 组件 | 版本 | 许可证 | 用途 |
|---|---|---|---|
| Python | 3.12.14 | PSF-2.0 | 运行时 |
| scikit-learn | 1.9.1 | BSD-3-Clause | TF-IDF 与逻辑回归 |
| numpy | 2.3.5 | BSD-3-Clause | 数值计算 |
| joblib | 1.6.0 | BSD-3-Clause | 模型序列化 |
| openpyxl | 3.1.5 | MIT | Excel 导出 |
| python-docx | 1.2.0 | MIT | Word 导出 |
| matplotlib | 3.11.2 | PSF-based (BSD 兼容) | 图表 |
| DeepSeek API | deepseek-chat | 服务条款 | 待办字段抽取 |

详见课程提交的报告 PDF 中「Skills 与组件复用」一节（含对 TfidfVectorizer 的行为核验与适配实验）。

## 8. 已知局限

- 300 条、单人标注，正例仅 83 条，指标方差大；类别模型（学业/事务/活动/生活）准确率仅 0.56，只用于界面展示。
- 跨群泛化明显下降（F1 0.889 → 0.538），说明模型仍部分依赖“群的语言风格”。
- 时间解析是规则实现，"晚上12点" 这类歧义表达会被解析为 12:00，属已知不足。

## 9. 常见问题

**页面显示「Failed to fetch」或右上角红点「服务未连接」**
说明浏览器里的页面还在，但后台的 Python 进程已经退出（关掉了启动窗口、或电脑重启过）。
页面只是外壳，分析逻辑全在后台进程里，所以必须重新启动：

```bat
启动.bat
```

看到「服务已启动：http://127.0.0.1:8000」后，回到浏览器按 F5 刷新即可。
注意：`启动.bat` 的那个命令行窗口必须一直开着，关掉它服务就停了。

**端口被占用（address already in use）**
说明已有一个实例在跑，直接打开 http://127.0.0.1:8000 即可；或换端口：
`.venv\Scripts\python -m app.main --port 8010`（需同步修改 app/main.py 中的 PORT，或用环境变量）。

**分析很慢**
每条消息约 0.5–3 秒，取决于模型服务的响应速度；一次粘贴 10 条会并发处理，
总耗时约为 2–4 秒 + 单条时间。首次调用还需加载模型，会多 1–2 秒。
