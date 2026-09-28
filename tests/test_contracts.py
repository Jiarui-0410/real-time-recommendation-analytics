import json
import unittest

from retail_stream.contracts import UserEvent

ROW = {
    "timestamp": "1440900000000",
    "visitorid": "1001",
    "event": "view",
    "itemid": "501",
    "transactionid": "",
}


class UserEventTest(unittest.TestCase):
    def test_event_id_is_deterministic(self) -> None:
        first = UserEvent.from_retailrocket_row(ROW)
        second = UserEvent.from_retailrocket_row(dict(ROW))
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(len(first.event_id), 64)

    def test_event_serializes_to_versioned_json(self) -> None:
        payload = json.loads(UserEvent.from_retailrocket_row(ROW).to_json())
        self.assertEqual(payload["schema_version"], 1)
        self.assertTrue(payload["occurred_at"].endswith("+00:00"))
        self.assertIsNone(payload["transaction_id"])

    def test_unknown_event_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported event type"):
            UserEvent.from_retailrocket_row({**ROW, "event": "refund"})
