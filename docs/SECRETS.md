# Medic Secrets Management

This document describes how secrets are managed in Medic across different environments.

## Overview

| Environment | Secret Source | Admin Key Setup |
|-------------|---------------|-----------------|
| **Local Dev** | Auto-generated | `MEDIC_AUTO_CREATE_ADMIN_KEY=true` |
| **Dev (K8s)** | AWS Secrets Manager | `medic/dev/secrets` |
| **Production** | AWS Secrets Manager | `medic/production/secrets` |

## AWS Secrets Manager

### Secret Locations

| Environment | Secret Name | ARN |
|-------------|-------------|-----|
| Production | `medic/production/secrets` | `arn:aws:secretsmanager:us-east-1:018143940435:secret:medic/production/secrets-*` |
| Dev | `medic/dev/secrets` | `arn:aws:secretsmanager:us-east-1:018143940435:secret:medic/dev/secrets-*` |

### Secret Structure

Both secrets contain the following keys:

```json
{
  "MEDIC_SECRETS_KEY": "base64-encoded-32-byte-key",
  "DATABASE_URL": "postgresql://user:pass@host:5432/medic",
  "REDIS_URL": "redis://host:6379/0",
  "MEDIC_ADMIN_API_KEY": "mdk_...",
  "SLACK_API_TOKEN": "xoxb-...",
  "SLACK_SIGNING_SECRET": "...",
  "PAGERDUTY_ROUTING_KEY": "..."
}
```

### Updating Secrets

#### Via AWS CLI

```bash
# View current secret value
aws secretsmanager get-secret-value \
  --secret-id "medic/production/secrets" \
  --query SecretString \
  --output text | jq .

# Update a single key (preserves other keys)
aws secretsmanager get-secret-value \
  --secret-id "medic/production/secrets" \
  --query SecretString \
  --output text | \
  jq '.MEDIC_ADMIN_API_KEY = "mdk_new_key_here"' | \
  aws secretsmanager put-secret-value \
    --secret-id "medic/production/secrets" \
    --secret-string file:///dev/stdin

# Update entire secret
aws secretsmanager put-secret-value \
  --secret-id "medic/production/secrets" \
  --secret-string '{
    "MEDIC_SECRETS_KEY": "...",
    "DATABASE_URL": "...",
    ...
  }'
```

#### Via AWS Console

1. Go to [AWS Secrets Manager Console](https://console.aws.amazon.com/secretsmanager/)
2. Search for `medic/production/secrets` or `medic/dev/secrets`
3. Click "Retrieve secret value"
4. Click "Edit"
5. Update the JSON values
6. Click "Save"

### After Updating Secrets

The External Secrets Operator syncs secrets every hour by default (`refreshInterval: 1h`).

To force an immediate sync:

```bash
# Trigger External Secrets refresh
kubectl annotate externalsecret medic-external \
  force-sync=$(date +%s) \
  -n medic --overwrite

# Or restart the pods to pick up new secrets
kubectl rollout restart deployment/medic-api -n medic
kubectl rollout restart deployment/medic-worker -n medic
```

## Admin API Key

### Generating a New Admin Key

```bash
# Generate a new API key
python3 -c "from Medic.Core.api_keys import generate_api_key; key, _ = generate_api_key(); print(key)"

# Example output: mdk_zhRyWACCgwxGdvDoRJKsJvY9WPzETGmiAlKomx41T5s
```

### Rotating the Admin Key

1. Generate a new key (see above)
2. Update the secret in AWS Secrets Manager
3. Restart the Medic pods (the init script will sync the new key to the database)
4. Distribute the new key to admins

```bash
# Quick rotation script
NEW_KEY=$(python3 -c "from Medic.Core.api_keys import generate_api_key; key, _ = generate_api_key(); print(key)")
echo "New admin key: $NEW_KEY"

# Update in AWS (production)
aws secretsmanager get-secret-value \
  --secret-id "medic/production/secrets" \
  --query SecretString \
  --output text | \
  jq --arg key "$NEW_KEY" '.MEDIC_ADMIN_API_KEY = $key' | \
  aws secretsmanager put-secret-value \
    --secret-id "medic/production/secrets" \
    --secret-string file:///dev/stdin

# Restart pods to sync
kubectl rollout restart deployment/medic-api -n medic
```

## Local Development

For local development with docker-compose, admin keys are auto-created on first startup.

### How It Works

1. `MEDIC_AUTO_CREATE_ADMIN_KEY=true` is set in docker-compose.yml
2. On first API startup, if no admin key exists, one is generated
3. The key is printed to the logs (only shown once!)
4. Use this key to log into the UI at http://localhost:80

### Viewing the Auto-Generated Key

```bash
# Check API logs for the auto-generated key
docker-compose logs medic-api | grep -A5 "AUTO-CREATED ADMIN"
```

### Manual Key Creation (Local Dev)

If you need to create a key manually:

```bash
# With docker-compose running
docker-compose exec medic-api python -m scripts.create_api_key \
  --name admin \
  --scopes admin \
  --force
```

## Environment Variables

| Variable | Description | Used In |
|----------|-------------|---------|
| `MEDIC_ADMIN_API_KEY` | Admin API key to sync from secrets | Production/Dev |
| `MEDIC_AUTO_CREATE_ADMIN_KEY` | Auto-create admin key if not exists | Local Dev |
| `MEDIC_SECRETS_KEY` | Encryption key for stored secrets | All |

## Security Notes

1. **API keys are hashed** using Argon2 before storage in the database
2. **Plaintext keys are never stored** - only shown once at creation
3. **Key rotation** requires updating AWS Secrets Manager and restarting pods
4. **Scopes**: `read`, `write`, `admin` - admin grants all permissions
5. **Expiration**: Keys can have optional expiration dates

## Troubleshooting

### Key Not Working After Rotation

1. Check External Secrets synced: `kubectl get externalsecret -n medic`
2. Check the K8s secret was updated: `kubectl get secret medic -n medic -o yaml`
3. Check pods restarted: `kubectl get pods -n medic`
4. Check init logs: `kubectl logs deployment/medic-api -n medic | grep -i "api key"`

### Lost Admin Key

If you lose the admin key:

1. Generate a new one
2. Update AWS Secrets Manager
3. Restart pods
4. The new key will be synced to the database (overwrites the old hash)
