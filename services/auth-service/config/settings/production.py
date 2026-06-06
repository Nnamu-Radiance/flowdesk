from .base import *

DEBUG = False
SECURE_SSL_REDIRECT = False  # TLS terminated at ingress; pods communicate over HTTP inside the cluster
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
