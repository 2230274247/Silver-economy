"""Encrypt push credentials at rest and derive non-reversible server fingerprints."""

import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import ApiError


def _key(settings):
    value = settings.notification_device_encryption_key.get_secret_value().strip()
    if not value:
        raise ApiError(
            503,
            "NOTIFICATION_ENCRYPTION_NOT_CONFIGURED",
            "设备通知服务尚未配置加密密钥",
        )
    return value.encode()


def encrypt_client_id(settings, client_id):
    try:
        return Fernet(_key(settings)).encrypt(client_id.encode()).decode()
    except (ValueError, TypeError):
        raise ApiError(
            503,
            "NOTIFICATION_ENCRYPTION_INVALID",
            "设备通知服务加密配置无效",
        ) from None


def decrypt_client_id(settings, ciphertext):
    try:
        return Fernet(_key(settings)).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        raise RuntimeError("NOTIFICATION_DEVICE_CREDENTIAL_UNREADABLE") from None


def device_fingerprint(settings, client_id):
    digest = hmac.new(_key(settings), client_id.encode(), hashlib.sha256).hexdigest()
    return digest
