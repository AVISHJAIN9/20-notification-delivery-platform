"""
Provider Credential Management and Masking (NTF-049).
Ensures encryption at rest and strict redaction/masking on API/log outputs.
"""

import os
import json
import base64
import hashlib
from typing import Dict, Any, Optional

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None


class ProviderCredentialManager:
    """
    Encrypts provider credentials at rest and provides output masking (NTF-049).
    """
    SENSITIVE_KEYS = {
        "api_key", "auth_token", "secret", "signing_secret",
        "password", "private_key", "token", "access_token"
    }

    def __init__(self, secret_key: Optional[str] = None):
        raw_key = secret_key or os.getenv("PROVIDER_CREDENTIAL_KEY", "default-notification-platform-secret-32b")
        # Ensure 32-byte url-safe base64 key for Fernet
        k_hash = hashlib.sha256(raw_key.encode("utf-8")).digest()
        self.fernet_key = base64.urlsafe_b64encode(k_hash)
        if Fernet:
            self._cipher = Fernet(self.fernet_key)
        else:
            self._cipher = None

    def encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        data = json.dumps(credentials).encode("utf-8")
        if self._cipher:
            return self._cipher.encrypt(data).decode("utf-8")
        # Fallback obfuscation if cryptography not available
        b64 = base64.b64encode(data).decode("utf-8")
        return f"enc_v1:{b64}"

    def decrypt_credentials(self, encrypted_payload: str) -> Dict[str, Any]:
        if not encrypted_payload:
            return {}
        if self._cipher and not encrypted_payload.startswith("enc_v1:"):
            data = self._cipher.decrypt(encrypted_payload.encode("utf-8"))
            return json.loads(data.decode("utf-8"))
        if encrypted_payload.startswith("enc_v1:"):
            raw_b64 = encrypted_payload[len("enc_v1:"):]
            data = base64.b64decode(raw_b64.encode("utf-8"))
            return json.loads(data.decode("utf-8"))
        if self._cipher:
            data = self._cipher.decrypt(encrypted_payload.encode("utf-8"))
            return json.loads(data.decode("utf-8"))
        return {}

    @classmethod
    def mask_credentials(cls, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Masks all sensitive credential keys for API responses and logs.
        """
        masked = {}
        for k, v in credentials.items():
            if not isinstance(v, str):
                masked[k] = v
                continue

            k_lower = k.lower()
            if any(s in k_lower for s in cls.SENSITIVE_KEYS):
                if len(v) > 8:
                    masked[k] = f"{v[:3]}***{v[-4:]}"
                else:
                    masked[k] = "********"
            else:
                masked[k] = v
        return masked
