---
name: scarcity-marketing-advisor
description: 为Athena OpenHuman项目提供稀缺性营销策略分析、生成和监控。基于《稀缺性营销：从温克尔曼到AI时代的全量操作手册》框架，结合OpenHuman技术特性设计稀缺性策略。
user-invocable: true
allowed-tools: "Read, Write, Edit, Bash, Glob, Grep, Agent"
hooks:
  UserPromptSubmit:
    - hooks:
        - type: command
          command: "if [ -f scarcity_analysis.md ]; then echo '[稀缺性营销顾问] 当前分析状态:'; head -30 scarcity_analysis.md; echo ''; echo '=== 最近策略 ==='; tail -20 marketing_strategy.md 2>/dev/null; echo ''; echo '[稀缺性营销顾问] 阅读scarcity_analysis.md获取完整分析，继续当前阶段工作。'; fi"
  PreToolUse:
    - matcher: "Write|Edit|Bash|Read|Glob|Grep|Agent"
      hooks:
        - type: command
          command: "cat scarcity_analysis.md 2>/dev/null | head -20 || true"
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "if [ -f scarcity_analysis.md ]; then echo '[稀缺性营销顾问] 更新marketing_strategy.md记录策略调整。如果阶段完成，更新scarcity_analysis.md状态。'; fi"
  Stop:
    - hooks:
        - type: command
          command: "SD=\"${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/scarcity-marketing-advisor}/scripts\"; sh \"$SD/check-complete.sh\" 2>/dev/null || true"
metadata:
  version: "1.0.0"
  project: "Athena OpenHuman"
  based_on: "稀缺性营销：从温克尔曼到AI时代的全量操作手册"
---

# 稀缺性营销顾问技能

为Athena OpenHuman碳硅基共生系统提供专业的稀缺性营销策略分析、生成和监控服务。本技能基于《稀缺性营销：从温克尔曼到AI时代的全量操作手册》框架，结合OpenHuman的技术特性（GSD V2架构、多模型差异化、知识库流水线）设计定制化的稀缺性营销策略。

## 核心功能模块

### 1. 稀缺性分析模块
- **系统状态分析**: 评估OpenHuman的技术稀缺性资产
- **市场定位分析**: 分析竞争格局和市场机会
- **用户画像分析**: 识别目标用户群体的稀缺性需求
- **风险评估**: 识别稀缺性策略的潜在风险

### 2. 策略生成模块
- **四大机制应用**: 物理稀缺、人为稀缺、时间稀缺、资格稀缺
- **五层战术设计**: 数字神圣化、时间档期化、空间封闭化、资格游戏化、叙事东方化
- **实施路线图**: 分阶段实施计划，资源分配方案
- **监控指标**: 关键绩效指标设计，效果评估体系

### 3. 效果监控模块
- **数据收集**: 收集实施数据、用户反馈、市场反应
- **效果分析**: 分析策略效果，识别优化机会
- **策略调整**: 基于数据反馈调整策略
- **危机预警**: 识别潜在危机，提供应对方案

## 使用流程

### 第一步：初始化分析
1. **创建分析文件**
   ```bash
   # 使用模板初始化
   cp templates/scarcity_analysis.md scarcity_analysis.md
   cp templates/marketing_strategy.md marketing_strategy.md  
   cp templates/monitoring_dashboard.md monitoring_dashboard.md
   ```

2. **收集系统状态数据**
   - OpenHuman系统配置（GSD V2架构、模型配置）
   - 知识库状态（013-EVO、007-AI-plan流转情况）
   - 用户基础数据（用户数量、活跃度、贡献度）
   - 市场环境数据（竞争对手分析、趋势分析）

3. **运行稀缺性评分算法**
   ```bash
   # 运行稀缺性评分脚本
   python scripts/calculate_scarcity_score.py --system-config skillos.json --knowledge-base evo/
   ```

### 第二步：策略生成
1. **基于评分生成策略**
   - 高稀缺性（≥80分）：精英准入策略
   - 中高稀缺性（60-79分）：时间档期策略  
   - 中低稀缺性（<60分）：行为门槛策略

2. **设计具体实施计划**
   - 用户分级体系设计
   - 时间档期规划
   - 资格审核机制
   - 叙事包装方案

3. **制定监控指标**
   - 稀缺性强度指标（申请通过率、等待队列、溢价率）
   - 用户参与指标（活跃度、贡献度、社区产出）
   - 商业效果指标（转化率、用户价值、品牌指数）

### 第三步：实施与监控
1. **分阶段实施**
   - 阶段一（1-2月）：基础建设
   - 阶段二（3-4月）：试点运营
   - 阶段三（5-6月）：全面推广
   - 阶段四（长期）：持续优化

2. **实时监控与调整**
   - 每日数据收集
   - 每周效果分析
   - 每月策略调整
   - 季度全面评估

## 文件系统结构

### 技能目录（${CLAUDE_PLUGIN_ROOT}/）
```
scarcity-marketing-advisor/
├── SKILL.md                    # 技能元数据（本文件）
├── config/                     # 配置文件
│   ├── scarcity-rules.yaml     # 稀缺性规则定义
│   ├── user-tiers.yaml         # 用户等级配置
│   ├── scheduling.yaml         # 时间档期配置
│   └── thresholds.yaml         # 阈值配置
├── scripts/                    # 执行脚本
│   ├── calculate_scarcity_score.py    # 稀缺性评分算法
│   ├── generate_strategy.py           # 策略生成引擎
│   ├── monitor_effects.py             # 效果监控脚本
│   ├── update_user_tier.py            # 用户等级更新
│   └── analyze_market_trends.py       # 市场趋势分析
├── templates/                  # 模板文件
│   ├── scarcity_analysis.md    # 稀缺性分析报告模板
│   ├── marketing_strategy.md   # 营销策略计划模板
│   ├── monitoring_dashboard.md # 监控仪表板模板
│   └── implementation_plan.md  # 实施计划模板
├── data/                       # 数据存储
│   ├── metrics/                # 指标数据
│   ├── user_profiles/          # 用户画像
│   └── market_trends/          # 市场趋势数据
└── reference/                  # 参考文档
    ├── scarcity_handbook.md    # 稀缺性营销手册摘要
    ├── openhuman_tech_spec.md  # OpenHuman技术规格
    └── case_studies.md         # 案例分析
```

### 项目目录（你的工作目录）
```
your-project/
├── scarcity_analysis.md        # 当前项目的稀缺性分析
├── marketing_strategy.md       # 营销策略计划
├── monitoring_dashboard.md     # 监控仪表板
├── implementation_timeline.md  # 实施时间线
└── data/                       # 项目特定数据
    ├── system_snapshot.json    # 系统状态快照
    └── user_feedback.json      # 用户反馈数据
```

## 核心算法

### 稀缺性评分算法
```python
def calculate_scarcity_score(system_state, market_data, user_base):
    """
    计算OpenHuman系统的综合稀缺性评分（0-100分）
    权重分配：
    - 技术稀缺性：40%
    - 市场稀缺性：30% 
    - 认知稀缺性：20%
    - 生态稀缺性：10%
    """
    # 技术稀缺性评估
    tech_score = evaluate_tech_uniqueness(
        gsdv2_architecture=system_state.gsdv2,
        multi_model_engine=system_state.models,
        carbon_silicon_symbiosis=system_state.symbiosis
    )
    
    # 市场稀缺性评估
    market_score = evaluate_market_position(
        competitor_analysis=market_data.competitors,
        market_gap_analysis=market_data.gaps,
        trend_analysis=market_data.trends
    )
    
    # 认知稀缺性评估
    perception_score = evaluate_brand_perception(
        brand_awareness=user_base.awareness,
        thought_leadership=user_base.leadership,
        community_engagement=user_base.engagement
    )
    
    # 生态稀缺性评估
    ecosystem_score = evaluate_ecosystem_strength(
        developer_community=user_base.developers,
        plugin_ecosystem=system_state.plugins,
        partner_network=system_state.partners
    )
    
    total_score = (
        tech_score * 0.4 +
        market_score * 0.3 +
        perception_score * 0.2 +
        ecosystem_score * 0.1
    )
    
    return round(total_score, 1)
```

### 策略推荐引擎
```python
def recommend_strategy(scarcity_score, resources, timeline):
    """
    基于稀缺性评分推荐最优营销策略
    """
    if scarcity_score >= 80:
        return {
            "strategy": "elite-access",
            "description": "精英准入策略 - 强化技术壁垒，严格审核",
            "key_actions": [
                "严格技术背景审核",
                "高价定位筛选用户",
                "绝对数量限制（<100席位）",
                "深度技术合作要求"
            ],
            "timeline": "6-12个月",
            "success_metrics": ["溢价率>300%", "申请通过率<10%", "等待队列>500人"]
        }
    elif scarcity_score >= 60:
        return {
            "strategy": "temporal-scarcity", 
            "description": "时间档期策略 - 固定发布节奏，制造紧迫感",
            "key_actions": [
                "每周四20:00固定上新",
                "提前内容预热（7-3-1天节奏）",
                "限量抢购机制",
                "倒计时营销"
            ],
            "timeline": "3-6个月",
            "success_metrics": ["售罄率>80%", "复购率>50%", "社群活跃度>30%"]
        }
    else:
        return {
            "strategy": "behavioral-barrier",
            "description": "行为门槛策略 - 贡献度体系，渐进解锁",
            "key_actions": [
                "贡献度积分体系",
                "任务挑战解锁权益",
                "社区参与要求",
                "渐进式权限开放"
            ],
            "timeline": "1-3个月",
            "success_metrics": ["月活跃度>20%", "贡献增长率>30%", "社区产出>100篇/月"]
        }
```

## 集成接口

### OpenClaw系统集成
```yaml
# skillos.json 扩展配置
"scarcity_marketing": {
  "enabled": true,
  "skill_path": "~/.skillos/skills/scarcity-marketing-advisor",
  "auto_analyze_frequency": "weekly",
  "integration_points": [
    "user_management",      # 用户分级体系
    "skill_marketplace",    # 技能市场稀缺性控制
    "release_scheduling",   # 发布时间档期
    "community_contributions" # 贡献度积分
  ],
  "alert_thresholds": {
    "scarcity_score_drop": 10,      # 稀缺性评分下降10分
    "application_approval_rate": 5, # 申请通过率低于5%
    "secondary_market_premium": 100 # 二级市场溢价低于100%
  }
}
```

### Athena知识库集成
```python
# 自动监控013-EVO想法库中的技术突破
def monitor_evo_for_scarcity_opportunities(evo_path):
    """
    扫描013-EVO目录，识别可转化为稀缺性资产的技术突破
    """
    opportunities = []
    
    for idea_file in glob.glob(f"{evo_path}/*.md"):
        content = read_file(idea_file)
        
        if contains_tech_breakthrough(content):
            breakthrough = extract_breakthrough(content)
            scarcity_potential = assess_scarcity_potential(breakthrough)
            
            if scarcity_potential > 70:  # 高稀缺性潜力
                opportunities.append({
                    "idea_file": idea_file,
                    "breakthrough": breakthrough,
                    "scarcity_potential": scarcity_potential,
                    "recommended_action": "转化为限量技能或认证体系",
                    "estimated_impact": "高"
                })
    
    return opportunities
```

## 使用场景

### 场景一：新功能发布稀缺性策划
```
用户请求: "为OpenHuman新状态机功能设计稀缺性发布策略"

技能响应:
1. 分析状态机功能的技术稀缺性
2. 评估目标用户群体的需求强度
3. 设计分级发布策略（内测→公测→正式）
4. 制定时间档期和数量限制
5. 设计资格审核机制
6. 创建营销叙事和内容预热计划
```

### 场景二：用户增长瓶颈突破
```
用户请求: "OpenHuman用户增长停滞，需要稀缺性策略刺激"

技能响应:
1. 分析当前用户结构和使用模式
2. 识别增长瓶颈的根本原因
3. 设计贡献度积分体系激励活跃度
4. 创建限量权益解锁机制
5. 建立用户等级晋升路径
6. 设计社群竞赛和挑战活动
```

### 场景三：生态合作伙伴稀缺性管理
```
用户请求: "管理OpenHuman插件开发者生态，避免过度竞争"

技能响应:
1. 分析当前插件生态的健康度
2. 设计插件类别数量限制
3. 建立开发者认证体系
4. 创建合作伙伴分级（青铜→白银→黄金）
5. 设计联合营销稀缺性权益
6. 建立插件质量标准和淘汰机制
```

## 关键原则

### 1. 真实性原则
- 稀缺性必须基于真实的技术优势或资源限制
- 避免制造虚假稀缺性（如泡泡玛特补货教训）
- 承诺的限量必须严格遵守（如百达翡丽停产策略）

### 2. 公平性原则
- 用行为门槛替代财富门槛（如三顿半返航计划）
- 设计透明公正的审核机制
- 为不同用户群体提供合理上升路径

### 3. 可持续性原则
- 稀缺性策略必须支持长期生态健康
- 平衡稀缺性与增长需求（如兰博基尼Urus策略）
- 建立反脆弱机制应对市场变化

### 4. 文化适配原则
- 东方市场：关系型稀缺（养客逻辑、配货制）
- 西方市场：机会型稀缺（公平竞争、抽签制）
- 本地化叙事包装（东方美学、技术民主化）

## 风险管理

### 1. 稀缺性泡沫破裂
- **症状**: 用户发现"稀缺是谎言"，信任崩塌
- **预防**: 严格遵守限量承诺，宁可停产也不增产
- **应对**: 百达翡丽式停产策略，维护信用而非短期收益

### 2. 黄牛反噬
- **症状**: 二级市场炒作伤害真实用户
- **预防**: 行为门槛设计（贡献度、任务挑战）
- **应对**: 三顿半式收编策略，将黄牛纳入生态

### 3. 规模诅咒
- **症状**: 用户增长稀释稀缺性
- **预防**: 结构性分层（大众产品扩量+高端产品护品牌）
- **应对**: 兰博基尼Urus模式，销量与品牌隔离

### 4. 文化冲突
- **症状**: 稀缺性遭遇道德审视
- **预防**: 技术独占替代人为限量
- **应对**: 优衣库式民主化稀缺，功能>象征

## 快速开始指南

### 1. 首次使用
```bash
# 初始化分析文件
cp templates/scarcity_analysis.md .
cp templates/marketing_strategy.md .
cp templates/monitoring_dashboard.md .

# 收集系统数据
python scripts/collect_system_data.py --config ~/.skillos/skillos.json

# 运行稀缺性分析
python scripts/calculate_scarcity_score.py --data system_data.json
```

### 2. 日常监控
```bash
# 每日数据收集
python scripts/collect_daily_metrics.py

# 更新监控仪表板
python scripts/update_dashboard.py

# 检查警报条件
python scripts/check_alerts.py
```

### 3. 策略调整
```bash
# 基于最新数据重新评估策略
python scripts/reassess_strategy.py --data latest_metrics.json

# 生成策略调整建议
python scripts/generate_adjustments.py --assessment assessment.json
```

## 模板文件说明

### scarcity_analysis.md
稀缺性分析报告模板，包含：
- 系统稀缺性资产清单
- 市场机会分析
- 用户需求评估
- 风险识别
- 综合评分和建议

### marketing_strategy.md
营销策略计划模板，包含：
- 目标设定和KPI
- 策略选择和理由
- 具体实施步骤
- 资源分配计划
- 时间线和里程碑

### monitoring_dashboard.md
监控仪表板模板，包含：
- 关键指标实时数据
- 趋势分析和预测
- 问题识别和预警
- 策略效果评估
- 建议调整方案

### implementation_plan.md
实施计划模板，包含：
- 分阶段任务分解
- 责任分配矩阵
- 风险评估和应对
- 预算和资源需求
- 成功标准定义

## 脚本功能说明

### calculate_scarcity_score.py
计算系统的综合稀缺性评分，基于：
- 技术架构独特性
- 市场定位差异化
- 用户认知价值
- 生态网络效应

### generate_strategy.py
基于稀缺性评分生成定制化营销策略，包括：
- 策略类型选择（精英准入/时间档期/行为门槛）
- 具体行动方案设计
- 资源需求评估
- 预期效果预测

### monitor_effects.py
监控策略实施效果，包括：
- 数据收集和清洗
- 指标计算和分析
- 趋势识别和预警
- 效果报告生成

### update_user_tier.py
管理用户分级体系，包括：
- 用户贡献度计算
- 等级晋升审核
- 权益分配和更新
- 通知和激励发放

### analyze_market_trends.py
分析市场趋势和竞争格局，包括：
- 竞争对手监控
- 市场机会识别
- 用户需求变化
- 技术发展趋势

## 更新和维护

### 版本更新
本技能将根据以下情况更新：
1. OpenHuman系统重大架构变更
2. 稀缺性营销理论新发展
3. 市场环境重大变化
4. 用户反馈和需求变化

### 数据备份
建议定期备份：
- 分析报告和策略文档
- 监控数据和趋势分析
- 用户反馈和案例研究
- 配置和算法参数

### 性能优化
监控技能性能指标：
- 分析计算时间
- 数据收集效率
- 报告生成速度
- 用户交互体验

## 支持与反馈

### 问题报告
如遇技能使用问题，请检查：
1. 系统依赖是否满足（Python版本、库依赖）
2. 配置文件是否正确
3. 数据访问权限是否足够
4. 网络连接是否正常

### 功能建议
欢迎提出功能改进建议，包括：
1. 新的分析维度
2. 额外的集成接口
3. 改进的算法模型
4. 更好的用户体验

### 贡献指南
如需贡献代码，请遵循：
1. 代码风格规范
2. 测试覆盖要求
3. 文档更新要求
4. 版本管理流程

---

**技能版本**: 1.0.0  
**最后更新**: 2026-04-11  
**适用系统**: Athena OpenHuman v2026.3.2+  
**依赖环境**: Python 3.8+, OpenClaw 2026.3.2+

*本技能基于《稀缺性营销：从温克尔曼到AI时代的全量操作手册》设计，专为Athena OpenHuman碳硅基共生系统优化。使用前请确保已阅读并理解相关理论和案例。*