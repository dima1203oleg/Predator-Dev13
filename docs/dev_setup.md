
# Локальне налаштування для розробки та тестів

Цей документ пояснює швидкі кроки для підготовки локального середовища (macOS) — підходить для запуску тестів і локального smoke (docker-compose) перед розгортанням у Kubernetes.

1) Перевірити Docker

- Запустіть перевірку (варіант A — через bash, не потребує chmod):

```bash
bash ./scripts/check_docker.sh
```

- Або зробіть скрипти виконуваними і запустіть напряму:

```bash
chmod +x ./scripts/*.sh
./scripts/check_docker.sh
```

- Якщо Docker не запущено: відкрийте Docker Desktop: `open -a Docker` або, якщо ви використовуєте Colima: `colima start`.

2) Підготувати Python 3.11 середовище

- Скрипт допоможе створити venv через `pyenv` або локальний `python3.11`.

Запустіть через bash (не вимагає додаткових прав):

```bash
bash ./scripts/setup_python311.sh
# потім (якщо використали pyenv): pyenv activate predator-venv-3.11
# або якщо створено .venv311: source .venv311/bin/activate
pip install -r requirements-dev.txt
pytest -q --maxfail=1 --junitxml=junit.xml
```

3) Згенерувати base64 kubeconfig для секрету GitHub (macOS)

- Використовуйте (через bash або зробіть скрипт виконуваним):

```bash
# копіювати в clipboard (macOS):
bash ./scripts/encode_kubeconfig.sh -c > /dev/null
# або зберегти у файл:
bash ./scripts/encode_kubeconfig.sh > kubeconfig.b64
cat kubeconfig.b64
```

- Скопіюйте вміст і вставте у секрет `KUBECONFIG_DATA` у GitHub (радимо зробити його secret в Organization/Repo).

- Альтернатива без скрипта (macOS):

```bash
openssl base64 -A < ~/.kube/config | pbcopy
```

4) Локальний smoke (після підняття Docker)

```bash
docker compose -f .devcontainer/compose.yml --profile core up -d
./scripts/test_containers.sh
docker compose -f .devcontainer/compose.yml down -v
```

### Збір діагностичних логів

Якщо у вас виникають проблеми з Docker або з pull-ами образів (DNS/pull), скористайтеся скриптом для збору діагностичних артефактів. Він згенерує tar.gz з:

- `docker version`, `docker info`, `docker ps --all`
- Docker Compose logs для профілю `core` (якщо присутній .devcontainer/compose.yml)
- DNS перевірки для `registry-1.docker.io` (dig/nslookup) та `curl https://registry-1.docker.io/v2/`

Запустіть локально:

```bash
bash ./scripts/collect_docker_logs.sh
```

Після виконання буде створено архів у каталозі `logs/` типу `logs/docker-diagnostics-YYYYMMDD-HHMMSS.tar.gz`.

Альтернатива: якщо хочете виконати збір на GitHub (наприклад, якщо ваша машина не має доступу до docker.io), запустіть робочий процес вручну в Actions: "Collect docker logs" (в UI репозиторію) — він запустить той самий скрипт і завантажить артефакт у розділ Run -> Artifacts.

### Автоматичне завантаження діагностики (gist + issue)

Якщо ви хочете автоматично завантажити текстові діагностичні файли в приватний gist і створити issue, використайте `gh` CLI і наш helper:

```bash
# збір + завантаження (потрібна авторизація: gh auth login)
bash ./scripts/collect_and_upload_logs.sh
```

Сценарій створює приватний gist з текстовими логами та намагається створити issue у репозиторії з посиланням на gist. Якщо `gh` не встановлено або не автентифіковано — отримаєте повідомлення і локальний архів буде доступний у `logs/`.

5) Зручні Make цілі

Ми додали Makefile з декількома зручними цілями, щоб запускати хелпери без потреби робити файли виконуваними:

```bash
make check-docker        # перевірка docker daemon
make setup-python       # створити Python 3.11 venv через скрипт
make encode-kubeconfig  # закодувати kubeconfig
make fix-perms          # встановити виконувані біти для скриптів
make smoke              # підняти smoke compose profile
```

6) Примітки

- Скрипти у `./scripts/` автоматизують рутинні дії. Вони не змінюють ваші конфіги і лише виводять рекомендації або створюють локальний venv.
- Якщо під час `docker compose` спроби пулити образи ви бачите помилку на кшталт `lookup registry-1.docker.io: no such host`, перевірте DNS / VPN / proxy — на деяких корпоративних мережах цей трафік блокується.

