---
name: dashscope-platform
description: "阿里云百炼平台(DashScope)技能包 — API密钥管理、模型可用性检查、故障排查"
version: "1.0.0"
user-invocable: true
---

# 阿里云百炼平台(DashScope)

## 触发条件
- 用户提到百炼、DashScope、Qwen、通义千问
- 用户需要检查 API 密钥或模型可用性
- 用户遇到 DashScope API 调用问题

## 执行步骤

### 1. API 密钥验证
```bash
# 检查环境变量
echo $DASHSCOPE_API_KEY

# 验证密钥有效性
curl -s https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-turbo","input":{"prompt":"test"}}'
```

### 2. IP 白名单检查
- 确认当前 IP 在白名单中
- 当前 IP: 从环境或 API 获取
- 白名单管理: 百炼控制台

### 3. 模型可用性检查
| 模型 | 用途 | 状态 |
|------|------|------|
| qwen-max | 最强推理 | 检查可用性 |
| qwen-plus | 均衡 | 检查可用性 |
| qwen-turbo | 快速 | 检查可用性 |

### 4. 故障排查
- 401: API Key 无效或过期
- 403: IP 不在白名单
- 429: 请求频率超限
- 500: 服务端错误，稍后重试

## 输出格式
```json
{
  "api_key_valid": true,
  "ip_whitelisted": true,
  "models": {
    "qwen-max": "available|unavailable",
    "qwen-plus": "available|unavailable",
    "qwen-turbo": "available|unavailable"
  },
  "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
}
```

## 配置
- API 密钥: DASHSCOPE_API_KEY 环境变量
- 端点: OpenAI 兼容格式
- 备选: 本地 Ollama (DeepSeek R1)
