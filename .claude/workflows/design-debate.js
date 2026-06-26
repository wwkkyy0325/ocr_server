// 设计辩论工作流 - Agent 之间互相反驳
// 用法: Workflow({name: 'design-debate', args: '讨论租户池是否应该保留'})

export const meta = {
  name: 'design-debate',
  description: '多Agent辩论：提出方案→互相反驳→收敛共识',
  phases: [
    { title: '提案', detail: '各 Agent 独立提出方案' },
    { title: '反驳', detail: 'Agent 互相质疑和反驳' },
    { title: '收敛', detail: 'Leader 总结共识' },
  ],
}

const PROPOSAL_SCHEMA = {
  type: 'object',
  properties: {
    proposal: { type: 'string' },
    pros: { type: 'array', items: { type: 'string' } },
    cons: { type: 'array', items: { type: 'string' } },
    risks: { type: 'array', items: { type: 'string' } },
    estimatedEffort: { type: 'string' },
  },
  required: ['proposal', 'pros', 'cons'],
}

// ========== Phase 1: 各 Agent 独立提案 ==========
phase('提案')
log(`辩论主题: ${args}`)

const [archProposal, productProposal, backendProposal] = await parallel([
  () => agent(
    `你是架构师。针对以下主题提出技术方案：

主题：${args}

当前项目：SaaS 多租户平台，Spring Boot + React

请阅读 docs/llmwiki/architecture/ 了解现有架构。

输出要求：
1. 你的方案（具体技术选型）
2. 优势（至少3点）
3. 劣势（至少3点）
4. 风险点
5. 预估工作量

必须给出明确的方案，不要模棱两可。`,
    { label: 'Architecture Agent', phase: '提案', schema: PROPOSAL_SCHEMA }
  ),

  () => agent(
    `你是产品经理。针对以下主题提出产品方案：

主题：${args}

请阅读 docs/llmwiki/ 了解现有功能。

输出要求：
1. 你的方案（用户体验角度）
2. 优势（至少3点）
3. 劣势（至少3点）
4. 用户影响
5. 预估工作量

必须给出明确的方案，不要模棱两可。`,
    { label: 'Product Agent', phase: '提案', schema: PROPOSAL_SCHEMA }
  ),

  () => agent(
    `你是后端架构师。针对以下主题提出实现方案：

主题：${args}

当前项目：Spring Boot 微服务，MyBatis-Plus，Kafka

请阅读现有代码了解实现细节。

输出要求：
1. 你的方案（实现路径）
2. 优势（至少3点）
3. 劣势（至少3点）
4. 技术风险
5. 预估工作量

必须给出明确的方案，不要模棱两可。`,
    { label: 'Backend Agent', phase: '提案', schema: PROPOSAL_SCHEMA }
  ),
])

log('提案阶段完成，开始反驳...')

// ========== Phase 2: 互相反驳 ==========
phase('反驳')

// 架构师反驳产品和后端
const archObjection = await agent(
  `你是架构师。你刚才提出了一个方案。现在阅读其他两位的方案并进行反驳：

你的方案：${JSON.stringify(archProposal)}
产品方案：${JSON.stringify(productProposal)}
后端方案：${JSON.stringify(backendProposal)}

反驳要求：
1. 指出对方方案中的技术漏洞
2. 质疑对方的假设是否成立
3. 提出对方忽略的风险
4. 用具体数据或案例支撑你的反驳
5. 保持专业，对事不对人

输出格式：
- 对产品方案的反驳：...
- 对后端方案的反驳：...`,
  { label: 'Architecture Agent (反驳)', phase: '反驳' }
)

// 产品反驳架构和后端
const productObjection = await agent(
  `你是产品经理。你刚才提出了一个方案。现在阅读其他两位的方案并进行反驳：

你的方案：${JSON.stringify(productProposal)}
架构方案：${JSON.stringify(archProposal)}
后端方案：${JSON.stringify(backendProposal)}

反驳要求：
1. 指出对方方案中不符合用户需求的地方
2. 质疑技术复杂度是否必要
3. 提出用户体验角度的风险
4. 用用户反馈或市场数据支撑
5. 保持专业，对事不对人

输出格式：
- 对架构方案的反驳：...
- 对后端方案的反驳：...`,
  { label: 'Product Agent (反驳)', phase: '反驳' }
)

// 后端反驳架构和产品
const backendObjection = await agent(
  `你是后端架构师。你刚才提出了一个方案。现在阅读其他两位的方案并进行反驳：

你的方案：${JSON.stringify(backendProposal)}
架构方案：${JSON.stringify(archProposal)}
产品方案：${JSON.stringify(productProposal)}

反驳要求：
1. 指出对方方案中的实现困难
2. 质疑资源和时间估算
3. 提出技术债风险
4. 用具体代码或架构约束支撑
5. 保持专业，对事不对人

输出格式：
- 对架构方案的反驳：...
- 对产品方案的反驳：...`,
  { label: 'Backend Agent (反驳)', phase: '反驳' }
)

log('反驳阶段完成，开始收敛...')

// ========== Phase 3: Leader 总结 ==========
phase('收敛')

const consensus = await agent(
  `你是技术总监（Leader）。三位专家已经提出了方案并互相反驳。现在你需要：

架构师方案：${JSON.stringify(archProposal)}
产品方案：${JSON.stringify(productProposal)}
后端方案：${JSON.stringify(backendProposal)}

架构师反驳：${archObjection}
产品反驳：${productObjection}
后端反驳：${backendObjection}

你的任务：
1. 总结各方观点的核心分歧
2. 评估每个反驳的有效性
3. 做出最终决策（选择一个方案或综合多个方案）
4. 说明决策理由
5. 列出需要 follow up 的事项

输出格式：
## 核心分歧
...

## 反驳评估
...

## 最终决策
...

## Follow Up
...`,
  { label: 'Leader Agent', phase: '收敛' }
)

log('辩论完成！')
return { archProposal, productProposal, backendProposal, archObjection, productObjection, backendObjection, consensus }
