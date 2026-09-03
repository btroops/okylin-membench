# -*- coding: utf-8 -*-
"""内置参考智能体：三种具有代表性、行为可预期的记忆策略。

用途：
1. 在没有外部智能体/LLM API 时，端到端验证评测流水线；
2. 验证 benchmark 的区分度——三种策略应当产出明显不同的六维雷达图；
3. 作为接入真实智能体时的行为对照基线。

- NoMemoryAgent   每轮对话结束即失忆（记忆库恒为空）
- NaiveMemoryAgent 全量照记：所有用户消息原样持久化（包括敏感信息），
                   回答时回放最相似的历史消息（先命中旧的，不会更新）
- SmartMemoryAgent 规则记忆：句子级槽位抽取、冲突覆盖、拒绝持久化敏感信息、
                   模板/操作复用，并支持 /write 文件工具
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

from .base import AgentAdapter

# 敏感信息：密码 / 口令 / 验证码 / token / api key / 身份证
SECRET_RE = re.compile(
    r"(密码|口令|验证码|otp|password|api[-_ ]?key|token|身份证)", re.IGNORECASE)

QUESTION_RE = re.compile(r"[?？]|吗[。！!]?$|是什么|什么名字|哪里|多少|怎么|哪些")

IDK_REPLY = "这个我暂时不确定，你可以再告诉我一次。"
SECRET_REFUSE_REPLY = "出于安全考虑，我不会记住密码、验证码这类敏感信息，请你自己妥善保存。"

_SENT_SPLIT_RE = re.compile(r"[。？！?!;；\n]+")
_TRAILING_PARTICLES_RE = re.compile(r"[了啦哦呀哟呗\s]+$")

PET_ADJ = r"(大|小|黑|白|花|橘|老|幼)?"


def _clean_value(s: str) -> str:
    """清理抽取出的槽位值：去掉句尾语气词与首尾空白。"""
    return _TRAILING_PARTICLES_RE.sub("", s.strip()).strip()


def _write_file(workdir: str, content: str) -> Optional[Tuple[str, str]]:
    """解析 /write 指令：'/write 相对路径 内容...'，成功返回 (路径, 内容)。"""
    m = re.match(r"^/write\s+(\S+)\s*(.*)$", content, re.DOTALL)
    if not m:
        return None
    rel, body = m.group(1), m.group(2)
    rel = rel.strip().lstrip("/")
    path = os.path.abspath(os.path.join(workdir, rel))
    workroot = os.path.abspath(workdir)
    if not path.startswith(workroot):  # 防目录穿越
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return rel, body


class NoMemoryAgent(AgentAdapter):
    """无长期记忆：session 结束后全部遗忘。

    预期画像：边界识别满分（什么都不存），其余维度接近 0。
    """
    name = "nomem"

    def __init__(self) -> None:
        self._workdir = "."

    def new_episode(self, workdir: str) -> None:
        self._workdir = workdir

    def session_start(self, session_id: str) -> None:
        pass

    def send_user(self, content: str) -> str:
        if content.startswith("/write"):
            res = _write_file(self._workdir, content)
            return "已写入。" if res else "写入失败。"
        if QUESTION_RE.search(content):
            return IDK_REPLY
        return "好的，了解了。"

    def session_end(self) -> None:
        pass  # 无状态

    def memory_dump(self) -> Optional[List[str]]:
        return []


class NaiveMemoryAgent(AgentAdapter):
    """全量照记型：把所有用户消息原样存档，回答时回放"最像"的那条。

    预期画像：长期保持/记忆调用较好，但动态更新、相近区分失败
    （总回放旧消息），边界识别失败（敏感信息被持久化甚至复述）。
    """
    name = "naive"

    def __init__(self) -> None:
        self._store: List[str] = []
        self._workdir = "."

    def new_episode(self, workdir: str) -> None:
        self._store = []
        self._workdir = workdir

    def session_start(self, session_id: str) -> None:
        pass

    def send_user(self, content: str) -> str:
        if content.startswith("/write"):
            res = _write_file(self._workdir, content)
            if res:
                self._store.append(content)
                return "已写入。"
            return "写入失败。"
        reply = self._recall(content)
        self._store.append(content)
        return reply

    def _recall(self, question: str) -> str:
        """回放与问题字符重合度最高的历史消息；并列时取最早的（永不更新）。"""
        best, best_score = None, 0.0
        for item in self._store:  # 当前问题尚未入 store
            overlap = _char_overlap(question, item)
            if overlap > best_score:
                best, best_score = item, overlap
        if best is None or best_score <= 0.05:
            return IDK_REPLY
        # 直接把旧消息"背"出来 —— 全量照记智能体的典型失败模式
        return re.sub(r"^(我的|我想|请记住[:：]?)", "你说过：", best)

    def session_end(self) -> None:
        pass  # 已实时落库

    def memory_dump(self) -> Optional[List[str]]:
        return list(self._store)


def _char_overlap(a: str, b: str) -> float:
    a2 = set(a) - set(" ，。？！.,?!我的请帮\n")
    b2 = set(b)
    if not a2:
        return 0.0
    return len(a2 & b2) / len(a2)


class SmartMemoryAgent(AgentAdapter):
    """规则记忆型：句子级槽位抽取 + 冲突覆盖 + 敏感拒绝 + 模板/操作复用。

    预期画像：六个维度整体较好（作为"好学生"基线）。
    """
    name = "smart"

    _RE_NAME = re.compile(r"我叫([\u4e00-\u9fa5A-Za-z·]{1,12})")
    _RE_JOB = re.compile(r"职业(?:是|为)\s*([\u4e00-\u9fa5A-Za-z]{1,15})")
    _RE_PROJECT = re.compile(r"(?:最近|现在|在)?(?:做|搞|弄|研发)\s*([A-Za-z][\w\-]{1,30})(?:这个|那个|项目)?")
    _RE_LANG_SKILL = re.compile(r"(?:我会|我只会|我(?!不)\S{0,2})?\s*(Python|Go|Java|Rust|C\+\+|C#|Ruby|PHP|TypeScript|JavaScript|Scala|Kotlin|Swift)\b")
    _RE_LANG_NOSKILL = re.compile(r"(?:我不会|不懂|不熟悉|没学过|只(?!用过))[^。，,]*?(Python|Go|Java|Rust|C\+\+|C#|Ruby|PHP|TypeScript|JavaScript|Scala|Kotlin|Swift)\b")
    _RE_HOME = re.compile(r"(?:我住在|我家在|家庭地址是)([^。，,；;！!？.\s]{2,40})")
    _RE_NICK = re.compile(r"(?:常用)?昵称(?:是|叫)\s*([\w\u4e00-\u9fa5\-]{1,20})")
    _RE_HOME_UPDATE = re.compile(
        r"(?:我家|我|家)(?:现在)?(?:搬(?:到|去|至)|住到|迁到)([^。，,；;！!？.\s]{2,40})")
    _RE_DATE_EVENT = re.compile(
        r"(20\d{2}[-/年]?\d{1,2}[-/月]?\d{1,2}日?)[，,]?\s*"
        r"((?:我[\u4e00-\u9fa5A-Za-z0-9]*\s*)?[^。.!！;；\n]{2,40})")
    _RE_WORK = re.compile(
        r"(?:公司|办公室)(?:地址)?(?:现在)?(?:在|搬到|迁到)([^。，,；;！!？.\s]{2,40})")
    _RE_PHONE = re.compile(
        r"(?:手机号|电话|手机)(?:号码)?[^0-9]{0,6}?(?:是|改为|换成)\s*([0-9+\-]{5,25})")
    _RE_IP = re.compile(
        r"(外网|公网|内网|局域网)?\s*(?:IP|ip)\s*(?:地址)?\s*(?:是|为)\s*([0-9.]{7,15})")  # 用 finditer
    _RE_EDITOR_A = re.compile(
        r"默认(?:的)?(编辑器|浏览器|终端|输入法|shell)(?:是|换成|改为|用)\s*([\w\u4e00-\u9fa5\-./]{1,24})")
    _RE_EDITOR_B = re.compile(
        r"用\s*([\w\u4e00-\u9fa5\-./]{1,24})\s*(?:作为|当)(?:我的)?默认(?:的)?(编辑器|浏览器|终端|输入法|shell)")
    _RE_PET = re.compile(
        r"(?:我[又还再]?[养拥有]了?一?只?|[又还再]?[养拥有]了?一?只?|我家的?|我们家)?" + PET_ADJ +
        r"(猫|狗)(?:的名字)?[，,]?(?:叫|名字叫|名字是)([^。，,；;！!？.\s]{1,15})")
    _RE_ALLERGY = re.compile(
        r"(?:我|对)(?:对)?(花生|芒果|海鲜|牛奶|鸡蛋|麸质|坚果)(?:过敏|不耐受)")
    _RE_ALLERGY2 = re.compile(
        r"(?:过敏源|忌口)(?:是|为)\s*(花生|芒果|海鲜|牛奶|鸡蛋|麸质|坚果)")
    _RE_SCHEDULE = re.compile(
        r"(下周[一二三四五六日天]|周[一二三四五六日天]|明天|后天|大后天)(?:我|我们)?(?:有|要)(?:一个)?"
        r"([\u4e00-\u9fa5A-Za-z]{1,12}?(?:评审会|会议|约会|面试|体检|生日|会))")
    _RE_PROC = re.compile(
        r"(?:安装|部署|卸载)\s*([\w][\w.\-]{0,40})[^。；;\n]*?"
        r"(?:命令是|命令为|命令|方式是|步骤是|用的是|直接用)\s*([^。；;\n]{2,120})")
    _RE_INSTALL_BARE = re.compile(
        r"(?:装|安装|部署|卸载|再加?一个?)\s*([\w][\w.\-]{0,40})")
    _RE_OP = re.compile(
        r"((?:清理|清除)[^。；;\n]{0,6}缓存|更新系统|备份[^。；;\n]{0,8}|重启[^。；;\n]{0,6}服务)"
        r"[^。；;\n]*?(?:命令|操作)(?:是|用|为)\s*((?:sudo\s+)?[a-zA-Z][^。；;\n]{1,60})")
    _RE_TEMPLATE = re.compile(
        r"(.{1,12}?)(?:的)?(模板|规范|格式)[：:]?(.+)")
    _RE_COMMIT_RULE = re.compile(r"提交信息必须以\s*([A-Za-z]+-)\s*开头")
    _EDITOR_NOUNS = ("编辑器", "浏览器", "终端", "输入法", "shell")

    def __init__(self) -> None:
        self._slots: Dict[str, str] = {}      # 槽位事实
        self._procs: Dict[str, str] = {}      # 安装目标 -> 命令模板（{pkg} 占位）
        self._ops: Dict[str, str] = {}        # 运维操作 -> 命令
        self._templates: Dict[str, str] = {}  # 模板/规范
        self._commit_prefix: str = ""         # 提交信息规范前缀
        self._events: List[tuple] = []        # (date, event) 按日期升序
        self._installed: List[str] = []       # 多 session 累积的安装列表
        self._workdir = "."

    # ---- 生命周期 -------------------------------------------------------
    def new_episode(self, workdir: str) -> None:
        self._slots, self._procs, self._ops, self._templates = {}, {}, {}, {}
        self._commit_prefix = ""
        self._events = []
        self._installed = []
        self._workdir = workdir

    def session_start(self, session_id: str) -> None:
        pass

    def session_end(self) -> None:
        pass

    def memory_dump(self) -> Optional[List[str]]:
        items = ["%s = %s" % (k, v) for k, v in self._slots.items()]
        items += ["procedure[%s] = %s" % (k, v) for k, v in self._procs.items()]
        items += ["op[%s] = %s" % (k, v) for k, v in self._ops.items()]
        items += ["template[%s] = %s" % (k, v) for k, v in self._templates.items()]
        if self._commit_prefix:
            items.append("commit_prefix = " + self._commit_prefix)
        for d, e in self._events:
            items.append("event[%s] = %s" % (d, e))
        for p in self._installed:
            items.append("installed = " + p)
        return items  # 敏感信息从不进入这里

    # ---- 对话 -----------------------------------------------------------
    def send_user(self, content: str) -> str:
        if content.startswith("/write"):
            return self._handle_write(content)
        reply = self._answer(content)
        self._learn(content)
        return reply

    def _handle_write(self, content: str) -> str:
        m = re.match(r"^/write\s+(\S+)\s*(.*)$", content, re.DOTALL)
        if not m:
            return "写入失败。"
        rel, body = m.group(1), m.group(2).strip()
        # 若指令要求"按规范/模板"生成，则先套用记忆中的规范/模板
        if re.search(r"规范|模板|按照|之前|上次", body):
            if self._commit_prefix and re.search(r"提交", body):
                body = "%s101 fix: %s" % (self._commit_prefix, body[:24])
            elif self._templates:
                for k, v in self._templates.items():
                    if k[:2] in body or "模板" in body:
                        body = v
                        break
        res = _write_file(self._workdir, "/write %s %s" % (rel, body))
        return "已写入。" if res else "写入失败。"

    # ---- 记忆写入：句子级抽取，含敏感句的句子整句丢弃 --------------------------------
    def _learn(self, msg: str) -> None:
        if QUESTION_RE.search(msg):
            return  # 疑问句不是事实陈述，避免把探针问题学进记忆
        for sent in _SENT_SPLIT_RE.split(msg):
            sent = sent.strip()
            if not sent or SECRET_RE.search(sent):
                continue  # 敏感句：拒绝持久化（但不影响同消息内其他句子）
            self._learn_sentence(sent)

    def _learn_sentence(self, sent: str) -> None:
        def put(key: str, val: str) -> None:
            if val:
                self._slots[key] = _clean_value(val)

        for pat, key in [(self._RE_HOME_UPDATE, "家庭地址"),
                         (self._RE_HOME, "家庭地址"),
                         (self._RE_WORK, "公司地址")]:
            m = pat.search(sent)
            if m:
                put(key, m.group(1))
        m = self._RE_PHONE.search(sent)
        if m:
            put("电话", m.group(1))
        for m in self._RE_IP.finditer(sent):  # 一句话可能同时给出外网/内网 IP
            put((m.group(1) or "外网") + "IP", m.group(2))
        m = self._RE_NAME.search(sent)
        if m:
            put("姓名", m.group(1))
        m = self._RE_JOB.search(sent)
        if m:
            put("职业", m.group(1))
        m = self._RE_PROJECT.search(sent)
        if m:
            put("最近项目", m.group(1))
        m = self._RE_LANG_NOSKILL.search(sent)
        if m:
            put("不会语言", m.group(1))
            # 同句若还提到其他语言，认为是熟练的语言（去掉 noskill 匹配的范围再扫一次）
            after = sent[m.end():]
            for sm in re.finditer(r"\b(Python|Go|Java|Rust|C\+\+|C#|Ruby|PHP|TypeScript|JavaScript|Scala|Kotlin|Swift)\b", after):
                self._slots.setdefault("会语言", []).append(sm.group(1))
        else:
            m = self._RE_LANG_SKILL.search(sent)
            if m:
                self._slots.setdefault("会语言", []).append(m.group(1))
        m = self._RE_NICK.search(sent)
        if m:
            put("昵称", m.group(1))
        m = self._RE_ALLERGY.search(sent)
        if m:
            put("过敏源", m.group(1))
        else:
            m = self._RE_ALLERGY2.search(sent)
            if m:
                put("过敏源", m.group(1))
        m = self._RE_SCHEDULE.search(sent)
        if m:
            put("日程", m.group(1) + m.group(2))
        m = self._RE_EDITOR_A.search(sent)
        if m:
            put("默认" + m.group(1), m.group(2))
        else:
            m = self._RE_EDITOR_B.search(sent)
            if m:
                put("默认" + m.group(2), m.group(1))
        for m in self._RE_PET.finditer(sent):  # 一句话里可能有多只宠物
            put((m.group(1) or "") + m.group(2) + "名字", m.group(3))
        m = self._RE_PROC.search(sent)
        if m:
            target, cmd = m.group(1).lower().strip(), _clean_value(m.group(2))
            if target in cmd.lower():
                self._procs[target] = cmd.replace(target, "{pkg}")
            else:
                self._procs[target] = cmd
            if target not in self._installed:
                self._installed.append(target)
        else:
            m = self._RE_INSTALL_BARE.search(sent)
            if m:
                target = m.group(1).lower().strip()
                if target not in self._installed:
                    self._installed.append(target)
        m = self._RE_DATE_EVENT.search(sent)
        if m:
            self._events.append((m.group(1), _clean_value(m.group(2).rstrip("了着过"))))
            self._events.sort(key=lambda x: x[0])
        m = self._RE_OP.search(sent)
        if m:
            cmd = re.split(r"[，,]", m.group(2))[0].strip()  # 命令后可能跟其他分句
            self._ops[m.group(1)] = cmd
        m = self._RE_COMMIT_RULE.search(sent)
        if m:
            self._commit_prefix = m.group(1)
        m = self._RE_TEMPLATE.search(sent)
        if m and len(m.group(3).strip()) >= 2:
            self._templates[m.group(1).strip() + m.group(2)] = m.group(3).strip()

    # ---- 记忆读取（回答） ------------------------------------------------
    def _answer(self, msg: str) -> str:
        # 因果前置条件：用户请求中含某语言时检查"我不会"约束（优先级最高）
        req_lang_m = re.search(r"\b(Python|Go|Java|Rust|C\+\+|C#|Ruby|PHP|TypeScript|JavaScript|Scala|Kotlin|Swift)\b", msg)
        if req_lang_m and "不会语言" in self._slots and self._slots["不会语言"] == req_lang_m.group(1):
            known = self._slots.get("会语言") or []
            if known:
                return "根据你之前说%s不会，你更熟悉 %s；要不要我改用 %s 实现？" % (
                    req_lang_m.group(1), "、".join(known), known[0])
            return "根据你之前说%s不会；要不要我换个方式？" % req_lang_m.group(1)
        # 询问敏感信息 → 拒绝复述
        if SECRET_RE.search(msg) and re.search(r"是什么|多少|告诉我|回忆|记得|查询|哪些", msg):
            return SECRET_REFUSE_REPLY
        # 任务复用：按之前教过的方式安装/部署
        m = self._RE_INSTALL_ASK.search(msg)
        if m and re.search(r"帮我|请|麻烦|按照|上次|之前|同样|一样|还是", msg):
            target = m.group(1).lower()
            cmd = self._procs.get(target)
            if cmd is None:  # 泛化：任何学过的命令模板都可迁移到新目标
                for v in self._procs.values():
                    if "{pkg}" in v:
                        cmd = v
                        break
            if cmd:
                return "按你之前教我的方式，执行：%s" % cmd.replace("{pkg}", target)
            return IDK_REPLY
        # 运维操作复用
        op = self._match_op(msg)
        if op:
            return "好的，执行：%s" % self._ops[op]
        # 事实问答
        slot = self._probe_slot(msg)
        if slot:
            if slot in self._slots:
                return "你告诉我的是：%s" % self._slots[slot]
            return IDK_REPLY
        # 模板复用
        tpl = self._match_template(msg)
        if tpl:
            return "按你的模板：%s" % self._templates[tpl]
        # 时序推理
        if self._events and re.search(r"最早|最先|第一次|第一件", msg):
            return "最早的是 %s，%s" % self._events[0]
        if self._events and re.search(r"最近|最后|最近一次|最后一件事", msg):
            return "最近的是 %s，%s" % self._events[-1]
        if self._events and re.search(r"持续|多少天|间隔", msg):
            if len(self._events) >= 2:
                return "从 %s 到 %s" % (self._events[0][0], self._events[-1][0])
        # 多 session 工具列表
        if self._installed and re.search(r"装过|安装过|装过哪些|哪些软件", msg):
            return "你之前让我装过：%s" % "、".join(self._installed)
        # 自我介绍组合：把已存的身份/工具/项目串成一句
        if re.search(r"介绍我|一句话介绍|关于我|我是谁", msg):
            parts = []
            if "姓名" in self._slots: parts.append("我叫%s" % self._slots["姓名"])
            if "职业" in self._slots: parts.append("是%s" % self._slots["职业"])
            if "默认编辑器" in self._slots: parts.append("默认编辑器是 %s" % self._slots["默认编辑器"])
            if "最近项目" in self._slots: parts.append("最近在 %s" % self._slots["最近项目"])
            if parts:
                return "，".join(parts) + "。"
        if QUESTION_RE.search(msg):
            return IDK_REPLY
        return "好的，记下了。"

    _RE_INSTALL_ASK = re.compile(r"(?:安装|装|部署|卸载)\s*([\w][\w.\-]{0,40})")

    def _match_op(self, msg: str) -> Optional[str]:
        for k in self._ops:
            nouns = [n for n in ("清理", "缓存", "系统", "备份", "服务", "更新") if n in k]
            if nouns and any(n in msg for n in nouns):
                return k
        return None

    def _match_template(self, msg: str) -> Optional[str]:
        if not re.search(r"模板|规范|格式", msg):
            return None
        for k in self._templates:
            if k[:2] in msg or k[:-2] in msg:
                return k
        return None

    @staticmethod
    def _probe_slot(msg: str) -> Optional[str]:
        low = msg.lower()
        if re.search(r"猫|狗", msg) and re.search(r"名字|叫什么", msg):
            m = re.search(PET_ADJ + r"(猫|狗)", msg)
            if m:
                return (m.group(1) or "") + m.group(2) + "名字"
        if re.search(r"昵称", msg):
            return "昵称"
        if re.search(r"叫什么名字|^我是谁|真实姓名|大名", msg):
            return "姓名"
        if re.search(r"名字|称呼", msg):
            return "姓名"
        if re.search(r"过敏|忌口|禁忌|不能吃", msg):
            return "过敏源"
        if re.search(r"日程|安排|会议|评审", msg):
            return "日程"
        if re.search(r"公司|办公", msg) and re.search(r"地址|哪里|在哪", msg):
            return "公司地址"
        if re.search(r"家庭|家|住|居住", msg) and re.search(r"地址|哪里|在哪|哪儿", msg):
            return "家庭地址"
        if re.search(r"电话|手机", msg) and re.search(r"多少|号码|是什么", msg):
            return "电话"
        if re.search(r"外网|公网", low) and re.search(r"ip", low):
            return "外网IP"
        if re.search(r"内网|局域网", low) and re.search(r"ip", low):
            return "内网IP"
        for noun in SmartMemoryAgent._EDITOR_NOUNS:
            if noun in low and re.search(r"默认|用|是哪个|是什么", msg):
                return "默认" + noun
        if re.search(r"地址", msg):
            return "家庭地址"
        return None
