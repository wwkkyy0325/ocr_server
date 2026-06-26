// 错误监控工作流 - 检测死循环、卡住等问题
// 用法: Workflow({name: 'error-monitor', args: '检查当前开发状态'})

export const meta = {
  name: 'error-monitor',
  description: '检测开发过程中的死循环、卡住、重复失败等问题，及时汇报',
  phases: [
    { title: '扫描', detail: '检查日志和代码状态' },
    { title: '分析', detail: '判断是否存在问题' },
    { title: '汇报', detail: '输出问题报告和建议' },
  ],
}

// Phase 1: 扫描当前状态
phase('扫描')
const scanResult = await agent(
  `你是开发监控专家。扫描当前开发状态，检查以下问题：

1. 检查最近的日志文件是否有重复的错误模式
   - 搜索: find /tmp -name "*.log" -mmin -30 2>/dev/null | head -5
   - 或检查 Java 进程输出

2. 检查是否有端口冲突
   - for port in 8081 8082 8083 8084 8085 8086 8088; do (echo >/dev/tcp/localhost/$port) 2>/dev/null && echo "$port: UP" || echo "$port: DOWN"; done

3. 检查数据库连接
   - mysql -h localhost -P 4000 -u root -e "SELECT 1" 2>/dev/null && echo "DB: OK" || echo "DB: FAIL"

4. 检查是否有 Java 进程卡住
   - jps -l 2>/dev/null | grep java | head -10

5. 检查最近的编译错误
   - 查看 target 目录的编译时间戳

输出格式：
## 扫描结果
- 服务状态: [UP/DOWN]
- 数据库: [OK/FAIL]
- 端口冲突: [有/无]
- 最近错误: [有/无]
- 卡住的进程: [有/无]`,
  { label: 'Scan Agent', phase: '扫描', agentType: 'Explore' }
)

// Phase 2: 分析
phase('分析')
const analysis = await agent(
  `你是问题分析专家。根据以下扫描结果判断是否存在开发问题：

扫描结果：${scanResult}

判断标准：
1. 如果多个服务 DOWN → 可能是启动脚本问题或端口冲突
2. 如果数据库 FAIL → 可能是 TiDB 未启动
3. 如果有重复错误模式 → 可能是死循环或卡住
4. 如果编译错误重复出现 → 可能是代码问题未修复

输出格式：
## 问题诊断
- 是否存在问题: [是/否]
- 问题类型: [启动失败/端口冲突/数据库/编译错误/死循环/正常]
- 严重程度: [critical/high/medium/low]
- 建议操作: [具体步骤]`,
  { label: 'Analysis Agent', phase: '分析' }
)

// Phase 3: 汇报
phase('汇报')
log('扫描和分析完成')
return { scanResult, analysis }
