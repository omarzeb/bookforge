# Cloudflare Tunnel Setup

Cloudflare Tunnel gives you a public HTTPS URL without opening ports or
needing a static IP. Free, works with any internet connection.

## Prerequisites
- A domain added to Cloudflare (free account works)
- Docker running with the BookForge stack

## Step 1 — Install cloudflared

**Windows (Anaconda prompt):**
```bash
winget install Cloudflare.cloudflared
```

**Linux/Mac:**
```bash
brew install cloudflare/cloudflare/cloudflared
# or
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

## Step 2 — Authenticate

```bash
cloudflared tunnel login
```
This opens a browser window. Select your domain. A credentials file is saved.

## Step 3 — Create the tunnel

```bash
cloudflared tunnel create bookforge
```
Note the tunnel ID printed (e.g. `abc123-...`).

## Step 4 — Create the config file

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: /root/.cloudflared/YOUR_TUNNEL_ID_HERE.json

ingress:
  - hostname: bookforge.yourdomain.com
    service: http://localhost:80    # Caddy listens here
  - service: http_status:404
```

## Step 5 — Create DNS record

```bash
cloudflared tunnel route dns bookforge bookforge.yourdomain.com
```

## Step 6 — Update Caddyfile

Replace `bookforge.yourdomain.com` in `deploy/local/Caddyfile` with your actual domain.

Since Cloudflare handles TLS termination, tell Caddy to use Cloudflare's
internal CA instead of Let's Encrypt:

```caddyfile
bookforge.yourdomain.com {
    tls internal   # Cloudflare Tunnel handles external TLS

    handle /api/* {
        reverse_proxy api:8080
    }
    handle {
        reverse_proxy frontend:3000
    }
}
```

## Step 7 — Run the tunnel

```bash
cloudflared tunnel run bookforge
```

## Step 8 — Run as a service (survives reboots)

**Linux (systemd):**
```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

**Windows:**
```bash
cloudflared service install
```

## Verify

Visit `https://bookforge.yourdomain.com` — you should see the BookForge landing page over HTTPS.

Now give this URL to UptimeRobot to monitor `/health`.
