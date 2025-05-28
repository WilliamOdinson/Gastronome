# Running Django with HTTPS Locally

This document explains how to serve your Django application over HTTPS in a local development environment. You will use **Gunicorn** as the WSGI HTTP server and **mkcert** (with the **nss** plugin) to generate a locally-trusted TLS certificate, all without modifying your `wsgi.py`.

## Prerequisites

Ensure you have the following tools installed:

- **Homebrew** for macOS package management
- **Gunicorn**, a lightweight WSGI HTTP server for running Python web applications:

  ```bash
  pip install gunicorn
  ```

## 1  Trusting a Local Certificate Authority with mkcert + nss

You need a certificate authority that your browser will accept. **mkcert** automates creation of a local CA and certificates signed by it. The **nss** plugin lets mkcert add this CA into Firefox's own trust store.

Run these commands in Terminal:

```bash
brew install mkcert nss
mkcert -install
```

You will be prompted for your administrator password. Upon success, mkcert confirms:

```bash
Created a new local CA
The local CA is now installed in the system trust store!
```

## 2  Generating a Certificate for `localhost`

With the CA trusted, generate a certificate covering both `localhost` and `127.0.0.1`. From your project root (where `manage.py` lives), run:

```bash
mkcert localhost 127.0.0.1
```

mkcert outputs two files in the current directory:

- `localhost+1.pem` - the public certificate
- `localhost+1-key.pem` - the corresponding private key

These files remain valid until the expiration date mkcert displays.

## 3  Organizing Your Certificate Files (Optional)

For clarity, you may wish to store these files under a dedicated directory. Create a folder named `certs/` and move the generated files there:

```bash
mkdir -p certs
mv localhost+1.pem certs/server.crt
mv localhost+1-key.pem certs/server.key
```

## 4  Serving Your Django App over HTTPS with Gunicorn

Gunicorn can handle HTTPS termination natively by pointing at your certificate and key. No changes are required in Django's `wsgi.py`.

### Option A: One-Off Command

Run Gunicorn directly from the command line, binding to port **8443** for HTTPS:

```bash
gunicorn \
  --bind localhost:8443 \
  --certfile certs/server.crt \
  --keyfile certs/server.key \
  Gastronome.wsgi:application
```

### Option B: Config-File-Driven

If you prefer a reusable configuration, create a file named `gunicorn.conf.py` in your project root with the following content:

```python
bind = 'localhost:8443'
certfile = 'certs/server.crt'
keyfile = 'certs/server.key'
workers = 2
```

Then start Gunicorn using:

```bash
gunicorn -c gunicorn.conf.py Gastronome.wsgi:application
```
