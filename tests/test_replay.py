import tempfile
import unittest
from pathlib import Path

from retail_stream.ingestion.replay import read_events, replay, replay_delays


class RecordingSink:
    def __init__(self) -> None:
        self.events = []
        self.closed = False

    def send(self, event) -> None:
        self.events.append(event)

    def close(self) -> None:
        self.closed = True


class ReplayTest(unittest.TestCase):
    sample = Path(__file__).parents[1] / "data" / "samples" / "events.csv"

    def test_read_events_sorts_by_source_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "events.csv"
            csv_path.write_text(
                "timestamp,visitorid,event,itemid,transactionid\n"
                "2000,1,view,10,\n"
                "1000,1,view,11,\n",
                encoding="utf-8",
            )
            events = read_events(csv_path)
        self.assertEqual([event.item_id for event in events], [11, 10])

    def test_replay_caps_source_time_gaps(self) -> None:
        delays = list(replay_delays(read_events(self.sample), speed=2, max_delay_seconds=0.25))
        self.assertEqual(delays[0][0], 0)
        self.assertTrue(all(delay <= 0.25 for delay, _ in delays))

    def test_replay_closes_sink(self) -> None:
        sink = RecordingSink()
        sent = replay(read_events(self.sample), sink, wait=False)
        self.assertEqual(sent, 6)
        self.assertTrue(sink.closed)
        self.assertEqual(len(sink.events), 6)
