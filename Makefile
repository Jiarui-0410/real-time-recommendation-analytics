.PHONY: infra test replay batch stream train index api

infra:
	docker compose up -d broker postgres qdrant

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

replay:
	replay-events data/raw/events.csv --speed 86400 --max-delay-seconds 0.1

batch:
	docker compose --profile spark run --rm spark /opt/spark/bin/spark-submit \
		--packages org.postgresql:postgresql:42.7.8 \
		/opt/project/src/retail_stream/processing/batch_etl.py \
		--raw-dir /opt/project/data/raw --output /opt/project/data/processed/clean_events \
		--load-postgres

stream:
	docker compose --profile spark exec spark /opt/spark/bin/spark-submit \
		--packages org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.3,org.postgresql:postgresql:42.7.8 \
		/opt/project/src/retail_stream/processing/streaming.py

train:
	train-two-tower data/processed/clean_events --output-dir artifacts/model

index:
	index-items --model-dir artifacts/model

api:
	serve-recommendations
