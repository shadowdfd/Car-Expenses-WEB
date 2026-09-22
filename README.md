# Car Expenses

Веб-приложение для учёта расходов на автомобили. Позволяет отслеживать затраты на топливо, запчасти, техническое обслуживание и прочие расходы.

! С этой же базой данных может одновременно работать desktop приложение из репозитория [Car-Expenses](https://github.com/shadowdfd/Car-Expenses)

## Возможности

- **История ТО** — учёт технического обслуживания с привязкой к пробегу и стандартным работам
- **Расходы** — фиксация различных типов расходов (страховка, штрафы, парковки и т.д.)
- **Топливо** — учёт заправок с расчётом стоимости
- **Покупки запчастей** — каталог запчастей с возможностью привязки к конкретным ТО
- **Каталог запчастей** — база запчастей с артикулами, производителями и системами автомобиля
- **Отчёты** — анализ выполнения регламентных работ и общий отчёт по автомобилю
- **Справочники** — настраиваемые справочники типов расходов, СТО, производителей и систем автомобиля
- **Фильтры** — глобальная фильтрация по автомобилю и периоду
- **Импорт/Экспорт** — обмен данными через CSV файлы

## Технологии

- Python 3.11 + Flask
- SQLAlchemy ORM
- SQLite база данных
- Bootstrap 5
- Docker

## Установка и запуск

### Windows

#### 1. Установка Docker Desktop

1. Скачайте Docker Desktop с официального сайта: https://www.docker.com/products/docker-desktop/
2. Запустите установщик и следуйте инструкциям
3. После установки перезагрузите компьютер
4. Запустите Docker Desktop и дождитесь его полной загрузки (иконка кита в трее должна стать активной)

#### 2. Запуск приложения

1. Создайте папку для проекта, например `C:\car-expenses`
2. Скачайте файл `docker-compose.yml` в эту папку или создайте его со следующим содержимым:

```yaml
services:
  web:
    image: shadowdfd/car-expenses:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
```

3. Откройте командную строку (Win+R → `cmd`) или PowerShell
4. Перейдите в папку проекта:
```cmd
cd C:\car-expenses
```

5. Запустите контейнер:
```cmd
docker-compose up -d
```

6. Откройте браузер и перейдите по адресу: http://localhost:8000

#### Управление контейнером

```cmd
# Остановить приложение
docker-compose stop

# Запустить приложение
docker-compose start

# Перезапустить приложение
docker-compose restart

# Остановить и удалить контейнер
docker-compose down

# Посмотреть логи
docker-compose logs -f
```

### Linux

#### 1. Установка Docker

**Ubuntu/Debian:**

```bash
# Обновление системы
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# Добавление официального GPG ключа Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавление репозитория Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Добавление текущего пользователя в группу docker
sudo usermod -aG docker $USER

# Выход и повторный вход для применения изменений группы
# или выполните: newgrp docker
```

**Fedora/CentOS/RHEL:**

```bash
# Установка Docker
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Запуск и автозапуск Docker
sudo systemctl start docker
sudo systemctl enable docker

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. Запуск приложения

1. Создайте папку для проекта:
```bash
mkdir ~/car-expenses
cd ~/car-expenses
```

2. Создайте файл `docker-compose.yml`:
```bash
cat > docker-compose.yml << 'EOF'
services:
  web:
    image: shadowdfd/car-expenses:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
EOF
```

3. Запустите контейнер:
```bash
docker compose up -d
```

4. Откройте браузер и перейдите по адресу: http://localhost:8000

#### Управление контейнером

```bash
# Остановить приложение
docker compose stop

# Запустить приложение
docker compose start

# Перезапустить приложение
docker compose restart

# Остановить и удалить контейнер
docker compose down

# Посмотреть логи
docker compose logs -f
```

## Хранение данных

Все данные (база данных SQLite) сохраняются в папке `./data` рядом с файлом `docker-compose.yml`. Эта папка создаётся автоматически при первом запуске.

Для резервного копирования достаточно скопировать содержимое папки `data`.

## Первый запуск

При первом запуске приложение создаст пустую базу данных. Рекомендуемый порядок заполнения:

1. Создайте автомобиль в справочнике "Автомобили"
2. Заполните справочники (типы расходов, СТО, производители запчастей и т.д.)
3. Добавьте стандартные работы для автомобиля (замена масла, фильтров и т.д.)
4. Начните вести учёт расходов, ТО и заправок

## Обновление

Для обновления приложения до последней версии:

**Windows:**
```cmd
docker-compose pull
docker-compose up -d
```

**Linux:**
```bash
docker compose pull
docker compose up -d
```

## Разработка

Если вы хотите запустить приложение в режиме разработки с возможностью внесения изменений:

1. Клонируйте репозиторий
2. Измените `docker-compose.yml`:
```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - .:/app
    environment:
      - FLASK_ENV=development
```

3. Запустите:
```bash
docker-compose up --build
```

## Лицензия

MIT

## Автор

ShadowDFD
