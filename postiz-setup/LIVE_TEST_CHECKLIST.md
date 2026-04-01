# Postiz Live Test Checklist

Run through this after deployment. Check each box as you go.

---

## Phase 1: Infrastructure Health

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@<EC2_IP>

# Check all containers are running
cd /opt/postiz
sudo docker compose ps
```

- [ ] All 7 containers show status `Up` or `Up (healthy)`
- [ ] `postiz-postgres` shows `Up (healthy)`
- [ ] `postiz-redis` shows `Up (healthy)`
- [ ] No containers in `Restarting` loop

```bash
# Check logs for errors
sudo docker compose logs postiz --tail 50
sudo docker compose logs temporal --tail 50
```

- [ ] No fatal errors in Postiz logs
- [ ] Temporal logs show "Temporal server started successfully" (or similar)

```bash
# Check memory usage
free -h
sudo docker stats --no-stream
```

- [ ] Total RAM usage under 3.5GB (on t3.medium)

---

## Phase 2: UI Access

Open in browser: `http://<EC2_IP>:4007`

- [ ] Login/registration page loads (may take 10-15s on first load)
- [ ] No browser console errors blocking functionality
- [ ] Page is not a blank white screen or 502 error

---

## Phase 3: Account Creation

- [ ] Click "Register" / "Sign Up"
- [ ] Enter email, password, name
- [ ] Account created successfully — redirected to dashboard
- [ ] Can log out and log back in

---

## Phase 4: API Key Generation

- [ ] Navigate to Settings > Developers (or Settings > Public API)
- [ ] Generate a new API key
- [ ] Copy the key — save it somewhere safe

Test the key from EC2 terminal:

```bash
curl -s -H "Authorization: YOUR_API_KEY" \
  http://localhost:4007/api/public/v1/integrations | python3 -m json.tool
```

- [ ] Returns a JSON response (empty array `[]` is fine — no channels connected yet)
- [ ] Does NOT return 401 Unauthorized

---

## Phase 5: Social Media Connection

### LinkedIn

1. Ensure `.env` has `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` set
2. Restart if you just edited: `sudo docker compose restart postiz`
3. In Postiz UI: go to Channels > Add Channel > LinkedIn
4. Authorize via OAuth popup

- [ ] OAuth redirect works (no "redirect_uri mismatch" error)
- [ ] LinkedIn account appears in Channels list
- [ ] Channel shows as connected (not disabled)

Verify via API:

```bash
curl -s -H "Authorization: YOUR_API_KEY" \
  http://localhost:4007/api/public/v1/integrations | python3 -m json.tool
```

- [ ] LinkedIn integration appears with an `id` and `providerIdentifier: "linkedin"`

### Facebook (optional — same flow)

1. Ensure `.env` has `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET`
2. Channels > Add Channel > Facebook
3. Authorize via OAuth

- [ ] Facebook Page appears in Channels list

---

## Phase 6: Create and Schedule a Post

### Test A: Post Immediately (via UI)

1. Click "Create Post" in the Postiz dashboard
2. Select your LinkedIn channel
3. Type: `Testing Postiz self-hosted deployment — please ignore`
4. Click "Post Now" (or equivalent)

- [ ] Post is submitted without error in the UI
- [ ] Check LinkedIn — post appears on your profile/page

### Test B: Schedule a Post (via UI)

1. Create another post
2. Select LinkedIn channel
3. Type: `Scheduled test post from Postiz — please ignore`
4. Set schedule time to 5 minutes from now
5. Submit

- [ ] Post shows as "Scheduled" in the dashboard
- [ ] After 5 minutes, post appears on LinkedIn
- [ ] Post status changes to "Published" in the dashboard

### Test C: Post via API

```bash
# Get your LinkedIn integration ID from Phase 5
INTEGRATION_ID="your-linkedin-integration-id"
API_KEY="your-api-key"

# Post immediately via API
curl -X POST http://localhost:4007/api/public/v1/posts \
  -H "Authorization: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"now\",
    \"date\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",
    \"shortLink\": false,
    \"tags\": [],
    \"posts\": [
      {
        \"integration\": { \"id\": \"$INTEGRATION_ID\" },
        \"value\": [
          {
            \"content\": \"API test post from Postiz self-hosted\",
            \"image\": []
          }
        ],
        \"settings\": {
          \"__type\": \"linkedin\"
        }
      }
    ]
  }"
```

- [ ] API returns 200/201 with a success response
- [ ] Post appears on LinkedIn

---

## Phase 7: Post Delivery Verification

- [ ] At least one post was actually delivered to the social platform (visible on LinkedIn/Facebook)
- [ ] Scheduled post was delivered at approximately the correct time
- [ ] API-created post was delivered

Check Temporal UI for workflow status: `http://<EC2_IP>:8080`

- [ ] Temporal UI loads
- [ ] Completed workflows visible (shows post delivery was processed)

---

## Phase 8: Integration Dry-Run (from our backend)

On your local machine (or wherever the main backend runs):

```bash
# Set env vars pointing to the self-hosted Postiz
export POSTIZ_API_KEY="your-api-key"
export POSTIZ_API_URL="http://<EC2_IP>:4007/api/public/v1"
export POSTIZ_INTEGRATION_LI="your-linkedin-integration-id"

# Run the existing publisher in dry-run mode
python postiz_publisher.py
```

- [ ] `postiz_publisher.py` connects to the self-hosted instance
- [ ] Lists integrations correctly
- [ ] Dry-run payload is generated without errors

---

## Result Summary

| Phase | Pass/Fail | Notes |
|-------|-----------|-------|
| 1. Infrastructure | | |
| 2. UI Access | | |
| 3. Account Creation | | |
| 4. API Key | | |
| 5. Social Connection | | |
| 6. Post Creation | | |
| 7. Delivery Verification | | |
| 8. Integration Dry-Run | | |

**Overall:** PASS / FAIL

**Tested by:** _______________  
**Date:** _______________  
**EC2 Instance ID:** _______________
