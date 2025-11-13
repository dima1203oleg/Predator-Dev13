# Observability stack for Predator Analytics

Ця директорія містить Helm values та алерти для:
- Prometheus (моніторинг, алерти)
- Grafana (дашборди)
- Loki (логи)
- Tempo (трейси)

## Як застосувати

- Встановіть Prometheus, Grafana, Loki, Tempo через Helm:
  ```sh
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
  helm repo add grafana https://grafana.github.io/helm-charts
  helm upgrade --install prometheus prometheus-community/prometheus -f prometheus-values.yaml -n monitoring --create-namespace
  helm upgrade --install grafana grafana/grafana -f grafana-values.yaml -n monitoring --create-namespace
  helm upgrade --install loki grafana/loki -f loki-values.yaml -n monitoring --create-namespace
  helm upgrade --install tempo grafana/tempo -f tempo-values.yaml -n monitoring --create-namespace
  ```
- Додайте алерти з `alerts.yaml` у PrometheusRule.

## Алерти
- HighErrorRate (>5% 5xx)
- HighLatency (p95 >0.8s)
- CDCLagHigh (>100s)
- QueueGrowing (>100)

---

[Детальніше: Prometheus](https://prometheus.io/)
[Детальніше: Grafana](https://grafana.com/)
[Детальніше: Loki](https://grafana.com/oss/loki/)
[Детальніше: Tempo](https://grafana.com/oss/tempo/)
