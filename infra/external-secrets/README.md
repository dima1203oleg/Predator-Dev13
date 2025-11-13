# External Secrets for Predator Analytics

Ця директорія містить маніфести для External Secrets Operator (ESO) з інтеграцією Vault.

## Як це працює

- `ClusterSecretStore` описує бекенд (Vault), з якого будуть тягнутися секрети.
- `ExternalSecret` створює Kubernetes Secret на основі даних з Vault.

## Приклад

- `secret-store-vault.yaml`: підключення до Vault (auth через token у Secret `vault-token`).
- `external-secret-api.yaml`: мапить секрети з Vault (`predator/api`) у Kubernetes Secret `api-secrets`.

## Вимоги

- External Secrets Operator встановлений у кластері.
- Vault доступний за вказаним URL.
- Token для Vault зберігається у Secret `vault-token` у namespace `predator-dev`.

## Безпека

- Не зберігайте .env або секрети у git! Всі секрети мають бути у Vault/Secret Manager.

---

---

[Детальніше: external-secrets.io](https://external-secrets.io/)
