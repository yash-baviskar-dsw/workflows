# Jenkins CI + Argo Workflows CD Pipeline

## 1. Overview

This document describes the Jenkins CI pipeline, Argo Workflows setup, Kubernetes permissions, and integration between Jenkins and Argo Workflows for the `workflows` repository.

The current implementation establishes a working CI-to-workflow trigger. The Argo `release-pipeline` is currently a smoke-test workflow; the actual build, image publishing, versioning, and Helm deployment stages are the next phase.

### Technology stack

| Component | Purpose |
|---|---|
| Jenkins | CI orchestration, source checkout, tests, and release-workflow triggering |
| GitHub | Source code repository |
| Kubernetes / K3s | Runs Jenkins-related workloads and Argo Workflows |
| Argo Workflows | Executes Kubernetes-native workflows |
| Helm | Intended deployment mechanism for the CD pipeline |
| Azure Container Registry (ACR) | Container image registry |
| MinIO | Object storage associated with the existing Argo installation; not required by the current smoke test |

### Repository

Repository: `https://github.com/yash-baviskar-dsw/workflows.git`

Relevant structure:

```text
workflows/
├── Jenkinsfile
├── Jenkinsfile.main
├── argo/
│   └── release-pipeline.yaml
├── frontend/
├── metadata/
├── service1/
└── service2/
```

- `Jenkinsfile` — existing Jenkins pipeline file.
- `Jenkinsfile.main` — pipeline configured for the main-branch CI job.
- `argo/release-pipeline.yaml` — Argo `WorkflowTemplate`.
- `service1`, `service2`, and `frontend` — application components.
- `metadata` — supporting project resources.

Container registry: `unifyaipublic.azurecr.io`

Jenkins UI: `http://192.168.122.228:8080`

---

## 2. Target architecture

The intended release flow is:

```text
Developer pushes or merges code into main
                  |
                  v
          GitHub repository
                  |
                  v
       Jenkins Poll SCM every 5 minutes
                  |
                  v
        Checkout source from main
                  |
                  v
       Run service1 and service2 tests
                  |
                  v
       Tests pass? -- No --> Jenkins fails
                  |
                 Yes
                  |
                  v
       Submit Workflow to Kubernetes
                  |
                  v
         Argo Workflows controller
                  |
                  v
       WorkflowTemplate: release-pipeline
                  |
                  v
         Actual CD stages (planned)
       - Identify changed components
       - Determine version increments
       - Build container images
       - Push images to ACR
       - Deploy using Helm
       - Verify rollout
       - Record version changes
```

**Separation of responsibilities**

- **Jenkins** decides when the pipeline runs, checks out source code, executes CI tests, and submits an Argo Workflow.
- **Argo Workflows** executes the release workflow as Kubernetes resources.
- **Kubernetes** schedules and runs the workflow pods.
- **Helm** will manage application deployments in the CD workflow.
- **ACR** will store the resulting container images.

The final CD stages shown above are planned functionality, not yet part of the verified smoke-test implementation.

---

## 3. Jenkins configuration

### 3.1 Create the Pipeline job

The Jenkins job is named:

`workflows-main-ci-cd`

Configure it as a **Pipeline** job.

| Setting | Value |
|---|---|
| Pipeline definition | Pipeline script from SCM |
| SCM | Git |
| Repository URL | `https://github.com/yash-baviskar-dsw/workflows.git` |
| Branch specifier | `*/main` |
| Script path | `Jenkinsfile.main` |
| Poll SCM | `H/5 * * * *` |

The `Jenkinsfile.main` script path tells Jenkins to load the pipeline from that file in the checked-out repository.

### 3.2 Why Poll SCM is used

The Jenkins VM is accessed through a private IP address, so the current setup uses SCM polling instead of relying on a GitHub webhook.

Polling schedule:

```text
H/5 * * * *
```

This means Jenkins checks the repository approximately every five minutes. `H` is Jenkins' hash-based scheduling value, which distributes polling times rather than making every job poll at the exact same minute.

When Jenkins detects a relevant SCM change, it can start a new build.

Polling is not an instantaneous notification mechanism; a change may take several minutes to be detected.

### 3.3 What a Jenkins Pipeline is

A Jenkins Pipeline defines an automated process using a `Jenkinsfile`.

Important concepts:

- **Agent:** where the pipeline or a stage executes.
- **Stage:** a logical step, such as testing or triggering a workflow.
- **Step:** an individual command or Jenkins operation.
- **SCM checkout:** retrieves source code from Git.
- **Environment variables:** expose values such as `GIT_COMMIT`.
- **Post actions:** run after the pipeline completes, for example to report success or failure.

The current pipeline uses the `Jenkinsfile.main` file and executes the CI stages before attempting to submit the Argo Workflow.

### 3.4 CI stage responsibilities

The current pipeline is organized around the following steps:

1. Check out the source code.
2. Confirm the intended main-branch execution.
3. Run the `service1` tests using a Python virtual environment and the project's requirements.
4. Validate `service2` using its Python environment and import check.
5. Submit an Argo Workflow if the preceding stages pass.
6. Report the final Jenkins build status.

This is the current CI scope. It does not yet represent the complete release pipeline.

### 3.5 Git commit and branch parameters

The trigger passes two parameters to Argo:

| Parameter | Meaning |
|---|---|
| `git-revision` | Commit SHA captured by Jenkins through `GIT_COMMIT` |
| `source-branch` | Branch name, currently `main` |

Passing these values makes the workflow's execution traceable to the source revision that triggered it.

For production use, the release workflow must explicitly check out or otherwise use that exact revision; merely passing the SHA does not automatically check out the source code inside an Argo pod.

---

## 4. Jenkins Kubernetes access

Jenkins invokes `kubectl` to create Argo Workflow resources in Kubernetes.

The Kubernetes configuration used by the Jenkins trigger is:

```text
/var/lib/jenkins/.kube/config
```

The relevant part of the Jenkins pipeline uses the equivalent of:

```bash
export KUBECONFIG=/var/lib/jenkins/.kube/config
```

### Why kubeconfig matters

A kubeconfig defines how a client such as `kubectl` connects to the Kubernetes API server and authenticates.

The root user's K3s kubeconfig is typically stored at:

```text
/etc/rancher/k3s/k3s.yaml
```

That file is not automatically readable by the unprivileged `jenkins` Linux user. Jenkins therefore needs its own usable Kubernetes configuration and appropriate API permissions.

**Security note:** Do not grant broad cluster-admin privileges to Jenkins merely to trigger workflows. The intended design uses a dedicated Kubernetes ServiceAccount with namespace-scoped permissions.

The Jenkins kubeconfig should be protected with restrictive filesystem permissions and should not be committed to Git or printed in build logs. If it contains a long-lived credential, use a controlled rotation process.

---

## 5. Argo Workflows concepts

### 5.1 What is Argo Workflows?

Argo Workflows is a Kubernetes-native workflow engine. It represents a series of tasks as Kubernetes custom resources and runs the tasks in pods.

It is useful for workflows such as:

- Building and testing software.
- Running data-processing pipelines.
- Executing multi-step release procedures.
- Running parallel tasks and dependent tasks.
- Performing deployment and verification stages.

### 5.2 Core resource types

| Resource | Purpose |
|---|---|
| `Workflow` | A particular execution of a workflow |
| `WorkflowTemplate` | A reusable workflow definition |
| `workflow-controller` | Watches workflow resources and coordinates execution |
| Workflow pod | Executes the steps or templates in a workflow |
| ServiceAccount | Identity used by a pod or Kubernetes API client |
| Role | Defines permissions within one namespace |
| RoleBinding | Grants a Role to a user, group, or ServiceAccount |

### 5.3 Workflow versus WorkflowTemplate

A `WorkflowTemplate` is a reusable definition. A `Workflow` represents a specific run.

The template is stored once:

```text
WorkflowTemplate: release-pipeline
```

Each execution creates a separate workflow resource:

```text
main-release-pnv6k
main-release-hqlrb
```

The generated suffixes distinguish individual executions. Reusing a template avoids duplicating the complete workflow specification in every trigger.

### 5.4 Workflow parameters

Workflow parameters let the triggering system provide input values.

For this setup:

- `git-revision` identifies the triggering Git commit.
- `source-branch` identifies the source branch.

The values can be referenced inside workflow templates using Argo parameter expressions, such as:

```text
{{workflow.parameters.git-revision}}
{{workflow.parameters.source-branch}}
```

### 5.5 Argo Workflows versus Argo CD

These are separate products with different responsibilities.

| Argo Workflows | Argo CD |
|---|---|
| Executes tasks and workflow steps | Reconciles Kubernetes resources against Git-defined desired state |
| Can build images, run tests, and execute scripts | Primarily manages continuous delivery through GitOps |
| Uses `Workflow` and `WorkflowTemplate` resources | Uses `Application` resources |
| Used in this pipeline to execute CD tasks | Not required for the current Jenkins-to-Argo-Workflows design |

The intended architecture uses **Jenkins + Argo Workflows + Helm**, without requiring Argo CD for this pipeline.

---

## 6. Argo Workflows installation and namespaces

The existing Argo Workflows installation uses the `argo` namespace for its controller and supporting components.

The release workflows are created in a separate namespace named `workflow`.

Conceptually:

```text
Namespace: argo
├── workflow-controller
├── argo-server
└── MinIO (existing installation)

Namespace: workflow
├── release-pipeline WorkflowTemplate
├── Jenkins trigger ServiceAccount
├── Workflow execution ServiceAccount
├── Roles and RoleBindings
└── Workflow executions and their pods
```

Check the installation using:

```bash
kubectl get pods -n argo
kubectl get pods -n workflow
kubectl get workflowtemplates -n workflow
kubectl get workflows -n workflow
```

The controller must be configured to watch the namespace in which the workflows are created. In this setup, it is processing the workflows submitted in `workflow`.

### MinIO and artifacts

MinIO provides S3-compatible object storage and can be used by Argo Workflows for artifacts, including files passed between tasks and archived outputs.

The current smoke-test workflow only prints messages and parameters. It does not need artifact storage, so an artifact repository is not part of this minimal workflow definition.

MinIO can be configured for future workflows that need to upload, download, or share artifacts.

---

## 7. Kubernetes permissions and ServiceAccounts

Kubernetes ServiceAccounts provide identities to workloads and automation clients. Roles and RoleBindings restrict the resources those identities can access.

This setup uses separate identities for triggering workflows and executing workflow tasks.

### 7.1 Jenkins trigger ServiceAccount

The trigger identity is:

```text
ServiceAccount: jenkins-argo-trigger
Namespace: workflow
```

Create it with:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: jenkins-argo-trigger
  namespace: workflow
```

Save as `jenkins-argo-trigger-sa.yaml`, then apply:

```bash
kubectl apply -f jenkins-argo-trigger-sa.yaml
```

### 7.2 Role for Jenkins

Jenkins needs permission to submit a workflow and inspect the relevant workflow resources.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: jenkins-argo-trigger
  namespace: workflow
rules:
  - apiGroups:
      - argoproj.io
    resources:
      - workflows
    verbs:
      - create
      - get
      - list
      - watch
  - apiGroups:
      - argoproj.io
    resources:
      - workflowtemplates
    verbs:
      - get
      - list
```

Save as `jenkins-argo-trigger-role.yaml` and apply:

```bash
kubectl apply -f jenkins-argo-trigger-role.yaml
```

**Why these permissions?**

- `create` allows Jenkins to submit a new Workflow.
- `get`, `list`, and `watch` allow it to inspect workflow execution resources.
- `get` and `list` on `workflowtemplates` allow it to inspect reusable workflow definitions.

A namespace-scoped `Role` is preferable to a `ClusterRole` when cluster-wide access is unnecessary.

### 7.3 RoleBinding for Jenkins

The RoleBinding connects the ServiceAccount to the Role.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: jenkins-argo-trigger
  namespace: workflow
subjects:
  - kind: ServiceAccount
    name: jenkins-argo-trigger
    namespace: workflow
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: jenkins-argo-trigger
```

Save as `jenkins-argo-trigger-rolebinding.yaml` and apply:

```bash
kubectl apply -f jenkins-argo-trigger-rolebinding.yaml
```

The RoleBinding grants the named ServiceAccount the permissions defined in the Role. It does not automatically configure Jenkins to authenticate as that ServiceAccount; Jenkins' kubeconfig or credential configuration must separately use the intended identity.

### 7.4 Verify Jenkins trigger permissions

Use Kubernetes authorization checks:

```bash
kubectl auth can-i create workflows.argoproj.io \
  -n workflow \
  --as=system:serviceaccount:workflow:jenkins-argo-trigger

kubectl auth can-i get workflowtemplates.argoproj.io \
  -n workflow \
  --as=system:serviceaccount:workflow:jenkins-argo-trigger
```

The expected result for both checks is:

```text
yes
```

These checks verify authorization for the specified identity. They do not prove that Jenkins' actual kubeconfig is authenticating as that identity.

### 7.5 Workflow execution ServiceAccount

Workflow pods also need an identity for their own Kubernetes API interactions.

The execution ServiceAccount is:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: workflow-executor
  namespace: workflow
```

Save as `workflow-executor-sa.yaml` and apply:

```bash
kubectl apply -f workflow-executor-sa.yaml
```

### 7.6 Role for workflow task results

The workflow execution setup uses a namespace-scoped Role for `workflowtaskresults`:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: workflow-task-results
  namespace: workflow
rules:
  - apiGroups:
      - argoproj.io
    resources:
      - workflowtaskresults
    verbs:
      - create
      - patch
```

Save as `workflow-task-results-role.yaml` and apply:

```bash
kubectl apply -f workflow-task-results-role.yaml
```

### 7.7 RoleBinding for workflow task results

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: workflow-task-results
  namespace: workflow
subjects:
  - kind: ServiceAccount
    name: workflow-executor
    namespace: workflow
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: workflow-task-results
```

Save as `workflow-task-results-rolebinding.yaml` and apply:

```bash
kubectl apply -f workflow-task-results-rolebinding.yaml
```

Verify the permissions:

```bash
kubectl auth can-i create workflowtaskresults.argoproj.io \
  -n workflow \
  --as=system:serviceaccount:workflow:workflow-executor
```

Expected output:

```text
yes
```

The permissions shown above document the configured baseline. If the workflow executor version or workflow features change, verify the required permissions against the installed Argo Workflows version rather than expanding privileges indiscriminately.

---

## 8. The `release-pipeline` WorkflowTemplate

The reusable template is stored in:

```text
argo/release-pipeline.yaml
```

It is applied with:

```bash
kubectl apply -f argo/release-pipeline.yaml
```

The resource is named:

```text
release-pipeline
```

A minimal smoke-test version of the template is:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: release-pipeline
  namespace: workflow
spec:
  serviceAccountName: workflow-executor
  entrypoint: release
  arguments:
    parameters:
      - name: git-revision
        value: unknown
      - name: source-branch
        value: main
  templates:
    - name: release
      container:
        image: alpine:3.20
        command: [sh, -c]
        args:
          - |
            echo "Argo Workflow triggered successfully"
            echo "Git revision: {{workflow.parameters.git-revision}}"
            echo "Source branch: {{workflow.parameters.source-branch}}"
            echo "Jenkins -> Argo connection successful"
```

This is a reference version of the smoke-test template. Retain any additional fields present in the working `argo/release-pipeline.yaml` when updating the repository.

### Important template concepts

- `metadata.name` gives the reusable template its name.
- `namespace` determines where the template is stored.
- `serviceAccountName` selects the identity used by workflow pods.
- `entrypoint` identifies the first template to execute.
- `arguments.parameters` defines default input values.
- `templates` contains the tasks that Argo can execute.
- `container.image` specifies the container image for the task.
- `command` and `args` define what the container executes.

The `alpine:3.20` container is sufficient for printing messages. The actual release workflow will need appropriate tooling and access to the source repository, container registry, and Kubernetes deployment resources.

---

## 9. Submitting a Workflow manually

A Workflow references the reusable `release-pipeline` template.

The following command submits a new execution:

```bash
kubectl create -n workflow -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: main-release-
spec:
  workflowTemplateRef:
    name: release-pipeline
  arguments:
    parameters:
      - name: git-revision
        value: test-commit
      - name: source-branch
        value: main
EOF
```

### What this manifest does

1. Creates a new Workflow in the `workflow` namespace.
2. Generates a unique name beginning with `main-release-`.
3. References the existing `release-pipeline` WorkflowTemplate.
4. Supplies a test revision and the `main` branch as parameters.
5. Lets the Argo Workflows controller schedule the execution.

The `test-commit` value is only a demonstration parameter; it is not a real Git SHA. Jenkins supplies the actual revision through `GIT_COMMIT`.

---

## 10. Connecting Jenkins to Argo Workflows

The Jenkins trigger stage submits a Workflow through the Kubernetes API using `kubectl`.

The key manifest submitted by Jenkins is equivalent to:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: main-release-
  namespace: workflow
spec:
  workflowTemplateRef:
    name: release-pipeline
  arguments:
    parameters:
      - name: git-revision
        value: "<JENKINS_GIT_COMMIT>"
      - name: source-branch
        value: main
```

In `Jenkinsfile.main`, the values are populated dynamically. The shell command uses the Jenkins commit variable and the fixed source branch.

Conceptually, the stage runs:

```bash
export KUBECONFIG=/var/lib/jenkins/.kube/config

kubectl create -n workflow -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: main-release-
spec:
  workflowTemplateRef:
    name: release-pipeline
  arguments:
    parameters:
      - name: git-revision
        value: "${GIT_COMMIT}"
      - name: source-branch
        value: main
EOF
```

### Integration sequence

1. Jenkins checks out the source revision.
2. Jenkins executes the CI tests.
3. If the preceding stages pass, Jenkins authenticates to Kubernetes through its kubeconfig.
4. Kubernetes authorizes the request using the credentials and RBAC configuration.
5. Jenkins creates a Workflow in the `workflow` namespace.
6. The Workflow references `release-pipeline`.
7. The Argo Workflows controller detects and schedules the workflow.
8. Kubernetes starts the workflow pod.
9. The pod executes the template and records the workflow's status.

### Submission versus completion

A successful `kubectl create` means Kubernetes accepted the Workflow resource. It does **not** mean the workflow's tasks have completed successfully.

The current Jenkins trigger stage submits the workflow. To make Jenkins reflect the actual release result, a later iteration should wait for the specific Workflow to reach a terminal state and fail Jenkins if the workflow fails or errors.

This is important before treating the pipeline as production-ready CD.

---

## 11. Monitoring workflow executions

List WorkflowTemplates:

```bash
kubectl get workflowtemplates -n workflow
```

List workflow executions:

```bash
kubectl get workflows -n workflow
```

Watch executions:

```bash
kubectl get workflows -n workflow -w
```

Watch the associated pods:

```bash
kubectl get pods -n workflow -w
```

Inspect a specific Workflow:

```bash
kubectl describe workflow <workflow-name> -n workflow
```

View pod logs:

```bash
kubectl logs <pod-name> -n workflow
```

For a workflow with multiple containers, specify the container when needed:

```bash
kubectl logs <pod-name> -n workflow -c main
kubectl logs <pod-name> -n workflow -c wait
```

The exact pod and container names depend on the workflow execution.

### Workflow states

| State | Meaning |
|---|---|
| Pending | The workflow is waiting to execute |
| Running | Workflow execution is in progress |
| Succeeded | The workflow completed successfully |
| Failed | A workflow task failed |
| Error | The workflow encountered an execution or orchestration error |

A completed pod and a successful Workflow are not necessarily interchangeable concepts; use the Workflow resource's status as the authoritative result of the overall execution.

---

## 12. Current implementation versus planned CD

### Implemented and verified

- Jenkins Pipeline job configured against the `workflows` repository.
- SCM polling configured for `main`.
- `Jenkinsfile.main` used as the pipeline script.
- CI checks for `service1` and `service2`.
- Dedicated namespace for release workflows.
- Jenkins trigger ServiceAccount, Role, and RoleBinding.
- Workflow execution ServiceAccount and task-results RBAC resources.
- `release-pipeline` WorkflowTemplate.
- Jenkins-to-Kubernetes submission of Argo Workflow resources.
- Manual workflow submission and successful completion of the smoke-test workflow.

### Planned next stages

- Check out the exact triggering Git revision inside the workflow.
- Detect changed components.
- Apply branch-based versioning rules.
- Update `version.txt` and Helm values.
- Build container images for changed components.
- Authenticate to and push images to `unifyaipublic.azurecr.io`.
- Deploy the updated components using Helm.
- Verify Kubernetes rollouts.
- Commit version updates back to `main`.
- Prevent bot-generated version commits from starting an unnecessary release loop.
- Make Jenkins wait for Argo Workflow completion and propagate the actual release result.

---

## 13. Operational considerations

### Credentials and access

- Keep the Jenkins kubeconfig protected.
- Use namespace-scoped permissions for workflow submission.
- Store registry credentials securely; do not place passwords or tokens in Git.
- Give the CD workflow only the Kubernetes permissions required for its target resources and namespace.
- Configure the workflow's container build approach explicitly; Docker access on the Jenkins VM is not automatically available inside an Argo pod.

### Idempotency and release loops

The release workflow is intended to commit version changes back to `main`. Since Jenkins polls `main`, those commits can trigger another Jenkins build.

Before enabling automated version commits, add an explicit mechanism to recognize and skip pipeline-generated commits, for example a commit-message marker such as `[skip ci]` that `Jenkinsfile.main` checks itself. Do not assume Jenkins automatically honors that marker.

### Workflow traceability

Retain the following information for every release:

- Git commit SHA.
- Source branch.
- Changed components.
- Image tags and, ideally, image digests.
- Helm release and namespace.
- Workflow execution name.
- Final rollout status.

This will make it easier to trace a deployed application back to the source revision and workflow that produced it.

---

## 14. Final architecture summary

The working foundation is a **Jenkins CI pipeline that submits reusable Argo Workflows**.

Jenkins is responsible for SCM polling, source checkout, testing, and workflow submission. Kubernetes RBAC provides controlled access to the API. Argo Workflows runs the submitted workflow in the `workflow` namespace using the reusable `release-pipeline` template.

The current smoke test validates that the Jenkins-to-Argo integration works. The remaining work is to extend that template into the actual CD pipeline for version management, container builds, ACR publishing, Helm deployment, and rollout verification.


