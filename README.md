# testudo-chart

Testudo Helm Chart，用于部署 `disaster-operator`、`disaster-server` 和 `disaster-web`。

## 快速安装

```bash
helm repo add testudo https://softcdata.github.io/testudo-chart
helm repo update

helm upgrade --install testudo testudo/testudo-chart \
  -n disaster-system \
  --create-namespace
```

默认镜像：

- `docker.io/softcdata/testudo-operator:v1.0.0`
- `docker.io/softcdata/testudo-server:v1.0.0`
- `docker.io/softcdata/testudo-web:v1.0.0`

默认 Web 访问地址：

```text
http://<NodeIP>:30087
```

完整部署说明见 [DEPLOYMENT.md](DEPLOYMENT.md)。
