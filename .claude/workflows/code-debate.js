// 代码辩论工作流 - 多 Agent 审查并互相反驳
// 用法: Workflow({name: 'code-debate', args: '审查 TenantPoolService 的设计'})

export const meta = {
  name: 'code-debate',
  description: '代码审查辩论：多角度审查→互相挑战→达成共识',
  phases: [
    { title: '独立审查', detail: '3 个 Agent 从不同角度审查' },
    { title: '交叉挑战', detail: '互相质疑发现的问题' },
    { title: '最终裁决', detail: 'Leader 决定修复优先级' },
  ],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          description: { type: 'string' },
          location: { type: 'string' },
          fix: { type: 'string' },
        },
      },
    },
  },
}

// ========== Phase 1: 独立审查 ==========
phase('独立审查')

const [securityReview, perfReview, designReview] = await parallel([
  () => agent(
    `你是安全审查专家。审查以下代码的安全性：

${args}

审查维度：
1. SQL 注入风险
2. 认证/授权漏洞
3. 敏感数据泄露
4. 加密算法安全性
5. 输入验证完整性
6. 会话管理安全

每个发现标注严重等级（critical/high/medium/low）。
使用 /security-guidance skill 辅助审查。`,
    { label: 'Security Reviewer', phase: '独立审查', schema: REVIEW_SCHEMA }
  ),

  () => agent(
    `你是性能专家。审查以下代码的性能：

${args}

审查维度：
1. N+1 查询问题
2. 缺失索引
3. 内存泄漏风险
4. 并发安全
5. 缓存策略
6. 数据库连接池

每个发现标注严重等级（critical/high/medium/low）。`,
    { label: 'Performance Reviewer', phase: '独立审查', schema: REVIEW_SCHEMA }
  ),

  () => agent(
    `你是架构审查专家。审查以下代码的设计：

${args}

审查维度：
1. 单一职责原则
2. 依赖方向
3. 接口设计
4. 错误处理策略
5. 可测试性
6. 可扩展性

每个发现标注严重等级（critical/high/medium/low）。`,
    { label: 'Design Reviewer', phase: '独立审查', schema: REVIEW_SCHEMA }
  ),
])

log('独立审查完成，开始交叉挑战...')

// ========== Phase 2: 交叉挑战 ==========
phase('交叉挑战')

const challenge1 = await agent(
  `你是安全审查专家。其他人发现了以下问题，你现在要挑战他们的发现：

安全发现：${JSON.stringify(securityReview)}
性能发现：${JSON.stringify(perfReview)}
设计发现：${JSON.stringify(designReview)}

你的任务：
1. 质疑性能发现中的"安全建议"是否准确
2. 质疑设计发现中的"安全风险"是否真的严重
3. 补充其他人忽略的安全问题
4. 用 OWASP Top 10 或 CVE 案例支撑`,
  { label: 'Security Challenge', phase: '交叉挑战' }
)

const challenge2 = await agent(
  `你是性能审查专家。其他人发现了以下问题，你现在要挑战他们的发现：

性能发现：${JSON.stringify(perfReview)}
安全发现：${JSON.stringify(securityReview)}
设计发现：${JSON.stringify(designReview)}

你的任务：
1. 质疑安全发现中的"性能建议"是否准确
2. 质疑设计发现中的"性能风险"是否真的严重
3. 补充其他人忽略的性能问题
4. 用基准测试数据或 profiling 结果支撑`,
  { label: 'Performance Challenge', phase: '交叉挑战' }
)

const challenge3 = await agent(
  `你是架构审查专家。其他人发现了以下问题，你现在要挑战他们的发现：

设计发现：${JSON.stringify(designReview)}
安全发现：${JSON.stringify(securityReview)}
性能发现：${JSON.stringify(perfReview)}

你的任务：
1. 质疑安全发现中的"架构建议"是否合理
2. 质疑性能发现中的"设计改动"是否必要
3. 补充其他人忽略的设计问题
4. 用 SOLID 原则或设计模式支撑`,
  { label: 'Design Challenge', phase: '交叉挑战' }
)

log('交叉挑战完成，开始最终裁决...')

// ========== Phase 3: 最终裁决 ==========
phase('最终裁决')

const verdict = await agent(
  `你是技术总监。三位审查专家已经独立审查并互相挑战。现在你需要裁决：

安全审查：${JSON.stringify(securityReview)}
性能审查：${JSON.stringify(perfReview)}
设计审查：${JSON.stringify(designReview)}

安全反驳：${challenge1}
性能反驳：${challenge2}
设计反驳：${challenge3}

裁决要求：
1. 评估每个发现的有效性（接受/拒绝/部分接受）
2. 确定修复优先级（P0/P1/P2/P3）
3. 输出最终修复清单
4. 说明哪些发现被推翻及原因

输出格式：
## 有效发现（需修复）
| 优先级 | 问题 | 修复方案 | 来源 |

## 被推翻的发现
| 问题 | 推翻原因 | 提出者 |

## 统计
- 总发现数：X
- 有效发现：X
- 被推翻：X`,
  { label: 'Leader Verdict', phase: '最终裁决' }
)

log('代码辩论完成！')
return { securityReview, perfReview, designReview, challenge1, challenge2, challenge3, verdict }
