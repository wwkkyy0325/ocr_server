# Skill 注册表

> 所有 Agent 在执行任务前应先阅读此文件，了解可用工具。

## 可用 Skills

### 前端开发
| Skill | 触发方式 | 用途 |
|-------|---------|------|
| `/frontend-design` | 用户请求创建 UI | 生成高质量前端界面，避免 AI 审美 |

### 代码质量
| Skill | 触发方式 | 用途 |
|-------|---------|------|
| `/code-review` | 代码审查请求 | 审查代码变更 |
| `/code-simplifier` | 代码简化请求 | 简化复杂代码 |
| `/code-modernization` | 代码现代化请求 | 升级旧代码 |

### Git 操作
| Skill | 触发方式 | 用途 |
|-------|---------|------|
| `/commit` | 提交代码时 | 自动生成 commit message |
| `/commit-push-pr` | 完整发布流程 | commit + push + 创建 PR |

### 安全
| Skill | 触发方式 | 用途 |
|-------|---------|------|
| `/security-guidance` | 安全审查请求 | 安全漏洞检查 |

### 功能开发
| Skill | 触发方式 | 用途 |
|-------|---------|------|
| `/feature-dev` | 新功能开发 | 功能开发辅助 |

## Agent 可用工具

### 所有 Agent 自动可用
- `Read` / `Write` / `Edit` — 文件操作
- `Bash` — 命令执行
- `Glob` / `Grep` — 代码搜索
- `Agent` — 启动子 Agent

### general-purpose Agent 额外可用
- 所有内置工具
- 可调用上述 Skills

### Explore Agent 只读
- 只能读取和搜索，不能修改文件

### Plan Agent 只读
- 只能分析和规划，不能修改文件

## 使用示例

```
# 前端 Agent 调用 frontend-design
使用 /frontend-design skill 创建用户个人中心页面

# 后端 Agent 调用 code-review
使用 /code-review skill 审查 TenantPoolService 的变更

# 测试 Agent 调用 security-guidance
使用 /security-guidance skill 检查认证模块的安全性

# Leader Agent 调用 commit
使用 /commit skill 提交本次变更
```
