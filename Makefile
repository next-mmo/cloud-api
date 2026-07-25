.PHONY: up down logs test zip

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

test:
	python scripts/smoke_test.py

zip:
	cd .. && zip -r wan-voxcpm-cloud-starter.zip wan-voxcpm-cloud-starter -x "*/node_modules/*" "*/data/*" "*/.git/*"
