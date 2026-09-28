#!/usr/bin/env bash
# AeroNerds SIH26011 — first-boot server setup for Ubuntu 24.04 on AWS EC2.
#
# Safe to re-run. Installs Docker, opens the firewall, and leaves the app
# deployment itself to deploy/deploy.sh.
#
#   ssh -i your-key.pem ubuntu@<ec2-public-ip>
#   bash setup_aws.sh
#
# If you would rather not run a script from the internet, paste the commands
# individually — they are all from the official Docker and Ubuntu apt repos.

set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------- packages ---
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker from the official Docker apt repository"
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg

    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin

    sudo usermod -aG docker "$USER"
    echo "  added $USER to the docker group — log out and back in for this to apply"
else
    log "Docker already present: $(docker --version)"
fi

# ------------------------------------------------------------------ nginx ---
if ! command -v nginx >/dev/null 2>&1; then
    log "Installing nginx and certbot"
    sudo apt-get install -y nginx certbot python3-certbot-nginx
    sudo systemctl enable --now nginx
else
    log "nginx already present"
fi

# --------------------------------------------------------------- swap note ---
# t3.micro / t4g.micro have 1 GB RAM. The portal itself is light, but give
# yourself headroom so the build does not get OOM-killed.
if [ "$(free -m | awk '/^Mem:/ {print $2}')" -lt 2048 ]; then
    log "Less than 2 GB RAM detected — creating a 2 GB swap file"
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile >/dev/null
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# ------------------------------------------------------------- directories ---
log "Creating deploy directories"
sudo mkdir -p /opt/aeronerds /var/www/certbot
sudo chown -R "$USER:$USER" /opt/aeronerds

# ------------------------------------------------------------ security group ---
log "Firewall"
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status verbose || true

cat <<'EOF'

--------------------------------------------------------------------
Next steps
--------------------------------------------------------------------
1. Make sure the EC2 security group allows inbound 80 and 443
   (and only 80/443/22 — never 8000, the app is bound to loopback).

2. Get the code onto the box:
       scp -i your-key.pem -r . ubuntu@<ip>:/opt/aeronerds/app

3. Deploy:
       cd /opt/aeronerds/app
       bash deploy/deploy.sh

4. Point DNS at the instance's Elastic IP.

5. Issue a certificate (do this after DNS resolves):
       sudo certbot --nginx -d your-domain.example

EOF
