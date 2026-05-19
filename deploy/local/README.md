# Running BookForge as a System Service (Linux)

This makes BookForge start automatically on boot and restart after crashes.

## Setup

```bash
# Clone repo to /opt/bookforge
sudo git clone https://github.com/YOUR_USERNAME/book-forge /opt/bookforge
cd /opt/bookforge

# Copy env file
sudo cp backend/.env.example backend/.env
sudo nano backend/.env  # fill in your values

# Install systemd unit
sudo cp deploy/local/bookforge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bookforge
sudo systemctl start bookforge
```

## Management

```bash
sudo systemctl status bookforge    # check if running
sudo systemctl restart bookforge   # restart everything
sudo systemctl stop bookforge      # stop
journalctl -u bookforge -f         # follow logs
```

## Updates

```bash
cd /opt/bookforge
git pull
sudo systemctl reload bookforge    # pulls new images + restarts
```
