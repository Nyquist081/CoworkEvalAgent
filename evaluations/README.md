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

## 新离线评测目录结构

```
evaluations/
└── <benchmark_id>/
    ├── manifest.json
    ├── <question_id>/
    │   ├── prompt.txt
    │   ├── 输入文件/
    │   └── 参考答案/
    └── runs/
        └── <run_label>/
            ├── run_meta.json
            └── <question_id>/
                └── attempt-1/
                    ├── trace.jsonl
                    └── 输出结果/
```

可直接试跑的样例：

```bash
curl -X POST http://localhost:8000/coworkeval/v1/runs/evaluate-offline \
  -H 'Content-Type: application/json' \
  -d '{"benchmark_root":"../evaluations/industrial-demo","run_label":"alarm-with-skill","judge_enabled":false}'
```

## 旧 Trace 对比工作流

旧的 `baselines/` 和 `traces/` 目录仍保留，用于单 Trace A/B 对比：

```
1. 无 Skill 执行任务 → 保存 Trace 到 baselines/
2. 有 Skill 执行任务 → 保存 Trace 到 traces/
3. ./coworkeval.sh compare -b baselines/xxx -a traces/xxx
4. 查看对比结果 → 量化 Skill 效果
```
