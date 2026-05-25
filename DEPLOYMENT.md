# Testudo Helm Chart 部署说明

本仓库用于维护 `testudo-chart` Helm Chart。Chart 会部署以下组件：

- `disaster-operator`
- `disaster-server`
- `disaster-web`

默认镜像使用 Docker Hub 公共仓库：

- `docker.io/softcdata/testudo-operator:v1.0.0`
- `docker.io/softcdata/testudo-server:v1.0.0`
- `docker.io/softcdata/testudo-web:v1.0.0`

## 1. 前置条件

- Kubernetes 集群可用
- `kubectl` 可正常访问目标集群
- Helm 版本为 v3 或以上
- 如启用默认 webhook 配置，目标集群需要已安装 cert-manager

## 2. 使用 GitHub Pages Helm 仓库安装

GitHub Pages 启用后，用户可以通过以下方式安装：

```bash
helm repo add testudo https://softcdata.github.io/testudo-chart
helm repo update

helm upgrade --install testudo testudo/testudo-chart \
  -n disaster-system \
  --create-namespace
```

默认安装完成后，可通过以下地址访问 Web 控制台：

```text
http://<NodeIP>:30087
```

## 3. 从源码目录本地安装

如果还没有启用 GitHub Pages，也可以从当前源码目录直接安装：

```bash
helm upgrade --install testudo . \
  -n disaster-system \
  --create-namespace
```

安装前建议先执行：

```bash
helm lint .
helm template testudo . > /tmp/testudo-chart-rendered.yaml
```

## 4. 关键配置项

### `global`

- `global.namespace`: 写入资源 `metadata.namespace` 的命名空间，默认值为 `disaster-system`
- `global.timezone`: 写入容器环境变量 `TZ`，默认值为 `Asia/Shanghai`

注意：本 Chart 的资源命名空间来自 `global.namespace`，不会自动跟随 `helm install -n`。如果安装到其他命名空间，例如 `demo`，需要同时设置：

```bash
helm upgrade --install testudo testudo/testudo-chart \
  -n demo \
  --create-namespace \
  --set global.namespace=demo
```

### `images`

- `images.operator.repository`: operator 镜像仓库
- `images.operator.tag`: operator 镜像标签
- `images.server.repository`: server 镜像仓库
- `images.server.tag`: server 镜像标签
- `images.web.repository`: web 镜像仓库
- `images.web.tag`: web 镜像标签

默认值指向 Docker Hub 公共镜像。若使用私有镜像仓库，可以通过 values 文件覆盖：

```yaml
images:
  operator:
    repository: registry.example.com/softcdata/testudo-operator
    tag: v1.0.0
  server:
    repository: registry.example.com/softcdata/testudo-server
    tag: v1.0.0
  web:
    repository: registry.example.com/softcdata/testudo-web
    tag: v1.0.0
```

本仓库内置了两份镜像源切换文件：

```bash
# Docker Hub，等同于默认 values.yaml
helm upgrade --install testudo . \
  -n disaster-system \
  --create-namespace \
  -f values-dockerhub.yaml

# 阿里云 ACR
helm upgrade --install testudo . \
  -n disaster-system \
  --create-namespace \
  -f values-aliyun.yaml
```

如果阿里云 ACR 仓库为私有仓库，先在目标命名空间创建或复用 `kubernetes.io/dockerconfigjson`
Secret，并追加 `--set imagePullSecret.existingSecret=<pull-secret-name>`。

### `imagePullSecret`

默认不创建、不引用 imagePullSecret，因为 Docker Hub 公共镜像不需要拉取凭据。

如需复用已有 Secret：

```bash
helm upgrade --install testudo testudo/testudo-chart \
  -n disaster-system \
  --create-namespace \
  --set imagePullSecret.existingSecret=my-registry-secret
```

如需让 Chart 创建 Secret：

```yaml
imagePullSecret:
  create: true
  name: default-secret
  registry: registry.example.com
  username: your-username
  password: your-password
  email: ""
```

### `web`

- `web.backendUrl`: Web 容器代理到 server 的地址，默认 `http://disaster-server:30081`
- `web.service.type`: 默认 `NodePort`
- `web.service.port`: 默认 `80`
- `web.service.nodePort`: 默认 `30087`

### `server`

- `server.service.type`: 默认 `ClusterIP`
- `server.service.port`: 默认 `30081`

### `license`

- `license.enabled`: server 侧 License gate 开关，默认 `true`
- `license.namespace`: License Secret、状态 ConfigMap 和 gate state 所在命名空间，默认跟随 `global.namespace`
- `license.secret.create`: 是否随 Chart 创建 `disaster-platform-license` Secret，默认 `false`
- `license.secret.license`: 当 `license.secret.create=true` 时写入 Secret `license.lic` 的 License JSON 内容
- `license.statusReader.enabled`: 是否创建面向 Web ServiceAccount 的只读 status ConfigMap 绑定，默认 `false`

默认安装不会创建真实 License Secret，避免把企业授权内容写入通用 values 文件。推荐通过后端接口安装 License，或在私有 values 文件中显式配置：

```yaml
license:
  secret:
    create: true
    license: |
      {"version":1,"licenseId":"LIC-...","product":"testudo"}
```

License 签发私钥不得写入 Chart、values 文件、镜像或仓库。

### `webhook`

- `webhook.enabled`: 是否安装 admission webhook，默认 `true`
- `webhook.certManager.enabled`: 是否使用 cert-manager 生成 webhook serving cert 并注入 CA，默认 `true`
- `webhook.caBundle`: 当 `webhook.certManager.enabled=false` 时显式提供 CA bundle

如果目标集群没有 cert-manager，可以关闭 webhook 证书自动管理：

```bash
helm upgrade --install testudo testudo/testudo-chart \
  -n disaster-system \
  --create-namespace \
  --set webhook.certManager.enabled=false
```

关闭 cert-manager 后，需要自行准备 webhook TLS Secret 和 `webhook.caBundle`。

### `uninstallCleanup`

Helm 默认不会在 `helm uninstall` 时删除 `crds/` 目录安装的 CRD。若需要卸载时删除 Testudo CRD，可显式开启 pre-delete 清理 hook：

```bash
helm upgrade --install testudo testudo/testudo-chart \
  -n disaster-system \
  --create-namespace \
  --set uninstallCleanup.enabled=true
```

- `uninstallCleanup.enabled`: 是否创建卸载清理 hook，默认 `false`
- `uninstallCleanup.deleteTestudoCrds`: 清理 Testudo CRD，默认 `true`
- `uninstallCleanup.deleteVeleroCrds`: 清理 Velero CRD，默认 `false`
- `uninstallCleanup.timeoutSeconds`: 单个 CRD 删除等待超时时间，默认 `120`
- `uninstallCleanup.kubectlImage`: 清理 Job 使用的 kubectl 镜像

注意：删除 CRD 会删除对应的全部 CR 实例数据。Velero CRD 可能由集群内其他 Velero 安装共享，只有确认不再需要时才开启 `uninstallCleanup.deleteVeleroCrds=true`。

## 5. 打包 Chart

```bash
helm lint .
helm package .
```

打包后会生成：

```text
testudo-chart-1.0.0.tgz
```

该包属于发布产物，不提交到源码分支；GitHub Pages 分支可以保存 `.tgz` 和 `index.yaml`。

## 6. GitHub Pages 托管建议

推荐使用如下分支布局：

- `main`: 保存 Chart 源码
- `gh-pages`: 保存 `index.yaml` 和 Chart 包

本仓库已包含 GitHub Actions 工作流：

```text
.github/workflows/publish-helm-chart.yml
```

推送到 GitHub `main` 分支后，该工作流会自动执行：

1. `helm lint .`
2. `helm package .`
3. 生成 Helm repo `index.yaml`
4. 将 `index.yaml` 和 `testudo-chart-1.0.0.tgz` 发布到 `gh-pages` 分支

GitHub 仓库侧需要在 `Settings -> Pages` 中选择：

```text
Source: Deploy from a branch
Branch: gh-pages
Folder: /
```

如需手动发布，可使用以下命令：

```bash
helm package .
mkdir -p /tmp/testudo-chart-pages
cp testudo-chart-1.0.0.tgz /tmp/testudo-chart-pages/
helm repo index /tmp/testudo-chart-pages \
  --url https://softcdata.github.io/testudo-chart
```

将 `/tmp/testudo-chart-pages` 的内容推送到 `gh-pages` 分支后，即可通过 `helm repo add` 使用。
