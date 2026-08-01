"""Tests for M7-P2 — verify_payment_sandbox.py（真实沙箱对接验证脚本）

只测无 key 的 SKIP 分支与加载逻辑；有 key 的载荷构造依赖持牌方测试账号，
不在自动化测试内执行（红线 §9 不打款）。
"""

import importlib.util
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "verify_payment_sandbox",
    _scripts / "verify_payment_sandbox.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_no_key_skips(monkeypatch, capfd):
    for k in (
        "SKILLOS_PAYMENT_PROVIDER",
        "SKILLOS_ALIPAY_APP_ID",
        "SKILLOS_ALIPAY_PRIVATE_KEY",
        "SKILLOS_ALIPAY_PUBLIC_KEY",
        "SKILLOS_WECHAT_MCH_ID",
        "SKILLOS_WECHAT_APIV3_KEY",
        "SKILLOS_WECHAT_PRIVATE_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    rc = _mod.main()
    assert rc == 0
    out = capfd.readouterr().out
    assert "SKIP" in out


def test_with_dummy_keys_builds_payloads(monkeypatch, capfd):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = (
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("utf-8")
    )
    monkeypatch.setenv("SKILLOS_ALIPAY_APP_ID", "app-test")
    monkeypatch.setenv("SKILLOS_ALIPAY_PRIVATE_KEY", pem)
    monkeypatch.setenv("SKILLOS_WECHAT_MCH_ID", "mch-1")
    monkeypatch.setenv("SKILLOS_WECHAT_APIV3_KEY", "v3-key")
    monkeypatch.delenv("SKILLOS_ALIPAY_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("SKILLOS_WECHAT_PRIVATE_KEY", raising=False)
    rc = _mod.main()
    assert rc == 0
    out = capfd.readouterr().out
    # 输出签名/载荷摘要，但不打印密钥本体
    assert "alipay" in out
    assert "wechat" in out
    assert pem not in out
    assert "v3-key" not in out
