# Slack App Integration

This guide covers how to set up the Medic Slack app for receiving heartbeat failure notifications.

## App Icons

Use these icons when creating your Slack apps:

| Environment | Icon | File |
|-------------|------|------|
| Production | ![Medic](assets/medic-icon-all-green.png) | `docs/assets/medic-icon-all-green.png` |
| Development | ![Dev-Medic](assets/medic-icon-dev.png) | `docs/assets/medic-icon-dev.png` |

The dev icon has a red "DEV" banner to make it easy to distinguish from production.

---

## Quick Setup (Recommended)

The fastest way to create the Medic Slack app is using the app manifest.

### Using the App Manifest

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Select **From an app manifest**
4. Select your workspace
5. Copy the contents of one of these manifest files:
   - **Production:** `slack-manifest.yml` (in the repo root)
   - **Development:** `slack-manifest-dev.yml` (for local dev/testing)
6. Paste the YAML content and click **Next**
7. Review the app configuration and click **Create**
8. Click **Install to Workspace** and authorize

After installation:
- Go to **Basic Information** → **Display Information** → Upload the appropriate icon:
  - Production: `docs/assets/medic-icon-all-green.png`
  - Development: `docs/assets/medic-icon-dev.png` (has red "DEV" banner)
- Go to **OAuth & Permissions** → Copy **Bot User OAuth Token**
- Go to **Basic Information** → **App Credentials** → Copy **Signing Secret**
- Update the **Interactivity Request URL** in app settings to your Medic instance URL

Then add these to your `.env` file:
```bash
# "Bot User OAuth Token" from Slack (starts with xoxb-)
SLACK_API_TOKEN=xoxb-your-copied-bot-token

# "Signing Secret" from Basic Information -> App Credentials
SLACK_SIGNING_SECRET=your-copied-signing-secret

# See "Finding the Channel ID" below
SLACK_CHANNEL_ID=C0123456789
```

Skip to [Finding the Channel ID](#finding-the-channel-id) to complete setup.

---

## Manual Setup

If you prefer to create the app manually or need to customize it:

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

### Step 5: Get the Signing Secret (For Interactive Features)

If you plan to use Slack interactive features (buttons, approvals, slash commands):

1. Go to **Basic Information** in your app settings
2. Scroll to **App Credentials**
3. Find **Signing Secret** and click **Show**
4. Copy the signing secret value

> **Note:** The signing secret is used to verify that incoming requests to your webhook endpoints actually come from Slack.

### Step 6: Invite Bot to Channel

1. In Slack, go to the channel where you want alerts
2. Type `/invite @Medic` or click the channel name → **Integrations** → **Add apps**
3. Note the **Channel ID** (click channel name → scroll to bottom of the popup)

---

## Environment Configuration

Set these environment variables in your Medic deployment (in your `.env` file):

```bash
# Bot token - for sending messages to Slack
SLACK_API_TOKEN=xoxb-your-token-here

# Channel ID - where alerts are sent
SLACK_CHANNEL_ID=C0123456789

# Signing secret - verifies incoming webhook requests from Slack
# Required for interactive features (approve/decline buttons)
SLACK_SIGNING_SECRET=your-signing-secret-here
```

| Variable | Slack Name | Purpose |
|----------|------------|---------|
| `SLACK_API_TOKEN` | "Bot User OAuth Token" (starts with `xoxb-`) | Authenticate API calls to send messages |
| `SLACK_CHANNEL_ID` | Channel ID (starts with `C`) | Target channel for alerts |
| `SLACK_SIGNING_SECRET` | "Signing Secret" | Verify button clicks came from Slack |

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

## Enabling Interactivity (For Playbook Approvals)

Medic supports interactive approval workflows where users can approve or decline playbook executions directly from Slack using buttons.

### Configure Interactivity

1. Go to your app settings at [api.slack.com/apps](https://api.slack.com/apps)
2. Select your Medic app
3. Go to **Interactivity & Shortcuts** in the sidebar
4. Toggle **Interactivity** to **On**
5. Set the **Request URL** to your Medic instance:
   ```
   https://your-medic-instance.example.com/api/v1/slack/interactions
   ```
6. Click **Save Changes**

### Local Development with Interactivity

For local development, Slack needs to reach your local server. Use a tunnel service:

**Using ngrok:**
```bash
# Start ngrok tunnel to your local Medic API
ngrok http 8080

# Note the https URL, e.g., https://abc123.ngrok.io
# Set the Request URL to: https://abc123.ngrok.io/api/v1/slack/interactions
```

**Using Cloudflare Tunnel:**
```bash
cloudflared tunnel --url http://localhost:8080
```

> **Important:** The signing secret (`SLACK_SIGNING_SECRET`) must be set in your `.env` file for Medic to verify that incoming button clicks actually came from Slack. Without it, the interactivity endpoint will reject all requests.

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
