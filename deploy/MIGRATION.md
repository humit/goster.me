# Production migration: `goster` -> `gosterme`

Current production state (2026-08-11):

- service account: `goster`
- application: `/opt/goster/app`
- systemd unit: `goster.service`
- process: `/usr/bin/python3 /opt/goster/app/public_app.py`

Target state:

- service account/group: `gosterme:gosterme`
- application: `/opt/goster.me`
- virtualenv: `/opt/goster.me/.venv`
- systemd unit: `gosterme.service`
- process: `/opt/goster.me/.venv/bin/python /opt/goster.me/product_app.py`
- persistent state: `/var/lib/goster.me/goster.sqlite3`

## Migration strategy

Do not replace the working service in place. Bring up the new deployment on a temporary
localhost port first, validate it, then perform a short cut-over on port 8090.

### Prepare the new account and tree

```sh
sudo useradd \
  --system \
  --home-dir /var/lib/goster.me \
  --create-home \
  --shell /usr/sbin/nologin \
  gosterme

sudo install -d -o gosterme -g gosterme -m 0755 /opt/goster.me
```

Clone/copy the repository into `/opt/goster.me` using the host's normal deployment
credentials, then make the application tree readable by `gosterme`.

### Create the virtualenv

```sh
cd /opt/goster.me
sudo -u gosterme python3 -m venv .venv
sudo -u gosterme .venv/bin/python -m pip install --upgrade pip
sudo -u gosterme .venv/bin/python -m pip install -r requirements.txt

sudo -u gosterme .venv/bin/python -m unittest -v test_shortlinks.py
sudo -u gosterme .venv/bin/python -m py_compile \
  product_app.py public_app.py adapters.py shortlinks.py
```

### Install the canonical environment and unit

```sh
sudo install -d -m 0755 /etc/goster.me
sudo install -m 0644 \
  /opt/goster.me/deploy/gosterme.env.example \
  /etc/goster.me/gosterme.env

sudo install -m 0644 \
  /opt/goster.me/deploy/systemd/gosterme.service \
  /etc/systemd/system/gosterme.service

sudo systemctl daemon-reload
```

### Side-by-side validation

Keep the legacy `goster.service` on port 8090. Temporarily run the new app on 8091:

```sh
sudo -u gosterme env \
  GOSTER_HOST=127.0.0.1 \
  GOSTER_PORT=8091 \
  GOSTER_DATABASE=/var/lib/goster.me/goster.sqlite3 \
  /opt/goster.me/.venv/bin/python \
  /opt/goster.me/product_app.py
```

From another shell:

```sh
curl -fsS http://127.0.0.1:8091/ >/dev/null
```

Also resolve at least one real URL and verify the resulting short link, copy/share controls
and QR page.

### Cut-over

Once 8091 testing succeeds:

```sh
sudo systemctl stop goster.service
sudo systemctl start gosterme.service
sudo systemctl enable gosterme.service

curl -fsS http://127.0.0.1:8090/ >/dev/null
sudo systemctl --no-pager --full status gosterme.service
```

If Caddy already proxies `goster.me` to `127.0.0.1:8090`, no proxy change is required.
Verify the public HTTPS endpoint:

```sh
curl -I https://goster.me/
```

Browser smoke tests:

1. URL resolve;
2. canonical `goster.me/<short-code>` open;
3. Copy;
4. Share;
5. QR transfer to a second device;
6. at least one YouTube render;
7. at least one educational-site adapter render.

## Rollback

Keep the old `goster.service`, account and `/opt/goster` tree until the new service has been
stable long enough to remove the rollback path intentionally.
