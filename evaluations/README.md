# CoworkEval 评测工作区

## 快速开始

```bash
cd backend

# 1. 注册评测集
./coworkeval.sh register sample_data/manifest.json

# 2. 评测一个 Trace
./coworkeval.sh evaluate -t ../evaluations/traces/alarm_with_skill.jsonl

# 3. A/B 对比（Baseline vs 实测）
./coworkeval.sh compare \
  -b ../evaluations/baselines/alarm_baseline_no_skill.jsonl \
  -a ../evaluations/traces/alarm_with_skill.jsonl

# 4. 从 Claude Code 会话提取 Trace
./coworkeval.sh segments -s ~/.claude/projects/<project>/<session>.jsonl
./coworkeval.sh extract -s ~/.claude/projects/<project>/<session>.jsonl -n 0 \
  -o ../evaluations/baselines/my_task_baseline

# 5. 启动 Web 界面
./coworkeval.sh serve
# 访问 http://localhost:8000/docs 查看 API
```

## 目录结构

```
evaluations/
├── baselines/          ← 存放 Baseline Trace（无 Skill 执行）
├── traces/             ← 存放实测 Trace（有 Skill 或其他版本）
├── results/            ← 评测结果输出
└── SKILL.md            ← 示例 Skill 文件
```

## 工作流

```
1. 无 Skill 执行任务 → 保存 Trace 到 baselines/
2. 有 Skill 执行任务 → 保存 Trace 到 traces/
3. ./coworkeval.sh compare -b baselines/xxx -a traces/xxx
4. 查看对比结果 → 量化 Skill 效果
```
