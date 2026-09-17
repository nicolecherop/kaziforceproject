"""Tests use Neon direct connections so pooler sessions do not block DB cleanup."""
from .settings import *  # noqa: F403
from copy import deepcopy

DATABASES = deepcopy(DATABASES)
host = DATABASES['default']['HOST']
if host.endswith('.neon.tech') and '-pooler.' in host:
    DATABASES['default']['HOST'] = host.replace('-pooler.', '.', 1)
DATABASES['default']['TEST'] = {'NAME': 'test_kaziforce'}
# Hashing speed is unrelated to these functional tests. Production uses Django defaults.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
