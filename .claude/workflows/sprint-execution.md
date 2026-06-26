# Sprint 执行工作流

## 触发条件
用户提出新功能需求或任务

## 流程

### Phase 1: 需求分析
- Product Agent 阅读用户需求
- 生成产品文档（用户故事 + 验收标准 + UI 描述）
- 输出到 docs/product/FEAT-{id}.md

### Phase 2: 架构设计
- Architecture Agent 阅读产品文档
- 搜索现有代码架构
- 设计数据模型和 API
- 输出到 docs/architecture/ARCH-{id}.md

### Phase 3: 并行开发
- Leader 拆解为子任务
- Backend Agent 实现后端代码
- Frontend Agent 实现前端代码
- 两个 Agent 可并行执行

### Phase 4: 测试
- 白盒测试 Agent 审查代码逻辑
- 黑盒测试 Agent 编写测试用例

### Phase 5: 审查合并
- Code Review Agent 检查代码质量
- Leader 最终审查并合并
