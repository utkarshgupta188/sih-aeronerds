# Deploying AeroNerds (SIH26011) to an AWS server

Target: **Ubuntu 24.04 on EC2**, Docker Compose, nginx in front, Let's Encrypt
for TLS. Everything here is scripted, so the whole deployment is a few commands.

> **Before you start.** The portal ships with visible demo passwords. That is
> deliberate for judging, and it is fine on a public IP you share with evaluators.
> It is *not* fine if you intend to store real citizen grievance data. See
> [Before you go public](#before-you-go-public).

---

## 1. Create the instance

**EC2 → Launch instance**

| Setting | Value | Why |
|---|---|---|
| Name | `aeronerds-sih26011` | |
| Image | Ubuntu Server 24.04 LTS | `setup_aws.sh` targets it |
| Architecture | x86_64 | matches the Docker build |
| Instance type | `t3.medium` (2 vCPU / 4 GB) | see the note below |
| Key pair | create or select an existing one | you need the `.pem` to SSH |
| Storage | 20 GB gp3 | the GeoJSON layers are a few hundred MB |

**Security group** — inbound rules, and only these three:

| Type | Port | Source | Note |
|---|---|---|---|
| SSH | 22 | your IP only | never `0.0.0.0/0` |
| HTTP | 80 | `0.0.0.0/0` | for TLS + ACME |
| HTTPS | 443 | `0.0.0.0/0` | the site |

**Do not open 8000.** The container is bound to `127.0.0.1`, so nothing but the
reverse proxy can reach it.

> **On instance size.** The portal itself is light — the heavy geospatial and ML
> stack ran offline to produce the GeoJSON. `t3.micro` will technically boot, but
> `docker build` gets OOM-killed on 1 GB, which is why the setup script adds swap.
> `t3.medium` builds comfortably. If your ML pipeline must also run on the box,
> use `t3.2xlarge` or a Graviton instance and see [Running the pipeline](#5-running-the-pipeline-on-the-server).

**Elastic IP** so the address survives an instance stop/start:
EC2 → Network → Elastic IPs → Allocate → Associate.

---

## 2. Connect and run the setup script

```bash
chmod 600 your-key.pem
ssh -i your-key.pem ubuntu@<elastic-ip>
```

On the server:

```bash
git clone <your-repo-url> aeronerds && cd aeronerds
bash deploy/setup_aws.sh
```

This installs Docker from Docker's official apt repo, nginx, certbot, enables
the firewall, and creates a swap file if you are under 2 GB RAM.

> You added yourself to the `docker` group. **Log out and back in** or the group
> change will not apply.
>
> ```bash
> exit && ssh -i your-key.pem ubuntu@<elastic-ip>
> ```

---

## 3. Upload the code

If you did not clone on the server, copy it in:

```bash
# from your laptop
scp -i your-key.pem -r . ubuntu@<elastic-ip>:/opt/aeronerds/app
```

Exclude `data/*.db` and `.env` — the server generates its own.

---

## 4. Deploy

```bash
cd /opt/aeronerds/app
bash deploy/deploy.sh
```

What it does:

1. Generates `AERONERDS_TOKEN_SECRET` into `.env` (once — reusing it on later runs
   so sessions survive a redeploy) and `chmod 600`.
2. Builds the image, with `.env` added to `.gitignore`.
3. **Pre-flight:** boots the new image on port 8099 and refuses to roll out
   unless `/api/meta/health` responds. A broken build never replaces a working
   container.
4. `docker compose up -d`.
5. Verifies the live container, that `/` serves the public homepage, that an
   unauthenticated API read returns 401, then runs `scripts/smoke_test.py`.

Set the domain in the nginx config before or after:

```bash
sudo cp /opt/aeronerds/app/deploy/nginx/aeronerds.conf /etc/nginx/sites-available/aeronerds
sudo nano /etc/nginx/sites-available/aeronerds   # replace your-domain.example
sudo ln -s /etc/nginx/sites-available/aeronerds /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. DNS and TLS

Point an **A record** at the Elastic IP, wait for it to resolve, then:

```bash
sudo certbot --nginx -d your-domain.example -d www.your-domain.example
sudo certbot renew --dry-run     # verify auto-renewal works
```

Certbot installs a systemd timer, so renewal is automatic.

Check it:

```bash
curl -I https://your-domain.example/            # 200, public homepage
curl -I https://your-domain.example/index.html  # 200, sign-in gate
curl -s  https://your-domain.example/api/meta/health
```

---

## 6. Operating it

```bash
docker compose ps                  # status
docker compose logs -f portal      # tail logs
docker compose restart portal      # restart
docker compose down                # stop (data survives in the volume)
docker compose up -d --build       # redeploy after a code change
bash deploy/deploy.sh              # full safe redeploy, with pre-flight
```

### Back up the auth database

Users, sessions and citizen-property links live in the `auth-db` volume.

```bash
docker run --rm -v aeronerds_auth-db:/data -v "$PWD":/backup alpine \
    tar czf /backup/aeronerds-auth-$(date +%F).tar.gz -C /data .
```

Put that in cron. **Also back up `.env`** — without the signing secret every
session is invalidated and, if it leaks, anyone can mint a session for any role.

### Scaling

The app is stateless apart from SQLite, so for more than one instance:

- move the auth store to PostgreSQL (`backend/users.py` is the only module that
  touches it),
- store the GeoJSON in S3 and serve it through CloudFront,
- run Gunicorn with multiple workers behind the proxy, or put ECS Fargate in
  front for autoscaling.

For a hackathon demo, one `t3.medium` is comfortably enough.

---

## 7. Running the pipeline on the server

The portal only reads GeoJSON. If you want to regenerate it on the box, the
processing stack is heavy — **use a Graviton instance with 16 GB+ RAM**
(`c7g.4xlarge` or better) and build a second image from `requirements` that
includes GeoPandas, Rasterio, GDAL, PDAL and PyTorch. Expect a multi-GB image
and a slow first build.

A cheaper pattern: run the pipeline in a **GitHub Actions self-hosted or
CodeBuild** step, push the resulting GeoJSON to the repo or S3, and let the
portal serve the output. The manifest requirements in AGENTS.md rule 9 apply
either way.

---

## 8. Optional: AWS App Runner or ECS instead

**App Runner** — simplest managed option:

```bash
aws apprunner-service create \
  --service-name aeronerds \
  --source-configuration "{
    \"imageRepository\":{\"imageConfiguration\":{\"port\":\"8000\",\"runtimeEnvironmentVariables\":{
      \"AERONERDS_TOKEN_SECRET\":\"$SECRET\"
    }},
    \"image\":<your-ecr-uri>,
    \"authenticationConfiguration\":{\"accessRole\":\"NONE\"}
  }" \
  --protocol-configuration "{\"protocol\":\"HTTP\",\"domainConfiguration\":{\"port\":8000}}"
```

The catch: App Runner has **no persistent volume**, so the SQLite file is
ephemeral and lives on user data. Migrate to RDS/Postgres first.

**ECS Fargate** — right answer once you are past a demo: real persistent
storage via EFS, autoscaling, and CloudFront in front. The `Dockerfile` already
works unchanged; only the compose file is replaced by a task definition.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Homepage loads, sign-in says "auth service offline" | `/api/meta/health` unreachable | `docker compose logs portal`; check the proxy target port |
| `502 Bad Gateway` | container not up, or port mismatch | `docker compose ps`; the proxy expects `127.0.0.1:8000` |
| Everyone logged out after a deploy | signing secret changed | back up `.env`; `deploy.sh` reuses it, so this only happens if it was deleted |
| Login always 401 in the browser but works in curl | session token not persisted | confirm you are on HTTPS — `sessionStorage` is dropped on plain HTTP across some browsers |
| `429` from nginx | rate limit hit | expected; sign-in is limited to 10/min/IP |
| Build OOM-killed | 1 GB instance | use `t3.medium` or let the swap file do its job |
| Certificate fails | DNS not propagated | wait, then `sudo certbot --nginx -d your-domain.example` |
| `403` on everything | clock skew | token validity is time-based; run `timedatectl` and enable NTP |

---

## Before you go public

The prototype is honest about its limits, but a few things are demo-only by
design. Before storing anything real:

- [ ] **Replace the demo passwords.** They are printed on the sign-in screen.
      `backend/users.py` seeds them; delete that seeding and provision real
      accounts.
- [ ] **Move off SQLite** if you run more than one instance.
- [ ] **Back up `.env`.** Rotating it logs everyone out; leaking it is worse.
- [ ] **Add CSRF protection.** The token lives in `sessionStorage` with a bearer
      header, which is acceptable same-origin, but a cookie session would want a
      CSRF token.
- [ ] **Persist reviewer decisions and grievances.** Both are in-memory now, so a
      restart loses the audit trail AGENTS.md rule 8 requires.
- [ ] **Keep the disclaimers.** The homepage, the portal footer and the README
      all state that this is a prototype with no official recognition. Do not
      remove them; AGENTS.md rule 2 forbids implying otherwise.
