import unittest
from unittest.mock import patch

import requests

from engine.research.security import PublicResearchSession, UnsafeUrl


class PublicTransportTests(unittest.TestCase):
    def test_each_prepared_destination_is_checked_before_transport(self):
        session = PublicResearchSession()
        self.addCleanup(session.close)
        target = requests.Request("GET", "http://127.0.0.1/").prepare()
        with patch.object(requests.Session, "send") as transport:
            with self.assertRaises(UnsafeUrl):
                session.send(target)
            transport.assert_not_called()
