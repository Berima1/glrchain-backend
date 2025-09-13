"""AES-GCM helpers — production must use KMS"""
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64

def encrypt_bytes(key: bytes, plaintext: bytes):
    iv = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return {'iv': base64.b64encode(iv).decode(), 'ciphertext': base64.b64encode(ciphertext).decode(), 'tag': base64.b64encode(tag).decode()}

def decrypt_bytes(key: bytes, iv_b64: str, ciphertext_b64: str, tag_b64: str):
    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    tag = base64.b64decode(tag_b64)
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    return cipher.decrypt_and_verify(ciphertext, tag)
