# Slack App Integration

This guide covers how to set up the Medic Slack app for receiving heartbeat failure notifications.

## App Icon

Use this icon when creating your Slack app:

![Medic App Icon](assets/medic-icon-all-green.png)

---

## Creating the Slack App

### Step 1: Create a New App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Select **From scratch**
4. Enter app details:
   - **App Name:** Medic
   - **Workspace:** Select your workspace
5. Click **Create App**

### Step 2: Configure App Icon

1. In the app settings, go to **Basic Information**
2. Scroll to **Display Information**
3. Click **Add App Icon**
4. Upload the Medic icon (`medic-icon-all-green.png`)
5. Set a background color: `#2C4356` (dark blue)

### Step 3: Set Up Bot Token Scopes

1. Go to **OAuth & Permissions** in the sidebar
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add the following scopes:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Send messages to channels |
| `chat:write.public` | Send messages to channels without joining |

### Step 4: Install to Workspace

1. Go to **OAuth & Permissions**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### Step 5: Invite Bot to Channel

1. In Slack, go to the channel where you want alerts
2. Type `/invite @Medic` or click the channel name → **Integrations** → **Add apps**
3. Note the **Channel ID** (click channel name → scroll to bottom of the popup)

---

## Environment Configuration

Set these environment variables in your Medic deployment:

```bash
# Bot token from Step 4
SLACK_API_TOKEN=xoxb-your-token-here

# Channel ID from Step 5
SLACK_CHANNEL_ID=C0123456789
```

### Finding the Channel ID

**Option 1: From Slack UI**
1. Right-click the channel name
2. Select **View channel details**
3. Scroll to the bottom - Channel ID is shown there

**Option 2: From URL**
1. Open the channel in Slack web
2. URL format: `https://app.slack.com/client/TXXXXXX/CXXXXXX`
3. The `CXXXXXX` part is your Channel ID

---

## Message Format

Medic sends alert messages in the following format:

### Heartbeat Failure Alert
```
🚨 Heartbeat failure for my-service-heartbeat

Service: my-service
Team: platform
Priority: P2
Threshold: 3 missed heartbeats
Last seen: 2024-01-15 10:30:00 UTC

Runbook: https://github.com/linq-team/medic/docs/RUNBOOK.md
```

### Alert Resolved
```
✅ Heartbeat restored for my-service-heartbeat

Service: my-service
Downtime: 5 minutes
```

---

## Testing the Integration

### Manual Test

```bash
# Test with curl
curl -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer xoxb-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "C0123456789",
    "text": "🧪 Medic test message - integration working!"
  }'
```

### Using Medic CLI

```bash
medic-cli health
# Check Slack status in output
```

### Using Health Endpoint

```bash
curl http://localhost:5000/health | jq '.checks.slack'
```

---

## Troubleshooting

### "not_in_channel" Error

**Cause:** Bot hasn't been invited to the channel

**Fix:** Invite the bot with `/invite @Medic`

### "invalid_auth" Error

**Cause:** Bot token is invalid or expired

**Fix:**
1. Go to app settings → **OAuth & Permissions**
2. Click **Reinstall to Workspace**
3. Copy new token and update `SLACK_API_TOKEN`

### "channel_not_found" Error

**Cause:** Invalid channel ID or bot lacks access

**Fix:**
1. Verify channel ID is correct (starts with `C`)
2. Ensure channel is not archived
3. For private channels, invite the bot first

### Messages Not Appearing

1. Check Medic logs for Slack errors
2. Verify `SLACK_CHANNEL_ID` is set correctly
3. Confirm bot has `chat:write` scope
4. Test with manual curl request above

---

## Security Best Practices

1. **Token Storage:** Never commit tokens to git. Use environment variables or secrets management.

2. **Channel Selection:** Use a dedicated alerts channel to avoid noise in general channels.

3. **Token Rotation:** Periodically rotate the bot token:
   - Go to app settings → **OAuth & Permissions**
   - Click **Reinstall to Workspace**
   - Update `SLACK_API_TOKEN` in your deployment

4. **Audit Access:** Regularly review which channels the bot has access to.

---

## Related Documentation

- [Slack API Documentation](https://api.slack.com/docs)
- [Medic Runbook](RUNBOOK.md)
- [Medic Architecture](ARCHITECTURE.md)
