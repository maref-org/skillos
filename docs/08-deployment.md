# 08. SkillOS 部署方案

**版本**: v0.5.0-beta
**更新日期**: 2026-06-06

---

## 1. 部署前检查清单

### 1.1 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.11 | 推荐使用 3.12 |
| SQLite | >= 3.35 | 开发/测试环境 |
| PostgreSQL | >= 15 | 生产环境（可选） |
| 内存 | >= 512MB | 最小运行内存 |
| 磁盘 | >= 1GB | 含日志和数据库 |

### 1.2 环境变量

```bash
# 必需
export SKILLOS_API_KEY="your-api-key-here"
export SKILLOS_SECRET_KEY="your-secret-key-here"

# 可选（有默认值）
export SKILLOS_DATABASE_URL="sqlite:///./skillos.db"  # 或 PostgreSQL
export SKILLOS_LOG_FORMAT="json"                      # json 或 console
export SKILLOS_LOG_LEVEL="INFO"                       # DEBUG/INFO/WARNING/ERROR
export SKILLOS_INSECURE="0"                           # 1=允许 HTTP（仅开发）
```

### 1.3 预部署验证

```bash
# 1. 运行全量测试
pytest tests/ -v --tb=short

# 2. 安全扫描
bandit -r skillos/
pip-audit

# 3. 代码格式检查
ruff check skillos/
mypy skillos/

# 4. 数据库迁移验证
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

---

## 2. 部署流程

### 2.1 标准部署（推荐）

```bash
# Step 1: 拉取代码
git pull origin main

# Step 2: 安装依赖
pip install -e ".[dev]"

# Step 3: 数据库迁移
alembic upgrade head

# Step 4: 记录部署版本
python -c "
from skillos.version import get_version_manager
mgr = get_version_manager()
mgr.record_deployment(
    version='0.5.0-beta',
    alembic_revision='$(alembic current | head -1 | cut -d' ' -f1)',
    deployed_by='$(whoami)',
    notes='Standard deployment'
)
"

# Step 5: 重启服务
systemctl restart skillos

# Step 6: 健康检查
curl -s http://localhost:8080/health | grep ok
```

### 2.2 灰度部署

```bash
# Step 1: 部署到 1% 用户
python -c "
from skillos.feature_flags import get_feature_flag_manager
mgr = get_feature_flag_manager()
mgr.create_flag('v0.5.0-beta-rollout', 'percentage', 'rollout', value=1)
"

# Step 2: 监控 15 分钟
# - 检查错误率: skillos_errors_total
# - 检查延迟: skillos_request_duration_seconds
# - 检查业务指标: skillos_skill_executions_total

# Step 3: 逐步扩大灰度
# 1% -> 5% -> 10% -> 25% -> 50% -> 100%
python -c "
from skillos.feature_flags import get_feature_flag_manager
mgr = get_feature_flag_manager()
mgr.update_flag('v0.5.0-beta-rollout', value=5)
"

# Step 4: 全量发布后关闭灰度开关
python -c "
from skillos.feature_flags import get_feature_flag_manager
mgr = get_feature_flag_manager()
mgr.update_flag('v0.5.0-beta-rollout', state='enabled')
"
```

### 2.3 Docker 部署

```bash
# 构建镜像
docker build -t skillos:v0.5.0-beta .

# 运行容器
docker run -d \
  --name skillos \
  -p 8080:8080 \
  -e SKILLOS_API_KEY="${SKILLOS_API_KEY}" \
  -e SKILLOS_SECRET_KEY="${SKILLOS_SECRET_KEY}" \
  -v skillos-data:/app/data \
  skillos:v0.5.0-beta

# 或使用 docker-compose
docker-compose up -d
```

### 2.4 Docker Compose 配置

```yaml
# docker-compose.yml
version: '3.8'
services:
  skillos:
    image: skillos:v0.5.0-beta
    ports:
      - "8080:8080"
    environment:
      - SKILLOS_API_KEY=${SKILLOS_API_KEY}
      - SKILLOS_SECRET_KEY=${SKILLOS_SECRET_KEY}
      - SKILLOS_DATABASE_URL=sqlite:///data/skillos.db
      - SKILLOS_LOG_FORMAT=json
    volumes:
      - skillos-data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./observability/prometheus.yml:/etc/prometheus/prometheus.yml
    depends_on:
      - skillos

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  skillos-data:
  grafana-data:
```

---

## 3. 回滚流程

### 3.1 自动回滚触发条件

- 错误率 > 1% 持续 2 分钟
- P99 延迟 > 2s 持续 5 分钟
- 健康检查失败持续 1 分钟

### 3.2 手动回滚

```bash
# 预览回滚
python scripts/rollback.py --dry-run

# 执行回滚
python scripts/rollback.py --confirm

# 或回滚到指定 revision
python scripts/rollback.py --to-revision abc123
```

### 3.3 回滚验证

```bash
# 检查版本
curl -s http://localhost:8080/version

# 检查数据库版本
alembic current

# 运行 smoke 测试
pytest tests/test_e2e.py -v
```

---

## 4. 监控与验证

### 4.1 部署后检查清单

- [ ] 服务启动无错误日志
- [ ] 健康检查通过
- [ ] 数据库连接正常
- [ ] 指标采集正常
- [ ] 审计日志写入正常
- [ ] 功能开关状态正确

### 4.2 关键指标

| 指标 | 健康阈值 | 检查命令 |
|------|---------|---------|
| 错误率 | < 0.1% | `curl -s localhost:8080/metrics \| grep errors` |
| P99 延迟 | < 500ms | `curl -s localhost:8080/metrics \| grep duration` |
| 活跃会话 | 正常范围 | `curl -s localhost:8080/metrics \| grep session_active` |
| 数据库连接 | 无报错 | 查看应用日志 |

### 4.3 告警确认

部署后 30 分钟内确认无 P0/P1 告警触发。

---

## 5. 部署窗口

| 环境 | 推荐窗口 | 备注 |
|------|---------|------|
| 开发 | 任意时间 | 影响范围: 开发者 |
| 测试 | 工作日 9:00-18:00 | 影响范围: QA 团队 |
| 预发布 | 工作日 14:00-16:00 | 影响范围: 内部用户 |
| 生产 | 周二/周四 02:00-04:00 UTC | 影响范围: 所有用户 |

---

## 6. 联系人

| 角色 | 联系人 | 职责 |
|------|--------|------|
| On-call SRE | sre@skillos.dev | 部署执行、故障处理 |
| Tech Lead | lead@skillos.dev | 技术决策、回滚审批 |
| Security | security@skillos.dev | 安全事件响应 |
| Product | product@skillos.dev | 业务影响评估 |
