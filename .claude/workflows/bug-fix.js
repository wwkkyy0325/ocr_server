// Bug 修复工作流 - 多 Agent 协同
// 用法: Workflow({name: 'bug-fix', args: '修复登录页面验证码倒计时显示错误'})

export const meta = {
  name: 'bug-fix',
  description: '多Agent协同：分析→定位→修复→验证',
  phases: [
    { title: '分析', detail: 'Explore Agent 搜索相关代码' },
    { title: '修复', detail: 'general-purpose Agent 修复代码' },
    { title: '验证', detail: 'Tester Agent 验证修复' },
  ],
}

// Phase 1: 分析
phase('分析')
const analysis = await agent(
  `你是高级开发工程师。分析以下 Bug：

Bug 描述：${args}

步骤：
1. 搜索相关代码文件
2. 阅读代码逻辑
3. 定位问题根因
4. 列出需要修改的文件和行号
5. 提出修复方案

项目路径：当前目录`,
  { label: 'Explore Agent', phase: '分析', agentType: 'Explore' }
)
log(`分析完成: ${analysis?.substring(0, 200)}...`)

// Phase 2: 修复
phase('修复')
const fixResult = await agent(
  `你是开发工程师。根据以下分析修复 Bug：

分析结果：${analysis}

可用 Skills：
- /code-simplifier — 修复时简化相关代码
- /frontend-design — 如涉及前端 UI 修复

要求：
1. 只修改必要的代码
2. 不要引入新问题
3. 确保编译通过
4. 添加必要的注释`,
  { label: 'Fix Agent', phase: '修复' }
)
log('修复完成')

// Phase 3: 验证
phase('验证')
const verifyResult = await agent(
  `你是测试工程师。验证以下修复是否正确：

Bug 描述：${args}
修复内容：${fixResult}

验证步骤：
1. 检查修改的代码逻辑
2. 确认没有引入新问题
3. 检查边界条件
4. 输出验证报告`,
  { label: 'Verify Agent', phase: '验证' }
)

return { analysis, fixResult, verifyResult }
