from .base import *  # noqa: F401,F403

DEBUG = False

# Faster password hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Celery: run tasks eagerly (synchronously) in tests instead of needing a broker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
