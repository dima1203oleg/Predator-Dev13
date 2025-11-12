# Security & Runtime Policies

Ця директорія містить базові політики для Kubernetes:

- **PodSecurityPolicy**: обмежує привілеї, дозволяє лише non-root, блокує hostPath.
- **NetworkPolicy**: default-deny для ingress/egress у predator-dev.
- **Kyverno**: ClusterPolicy для non-root контейнерів та заборони hostPath.

## Як застосувати

- Застосуйте всі manifests через `kubectl apply -f <file>`.
- Для Kyverno потрібен встановлений Kyverno CRD.

## Рекомендації

- Використовуйте restricted політики для всіх продакшн namespaces.
- Додавайте додаткові правила для compliance (PCI, SOC2, GDPR).

---

[Kyverno docs](https://kyverno.io/policies/)
[Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
[Kubernetes PodSecurity](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
