import unittest

from sf_dia.manager import IntegrationStatus
import sf_dia.manager as csaxs_manager
from tests.utils import get_test_bsread_integration_manager


class TestSfStateMachine(unittest.TestCase):
    def test_state_machine(self):
        manager = get_test_bsread_integration_manager(csaxs_manager)

        manager.writer_client.status = "stopped"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "INITIALIZED"
        manager.bsread_client.is_running = False
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.INITIALIZED)

        manager.writer_client.status = "stopped"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "CONFIGURED"
        manager.bsread_client.is_running = False
        manager.last_config_successful = True
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.CONFIGURED)

        manager.last_config_successful = False
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.ERROR)

        manager.writer_client.status = "receiving"
        manager.detector_client.status = "running"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = True
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.RUNNING)

        manager.writer_client.status = "writing"
        manager.detector_client.status = "waiting"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = True
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.RUNNING)

        manager.writer_client.status = "receiving"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.status = {"is_running": True}
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.DETECTOR_STOPPED)

        manager.writer_client.status = "writing"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = True
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.DETECTOR_STOPPED)

        manager.writer_client.status = "receiving"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = False
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.DETECTOR_STOPPED)

        manager.writer_client.status = "writing"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = False
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.DETECTOR_STOPPED)

        manager.writer_client.status = "finished"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = True
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.BSREAD_STILL_RUNNING)

        manager.writer_client.status = "stopped"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = True
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.BSREAD_STILL_RUNNING)

        manager.writer_client.status = "finished"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = False
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.FINISHED)

        manager.writer_client.status = "stopped"
        manager.detector_client.status = "idle"
        manager.backend_client.status = "OPEN"
        manager.bsread_client.is_running = False
        self.assertEqual(manager.get_acquisition_status(), IntegrationStatus.FINISHED)