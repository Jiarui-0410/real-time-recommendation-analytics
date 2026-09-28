from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

ALLOWED_EVENT_TYPES = frozenset({"view", "addtocart", "transaction"})


def _required_int(row: Mapping[str, str], field: str) -> int:
    raw = row.get(field)
    if raw is None or not raw.strip():
        raise ValueError(f"missing required field: {field}")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class UserEvent:
    event_id: str
    source_timestamp_ms: int
    occurred_at: str
    visitor_id: int
    item_id: int
    event_type: str
    transaction_id: str | None
    source: str = "retailrocket_replay"
    schema_version: int = 1

    @classmethod
    def from_retailrocket_row(cls, row: Mapping[str, str]) -> UserEvent:
        timestamp_ms = _required_int(row, "timestamp")
        visitor_id = _required_int(row, "visitorid")
        item_id = _required_int(row, "itemid")
        event_type = (row.get("event") or "").strip().lower()
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"unsupported event type: {event_type!r}")

        transaction_raw = (row.get("transactionid") or "").strip()
        transaction_id = transaction_raw or None
        identity = "|".join(
            (str(timestamp_ms), str(visitor_id), event_type, str(item_id), transaction_id or "")
        )
        event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        occurred_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()
        return cls(
            event_id=event_id,
            source_timestamp_ms=timestamp_ms,
            occurred_at=occurred_at,
            visitor_id=visitor_id,
            item_id=item_id,
            event_type=event_type,
            transaction_id=transaction_id,
        )

    @property
    def kafka_key(self) -> bytes:
        return str(self.visitor_id).encode("utf-8")

    def to_json(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True).encode("utf-8")

