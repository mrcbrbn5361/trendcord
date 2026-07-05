.PHONY: help install dev test lint build deploy clean

# Colors
COLOR_RESET := \033[0m
COLOR_GREEN := \033[32m
COLOR_BLUE := \033[34m

# Default target
help:
	@echo "$(COLOR_GREEN)Trendcord v2.0 - Kullanılabilir komutlar:$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BLUE)Kurulum:$(COLOR_RESET)"
	@echo "  make install        - Tüm bağımlılıkları kur"
	@echo "  make install-api    - API bağımlılıklarını kur"
	@echo "  make install-web    - Web bağımlılıklarını kur"
	@echo "  make install-bot    - Bot bağımlılıklarını kur"
	@echo ""
	@echo "$(COLOR_BLUE)Geliştirme:$(COLOR_RESET)"
	@echo "  make dev            - Tüm servisleri başlat"
	@echo "  make dev-api        - API sunucusunu başlat"
	@echo "  make dev-web        - Web sunucusunu başlat"
	@echo "  make dev-bot        - Bot'u başlat"
	@echo ""
	@echo "$(COLOR_BLUE)Test:$(COLOR_RESET)"
	@echo "  make test           - Tüm testleri çalıştır"
	@echo "  make test-api       - API testlerini çalıştır"
	@echo "  make test-web       - Web testlerini çalıştır"
	@echo ""
	@echo "$(COLOR_BLUE)Lint:$(COLOR_RESET)"
	@echo "  make lint           - Lint kontrolü yap"
	@echo "  make format         - Kodu formatla"
	@echo "  make type-check     - Tip kontrolü yap"
	@echo ""
	@echo "$(COLOR_BLUE)Docker:$(COLOR_RESET)"
	@echo "  make docker-up      - Docker servislerini başlat"
	@echo "  make docker-down    - Docker servislerini durdur"
	@echo "  make docker-build   - Docker imajlarını oluştur"
	@echo "  make docker-logs    - Docker loglarını göster"
	@echo ""
	@echo "$(COLOR_BLUE)Veritabanı:$(COLOR_RESET)"
	@echo "  make db-migrate     - Migrasyon oluştur"
	@echo "  make db-upgrade     - Migrasyonları uygula"
	@echo "  make db-downgrade   - Migrasyonları geri al"
	@echo "  make db-reset       - Veritabanını sıfırla"
	@echo ""
	@echo "$(COLOR_BLUE)Temizlik:$(COLOR_RESET)"
	@echo "  make clean          - Geçici dosyaları temizle"

# Install
install: install-api install-web install-bot

install-api:
	cd apps/api && pip install -r requirements/dev.txt

install-web:
	cd apps/web && pnpm install

install-bot:
	cd apps/bot && pip install -r requirements.txt

# Development
dev:
	docker-compose up -d

dev-api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

dev-web:
	cd apps/web && pnpm dev

dev-bot:
	cd apps/bot && python main.py

# Test
test: test-api test-web

test-api:
	cd apps/api && pytest

test-web:
	cd apps/web && pnpm test

# Lint
lint: lint-api lint-web

lint-api:
	cd apps/api && ruff check .
	cd apps/api && ruff format --check .

lint-web:
	cd apps/web && pnpm lint

format: format-api format-web

format-api:
	cd apps/api && ruff format .
	cd apps/api && ruff check --fix .

format-web:
	cd apps/web && pnpm prettier --write .

type-check:
	cd apps/api && mypy .
	cd apps/web && pnpm type-check

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f

# Database
db-migrate:
	cd apps/api && alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	cd apps/api && alembic upgrade head

db-downgrade:
	cd apps/api && alembic downgrade -1

db-reset:
	docker-compose exec postgres psql -U trendcord -d trendcord -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	cd apps/api && alembic upgrade head

# Clean
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name ".next" -exec rm -rf {} +
