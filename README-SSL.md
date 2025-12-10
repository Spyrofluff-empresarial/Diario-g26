HTTPS for local testing (self-signed cert or mkcert)

Option A — mkcert (recommended for dev on Windows)
1) Install mkcert: https://github.com/FiloSottile/mkcert
2) Install a local CA (run once):

```powershell
mkcert -install
```

3) Create certs for localhost in the project root:

```powershell
mkcert -cert-file cert.pem -key-file key.pem localhost 127.0.0.1 ::1
```

4) Run the Flask server (it will detect `cert.pem`/`key.pem` and enable HTTPS):

```powershell
python server.py
```

Option B — OpenSSL self-signed (if you don't want to use mkcert)
1) Generate key and cert:

```powershell
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

2) Run the server:

```powershell
python server.py
```

Notes
- The Flask process will run on `https://localhost:5000` when it finds `cert.pem` and `key.pem`.
- Browsers may warn for self-signed certs unless using mkcert (which makes the cert trusted locally).
- For production, obtain a valid certificate (e.g., Let's Encrypt) and run behind a proper webserver or reverse proxy.
