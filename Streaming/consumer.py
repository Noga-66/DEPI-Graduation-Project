import argparse
import json
import os
import sys
from typing import Optional

from kafka import KafkaConsumer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consume Kafka messages and print them.")
    parser.add_argument("--topic", required=True, help="Kafka topic name")
    parser.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    parser.add_argument("--group-id", default="role5-consumer", help="Consumer group id")
    parser.add_argument("--from-beginning", action="store_true", help="Read from earliest offset")
    parser.add_argument("--max-messages", type=int, default=0, help="Stop after N messages (0 = no limit)")
    return parser.parse_args()


def build_consumer(
    topic: str,
    bootstrap_servers: str,
    group_id: str,
    from_beginning: bool,
) -> KafkaConsumer:
    auto_offset_reset = "earliest" if from_beginning else "latest"
    return KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v else None,
    )


def format_message(message: Optional[dict]) -> str:
    if message is None:
        return "<empty>"
    return json.dumps(message, ensure_ascii=False)


def main() -> int:
    args = parse_args()
    consumer = build_consumer(
        topic=args.topic,
        bootstrap_servers=args.bootstrap,
        group_id=args.group_id,
        from_beginning=args.from_beginning,
    )

    count = 0
    try:
        for message in consumer:
            print(format_message(message.value))
            count += 1

            if args.max_messages and count >= args.max_messages:
                break
    except KeyboardInterrupt:
        print("Interrupted. Closing consumer...", file=sys.stderr)
    finally:
        consumer.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
