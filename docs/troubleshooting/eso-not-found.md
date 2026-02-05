# ESO CRD Not Found

## Error Message

When running `terraform plan` or `terraform apply` for Medic, you may see:

```
Error: Resource precondition failed

External Secrets Operator (ESO) CRD not found on the cluster.

ESO is a prerequisite deployed by o11y-tf. The 'externalsecrets.external-secrets.io'
CRD must exist before Medic can be deployed.
```

## What This Means

Medic uses [External Secrets Operator (ESO)](https://external-secrets.io/) to sync secrets from AWS Secrets Manager into Kubernetes. ESO is **not** deployed by Medic's Terraform — it is deployed by the **o11y-tf** platform infrastructure.

Medic's Terraform includes a validation check that verifies the `externalsecrets.external-secrets.io` CRD exists on the cluster before proceeding. If ESO is not installed, this check fails with a clear error to prevent a partial deployment.

## Verify ESO Installation

Check if the ESO CRD exists on the cluster:

```bash
kubectl get crd externalsecrets.external-secrets.io
```

**Expected output (ESO installed):**
```
NAME                                       CREATED AT
externalsecrets.external-secrets.io        2024-01-15T12:00:00Z
```

**Error output (ESO not installed):**
```
Error from server (NotFound): customresourcedefinitions.apiextensions.k8s.io "externalsecrets.external-secrets.io" not found
```

You can also check if the ESO pods are running:

```bash
kubectl get pods -n external-secrets
```

## Resolution

### 1. ESO Has Not Been Deployed

If ESO is not installed on the cluster, it needs to be deployed via the **o11y-tf** repository. ESO is part of the shared platform infrastructure and is deployed once per cluster.

**Steps:**
1. Verify the target EKS cluster exists and is accessible
2. Run the o11y-tf Terraform for the target environment to deploy ESO
3. Confirm ESO CRDs are available: `kubectl get crd | grep external-secrets`
4. Re-run Medic's Terraform

### 2. Kubeconfig Is Pointing to the Wrong Cluster

If ESO is deployed but you're seeing this error, your kubeconfig may be pointing to the wrong cluster.

**Steps:**
1. Check your current context: `kubectl config current-context`
2. Verify it matches the target cluster (e.g., `o11y-prod` for prod, `dev-o11y` for dev)
3. Update your context if needed:
   ```bash
   aws eks update-kubeconfig --name <cluster-name> --region us-east-2
   ```

### 3. Dev Environment (Expected Failure)

If you are deploying to the **dev** environment, this error is expected until the dev-o11y-tf cluster is provisioned. The dev environment is pre-configured for a future dev cluster.

Until the dev cluster exists, dev deployments will fail at this validation step. This is by design.

## Related Resources

- **o11y-tf repository** — Deploys ESO and other shared platform components
- **ESO documentation** — https://external-secrets.io/
- Medic's `ClusterSecretStore` and `ExternalSecret` resources depend on ESO being installed
