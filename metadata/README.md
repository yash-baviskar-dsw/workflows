# metadata Helm chart

Deploys PostgreSQL as a StatefulSet and pgAdmin as a Deployment in the `metadata` namespace. pgAdmin receives a preconfigured PostgreSQL server definition from a Secret-mounted `servers.json`; you should not need to register the database manually in the UI.

## Resources

- PostgreSQL StatefulSet and ClusterIP Service
- PostgreSQL PersistentVolumeClaim (`local-path` by default)
- pgAdmin Deployment and ClusterIP Service
- ConfigMap for `config_local.py`
- Secret for PostgreSQL/pgAdmin credentials, pgAdmin server definition, and pgpass file

With K3s `local-path-provisioner`, the PVC dynamically provisions a PersistentVolume. Do **not** create a separate static PV for this setup; that would conflict with the provisioner's dynamic provisioning. The provisioned disk is node-local and is not replicated.

## Install

From the directory containing this chart:

```bash
kubectl create namespace metadata --dry-run=client -o yaml | kubectl apply -f -
helm lint ./metadata
helm template metadata ./metadata -n metadata
helm upgrade --install metadata ./metadata -n metadata --create-namespace \
  --set postgres.password='REPLACE_WITH_A_STRONG_POSTGRES_PASSWORD' \
  --set pgadmin.password='REPLACE_WITH_A_STRONG_PGADMIN_PASSWORD'
```

For a persistent setup, put credentials in a private values file that is not committed to Git, or use your organization's external secret manager. Note that Helm release records contain rendered Kubernetes Secret data; Kubernetes Secrets are base64-encoded, not encrypted by themselves.

## Access pgAdmin

```bash
kubectl -n metadata port-forward svc/metadata-pgadmin 8080:80
```

Open <http://localhost:8080> and sign in using `pgadmin.email` / `pgadmin.password` from your values. The default email is `admin@example.com`.

The PostgreSQL server is registered under **Servers** using the service DNS name `metadata-postgres.metadata.svc.cluster.local` (for the default release name `metadata`). If you use a different Helm release name, the service name is `<release>-postgres` and the chart builds the matching server definition automatically.

## Verify

```bash
kubectl -n metadata get deploy,sts,svc,pvc,pv,cm,secret
kubectl -n metadata get pods -w
kubectl -n metadata logs deploy/metadata-pgadmin
kubectl -n metadata logs sts/metadata-postgres
```

## Important notes

- The chart assumes the StorageClass is named `local-path`, as in a typical K3s installation. Check with `kubectl get storageclass`; override `postgres.storage.storageClassName` if needed.
- The PostgreSQL PVC uses `ReadWriteOnce`, which is appropriate for local-path storage.
- This is a learning/local-development chart, not a production database deployment. It does not configure TLS, backups, replication, resource limits, network policies, or a secret manager.
- PostgreSQL's initial `POSTGRES_*` environment variables only initialize a new empty data directory. Changing the password in Helm after the database has already initialized will not change the existing PostgreSQL role password automatically; rotate it in PostgreSQL as well.
