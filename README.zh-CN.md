# ctxlens

**给你的编码 agent 上下文窗口拍一张 X 光片。**

[English](README.md) | 简体中文

> 上下文窗口到底被什么吃了？确定性回答 · 零 LLM · 零网络 · 零依赖

[![CI](https://github.com/zhengqiuyang/ctxlens/actions/workflows/ci.yml/badge.svg)](https://github.com/zhengqiuyang/ctxlens/actions/workflows/ci.yml)
[![License: MIT](https://github.com/zhengqiuyang/ctxlens/blob/main/LICENSE)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)

## 你从没看见过的那道悬崖

凌晨两点。你的 agent 已经追了九十分钟双扣费 bug，干得漂亮极了——直到它突然不漂亮了。

它把第九分钟读过的文件又读了一遍。它问了你早就回答过的问题。然后它道歉，用那种平直的机器道歉，说对话被 *压缩*（compacted）了。

你知道发生了什么：上下文窗口满了。某个环节——一次 `Read` 拉回 1900 行文件、一次 `WebFetch` 整页吞下文档——窗口越过了红线，agent 为了继续干活，悄悄截断了自己的记忆。

到底丢了什么？*没有工具给你看这个。*

用量面板只给你看**账单**，agent 只给你看一个百分比。没人给你看**解剖结构**：哪一块吃了 46k token、compaction 带走了什么、曲线是在哪里竖起来的。

ctxlens 就是那张 X 光片。它读取你磁盘上现成的会话日志，确定性回答三个问题——全程零 LLM 调用：

1. **窗口里现在装着什么** —— system 提示、历史、工具调用、工具结果，各占几成。
2. **最大的块是哪些** —— 元凶排行榜，带预览。
3. **compaction 带走了什么** —— 前后对比、净损失、最大的牺牲者。

![demo X 光片](docs/xray.svg)

## 快速开始

```bash
uv tool install git+https://github.com/zhengqiuyang/ctxlens
# 或者: pip install git+https://github.com/zhengqiuyang/ctxlens
```

先看内置的虚构会话——不碰任何真实日志：

```bash
ctxlens scan --demo
```

然后拍你自己的：

```bash
ctxlens                       # 最近一次会话，自动识别 agent
ctxlens sessions              # 本机有哪些会话日志
ctxlens scan ~/.codex/sessions/2026/10/28/rollout-....jsonl --format svg --out xray.svg
ctxlens scan --agent claude --top 15
```

## 它看见什么

**成分拆解。** 活上下文——最近一次 compaction 之后还活着的部分——拆成六个桶：system、user、assistant、tool calls、tool results、other。当 agent 自己记了用量数字，ctxlens 会把各桶按真实总量缩放，并明确标注。

**元凶排行。** 会话里最大的块，按估算大小排序：一次 46,800 token 的文件读取、一整页 31,500 token 的网页、越长越大的测试输出。每条带一行预览。

**Compaction 取证。** 每一刀都有前后账：两侧的上下文大小、净损失、进去后再没出来的五个最大的块。

**膨胀曲线。** 整场会话的上下文尺寸——agent 记了用量就用真实值，否则用确定性估算。compaction 的刀口画成悬崖。形状一眼讲完故事。

## 闸门

报告很好看，闸门才会被合并。`--max-tokens` 把 ctxlens 变成两秒钟的 CI 检查：

```bash
ctxlens scan "$SESSION_FILE" --max-tokens 150000
echo $?   # 0 预算内 · 3 超预算
```

退出码：`0` 成功 · `1` 无可扫描 · `2` 用法错误 · `3` 预算超限。

## 诚实声明

ctxlens 从不调用 LLM、从不联网、从不假装自己是分词器。

- **逐块大小是估算值。** 一个写进文档的启发式（ASCII ≈ 4 字符/token，CJK ≈ 1 字符/token），与真实分词器偏差通常在 25% 以内。*排序*——谁最大——是稳健的；具体数字是灯笼，不是千分尺。
- **有真实数字时，真实数字优先。** 会记录用量的 agent（Claude Code 会；Codex 部分版本会）会把真实提示尺寸喂给 ctxlens，各桶按它缩放，并标注 `scaled to real usage`。
- **同样的输入，永远同样的输出。** 无时间戳、无随机数、无本地化。报告可 diff，SVG 逐字节一致。

## 设计原则

1. **分析路径零 LLM。** 会话文件是唯一输入。
2. **零依赖。** 纯标准库，Python 3.9+。dev 才要 pytest。
3. **本地优先。** 什么都不发出去，因为什么都不需要发出去。
4. **容错适配器。** agent 日志格式每个版本都在漂移；看不懂的行记数跳过，绝不崩溃。
5. **确定性是特性。** 两次运行结果不一样的报告，没法基线、没法 diff、没法设闸。

## 适配器

| Agent | 位置 | 状态 |
|---|---|---|
| Claude Code | `~/.claude/projects/**/*.jsonl` | ✅ 含真实用量 + compaction 检测 |
| Codex CLI | `~/.codex/sessions/**/*.jsonl` | ✅ 含 session meta 的 `context_window` |
| 通用 JSONL | 任意文件，尽力而为 | ✅ role/type 启发式 |

`CTXLENS_HOME` 可重定向发现根目录（测试、便携安装）。

## 有什么不一样

- **对比 agent 内置的 `/context`** —— 那是单会话瞬时快照。ctxlens 跨会话、排元凶、做 compaction 取证。
- **对比用量监控** —— 它们管钱管额度，ctxlens 管**解剖结构**：窗口由什么构成、去哪儿了。
- **对比把日志传上云** —— ctxlens 更愿意待在家里。"我的 agent 读了什么"这个问题，值得一个本地的答案。

## 路线图

- [ ] OpenCode 适配器
- [ ] `ctxlens watch` —— 会话进行时的实时窗口表
- [ ] 跨会话漂移报告（同一仓库，周对周）
- [ ] 嵌套工具结果的火焰图视图

## 许可

[MIT](LICENSE)
