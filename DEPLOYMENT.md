# 灾备系统部署说明

本说明面向当前仓库中的 `disaster-system` Helm Chart。该 Chart 会部署三个组件：

- `disaster-operator`
- `disaster-server`
- `disaster-web`

## 1. 当前默认部署拓扑

当前 Chart 的默认行为如下：

- `disaster-web` 通过 `NodePort` 对外暴露，默认端口为 `30087`
- `disaster-server` 通过 `ClusterIP` 在集群内暴露，默认端口为 `30081`
- `disaster-web` 默认通过集群内地址 `http://disaster-server:30081` 访问后端

因此，正常安装时通常不需要手工指定 `web.backendUrl`。

## 2. 前置条件

- Kubernetes 集群可用
- `kubectl` 可正常访问目标集群
- Helm 版本为 v3 或以上

如未安装 Helm，可参考官方脚本：

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
```

## 3. 关键配置项

当前默认值以 `values.yaml` 为准。

### `global`

- `global.namespace`: 写入资源 `metadata.namespace` 的命名空间，默认值为 `disaster-system`
- `global.timezone`: 写入 `disaster-operator` 和 `disaster-server` 容器环境变量 `TZ`，默认值为 `Asia/Shanghai`

注意：本 Chart 的资源命名空间来自 `global.namespace`，不是自动跟随 `helm install -n ...`。如果你安装到其他命名空间，例如 `demo`，请同时设置：

```bash
--set global.namespace=demo
```

### `imagePullSecret`

- `imagePullSecret.existingSecret`: 已存在的镜像拉取 Secret 名称；设置后 Chart 不再创建 `default-secret`
- `imagePullSecret.registry`: 镜像仓库地址
- `imagePullSecret.username`: 镜像仓库用户名
- `imagePullSecret.password`: 镜像仓库密码
- `imagePullSecret.email`: 可选邮箱字段

说明：

- `disaster-operator`、`disaster-server`、`disaster-web` 三个 Deployment 都会引用镜像拉取 Secret
- 默认情况下，Chart 会创建名为 `default-secret` 的 `kubernetes.io/dockerconfigjson` Secret
- 如果设置了 `imagePullSecret.existingSecret`，Chart 会直接复用该 Secret，并跳过创建 `default-secret`
- 仅在未设置 `imagePullSecret.existingSecret` 时，`imagePullSecret.username` / `imagePullSecret.password` 才是必填项

### `images`

- `images.operator`: 默认 `ghcr.io/softcdata/testudo-operator:v2.3.0`
- `images.server`: 默认 `ghcr.io/softcdata/testudo-server:v2.3.0`
- `images.web`: 默认 `ghcr.io/softcdata/testudo-web:v2.2.0`

### `strategy`

- `operator.strategy`: 对应 `disaster-operator` Deployment 的发布策略
- `server.strategy`: 对应 `disaster-server` Deployment 的发布策略
- `web.strategy`: 对应 `disaster-web` Deployment 的发布策略

说明：默认值均为 `{}`，即沿用 Kubernetes 默认策略。你可以配置 `type: Recreate` 或 `type: RollingUpdate` 及其子字段。

### `web`

- `web.backendUrl`: 默认 `http://disaster-server:30081`
- `web.service.type`: 默认 `NodePort`
- `web.service.port`: 默认 `80`
- `web.service.nodePort`: 默认 `30087`

说明：`web.backendUrl` 默认使用集群内服务发现。只有当你希望前端代理到其他后端地址时，才需要覆盖它。

### `server`

- `server.service.type`: 默认 `ClusterIP`
- `server.service.port`: 默认 `30081`

说明：当前 Chart 没有 `server.service.nodePort` 配置项，`server` 默认不直接对集群外暴露。

### `license`

- `license.enabled`: server 侧 License gate 开关，默认 `true`
- `license.namespace`: License Secret、状态 ConfigMap 和 gate state 所在命名空间；默认跟随 `global.namespace`
- `license.caPath`: Pod 内用于计算部署指纹的 API Server CA 路径，默认 `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`
- `license.secret.create`: 是否随 Chart 创建 `disaster-platform-license` Secret，默认 `false`
- `license.secret.license`: 当 `license.secret.create=true` 时写入 Secret `license.lic` 的 License JSON 内容
- `license.statusReader.enabled`: 是否创建面向 `disaster-web` ServiceAccount 的只读 status ConfigMap 绑定，默认 `false`

说明：

- 默认安装不会创建真实 License Secret，避免把企业授权内容写入通用 values 文件。
- 安装企业 License 推荐使用后端接口 `POST /apis/v1/platform-license/install` 或 `disasterctl license install`。
- 如需通过 Helm 预置 License，可使用 `license.secret.create=true` 并提供完整 License JSON。
- License 签发私钥不得写入 Chart、values 文件、镜像或仓库；Chart 只允许携带已签发的 `.lic` 内容。
- Chart 会为 operator/server 创建 License 相关 Role/RoleBinding：operator 可维护 `disaster-platform-license-status`、`disaster-platform-license-gate-state` 和安装 ID；server 可安装/读取 `disaster-platform-license` 并读取 status ConfigMap。
- `disaster-platform-license-status-reader` 只允许读取 `disaster-platform-license-status`，不授予读取 License Secret 或写 status ConfigMap 的权限。

### `webhook`

- `webhook.enabled`: 是否安装 admission webhook，默认 `true`
- `webhook.certManager.enabled`: 是否使用 cert-manager 生成 webhook serving cert 并注入 CA，默认 `true`
- `webhook.caBundle`: 当 `webhook.certManager.enabled=false` 时可显式提供 `ValidatingWebhookConfiguration` 的 CA bundle

说明：

- 默认会安装 `disaster-operator-webhook-service`、`Certificate`、`Issuer` 和 `ValidatingWebhookConfiguration`。
- Cluster validating webhook 路径为 `/validate-testudo-softcdata-com-v1-cluster`，用于在 admission 阶段拦截第 3 个免费版 Cluster。
- 默认依赖 cert-manager CRD。若目标集群没有 cert-manager，请关闭 `webhook.certManager.enabled` 并提供 `webhook.caBundle` 与同名 TLS Secret，或先安装 cert-manager。

## 4. 镜像准备

镜像版本要与 `values.yaml` 保持一致。

### 方式 A：集群节点可直接拉取

```bash
docker login <registry>
```

如果你不复用已有 Secret，Chart 会默认创建并引用名为 `default-secret` 的镜像拉取 Secret。此时需要在 `values.yaml` 中配置 `imagePullSecret.registry`、`imagePullSecret.username` 和 `imagePullSecret.password`。

### 方式 B：离线导入镜像

在一台可访问公网的机器上先拉取并导出镜像：

```bash
docker login <registry>

docker pull ghcr.io/softcdata/testudo-operator:v2.3.0
docker pull ghcr.io/softcdata/testudo-server:v2.3.0
docker pull ghcr.io/softcdata/testudo-web:v2.2.0

docker save \
  ghcr.io/softcdata/testudo-operator:v2.3.0 \
  ghcr.io/softcdata/testudo-server:v2.3.0 \
  ghcr.io/softcdata/testudo-web:v2.2.0 \
  -o disaster-images.tar
```

然后在目标节点导入：

```bash
# Docker
docker load -i disaster-images.tar

# containerd
ctr -n k8s.io images import disaster-images.tar
```

说明：即使是离线导入镜像的场景，你也可以二选一：

- 继续让 Chart 创建 `default-secret`
- 或设置 `imagePullSecret.existingSecret` 复用集群中已有的拉取凭据

## 5. 安装

确保当前目录下已有 chart 包，例如：

- `disaster-system-2.3.0.tgz`

### 默认安装

先准备一个 values 文件，至少填入镜像仓库凭据，例如：

```yaml
imagePullSecret:
  existingSecret: ""
  registry: <registry>
  username: "<username>"
  password: "<password>"
  email: ""
```

```bash
helm install disaster-system ./disaster-system-2.3.0.tgz \
  -n disaster-system \
  --create-namespace \
  -f my-values.yaml
```

### 复用集群已有 Secret

如果命名空间里已经存在可用的镜像拉取 Secret，例如你的集群里已有 `default-secret`，安装时可以直接指定：

```bash
helm upgrade --install disaster-system ./disaster-system-2.3.0.tgz \
  -n disaster-system \
  --create-namespace \
  --set imagePullSecret.existingSecret=default-secret
```

默认安装成功后，可通过以下地址访问前端：

- `http://<NodeIP>:30087`

### 预置 License Secret（可选）

默认不通过 Helm 安装 License。若确实需要把 License 随 Chart 一起安装，可在私有 values 文件中配置：

```yaml
license:
  secret:
    create: true
    license: |
      {"version":1,"licenseId":"LIC-...","product":"disaster-platform"}
```

注意：示例中的 JSON 只是结构占位，实际内容必须使用正式签发工具生成，不能使用截断或自签内容。

### 安装到自定义命名空间

如果目标命名空间不是 `disaster-system`，必须同时覆盖 `global.namespace`：

```bash
helm install disaster-system ./disaster-system-2.3.0.tgz \
  -n demo \
  --create-namespace \
  -f my-values.yaml \
  --set global.namespace=demo
```

### 使用自定义 values 文件

以下示例展示如何同时配置镜像拉取凭据、前端对外端口和发布策略：

```yaml
global:
  namespace: disaster-system

imagePullSecret:
  registry: <registry>
  username: "<username>"
  password: "<password>"
  email: ""

web:
  service:
    type: NodePort
    nodePort: 30088
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0

server:
  strategy:
    type: Recreate

operator:
  strategy:
    type: RollingUpdate
```

执行安装：

```bash
helm install disaster-system ./disaster-system-2.3.0.tgz \
  -n disaster-system \
  --create-namespace \
  -f my-values.yaml
```

## 6. 验证

```bash
helm ls -n disaster-system
kubectl get pods,svc -n disaster-system
```

如需查看渲染后的资源清单：

```bash
helm template disaster-system ./disaster-system-2.3.0.tgz -f my-values.yaml
```

## 7. 升级

修改 values 后执行：

```bash
helm upgrade disaster-system ./disaster-system-2.3.0.tgz \
  -n disaster-system \
  -f my-values.yaml
```

如果使用的是自定义命名空间，请保持 `global.namespace` 与发布命名空间一致：

```bash
helm upgrade disaster-system ./disaster-system-2.3.0.tgz \
  -n demo \
  -f my-values.yaml \
  --set global.namespace=demo
```

## 8. 卸载

```bash
helm uninstall disaster-system -n disaster-system
```

说明：该命令会删除当前 Helm Release 管理的资源，但不会自动删除命名空间。
