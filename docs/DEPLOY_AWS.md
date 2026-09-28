# Deploying AeroNerds (SIH26011) to an AWS server

Two supported paths, both scripted:

| | [Native](#path-a-native-recommended) | [Docker](#path-b-docker) |
|---|---|---|
| Needs Docker | no | yes |
| Install | `sudo bash deploy/install.sh` | `bash deploy/setup_aws_docker.sh` + `bash deploy/deploy_docker.sh` |
| Service manager | systemd | Docker Compose |
| Redeploy | `sudo bash deploy/deploy.sh` | `bash deploy/deploy_docker.sh` |
| Rollback | previous tree kept on disk | previous image tag |
| Memory overhead | ~120 MB | ~200 MB |

Both produce the same thing: the portal on `127.0.0.1:8000`, nginx in front
terminating TLS with Let's Encrypt. **Path A is the default** — fewer moving
parts, no container runtime to patch, and systemd gives you `journalctl`.

The app is light. The heavy geospatial and ML stack ran offline to produce the
GeoJSON in `frontend/data/`, so the server needs only FastAPI, uvicorn and
pydantic.

> **Before you start.** The portal ships with visible demo passwords. That is
> deliberate for judging and fine on a public IP you share with evaluators. It is
> *not* fine if you intend to store real citizen grievance data — see
> [Before you go public](#9-before-you-go-public).

---

## 1. Create the instance

**EC2 → Launch instance**

| Setting | Value | Why |
|---|---|---|
| Name | `aeronerds-sih26011` | |
| Image | Ubuntu Server 24.04 LTS | the scripts target it |
| Architecture | x86_64 | |
| Instance type | `t3.small` (2 GB) native, `t3.medium` (4 GB) Docker | see below |
| Key pair | create or select an existing one | you need the `.pem` |
| Storage | 20 GB gp3 | the GeoJSON layers are a few hundred MB |

**Security group** — inbound rules, and only these three:

| Type | Port | Source | Note |
|---|---|---|---|
| SSH | 22 | your IP only | never `0.0.0.0/0` |
| HTTP | 80 | `0.0.0.0/0` | for TLS + ACME |
| HTTPS | 443 | `0.0.0.0/0` | the site |

**Do not open 8000.** Both paths bind the app to loopback, so nothing but the
reverse proxy can reach it. See [§7](#7-troubleshooting) if you are tempted.

> **On instance size.** The portal itself is light — 12,887 building footprints
> are served as static GeoJSON, and the API holds a few records in memory. The
> native path fits in 2 GB comfortably. Docker needs more headroom because
> `docker build` can be OOM-killed while compiling wheels, so use `t3.medium`
> there. If you also need to run the ML pipeline on the box, use a
> Graviton instance with 16 GB+ — see [§8](#8-running-the-pipeline-on-the-server).

**Elastic IP** so the address survives a stop/start:
EC2 → Network → Elastic IPs → Allocate → Associate.

---

## Path A: native (recommended)

No container runtime. A systemd service runs uvicorn as a dedicated
unprivileged user, with nginx in front.

### 2. Connect

```bash
chmod 600 your-key.pem
ssh -i your-key.pem ubuntu@<elastic-ip>
```

### 3. Upload the code

```bash
# on your laptop
scp -i your-key.pem -r . ubuntu@<elastic-ip>:/opt/aeronerds-src
```

Exclude `data/*.db` and `.env` — the server generates its own. Or clone on the
server if you pushed to a remote:

```bash
git clone <your-repo-url> /opt/aeronerds-src
```

### 4. Install

```bash
sudo bash /opt/aeronerds-src/deploy/install.sh
```

The script does the lot and verifies each step:

1. Installs `python3-venv`, nginx and certbot if missing.
2. Creates the `aeronerds` system user (nologin, never root).
3. Copies code to `/opt/aeronerds/app`, creating a virtualenv at
   `/opt/aeronerds/venv` and installing pinned dependencies.
4. Generates `AERONERDS_TOKEN_SECRET` into `/etc/aeronerds/aeronerds.env`
   (mode `0640`, root-owned) — **only if absent**, so rerunning does not log
   everyone out.
5. Installs the systemd unit and starts the service.
6. Verifies the health endpoint, that `/` renders the homepage, that an
   unauthenticated API read returns 401, and that the auth database really is
   on the writable volume — then runs the access-model smoke test.

Layout:

```
/opt/aeronerds/app       application code
/opt/aeronerds/venv      Python virtualenv
/var/lib/aeronerds       the auth database — the only writable path
/etc/aeronerds/…env      signing secret, 0640
```

### 5. nginx and TLS

```bash
sudo cp /opt/aeronerds-src/deploy/nginx/aeronerds.conf /etc/nginx/sites-available/aeronerds
sudo nano /etc/nginx/sites-available/aeronerds     # set server_name
sudo ln -s /etc/nginx/sites-available/aeronerds /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Point a DNS **A record** at the Elastic IP, then:

```bash
sudo certbot --nginx -d your-domain.example
sudo certbot renew --dry-run     # verify auto-renewal
```

### 6. Day-to-day

```bash
sudo systemctl status aeronerds
sudo journalctl -u aeronerds -f
sudo systemctl restart aeronerds

# redeploy after a code change
sudo bash /opt/aeronerds-src/deploy/deploy.sh
```

`deploy.sh` imports the new code in a throwaway process first, snapshots the
current tree to `/opt/aeronerds/app.prev`, reinstalls dependencies only if
`requirements-auth.txt` changed, restarts, and re-runs the smoke test. If the
service does not come up it prints the rollback command rather than leaving you
hanging.

```bash
# manual rollback
sudo rm -rf /opt/aeronerds/app
sudo mv /opt/aeronerds/app.prev /opt/aeronerds/app
sudo systemctl restart aeronerds
```

### Security hardening already applied

The unit sets `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`,
`PrivateDevices`, `NoNewPrivileges`, `LockPersonality`,
`MemoryDenyWriteExecute` and a `RestrictAddressFamilies` allowlist, with
`ReadWritePaths=/var/lib/aeronerds` as the single writable directory. The
service runs as `aeronerds`, not root, and cannot write to its own code.

Check it:

```bash
sudo systemd-analyze security aeronerds
```

---

## Path B: Docker

Identical outcome, containerised. Use this if you want the build environment
reproducible or expect to move to ECS later.

```bash
ssh -i your-key.pem ubuntu@<elastic-ip>
git clone <your-repo-url> aeronerds && cd aeronerds
bash deploy/setup_aws_docker.sh     # Docker, nginx, certbot, firewall, swap
# log out and back in for the docker group change to apply
exit && ssh -i your-key.pem ubuntu@<elastic-ip>
```

Then follow [§2](#2-connect) → [§5](#5-nginx-and-tls) using
`bash deploy/deploy_docker.sh` for the roll-out and
`bash deploy/deploy_docker.sh` again for redeploys.

The compose file binds `127.0.0.1:8000:8000`, keeps the auth database on a named
volume, and fails fast if `AERONERDS_TOKEN_SECRET` is unset.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `502 Bad Gateway` in nginx | service not listening | `systemctl status aeronerds`; `journalctl -u aeronerds -n 50` |
| Service fails to start | permissions or missing dep | `journalctl -u aeronerds -n 50`; check `/var/lib/aeronerds` is owned by `aeronerds` |
| `status=203/EXEC` | venv path wrong | the unit expects `/opt/aeronerds/venv`; rerun `install.sh` |
| Homepage loads, sign-in says "auth service offline" | `/api` unreachable | check nginx proxies `/api/` to `127.0.0.1:8000` |
| Everyone logged out after deploy | signing secret changed | never edit `/etc/aeronerds/aeronerds.env`; back it up instead |
| Login 401 in the browser, works in curl | `sessionStorage` dropped | serve over HTTPS; some browsers discard it on plain HTTP |
| Service won't write the database | `ProtectSystem=strict` blocking | only `/var/lib/aeronerds` is writable; check `AERONERDS_AUTH_DB` points there |
| pip refuses to install | Ubuntu 24.04 PEP 668 | use the venv at `/opt/aeronerds/venv`, never system pip |
| `429` from nginx | rate limit hit | expected; sign-in is limited to 10/min/IP |
| OOM-killed | 1 GB instance | bump to `t3.medium`, or add swap (Docker script does this) |
| Certificate fails | DNS not propagated | wait, then `sudo certbot --nginx -d your-domain.example` |
| 403 on everything | clock skew | tokens are time-based; `timedatectl` and enable NTP |

---

## 8. Running the pipeline on the server

The portal only reads GeoJSON. To regenerate it on the box, the processing stack
is heavy — **use a Graviton instance with 16 GB+** (`c7g.4xlarge` or better).
Expect a multi-GB environment with GeoPandas, Rasterio, GDAL, PDAL and PyTorch,
and a slow first install.

A cheaper pattern: run the pipeline in **GitHub Actions** or **AWS CodeBuild**,
push the resulting GeoJSON to the repo or S3, and let the portal serve the
output. The manifest requirements in AGENTS.md rule 9 apply either way.

---

## 9. Before you go public

The prototype is honest about its limits, but a few things are demo-only by
design. Before storing anything real:

- [ ] **Replace the demo passwords.** They are printed on the sign-in screen.
      `backend/users.py` seeds them; remove that seeding and provision real
      accounts.
- [ ] **Back up `/etc/aeronerds/aeronerds.env`.** Rotating it logs everyone
      out; leaking it lets an attacker mint a session for any role. It replaces
      the `.env` file on the Docker path.
- [ ] **Back up the auth database**, on a schedule:

      ```bash
      # native
      sudo install -d -m 0700 /var/backups/aeronerds
      sudo sqlite3 /var/lib/aeronerds/aeronerds_auth.db \
        ".backup '/var/backups/aeronerds/auth-$(date +%F).db'"

      # docker
      docker run --rm -v aeronerds_auth-db:/data -v "$PWD":/backup alpine \
          tar czf /backup/aeronerds-auth-$(date +%F).tar.gz -C /data .
      ```

- [ ] **Move off SQLite** if you run more than one instance. `backend/users.py`
      is the only module that touches it.
- [ ] **Add CSRF protection.** The token lives in `sessionStorage` with a bearer
      header, which is acceptable same-origin, but a cookie session would want a
      CSRF token.
- [ ] **Persist reviewer decisions and grievances.** Both are in-memory now, so
      a restart loses the audit trail AGENTS.md rule 8 requires.
- [ ] **Keep the disclaimers.** The homepage, the portal footer and the README
      all state that this is a prototype with no official recognition. Do not
      remove them; AGENTS.md rule 2 forbids implying otherwise.
