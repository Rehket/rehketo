from __future__ import annotations

import pytest

from rehketo.auth.crypto import decrypt_token, encrypt_token


def test_roundtrip(settings_env: pytest.MonkeyPatch) -> None:
    ct = encrypt_token("my-refresh-token")
    assert isinstance(ct, bytes)
    assert decrypt_token(ct) == "my-refresh-token"


def test_ciphertext_differs_across_calls(settings_env: pytest.MonkeyPatch) -> None:
    assert encrypt_token("same") != encrypt_token("same")


def test_tampered_ciphertext_fails(settings_env: pytest.MonkeyPatch) -> None:
    ct = bytearray(encrypt_token("x"))
    ct[-1] ^= 0x01
    with pytest.raises(ValueError):
        decrypt_token(bytes(ct))
