#!/usr/bin/env python3
"""真实支付沙箱对接验证（红线 §9 不托管真实资金）

职责：
  - 检查持牌支付 adapter 所需环境变量是否配置完整
  - 配置完整 → 调 adapter 构造签名请求载荷，打印签名/载荷摘要（验证可构造）
  - 未配置 → 打印 SKIP（rc=0，不失败）

红线：
  - 不实际打款：只验证签名与载荷可构造，真实沙箱打款需持牌方测试账号（人工步骤）
  - 不打印密钥本体：输出只含签名长度 / 载荷字段摘要

用法::
    .venv/bin/python scripts/verify_payment_sandbox.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 各平台必需环境变量
_REQUIRED = {
    "alipay": ("SKILLOS_ALIPAY_APP_ID", "SKILLOS_ALIPAY_PRIVATE_KEY"),
    "wechat": ("SKILLOS_WECHAT_MCH_ID", "SKILLOS_WECHAT_APIV3_KEY"),
}


def _missing_keys(provider: str) -> list[str]:
    return [k for k in _REQUIRED[provider] if not os.environ.get(k)]


def _verify_alipay() -> bool:
    from skillos.market.payments.alipay import AlipayProvider

    provider = AlipayProvider()
    manifest = {
        "manifest_id": "verify-alipay-1",
        "total_amount": 1.0,
        "payee": {"account": "test-alipay-user"},
        "note": "SkillOS sandbox verification",
    }
    params = provider._build_signed_params("alipay.fund.trans.uni.transfer", provider._build_biz_content(manifest))
    sign = params.pop("sign", "")
    print("  alipay 载荷摘要: app_id=%s method=%s biz_content=%d chars"
          % (params.get("app_id", ""), params.get("method", ""), len(params.get("biz_content", ""))))
    print("  alipay RSA2 签名长度: %d chars（可构造 ✅）" % len(sign))
    return bool(sign)


def _verify_wechat() -> bool:
    from skillos.market.payments.wechat import WeChatPayProvider

    provider = WeChatPayProvider()
    payload = provider._build_transfer_payload(
        {
            "manifest_id": "verify-wechat-1",
            "total_amount": 1.0,
            "payee": {"openid": "test-openid"},
            "note": "SkillOS sandbox verification",
        }
    )
    headers = provider._signed_headers("POST", "/v3/fund-app/mch-transfer/transfer-bills", payload)
    auth = headers.get("Authorization", "")
    sig = auth.split('signature="')[1].split('"')[0] if 'signature="' in auth else ""
    print("  wechat 载荷摘要: out_bill_no=%s transfer_amount=%d"
          % (payload.get("out_bill_no", ""), payload.get("transfer_amount", 0)))
    print("  wechat 签名长度: %d chars, scheme=%s（可构造 ✅）"
          % (len(sig), "RSA-SHA256" if provider.private_key_pem else "HMAC-sandbox"))
    return bool(sig)


def main() -> int:
    rc = 0
    any_configured = False
    print("=" * 66)
    print("支付沙箱对接验证（只构造签名/载荷，不打款）")
    print("=" * 66)
    for provider in ("alipay", "wechat"):
        missing = _missing_keys(provider)
        if missing:
            print(f"  [{provider:8s}] SKIP: 缺 {' / '.join(missing)}")
            continue
        any_configured = True
        print(f"  [{provider:8s}] 配置完整，验证签名载荷构造:")
        ok = _verify_alipay() if provider == "alipay" else _verify_wechat()
        if not ok:
            rc = 1
    if not any_configured:
        print("  无平台配置。配置持牌方测试 key 后运行可验证真实沙箱对接。")
        print("  （真实沙箱打款需持牌方测试账号，人工执行步骤）")
    print("=" * 66)
    print(f"验证结果: {'FAIL' if rc else 'OK / SKIP'} (rc={rc})")
    print("=" * 66)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
