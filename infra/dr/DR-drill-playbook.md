# DR Drill Playbook: Predator Analytics

## Цілі

- RTO ≤ 60 хвилин
- RPO ≤ 15 хвилин

## Кроки перевірки

1. **Імітація аварії**
   - Видалити namespace `predator-dev` або ключові PVC/дані.
2. **Відновлення з Velero**
   - Запустити: `velero restore create --from-backup <latest-backup>`
   - Перевірити статус: `velero restore get`
3. **Відновлення бази через pgBackRest**
   - Відновити останній full/incr backup.
   - Перевірити логи та консистентність.
4. **Відновлення MinIO даних**
   - Перевірити versioning, відновити потрібні об'єкти.
5. **Smoke-тест**
   - Запустити smoke-job для перевірки API, ETL, Qdrant, OpenSearch.
6. **Верифікація RTO/RPO**
   - Зафіксувати час старту/фінішу, втрату даних.

## Acceptance Criteria

- Всі сервіси працюють, дані відновлені.
- RTO ≤ 60 хвилин, RPO ≤ 15 хвилин.
- Smoke-job проходить без помилок.

---

[Velero docs](https://velero.io/docs/)
[pgBackRest docs](https://pgbackrest.org/)
[MinIO docs](https://min.io/docs/)
