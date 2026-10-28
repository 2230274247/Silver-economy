import socket
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import main as launcher


class LauncherTests(unittest.TestCase):
    def test_occupied_port_is_refused_without_touching_its_listener(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, str(port)):
                launcher.check_port(port)
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass

    def test_browser_opens_once_only_after_both_services_are_ready(self):
        server = SimpleNamespace(started=True, should_exit=False)
        child = Mock()
        child.poll.return_value = None
        stop = Mock()
        stop.wait.side_effect = [False, False, False, True]
        failed = threading.Event()
        with (
            patch("main.ready", side_effect=[False, True]) as ready,
            patch("main.webbrowser.open", return_value=True) as browser,
            patch.dict(sys.modules, {"httpx": SimpleNamespace(Client=MagicMock())}),
        ):
            launcher.watch_services(server, [child], stop, failed, True)
        self.assertEqual(ready.call_count, 2)
        browser.assert_called_once_with(launcher.WEBSITE)
        self.assertFalse(failed.is_set())

    def test_child_failure_stops_api_without_opening_browser(self):
        server = SimpleNamespace(started=True, should_exit=False)
        child = Mock()
        child.poll.return_value = 1
        stop = Mock()
        stop.wait.return_value = False
        failed = threading.Event()
        with (
            patch("main.webbrowser.open") as browser,
            patch.dict(sys.modules, {"httpx": SimpleNamespace(Client=MagicMock())}),
        ):
            launcher.watch_services(server, [child], stop, failed, True)
        self.assertTrue(server.should_exit)
        self.assertTrue(failed.is_set())
        browser.assert_not_called()

    def test_ready_requires_api_database_and_frontend_success(self):
        client = Mock()
        client.get.side_effect = [
            SimpleNamespace(status_code=503),
            SimpleNamespace(status_code=200),
        ]
        self.assertFalse(launcher.ready(client))
        client.get.side_effect = [
            SimpleNamespace(status_code=200, json=lambda: {"status": "ready"}),
            SimpleNamespace(status_code=200),
        ]
        self.assertTrue(launcher.ready(client))


if __name__ == "__main__":
    unittest.main()
