# goster.me deployment

This directory contains the canonical production deployment definition for the
public goster.me service.

## Naming

Use `goster.me` for the product, domain, repository paths and state directory.
Use `gosterme` where Unix identifiers cannot or should not contain a dot:

- service account: `gosterme`
- group: `gosterme`
- systemd unit: `gosterme.service`

Canonical paths:

- application: `/opt/goster.me`
- virtualenv: `/opt/goster.me/.venv`
- environment: `/etc/goster.me/gosterme.env`
- persistent state: `/var/lib/goster.me`

## First-time host setup

Create a dedicated non-login service account:

```sh
sudo useradd \
  --system \
  --home-dir /var/lib/goster.me \
  --create-home \
  --shell /usr/sbin/nologin \
  gosterme
```

Install the repository under `/opt/goster.me`, then create the virtualenv and
install dependencies:

```sh
cd /opt/goster.me
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Install the environment file and systemd unit:

```sh
sudo install -d -m 0755 /etc/goster.me
sudo install -m 0644 deploy/gosterme.env.example /etc/goster.me/gosterme.env
sudo install -m 0644 deploy/systemd/gosterme.service /etc/systemd/system/gosterme.service
sudo systemctl daemon-reload
sudo systemctl enable --now gosterme.service
```

The service uses systemd `StateDirectory=goster.me`, so `/var/lib/goster.me`
is created and owned for the `gosterme` account automatically.

## Caddy

`deploy/caddy/goster.me.Caddyfile` is the canonical reverse-proxy example. Merge
its site block into the host Caddy configuration, validate, and reload Caddy.

## Updating

```sh
cd /opt/goster.me
git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest -v test_shortlinks.py
.venv/bin/python -m py_compile product_app.py public_app.py adapters.py shortlinks.py
sudo systemctl restart gosterme.service
sudo systemctl --no-pager --full status gosterme.service
```

## Migration from earlier prototype names

Before changing a live host, inspect the existing unit, user and application path.
Do not delete the old service until the new `gosterme.service` has passed a local
health check and the public HTTPS endpoint works.

Recommended migration sequence:

1. stop the old public-app unit;
2. move or clone the repository to `/opt/goster.me`;
3. create the `gosterme` service account;
4. create `/opt/goster.me/.venv` and install dependencies;
5. install `/etc/goster.me/gosterme.env` and `gosterme.service`;
6. start `gosterme.service` and test `http://127.0.0.1:8090/`;
7. reload Caddy and test `https://goster.me/`;
8. only then disable/remove the old unit and legacy account/path if no longer used.

Preserve any existing SQLite state when migrating by copying it into
`/var/lib/goster.me/goster.sqlite3` with ownership `gosterme:gosterme`.
