import signal
import unittest

from multiprocessing import Process
from time import sleep

import os

from sf_dia import manager
from tests.utils import start_test_bsread_integration_server


class TestReadme(unittest.TestCase):
    def setUp(self):
        self.host = "0.0.0.0"
        self.port = 10000

        self.dia_process = Process(target=start_test_bsread_integration_server, args=(self.host, self.port, manager))
        self.dia_process.start()

        # Give it some time to start.
        sleep(1)

    def tearDown(self):
        self.dia_process.terminate()
        sleep(0.5)

        os.kill(self.dia_process.pid, signal.SIGINT)

        # Wait for the server to die.
        sleep(1)

    def test_example(self):
        # This test needs to be fixed once we have the final example.
        self.assertTrue(False)
