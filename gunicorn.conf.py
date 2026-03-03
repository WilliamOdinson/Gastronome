"""
Gunicorn WSGI server configuration.

Binds to ``localhost:8443`` with TLS enabled using the self-signed
certificates in ``certs/``. Two worker processes are used by default.
"""

bind = 'localhost:8443'
certfile = 'certs/server.crt'
keyfile = 'certs/server.key'
workers = 2