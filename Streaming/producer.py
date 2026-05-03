import argparse
import csv
import json
import os
import sys
import time
from typing import Dict, Iterable

from kafka import KafkaProducer


def iter_csv_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def build_producer(bootstrap_servers: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda v: v.encode("utf-8") if v else None,
        retries=5,
        linger_ms=50,
    )


def validate_row(row: Dict[str, str], required_fields: Iterable[str]) -> bool:
    for field in required_fields:
        if field not in row or row[field] is None or row[field] == "":
            return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream CSV rows to Kafka.")
    parser.add_argument("--csv", required=True, help="Path to source CSV file")
    parser.add_argument("--topic", required=True, help="Kafka topic name")
    parser.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    parser.add_argument("--rate", type=float, default=1.0, help="Rows per second")
    parser.add_argument("--loop", action="store_true", help="Loop the CSV forever")
    parser.add_argument("--key-field", default="", help="CSV field to use as Kafka message key")
    parser.add_argument("--required", default="", help="Comma-separated required fields")
    parser.add_argument("--max-rows", type=int, default=0, help="Stop after N rows (0 = no limit)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required_fields = [f.strip() for f in args.required.split(",") if f.strip()]

    if args.rate <= 0:
        print("rate must be > 0", file=sys.stderr)
        return 2

    producer = build_producer(args.bootstrap)
    sleep_seconds = 1.0 / args.rate
    rows_sent = 0

    try:
        while True:
            for row in iter_csv_rows(args.csv):
                if required_fields and not validate_row(row, required_fields):
                    print("Skipping invalid row: missing required fields", file=sys.stderr)
                    continue

                key = row.get(args.key_field) if args.key_field else None
                producer.send(args.topic, key=key, value=row)
                rows_sent += 1

                if args.max_rows and rows_sent >= args.max_rows:
                    producer.flush()
                    return 0

                time.sleep(sleep_seconds)

            if not args.loop:
                break
    except KeyboardInterrupt:
        print("Interrupted. Flushing producer...", file=sys.stderr)
    finally:
        producer.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
