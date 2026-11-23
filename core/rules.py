# -*- coding: utf-8 -*-
"""基线①：关键词规则。用于实验对照，也是 Agent 的兜底判断。"""
from __future__ import annotations

import re

STRONG = [
    "截止", "之前", "前完成", "请于", "务必", "抓紧", "尽快", "别忘", "不要错过",
    "报名", "提交", "上交", "交给我", "发给我", "私信我", "填写", "填表", "填报",
    "领取", "来拿", "来领", "签到", "参加", "参会", "开会", "集合", "缴费", "投保",
    "上报", "核对", "确认", "接龙", "投递", "请假",
]
WEAK = ["请", "务必", "@所有人"]

PAT_STRONG = re.compile("|".join(map(re.escape, STRONG)))
PAT_TIME = re.compile(r"(\d{1,2}[月.．]\d{1,2}|\d{1,2}[:：]\d{2}|明天|今天|本周|下周|今晚|截止|之前|前)")

# 明显的噪声：机器人战报、纯表情/图片
NOISE = re.compile(r"^(╔|╒|╠|├|\[图片\]$|\[动画表情\]$|\[视频\]$|\[表情\]$)")


def rule_score(text: str) -> tuple[int, float]:
    """返回 (是否待办, 置信度)。置信度是启发式：命中强动词+时间=0.8，仅强动词=0.6。"""
    t = text.strip()
    if not t or NOISE.match(t):
        return 0, 0.9
    hit = bool(PAT_STRONG.search(t))
    has_time = bool(PAT_TIME.search(t))
    if hit and has_time and len(t) >= 8:
        return 1, 0.80
    if hit and len(t) >= 10:
        return 1, 0.62
    return 0, 0.55
