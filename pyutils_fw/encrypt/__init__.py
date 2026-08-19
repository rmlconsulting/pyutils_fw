"""AES file encryption helpers.

Deliberately no eager re-export: ``AESEncrypt`` imports ``pyAesCrypt``,
which is NOT a declared dependency of pyutils-fw (see KNOWN-ISSUES.md).
Install pyAesCrypt yourself, then::

    from pyutils_fw.encrypt.AESEncrypt import AESEncrypt
"""
