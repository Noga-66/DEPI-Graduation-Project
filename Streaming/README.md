# Streaming Engineer - Role 5 Code

## Files
- producer.py: Streams CSV rows to Kafka at a configurable rate
- consumer.py: Reads messages from Kafka and prints them
- requirements.txt: Python dependencies

## Quick Start
1) Install deps:

```bash
pip install -r requirements.txt
```

2) Run a producer:

```bash
python producer.py --csv path/to/file.csv --topic my-topic --rate 2
```

3) Run a consumer:

```bash
python consumer.py --topic my-topic --from-beginning
```

## Options
- --bootstrap: Kafka bootstrap servers (default: localhost:9092)
- --rate: Rows per second (default: 1)
- --loop: Loop CSV forever
- --key-field: CSV field to use as key
- --required: Comma-separated required fields
- --max-rows: Stop after N rows
