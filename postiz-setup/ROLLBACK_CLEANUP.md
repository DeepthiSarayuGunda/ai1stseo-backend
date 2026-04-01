# Postiz Rollback & Cleanup

Commands to stop, remove, and fully clean up the Postiz deployment if testing fails.

---

## Quick Stop (keep data)

```bash
cd /opt/postiz
sudo docker compose down
```

This stops all 7 containers but preserves volumes (database, uploads, config). You can restart later with `sudo docker compose up -d`.

---

## Full Cleanup (remove everything)

```bash
cd /opt/postiz

# Stop containers and delete all volumes (database, uploads, redis data)
sudo docker compose down -v

# Remove all pulled images
sudo docker rmi ghcr.io/gitroomhq/postiz-app:latest \
  postgres:17-alpine \
  postgres:16 \
  redis:7.2 \
  elasticsearch:7.17.27 \
  temporalio/auto-setup:1.28.1 \
  temporalio/ui:2.34.0 \
  2>/dev/null || true

# Remove the Postiz directory
sudo rm -rf /opt/postiz

# Prune unused Docker resources
sudo docker system prune -af --volumes
```

---

## Uninstall Docker (optional — only if Docker was installed solely for this)

```bash
# Ubuntu
sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo rm -rf /var/lib/docker /var/lib/containerd /etc/apt/keyrings/docker.gpg /etc/apt/sources.list.d/docker.list

# Amazon Linux 2023
sudo yum remove -y docker
sudo rm -rf /var/lib/docker
```

---

## Terminate EC2 Instance

If the entire instance was created just for this test:

```bash
# From your local machine (AWS CLI)
aws ec2 terminate-instances --instance-ids i-0xxxxxxxxxxxx

# Or via AWS Console: EC2 > Instances > select instance > Instance State > Terminate
```

---

## Verify Cleanup

```bash
# Confirm no containers running
sudo docker ps -a

# Confirm no volumes left
sudo docker volume ls

# Confirm directory removed
ls /opt/postiz 2>/dev/null && echo "Still exists" || echo "Cleaned up"
```

All three should return empty/clean results.
