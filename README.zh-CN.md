# Codex Token Audit

[English](README.md) | 中文

一个面向 OpenAI Codex 的轻量上下文审计 Skill。找出长期占用上下文的 `AGENTS.md`、Skill 元数据、重复 Skill 和闲置插件，并在用户确认后完成瘦身和复测。

## 它解决什么问题

Codex 配置会随使用逐渐膨胀：

- `AGENTS.md` 越写越长，每个任务重复加载。
- 安装大量 Skill 后，名称和描述进入发现上下文。
- Skill 重名或触发范围过宽，可能加载不必要的流程。
- 插件长期启用，但当前项目并不使用。
- 缓存文件很多，却无法区分“磁盘存在”和“实际启用”。

这些开销单次看不明显，长任务和多轮对话中会持续累积。

## 工作方式

1. 只读扫描 Codex 配置。
2. 显示估算总量和具体高耗项。
3. 最多提出三项高收益整改。
4. 用户确认后，Codex 备份并执行批准的改动。
5. 再次审计，比较改动前后结果。

安装和默认审计不会修改任何文件。真正节省 token 的改动只会在用户明确批准后执行。

## 检查内容

- 全局及项目 `AGENTS.md` 大小
- 当前有效 Skill 数量和元数据估算
- Skill 重名
- 触发范围过宽的 Skill
- 启用、禁用插件
- 有效配置与物理缓存的区别
- 最大的 Skill 元数据来源

## 安装

在 Codex 中让 Skill Installer 安装：

```text
https://github.com/geeksocial/codex-token-audit/tree/main/skills/codex-token-audit
```

安装后重启 Codex。

## 使用

直接审计：

```text
$codex-token-audit
```

忽略已经接受、不需要重复建议的 Skill：

```bash
python scripts/audit.py --ignore-skill <skill-name>
```

建立基线并定期比较：

```bash
python scripts/audit.py --save-baseline token-baseline.json
python scripts/audit.py --compare token-baseline.json
```

分享报告前隐藏本地路径：

```bash
python scripts/audit.py --redact-paths
```

## 安全边界

- 不覆盖现有 `AGENTS.md`。
- 不自动修改 Codex 配置。
- 不包含 hook、安装后脚本或插件 manifest。
- 不联网、不上传数据、不包含遥测。
- 默认审计只读。
- 修改前必须显示范围并获得用户确认。
- 修改后必须重新验证。

## 如何理解报告

- `active`：按当前配置可能进入 Skill 发现上下文的项目。
- `physical`：磁盘上的文件，可能只是禁用插件缓存，不等于 token 开销。
- `metadata tokens`：根据文本估算，用于比较配置变化，不是账单数据。
- `broad trigger`：描述覆盖“所有任务”“每次回复”等范围，容易被自动触发。

## 限制

本工具测量静态配置，不读取 OpenAI 账单，也不能准确计算模型推理 token、完整任务历史或服务端压缩后的真实上下文。估算适合发现趋势和比较改动前后，不应当作精确计费数据。

## 简短介绍文案

> Codex Token Audit 是一个轻量、只读的 Codex Skill，用于检查 `AGENTS.md`、Skill 元数据、重复触发和闲置插件造成的上下文浪费。它只给出最多三项高收益建议，用户确认后再执行，并用前后对比验证实际瘦身结果。无遥测、不联网、不自动覆盖配置。

## 许可证

MIT
