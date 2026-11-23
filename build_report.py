# -*- coding: utf-8 -*-
"""生成期末报告 docx。"""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = Path(__file__).resolve().parent
RES = BASE / "results"


def load_json(name, default=None):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


exp = load_json("experiment.json", [])
clf = load_json("clf_metrics.json", {})
feat = load_json("feature_ablation.json", [])

doc = Document()

# ---------- 页面与样式 ----------
sec = doc.sections[0]
sec.top_margin = Cm(2.5)
sec.bottom_margin = Cm(2.5)
sec.left_margin = Cm(2.8)
sec.right_margin = Cm(2.8)

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(10.5)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
normal.paragraph_format.line_spacing = 1.5
normal.paragraph_format.space_after = Pt(4)


def set_cn(run, font="宋体", size=10.5, bold=False, color=None):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def p(text, size=10.5, bold=False, align=None, indent=True, font="宋体", space_after=4):
    par = doc.add_paragraph()
    par.paragraph_format.line_spacing = 1.5
    par.paragraph_format.space_after = Pt(space_after)
    if indent:
        par.paragraph_format.first_line_indent = Pt(21)
    if align:
        par.alignment = align
    set_cn(par.add_run(text.replace("**", "")), font=font, size=size, bold=bold)
    return par


def h(text, level=1):
    par = doc.add_heading("", level=level)
    run = par.add_run(text)
    set_cn(run, font="黑体", size={1: 15, 2: 12.5, 3: 11}[level], bold=True, color=(0x1F, 0x2A, 0x44))
    par.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    par.paragraph_format.space_after = Pt(6)
    return par


def caption(text):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_after = Pt(8)
    set_cn(par.add_run(text), size=9, color=(0x55, 0x5F, 0x75))


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, hd in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(hd)
        set_cn(run, font="黑体", size=9.5, bold=True)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            set_cn(run, size=9.5)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if widths:
        for i, w in enumerate(widths):
            t.columns[i].width = Cm(w)
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def figure(path, cap, width=14.5):
    if not Path(path).exists():
        return
    doc.add_picture(str(path), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(cap)


# ================= 封面 =================
for _ in range(3):
    doc.add_paragraph()
par = doc.add_paragraph()
par.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_cn(par.add_run("《机器学习》课程期末项目报告"), font="黑体", size=22, bold=True)

par = doc.add_paragraph()
par.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_cn(par.add_run("群消息待办整理 Agent"), font="黑体", size=18, bold=True, color=(0x3B, 0x5B, 0xDB))
par = doc.add_paragraph()
par.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_cn(par.add_run("——用课程中的文本分类方法为 Agent 提供「判断」能力"), font="宋体", size=12,
       color=(0x44, 0x4C, 0x5E))

for _ in range(5):
    doc.add_paragraph()

info = [("课程名称", "机器学习"), ("姓名 / 学号", "＿＿＿＿＿＿ / ＿＿＿＿＿＿"),
        ("项目类型", "个人项目"), ("提交日期", "2026 年 11 月 27 日"),
        ("代码仓库", "msg2todo（本地可运行原型）")]
t = doc.add_table(rows=0, cols=2)
t.alignment = WD_TABLE_ALIGNMENT.CENTER
for k, v in info:
    cells = t.add_row().cells
    cells[0].text = ""
    set_cn(cells[0].paragraphs[0].add_run(k), font="黑体", size=11, bold=True)
    cells[0].width = Cm(4.5)
    cells[1].text = ""
    set_cn(cells[1].paragraphs[0].add_run(v), size=11)
    cells[1].width = Cm(8)

doc.add_page_break()

# ================= 摘要 =================
h("摘要", 1)
p("本项目把「群里消息太多、待办靠脑子记」这一日常问题，做成一个可运行、可评估、可复现的 "
  "Agent：用户粘贴一段群聊记录，系统返回结构化待办清单——要做什么、原文怎么写的截止时间、"
  "归一化后的具体日期、事项类别、以及是否需要人工确认。")
p("系统的核心设计是「判断交给分类器、生成交给大模型」：用 TF-IDF 字符 n-gram 加逻辑回归训练一个"
  "判别「是不是待办」的小模型作为门控，只把可能相关的消息交给大模型抽取字段。这样既把课程中的"
  "监督学习方法放在了系统的关键路径上，也在成本和稳定性上优于此前的两种简单做法。")
p("在自建的 300 条三群脱敏数据上，分类器在随机分层测试集上取得 F1 0.889、AUC 0.965；"
  "但跨群测试 F1 降至 0.538，暴露了「学到了群的语言风格」这一真实弱点。在 60 条系统测试集上，"
  "本方案 F1 0.839，优于纯大模型零样本（0.788）、关键词规则（0.733）与规则门控（0.643），"
  "同时把模型调用量从 60 次降到 23 次、成本降到 0.014 元。消融显示：去掉分类器门控后，"
  "效果退回到纯大模型水平而成本翻倍。此外，特征表示实验证明：scikit-learn 的默认按空格切词"
  "在中文本上只有 0.655 的交叉验证 F1，改用字符 n-gram 后提升至 0.794——这是复用组件时必须做的适配。")

# ================= 1 需求 =================
h("一、需求与目标", 1)
h("1.1 场景与痛点", 2)
p("我所在的三个微信群（班级群、年级群、娱乐群）每天产生大量消息。班级群里混着闲聊、表情包和"
  "「明天 13:00-14:00 来教学楼领书」这样的通知；年级群里是辅导员发布的长公告，一条消息里常常"
  "包含多个截止时间；娱乐群里几乎全是游戏战报与玩笑。")
p("现有做法的问题有三点：其一，信息与噪声混排，重要通知会被刷屏淹没；其二，时间表达高度口语化"
  "（「本周日（9.27）中午十二点之前」「9.28 晚 12 点之前」），需要人脑换算；其三，靠记忆管理"
  "待办，一旦漏掉就是真实的学业损失。这不是一个需要「更聪明的对话」的问题，而是一个"
  "「把非结构化文本变成结构化任务」的问题——恰好是课程中文本分类与信息抽取的用武之地。")
h("1.2 目标用户与成功标准", 2)
p("目标用户是本人及同专业同学。输入是一段或多条群消息（支持直接粘贴带时间行的聊天记录，系统自动"
  "按时间行切分），输出是待办清单，并支持导出 Excel / Word。")
p("可验证的成功标准定义如下：①在 60 条人工标注测试消息上，待办检测的精确率、召回率与 F1；"
  "②正确识别为待办的样本中，截止时间字段与金标准日期的一致性；③处理一条消息的平均模型成本与延迟；"
  "④低置信度消息是否能被标记为「需要人工确认」。这四条都可以用脚本重复测量，不需要主观打分。")
h("1.3 为什么需要机器学习，而不是只用大模型", 2)
p("直觉上，大模型可以直接读消息并输出待办，为什么还要训练一个分类器？理由有三：第一，成本。"
  "课程群里 70% 以上的消息是闲聊和战报，逐条调用大模型既慢又贵；一个本地分类器在毫秒级完成初筛，"
  "能把调用量削减一半以上（实测 60 条降到 23 条）。第二，可解释与可度量。分类器给出的是概率值，"
  "阈值可以调，效果可以用 F1 和混淆矩阵逐项核对；而「模型说它是」无法量化。第三，可离线降级。"
  "断网或接口故障时，本地分类器仍然工作，系统退化为「只筛不抽」，而不是整体不可用。"
  "文档也明确要求：单纯调用通用大模型 API 不足以构成机器学习环节——本项目的分类器正是这个环节。")

# ================= 2 方案 =================
h("二、方案与系统设计", 1)
h("2.1 总体架构", 2)
p("系统分为三层。数据层负责解析与脱敏；判断层是一个离线训练、离线推理的文本分类器；生成层是"
  "大模型与规则化的时间解析。三层通过 core/pipeline.py 串成一条链路，Web 服务与命令行共用同一套核心逻辑，"
  "因此「网页里看到的结果」与「实验里的数字」出自同一份代码。")
table(["层次", "组件", "输入", "输出"],
      [["数据层", "core/parse.py", "微信 txt 记录", "结构化消息 + 脱敏文本"],
       ["判断层", "models/clf.pkl（TF-IDF + LR）", "单条消息", "待办概率 p"],
       ["生成层", "DeepSeek API + core/timeparse.py", "消息 + 发出时间", "事项/时间原文/归一化时间"],
       ["交互层", "app/main.py + 静态页", "用户粘贴文本", "待办卡片、Excel/Word"]],
      widths=[2.2, 6.0, 4.2, 3.6])
caption("表 1  系统分层与各层职责")
figure(RES / "shot_main.png", "图 1  系统界面：左侧粘贴 4 条消息，右侧输出 3 条待办（其中 1 条闲聊被过滤）")
h("2.2 任务流程", 2)
p("一次分析包含五步。第一步，切分：若粘贴内容含「2026年11月23日 09:12」这类时间行，则按时间行切分为"
  "多条消息，否则整体视为一条。第二步，门控：分类器给出待办概率 p，p<0.35 判为噪声，直接跳过；"
  "0.35≤p<0.60 仍然处理但打上「建议人工确认」；p≥0.60 正常处理。第三步，抽取：把消息正文与"
  "「消息发出时间」一起交给大模型，要求输出 JSON（is_todo、task、due、category、evidence），"
  "其中 due 只允许摘录原文出现的时间表达，禁止自行推算。第四步，归一化：由本地规则把"
  "「明天 13:00-14:00」「9.28 晚 12 点之前」换算成 ISO 时间，并按当前时间归入"
  "「已过期/今天/三天内/一周内/更晚」。第五步，呈现：按紧急程度排序，支持逐条勾选、改写、导出。")
p("这里的职责划分是刻意的：**相对时间的换算不放给模型**。模型擅长理解语义，但在日期算术上会"
  "产生幻觉（例如把「下周二」算错一周）；规则实现虽然覆盖面有限，但结果确定、可测试、可复现。"
  "因此模型只负责「摘录」，代码负责「计算」。")
h("2.3 关键设计选择", 2)
p("选择一：不用 Agent 框架。流程只有五步，引入 LangChain 一类框架会带来黑盒与版本漂移，"
  "反而增加复现成本。选择二：不用 Web 框架。后端用标准库 http.server 手写三个接口（analyze / export / health），"
  "约 120 行，换来的是「一条命令启动、零额外依赖」。选择三：前端不用框架，原生 JS 约 300 行，"
  "没有构建步骤，任何一台装了 Python 的电脑双击 启动.bat 即可演示。")
h("2.4 失败与安全处理", 2)
p("系统对四类异常做了处理：①模型返回非法 JSON 时捕获异常，保留门控结果并把该条标记为需人工确认；"
  "②接口超时或断网时，pipeline 记录 error 字段，页面用黄色边框提示，不会静默丢弃；"
  "③时间解析失败（返回 None）时，页面显示「未提及时间」而不是猜一个日期；"
  "④隐私方面，脱敏发生在解析阶段，早于任何网络请求，因此发送给模型的文本不含姓名、学号、手机号。"
  "低置信度必须人工确认这一设计，也回应了「高影响结果不应自动决策」的要求。")

# ================= 3 方法 =================
h("三、机器学习方法", 1)
h("3.1 数据来源与标注", 2)
p("数据来自本人所在三个微信群各 100 条，共 300 条，保留原始的发送者昵称、时间与正文。"
  "三个群的构成差异极大：娱乐群 100 条中 0 条待办；年级群 26 条；班级群 57 条。这种不均衡是"
  "真实数据的特点，也直接构成了后文的跨群实验。")
p("标注规范明确四条：①待办指「要求群成员在某个时间点或截止时间前完成一个具体动作」，"
  "动作须有可定位的对象；②以消息发出时的语境判断，不因今天已过期而改判（是否过期交给运行时规则）；"
  "③类别限定为学业/事务/活动/生活/其他；④截止时间只摘录原文表达。"
  "标注流程是「大模型按规范预标 → 人工逐条复核」。复核时我逐条核对了 300 条，修正 7 条"
  "（例如把「实习岗位介绍，无截止无指令」从待办改为非待办，把「请大家积极报名献血」从非待办改为待办），"
  "一致率 97.7%，最终正例 83 条（27.7%）。")
p("需要说明的是：这是单人标注，没有第二人独立标注，因此无法报告标注者间一致性。"
  "我在报告中如实保留这一局限，而不是用「双人标注」的说法掩盖。")
h("3.2 预处理与脱敏", 2)
p("解析阶段把昵称映射为 [成员N]、群名映射为 [群N]，手机号与 9 位学号替换为占位符，"
  "长链接压缩为 [链接]，微信自动生成的文件名（如 微信图片_20261121110236_7230.dat）删除。"
  "这样既保护隐私，也降低了与任务无关的噪声。原始记录保存在 data/raw/，已加入 .gitignore。")
h("3.3 特征表示", 2)
p("中文没有空格，不能直接套用英文的「按空格切词」。本文使用字符级 n-gram（char_wb，1-3 元），"
  "配合 sublinear_tf 与最大 30000 维词表。选择 1-3 元的理由是：单字能覆盖「交」「领」等动词，"
  "二元与三元能捕捉「截止」「报名」「交给我」这类构式，而对 300 条的小样本来说，更长的 n-gram 只会"
  "增加维度、不会带来信息增量——这一点在第四章的消融中得到验证（1-4 元与 1-3 元打平）。")
h("3.4 模型与超参数", 2)
p("分类器选用 L2 正则的逻辑回归，class_weight='balanced' 以缓解 27.7% 的正例比例。"
  "选择逻辑回归而非线性 SVM 的原因是前者直接输出概率：门控需要 p<0.35 与 p<0.60 两个阈值，"
  "而 SVM 的 decision_function 不是概率，需要额外校准。超参数 C 在 {0.3, 1, 3, 10} 上做 5 折交叉验证选择，"
  "C=10 的 F1 最高（0.799），但各档差异在 0.005 以内，说明模型对该参数不敏感——这本身是一个有用的结论："
  "在小样本上，特征表示的影响远大于正则强度。")
h("3.5 基线", 2)
p("设置两条基线。规则基线：命中「截止/报名/提交/领取/缴费」等 40 余个关键词且长度足够即判为待办，"
  "并给出启发式置信度。大模型零样本基线：不做任何本地判断，把原文直接交给模型，让它同时完成分类与抽取。"
  "两者分别代表「不用机器学习」和「不用课程方法」的两种极端做法。")

# ================= 4 复用 =================
h("四、Skills 与组件复用", 1)
h("4.1 复用清单", 2)
table(["组件", "版本", "许可证", "用途", "本项目改动"],
      [["scikit-learn", "1.9.1", "BSD-3-Clause", "向量化与分类器", "改用 char_wb，调 C 与类别权重"],
       ["numpy", "2.3.5", "BSD-3-Clause", "数组运算", "无"],
       ["joblib", "1.6.0", "BSD-3-Clause", "模型持久化", "无"],
       ["openpyxl", "3.1.5", "MIT", "Excel 导出", "自定义列宽与表头样式"],
       ["python-docx", "1.2.0", "MIT", "Word 导出与报告排版", "表格样式与中文字体设置"],
       ["matplotlib", "3.11.2", "PSF-based", "实验图表", "中文字体回退"],
       ["DeepSeek API", "deepseek-chat", "服务条款", "字段抽取", "自定义提示词、JSON 模式、缓存"]],
      widths=[3.0, 2.2, 2.8, 3.4, 4.6])
caption("表 2  复用组件清单（未使用任何 Agent 编排框架）")
h("4.2 深入分析：TfidfVectorizer", 2)
p("本项目最关键的一个复用组件是 scikit-learn 的 TfidfVectorizer，它承担「把中文文本变成特征向量」"
  "这一子任务。它的输入是字符串列表，输出是稀疏的 TF-IDF 矩阵；关键参数 analyzer 决定切分方式，"
  "ngram_range 决定 n 元组范围，min_df/max_features 控制词表规模。")
p("它的默认配置是为英文设计的：analyzer='word' 依赖空白字符切词。中文句子没有空格，"
  "默认行为会把整句切成极少数几个 token。我用一条真实消息做了行为核验：输入"
  "「明天13:00-14:00在小程序订过书的来教学楼领书」，默认配置输出的词表是"
  "「明天13」「00」「14」「00在小程序订过书的来教学楼领书」这类碎片——它只按数字间的空格和标点断开，"
  "中文部分整段成为一个 token。这意味着默认配置在中文上等价于「整句哈希」，几乎无法泛化。")
p("这个核验直接决定了后续的适配工作：把 analyzer 改为 char_wb、ngram_range 改为 (1,3)，"
  "并加入 sublinear_tf。适配效果在第四章的特征消融中量化：默认配置 5 折交叉验证 F1 只有 0.655，"
  "改字符级后升至 0.794，提升 0.139。这不是「装个库就能用」的组件，而是必须读懂其默认假设、"
  "并用实验验证适配是否有效——这正是课程要求的「复用组件的实质工作」。")
h("4.3 核验与集成", 2)
p("除行为核验外，我还为其写了两类测试：一是单元级——固定一条消息，检查时间解析、规则判定与"
  "导出函数（tests/test_basic.py，共 20 项，全部通过）；二是结构级——对导出的 Word 文件做"
  "压缩包与内部关系校验，确认文件可被正常打开。集成中处理的具体问题包括：中文在 matplotlib 中"
  "显示为方块（需显式设置字体回退）、python-docx 的段落缩进不作用于中文字体（需设 eastAsia 字体）、"
  "openpyxl 写入长文本时不自动换行（需设 wrap_text）。")

# ================= 5 实验 =================
h("五、实验设计与结果", 1)
h("5.1 测试集与划分", 2)
p("数据划分两种。主实验：按「群 × 标签」分层随机抽取 60 条作为测试集（16 条待办），其余 240 条训练，"
  "随机种子固定为 20261123，保证可复现。跨群实验：用娱乐群 + 年级群共 200 条训练，"
  "把班级群 100 条整体作为测试集，用于观察域偏移。前者回答「同类数据上能做到多好」，"
  "后者回答「换个群还能不能用」。")
h("5.2 分类器结果", 2)
tm = clf.get("test", {})
cm_ = clf.get("cross_group", {})
p(f"在主测试集上，分类器精确率 {tm.get('precision')}、召回率 {tm.get('recall')}、F1 {tm.get('f1')}、"
  f"AUC {tm.get('auc')}；关键词规则基线在同一测试集上 F1 为 {clf.get('baseline', {}).get('f1')}。"
  f"跨群测试则明显下降：精确率 {cm_.get('precision')}、召回率 {cm_.get('recall')}、F1 {cm_.get('f1')}，"
  f"但 AUC 仍有 {cm_.get('auc')}。")
p("这个结果值得展开。跨群时精确率保持 1.0，召回率却跌到 0.368：模型几乎不误报，但把大量班级群的"
  "待办判成了非待办。原因是年级群的公告用词正式（「兹定于」「请于」），而班级群的通知极短且口语化"
  "（「下课来第二排找我领学生证」），模型在年级群上学到的「正式句式」无法迁移。AUC 仍有 0.894 说明"
  "排序能力还在，只是固定阈值 0.5 不再适用——这是一个可以直接改进的点：按目标群重新校准阈值。")
figure(RES / "fig_cm.png", "图 2  本方案在 60 条测试集上的混淆矩阵", width=9)
h("5.3 系统对照实验", 2)
rows = [[e["name"], e["precision"], e["recall"], e["f1"], e["acc"],
         e.get("due_acc"), f'{e["cost_yuan"]:.3f}'] for e in exp]
table(["方案", "精确率", "召回率", "F1", "准确率", "日期准确率", "成本(元)"], rows,
      widths=[5.6, 1.9, 1.9, 1.8, 1.8, 2.2, 2.0])
caption("表 3  五种方案在 60 条测试消息上的结果")
p("本方案（D）F1 0.839，高于纯大模型零样本（B，0.788）与关键词规则（A，0.733）。"
  "规则门控（C）表现最差（0.643），原因是关键词的正则覆盖不足，把「下课来找我领学生证」这类"
  "没有明显关键词的短指令挡在了外面——规则召回只有 0.562，比纯大模型低 0.25。"
  "这解释了为什么「用规则做门控」并不划算：规则的高精确是以漏掉大量口语化通知为代价的。")
p("消融（E，去掉分类器门控、其余完全相同）的 F1 为 0.788，与本方案相差 0.051，但成本从 0.014 元"
  "涨到 0.034 元，调用次数从 23 次涨到 60 次。也就是说，**分类器门控用 2.5 倍的调用换来了 0.05 的 F1**，"
  "并且把平均延迟从 776 ms 降到 554 ms。在大规模场景下，这个比例还会进一步放大。")
figure(RES / "fig_metrics.png", "图 3  五种方案的三项检测指标对比")
figure(RES / "fig_cost.png", "图 4  效果—成本权衡（左上为佳）", width=11)
h("5.4 特征表示消融", 2)
frows = [[f["config"], f["cv_f1"], f["cv_acc"], f["n_features"]] for f in feat]
if frows:
    table(["特征配置", "CV-F1", "CV-准确率", "特征数"], frows, widths=[6.4, 2.6, 3.0, 3.0])
    caption("表 4  TfidfVectorizer 特征表示消融（240 条训练集，5 折）")
p("表 4 是「复用组件适配」的定量证据：默认的按空格切词只有 0.655，字符二元 0.784，"
  "字符 n-gram（1-3）0.794，而 (1-4) 与 (1-3) 完全打平（0.794）却多出近 7000 个特征，"
  "在小样本上是纯粹的维度浪费。")
h("5.5 错误分析", 2)
p("本方案在 60 条测试集上漏报 3 条、误报 2 条，且 5 条错误全部发生在「模型已经调用」的情形，"
  "没有一条是分类器门控造成的——这说明在 0.35 的阈值下，门控的漏检代价已经很低，"
  "剩余瓶颈在抽取阶段的语义判断。逐条查看错误案例：")
for line in (RES / "error_cases.md").read_text(encoding="utf-8").splitlines():
    if line.startswith("- `"):
        p(line[2:].replace("`", ""), size=9.5, indent=False)
p("典型错误一：一条消息同时包含「成绩单和就业推荐表在付威涵同学那里，你们有空去 4031 拿一下」，"
  "信息量足但句式松散，模型判为否；典型错误二：「@所有人 还有需要的同学尽快把电子版发给我」，"
  "动作与对象都有，但缺少时间锚点，模型倾向于判否。相反方向的误报主要来自「@所有人」加长文本的"
  "招聘宣讲会通知——它们确实要求行动，但更像「信息分享」，标注规范与模型理解之间存在边界模糊。")
figure(RES / "fig_data.png", "图 5  三个群的待办分布（数据本身的域差异）", width=10)

# ================= 6 讨论 =================
h("六、讨论与改进", 1)
h("6.1 结论", 2)
p("三点结论。第一，把课程中的文本分类放在 Agent 的关键路径上是有效的：分类器门控在同一测试集上"
  "同时改善了效果（F1 +0.051）与成本（-58%），且提供了可解释的概率与可调的阈值。"
  "第二，复用组件必须读懂默认假设：TfidfVectorizer 的默认切词在中文上近乎失效，"
  "这是本项目最重要的一条工程经验。第三，小样本下方法间的差距可能落在噪声范围内，"
  "因此报告里给出的每一个数字都附带样本量与划分方式，避免过度解读。")
h("6.2 局限", 2)
p("局限有四。其一，数据规模小且单人标注，83 条正例使指标方差较大，"
  "0.05 量级的差异不应被当作稳定结论。其二，跨群泛化明显不足（F1 0.538），"
  "模型仍部分依赖群的语言风格。其三，类别模型（学业/事务/活动/生活）只有 0.56 的准确率，"
  "仅用于界面展示，未参与核心指标。其四，时间解析是规则实现，"
  "对「晚上 12 点」这类歧义表达会解析为 12:00，对「月底前」这类模糊表达则无法处理。")
h("6.3 改进方向", 2)
p("短期改进有三条，都有数据支撑：①按群分别校准阈值——跨群 AUC 0.894 说明排序能力仍在，"
  "只需重新选阈值即可把召回从 0.368 拉回；②把「@所有人 + 长文本 + 招聘宣讲」这一误报模式加入"
  "负例样本，预计可直接消掉当前 2 条误报；③用主动学习扩充标注：当前 300 条中仅 83 条正例，"
  "优先标注「模型概率落在 0.35-0.6 之间」的样本，边际收益最高。")
p("长期看，更有价值的方向是把「消息流」而非「单条消息」作为输入：真实场景中一个人的待办会跨消息"
  "演化（先发「报名截止 9 号」，隔天再发「今天最后一天」），把同一事项的多条消息聚类后再抽取，"
  "才能得到真正的「事项状态」。这已经超出本次课程作业的范围，但它是这个系统能否真正被人长期使用的关键。")

# ================= 参考文献 =================
h("参考文献", 1)
refs = [
    "[1] Pedregosa F, et al. Scikit-learn: Machine Learning in Python. JMLR, 2011, 12: 2825-2830.",
    "[2] Zhang X, Zhao J, LeCun Y. Character-level Convolutional Networks for Text Classification. NeurIPS, 2015.",
    "[3] Devlin J, et al. BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. NAACL, 2019.",
    "[4] Wei J, et al. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models. NeurIPS, 2022.",
    "[5] DeepSeek. DeepSeek API Documentation. https://api-docs.deepseek.com/, 2026.",
    "[6] 李航. 统计学习方法（第 2 版）. 清华大学出版社, 2019.",
    "[7] Kowsari K, et al. Text Classification Algorithms: A Survey. Information, 2019, 10(4): 150.",
    "[8] scikit-learn developers. TfidfVectorizer API Reference. https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html",
]
for r in refs:
    p(r, size=9.5, indent=False, space_after=2)

# ================= 附录 =================
h("附录 A  运行方法", 1)
for line in ["1. 双击 启动.bat（或命令行 python -m app.main）；",
             "2. 浏览器打开 http://127.0.0.1:8000；",
             "3. 左侧粘贴消息，点击「开始分析」；",
             "4. 右侧可逐条勾选/改写，点「导出 Excel」或「导出 Word」。",
             "5. 复现实验：python train.py → python cli.py experiment → python ablation_features.py。"]:
    p(line, size=9.5, indent=False, space_after=2)

h("附录 B  主要代码文件", 1)
table(["文件", "行数量级", "职责"],
      [["core/parse.py", "~130", "聊天记录解析与脱敏"],
       ["core/pipeline.py", "~190", "门控、抽取、归一化、排序"],
       ["core/timeparse.py", "~140", "中文时间表达归一化"],
       ["core/llm.py", "~110", "API 调用、缓存、并发"],
       ["app/main.py", "~200", "HTTP 服务与两个导出接口"],
       ["app/static/*", "~400", "单页前端"],
       ["train.py / cli.py", "~180", "训练与批量实验"]],
      widths=[4.4, 3.0, 7.0])
caption("表 5  核心代码文件与职责（完整代码见提交的代码仓库）")

h("附录 C  复用组件清单与许可证", 1)
p("本表用于说明每一项被复用组件的名称、版本、来源、许可证与具体用途；本项目未修改上述组件的源码，"
  "仅通过公开 API 调用与参数配置使用。", size=9.5, indent=False)
table(["组件", "版本", "来源", "许可证", "用途与改动"],
      [["Python", "3.12.14", "python.org", "PSF-2.0", "运行时，无改动"],
       ["scikit-learn", "1.9.1", "scikit-learn.org", "BSD-3-Clause", "TfidfVectorizer 改 char_wb；LogisticRegression 调 C 与 class_weight"],
       ["numpy", "2.3.5", "numpy.org", "BSD-3-Clause", "数组与数值运算，无改动"],
       ["joblib", "1.6.0", "joblib.readthedocs.io", "BSD-3-Clause", "模型持久化为 pkl，无改动"],
       ["openpyxl", "3.1.5", "openpyxl.readthedocs.io", "MIT", "Excel 导出；自定义表头样式与列宽"],
       ["python-docx", "1.2.0", "python-docx.readthedocs.io", "MIT", "Word 导出与本报告排版；设置 eastAsia 中文字体"],
       ["matplotlib", "3.11.2", "matplotlib.org", "PSF-based (BSD 兼容)", "实验图表；设置中文字体回退"],
       ["DeepSeek API", "deepseek-chat", "api-docs.deepseek.com", "服务条款", "字段抽取；自定义提示词、JSON 模式、响应缓存"]],
      widths=[3.0, 2.4, 4.2, 3.4, 6.0])
caption("表 6  复用组件清单（含来源与许可证）")
p("数据方面，300 条群消息由本人导出并在本地脱敏，未使用第三方数据集；因此不涉及数据集的许可证问题，"
  "但涉及个人信息保护，处理方式见第三章 3.2 节与 README。", size=9.5, indent=False)

out = BASE / "报告-群消息待办整理Agent.docx"
doc.save(out)
print("已生成:", out)
