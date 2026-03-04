# 灾备系统 (Disaster System) 部署文档

本指南介绍了如何使用 Helm 部署 `disaster-system`。该 Chart 包含了前端、服务端和 Operator 三个核心组件。

## 1. 前置要求
- 一个运行中的 Kubernetes 集群。
- 安装了 `kubectl` 并能正常访问目标集群。
- 安装了 `helm` 命令行工具（v3 及以上版本）。

未安装 Helm 请尝试如下命令：
```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
```

## 2. 核心配置说明 (values.yaml)
部署时你可以通过修改默认配置来满足你的个性化需求。以下是关键配置项的作用说明：

### 基本配置
- `global.namespace`: 指定内部资源部署时附带的命名空间标签（建议直接在 `helm install` 中用 `-n` 明确）。 

### 镜像配置 (`images` 块)
这里统一定义了组件拉取的镜像仓库地址和版本号标签：
- `images.operator`: 控制 Operator 的镜像 (`repository`, `tag`, `pullPolicy`)
- `images.server`: 控制后端的镜像
- `images.web`: 控制前端的镜像

### Web 端配置 (`web` 块)
- `web.backendUrl`: 这是最核心的配置！前端 `disaster-web` 与用户浏览器交互，需要向后台发起请求。这个地址 **必须配置为客户端浏览器能够直接访问到的 Server 地址**。格式示例：`http://192.168.120.140:30081`（如果在同一台机器并开放了 NodePort 30081）
- `web.service.type`: Service 类型（默认为 `NodePort`）。
- `web.service.port`: Service 接收的集群内端口（默认为 80）。
- `web.service.nodePort`: 映射到宿主机上的外部访问端口（默认为 `30087`）。

### Server 端配置 (`server` 块)
- `server.service.type`: Service 类型（默认 `NodePort`）。
- `server.service.port`: Server 在集群内的微服务内部暴露端口（默认 `8081`）。
- `server.service.nodePort`: 映射到宿主机上的外部访问端口（默认为 `30081`）。提供给 Web 或者外部直接调用 API。

---

## 3. 镜像准备与仓库登录（必读）

此部署包使用的镜像托管在华为云 SWR 镜像集市中。

### 方式A：有外网的集群自动拉取镜像
如果在集群的各个节点都有外网环境，您可以直接连上华为云并执行以下命令认证登录：
```bash
docker login -u cn-east-3@HPUASTMUH2SDASAZ6DUR -p 97cd784341e5334bc03a386c92ed8f1689630f22f6f84e7eb4e3d20db4c7481d swr.cn-east-3.myhuaweicloud.com
```
*提示：如果使用 containerd 可能需要配置对应的 registry 凭证。*

### 方式B：离线/无外网环境（预先导出镜像包）
如果客户的环境是**完全隔离的内网**，无法连接公网进行 docker pull，则需要提前找一台有网的机器预先下载并打包好所有的镜像：

1. **预拉取并在有网的机器打成包 (tar):**
```bash
# 1. 登录仓库
docker login -u cn-east-3@HPUASTMUH2SDASAZ6DUR -p 97cd784341e5334bc03a386c92ed8f1689630f22f6f84e7eb4e3d20db4c7481d swr.cn-east-3.myhuaweicloud.com

# 2. 拉取所有涉及的镜像（注意版本号与 values.yaml 保持一致）
docker pull swr.cn-east-3.myhuaweicloud.com/chenmou/disaster-operator-arm64:v2.0.0
docker pull swr.cn-east-3.myhuaweicloud.com/chenmou/disaster-server:v2.0.0
docker pull swr.cn-east-3.myhuaweicloud.com/chenmou/disaster-web:v2.0.0

# 3. 将其导出为普通压缩包
docker save swr.cn-east-3.myhuaweicloud.com/chenmou/disaster-operator-arm64:v2.0.0 swr.cn-east-3.myhuaweicloud.com/chenmou/disaster-server:v2.0.0 swr.cn-east-3.myhuaweicloud.com/chenmou/disaster-web:v2.0.0 -o disaster-images.tar
```

2. **在客户内网每台目标节点上导入:**
将上一步骤产生的 `disaster-images.tar` 拷贝到目标集群的各个工作节点上，然后执行：
```bash
# Docker 架构的集群使用:
docker load -i disaster-images.tar

# Containerd 架构的集群使用:
ctr -n k8s.io images import disaster-images.tar
# (或者使用 crictl / nerdctl load 功能)
```

---

## 4. 部署方式

### 获取安装包
确保当前目录下有包含组件定义的 `.tgz` 文件，例如 `disaster-system-2.0.0.tgz`。

### 方式一：快捷安装（默认配置）
如果你直接使用打包好的默认端口 (`Web: 30087`, `Server: 30081`)，并且目标机器 IP 和 `web.backendUrl` 的默认值一致，则可直接运行：
```bash
helm install disaster-system ./disaster-system-2.0.0.tgz \
  -n disaster-system \
  --create-namespace
```

### 方式二：动态替换特定参数安装 (推荐)
如果后端 IP 有变动，你可以使用 `--set` 直接在命令行中替换对应的值：
```bash
helm install disaster-system ./disaster-system-2.0.0.tgz \
  -n disaster-system \
  --create-namespace \
  --set web.backendUrl=http://<你的目标后端IP>:30081 \
  --set server.service.nodePort=30081
```

### 方式三：使用自定义 Value 文件安装
针对更复杂的配置场景，创建一个自定义的 `my-values.yaml` 文件：
```yaml
# my-values.yaml 示例
web:
  backendUrl: "http://10.0.0.10:30088"
  service:
    nodePort: 30089

server:
  service:
    nodePort: 30088

images:
  web:
    tag: "v2.0.1-rc1" # 修改为你最新打包的版本
```

然后使其生效：
```bash
helm install disaster-system ./disaster-system-2.0.0.tgz \
  -n disaster-system \
  --create-namespace \
  -f my-values.yaml
```

---

## 4. 验证部署结果
执行以下命令检查 Pod 和 Service：
```bash
# 查看发布状态
helm ls -n disaster-system

# 查看内部组件是否全部变为 Running
kubectl get all -n disaster-system
```
如果一切正常，您就可以通过浏览器访问了：
- **Web UI**: `http://<Node_IP>:30087`

---

## 5. 配置更新与升级
如果你安装后发现填写的值有误或后来想要调整（例如 `backendUrl` 填错），修改好 `my-values.yaml` 或更换 `--set` 参数，然后使用 `upgrade` 指令：

```bash
helm upgrade disaster-system ./disaster-system-2.0.0.tgz \
  -n disaster-system \
  -f my-values.yaml
```
Helm 将自动重启变更的容器并加载新配置。

## 6. 完全卸载系统
当你不需要这套系统时，可以使用以下命令进行清除：
```bash
helm uninstall disaster-system -n disaster-system
```
*(注意：此命令将同时清除对应命名空间下属于该 Release 的所有相关资源，不包含命名空间本身。)*
