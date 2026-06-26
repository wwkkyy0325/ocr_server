// Sprint 执行工作流 - 多 Agent 协同
// 用法: Workflow({name: 'sprint-execution', args: '实现用户头像上传功能'})

export const meta = {
  name: 'sprint-execution',
  description: '多Agent协同：需求分析→架构设计→并行开发→测试→审查',
  phases: [
    { title: '需求分析', detail: 'Product Agent 生成产品文档' },
    { title: '架构设计', detail: 'Architecture Agent 技术方案' },
    { title: '并行开发', detail: 'Backend + Frontend Agent 并行实现' },
    { title: '测试', detail: '白盒 + 黑盒测试' },
    { title: '审查合并', detail: 'Code Review + Leader 合并' },
  ],
}

// Product Doc Schema
const PRODUCT_DOC = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    userStory: { type: 'string' },
    acceptanceCriteria: { type: 'array', items: { type: 'string' } },
    uiDescription: { type: 'string' },
    dataModel: { type: 'string' },
    apiEndpoints: { type: 'string' },
    techConstraints: { type: 'string' },
  },
  required: ['title', 'userStory', 'acceptanceCriteria'],
}

// Phase 1: 需求分析
phase('需求分析')
log(`开始分析需求: ${args}`)
const productDoc = await agent(
  `你是产品经理。根据以下需求生成产品文档：

需求：${args}

项目背景：这是一个 SaaS 多租户平台，使用 Spring Boot + React 技术栈。
请阅读 docs/llmwiki/ 了解现有架构。

输出要求：
1. 用户故事
2. 验收标准（可勾选）
3. UI 描述（页面布局、交互流程、状态变化）
4. 数据模型（新增字段）
5. API 接口定义
6. 技术约束`,
  { label: 'Product Agent', phase: '需求分析', schema: PRODUCT_DOC }
)
log(`产品文档生成完成: ${productDoc?.title}`)

// Phase 2: 架构设计
phase('架构设计')
const archDoc = await agent(
  `你是架构师。根据产品文档设计技术方案：

产品需求：${JSON.stringify(productDoc, null, 2)}

请阅读以下文件了解现有架构：
- docs/llmwiki/architecture/ARCHITECTURE.md
- docs/llmwiki/cross-service.md
- 现有实体类和 Controller

输出要求：
1. 数据库 Schema 变更
2. API 接口详细设计
3. 服务间调用关系
4. 需要修改的文件列表
5. 实现步骤`,
  { label: 'Architecture Agent', phase: '架构设计' }
)
log('架构设计完成')

// Phase 3: 并行开发
phase('并行开发')
const [backendResult, frontendResult] = await parallel([
  () => agent(
    `你是后端开发工程师。根据以下架构设计实现后端代码：

${archDoc}

项目技术栈：Spring Boot + MyBatis-Plus + Kafka
代码规范：参考 docs/llmwiki/conventions.md

实现步骤：
1. 创建/修改实体类
2. 创建/修改 Service
3. 创建/修改 Controller
4. 创建 Feign 客户端（如需要）
5. 创建数据库迁移

每个文件写完后确认编译通过。`,
    { label: 'Backend Agent', phase: '并行开发' }
  ),
  () => agent(
    `你是前端开发工程师。根据以下需求和架构设计实现前端代码：

产品需求：${JSON.stringify(productDoc, null, 2)}
架构设计：${archDoc}

项目技术栈：React + TypeScript + Ant Design
代码规范：参考 docs/llmwiki/conventions.md

可用 Skills：/frontend-design（创建高质量 UI 时使用）

实现步骤：
1. 使用 /frontend-design skill 创建页面组件
2. 添加 API 调用
3. 更新路由配置
4. 确保 npm build 通过`,
    { label: 'Frontend Agent', phase: '并行开发' }
  ),
])
log('并行开发完成')

// Phase 4: 测试
phase('测试')
await parallel([
  () => agent(
    `你是白盒测试工程师。审查以下代码的逻辑正确性：

${backendResult}

可用 Skills：/security-guidance — 安全漏洞扫描

检查项：
1. 边界条件处理
2. 并发安全
3. 异常处理
4. 数据一致性
5. SQL 注入风险
6. 使用 /security-guidance skill 进行安全审查

输出 Bug 列表和修复建议。`,
    { label: 'White-box Tester', phase: '测试' }
  ),
  () => agent(
    `你是黑盒测试工程师。为以下功能编写测试用例：

${productDoc}

输出：
1. 功能测试用例
2. 接口测试用例
3. 异常场景测试`,
    { label: 'Black-box Tester', phase: '测试' }
  ),
])
log('测试完成')

// Phase 5: 审查
phase('审查合并')
const reviewResult = await agent(
  `你是代码审查工程师。审查以下变更：

后端变更：${backendResult}
前端变更：${frontendResult}

可用 Skills：
- /code-review — 代码质量审查
- /security-guidance — 安全漏洞检查
- /code-simplifier — 代码简化建议

检查项：
1. 代码规范（命名、格式、注释）
2. 安全漏洞
3. 性能问题
4. 最佳实践

输出审查报告，标记问题严重等级。`,
  { label: 'Code Review Agent', phase: '审查合并' }
)

log('所有阶段完成！')
return { productDoc, archDoc, reviewResult }
