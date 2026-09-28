from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol

from retail_stream.contracts import UserEvent


class EventSink(Protocol):
    def send(self, event: UserEvent) -> None: ...

    def close(self) -> None: ...


class StdoutSink:
    def send(self, event: UserEvent) -> None:
        print(event.to_json().decode("utf-8"))

    def close(self) -> None:
        return None


class KafkaSink:
    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        try:
            from confluent_kafka import Producer
        except ImportError as exc:
            raise RuntimeError("Install the project dependencies before using Kafka") from exc
        self._producer = Producer({"bootstrap.servers": bootstrap_servers})
        self._topic = topic

    def send(self, event: UserEvent) -> None:
        while True:
            try:
                self._producer.produce(
                    self._topic,
                    key=event.kafka_key,
                    value=event.to_json(),
                    headers=[("schema_version", str(event.schema_version).encode("ascii"))],
                )
                break
            except BufferError:
                self._producer.poll(0.5)
        self._producer.poll(0)

    def close(self) -> None:
        remaining = self._producer.flush(10)
        if remaining:
            raise RuntimeError(f"failed to deliver {remaining} Kafka message(s)")


def read_events(path: Path) -> list[UserEvent]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {"timestamp", "visitorid", "event", "itemid"}
        missing = expected.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")
        events = [UserEvent.from_retailrocket_row(row) for row in reader]
    events.sort(key=lambda event: (event.source_timestamp_ms, event.event_id))
    return events


def replay_delays(
    events: Iterable[UserEvent], speed: float, max_delay_seconds: float
) -> Iterator[tuple[float, UserEvent]]:
    if speed <= 0:
        raise ValueError("speed must be positive")
    if max_delay_seconds < 0:
        raise ValueError("max delay must be non-negative")

    previous_timestamp: int | None = None
    for event in events:
        if previous_timestamp is None:
            delay = 0.0
        else:
            source_gap = max(0, event.source_timestamp_ms - previous_timestamp) / 1000
            delay = min(source_gap / speed, max_delay_seconds)
        previous_timestamp = event.source_timestamp_ms
        yield delay, event


def replay(
    events: Iterable[UserEvent],
    sink: EventSink,
    *,
    speed: float = 3600.0,
    max_delay_seconds: float = 2.0,
    wait: bool = True,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    sent = 0
    try:
        for delay, event in replay_delays(events, speed, max_delay_seconds):
            if wait and delay:
                sleeper(delay)
            sink.send(event)
            sent += 1
    finally:
        sink.close()
    return sent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay Retailrocket events into Kafka")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    )
    parser.add_argument("--topic", default=os.getenv("KAFKA_TOPIC", "user_events"))
    parser.add_argument(
        "--speed", type=float, default=3600.0, help="source-time acceleration factor"
    )
    parser.add_argument("--max-delay-seconds", type=float, default=2.0)
    parser.add_argument("--no-wait", action="store_true", help="emit as fast as possible")
    parser.add_argument("--dry-run", action="store_true", help="write JSON lines to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        events = read_events(args.csv_path)
        sink: EventSink = (
            StdoutSink()
            if args.dry_run
            else KafkaSink(args.bootstrap_servers, args.topic)
        )
        sent = replay(
            events,
            sink,
            speed=args.speed,
            max_delay_seconds=args.max_delay_seconds,
            wait=not args.no_wait,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"replayed {sent} event(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
