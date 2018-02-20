from copy import copy
from enum import Enum
from logging import getLogger

from detector_integration_api.utils import ClientDisableWrapper, check_for_target_status

_logger = getLogger(__name__)
_audit_logger = getLogger("audit_trail")


class IntegrationStatus(Enum):
    INITIALIZED = "initialized",
    CONFIGURED = "configured",
    RUNNING = "running",
    DETECTOR_STOPPED = "detector_stopped",
    BSREAD_STILL_RUNNING = "bsread_still_running",
    FINISHED = "finished"
    ERROR = "error"


class IntegrationManager(object):
    def __init__(self, backend_client, writer_client, detector_client, bsread_client):
        self.backend_client = ClientDisableWrapper(backend_client)
        self.writer_client = ClientDisableWrapper(writer_client)
        self.detector_client = ClientDisableWrapper(detector_client)
        self.bsread_client = ClientDisableWrapper(bsread_client)

        self._last_set_backend_config = {}
        self._last_set_writer_config = {}
        self._last_set_detector_config = {}
        self._last_set_bsread_config = {}

        self.last_config_successful = False

    def start_acquisition(self):
        _audit_logger.info("Starting acquisition.")

        status = self.get_acquisition_status()
        if status != IntegrationStatus.CONFIGURED:
            raise ValueError("Cannot start acquisition in %s state. Please configure first." % status)

        _audit_logger.info("bsread_client.start()")
        self.bsread_client.start()

        _audit_logger.info("backend_client.open()")
        self.backend_client.open()

        _audit_logger.info("writer_client.start()")
        self.writer_client.start()

        _audit_logger.info("detector_client.start()")
        self.detector_client.start()

        return check_for_target_status(self.get_acquisition_status, IntegrationStatus.RUNNING)

    def stop_acquisition(self):
        _audit_logger.info("Stopping acquisition.")

        status = self.get_acquisition_status()

        if status == IntegrationStatus.RUNNING:
            _audit_logger.info("detector_client.stop()")
            self.detector_client.stop()

            _audit_logger.info("backend_client.close()")
            self.backend_client.close()

            _audit_logger.info("writer_client.stop()")
            self.writer_client.stop()

            _audit_logger.info("bsread_client.stop()")
            self.bsread_client.stop()

        return self.reset()

    def get_acquisition_status(self):
        status = self.interpret_status(self.get_status_details())

        # There is no way of knowing if the detector is configured as the user desired.
        # We have a flag to check if the user config was passed on to the detector.
        if status == IntegrationStatus.CONFIGURED and self.last_config_successful is False:
            return IntegrationStatus.ERROR

        return status

    def get_acquisition_status_string(self):
        return str(self.get_acquisition_status())

    def get_status_details(self):
        _audit_logger.info("Getting status details.")

        _audit_logger.info("writer_client.get_status()")
        writer_status = self.writer_client.get_status()["is_running"] \
            if self.writer_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

        _audit_logger.info("backend_client.get_status()")
        backend_status = self.backend_client.get_status() \
            if self.backend_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

        _audit_logger.info("detector_client.get_status()")
        detector_status = self.detector_client.get_status() \
            if self.detector_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

        _audit_logger.info("bsread_client.get_status()")
        bsread_status = self.bsread_client.get_status()["is_running"] \
            if self.bsread_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

        _logger.debug("Detailed status requested:\nWriter: %s\nBackend: %s\nDetector: %s\nbsread: %s",
                      writer_status, backend_status, detector_status, bsread_status)

        return {"writer": writer_status,
                "backend": backend_status,
                "detector": detector_status,
                "bsread": bsread_status}

    def get_acquisition_config(self):
        # Always return a copy - we do not want this to be updated.
        return {"writer": copy(self._last_set_writer_config),
                "backend": copy(self._last_set_backend_config),
                "detector": copy(self._last_set_detector_config),
                "bsread": copy(self._last_set_bsread_config)}

    def set_acquisition_config(self, new_config):
        if {"writer", "backend", "detector", "bsread"} != set(new_config):
            raise ValueError("Specify config JSON with 4 root elements: 'writer', 'backend', 'detector', 'bsread'.")

        writer_config = new_config["writer"]
        backend_config = new_config["backend"]
        detector_config = new_config["detector"]
        bsread_config = new_config["bsread"]

        status = self.get_acquisition_status()

        self.last_config_successful = False

        if status not in (IntegrationStatus.INITIALIZED, IntegrationStatus.CONFIGURED):
            raise ValueError("Cannot set config in %s state. Please reset first." % status)

        # The backend is configurable only in the INITIALIZED state.
        if status == IntegrationStatus.CONFIGURED:
            _logger.debug("Integration status is %s. Resetting before applying config.", status)
            self.reset()

        _audit_logger.info("Set acquisition configuration:\n"
                           "Writer config: %s\n"
                           "Backend config: %s\n"
                           "Detector config: %s\n",
                           writer_config, backend_config, detector_config)

        # Before setting the new config, validate the provided values. All must be valid.
        if self.writer_client.client_enabled:
            self.validate_writer_config(writer_config)

        if self.backend_client.client_enabled:
            self.validate_backend_config(backend_config)

        if self.detector_client.client_enabled:
            self.validate_detector_config(detector_config)

        self.validate_configs_dependencies(writer_config, backend_config, detector_config, bsread_config)

        _audit_logger.info("backend_client.set_config(backend_config)")
        self.backend_client.set_config(backend_config)
        self._last_set_backend_config = backend_config

        _audit_logger.info("writer_client.set_parameters(writer_config)")
        self.writer_client.set_parameters(writer_config)
        self._last_set_writer_config = writer_config

        _audit_logger.info("detector_client.set_config(detector_config)")
        self.detector_client.set_config(detector_config)
        self._last_set_detector_config = detector_config

        _audit_logger.info("bsread_client.set_parameters(bsread_config)")
        self.bsread_client.set_parameters(bsread_config)
        self._last_set_bsread_config = bsread_config

        self.last_config_successful = True

        return check_for_target_status(self.get_acquisition_status, IntegrationStatus.CONFIGURED)

    def update_acquisition_config(self, config_updates):
        current_config = self.get_acquisition_config()

        _logger.debug("Updating acquisition config: %s", current_config)

        def update_config_section(section_name):
            if section_name in config_updates and config_updates.get(section_name):
                current_config[section_name].update(config_updates[section_name])

        update_config_section("writer")
        update_config_section("backend")
        update_config_section("detector")
        update_config_section("bsread")

        self.set_acquisition_config(current_config)

        return check_for_target_status(self.get_acquisition_status, IntegrationStatus.CONFIGURED)

    def set_clients_enabled(self, client_status):

        if "backend" in client_status:
            self.backend_client.set_client_enabled(client_status["backend"])
            _logger.info("Backend client enable=%s.", self.backend_client.is_client_enabled())

        if "writer" in client_status:
            self.writer_client.set_client_enabled(client_status["writer"])
            _logger.info("Writer client enable=%s.", self.writer_client.is_client_enabled())

        if "detector" in client_status:
            self.detector_client.set_client_enabled(client_status["detector"])
            _logger.info("Detector client enable=%s.", self.detector_client.is_client_enabled())

        if "bsread" in client_status:
            self.bsread_client.set_client_enabled(client_status["bsread"])
            _logger.info("bsread client enable=%s.", self.bsread_client.is_client_enabled())

    def get_clients_enabled(self):
        return {"backend": self.backend_client.is_client_enabled(),
                "writer": self.writer_client.is_client_enabled(),
                "bsread": self.bsread_client.is_client_enabled(),
                "detector": self.detector_client.is_client_enabled()}

    def reset(self):
        _audit_logger.info("Resetting integration api.")

        self.last_config_successful = False

        _audit_logger.info("detector_client.stop()")
        self.detector_client.stop()

        _audit_logger.info("backend_client.reset()")
        self.backend_client.reset()

        _audit_logger.info("writer_client.reset()")
        self.writer_client.reset()

        _audit_logger.info("bsread_client.reset()")
        self.bsread_client.reset()

        return check_for_target_status(self.get_acquisition_status, IntegrationStatus.INITIALIZED)

    def get_server_info(self):
        return {
            "clients": {
                "backend_url": self.backend_client.backend_url,
                "writer_url": self.writer_client._api_address.format(url=""),
                "bsread_url": self.bsread_client._api_address.format(url="")},
            "clients_enabled": self.get_clients_enabled(),
            "validator": "NOT IMPLEMENTED",
            "last_config_successful": self.last_config_successful
        }

    def get_metrics(self):
        # Always return a copy - we do not want this to be updated.
        return {"writer": {},
                "backend": self.backend_client.get_metrics(),
                "detector": {},
                "bsread": {}}

    def validate_writer_config(self, configuration):
        if configuration is None:
            raise ValueError("Writer configuration cannot be None.")

    def validate_backend_config(self, configuration):
        if configuration is None:
            raise ValueError("Backend configuration cannot be None.")

    def validate_detector_config(self, configuration):
        if configuration is None:
            raise ValueError("Detector configuration cannot be None.")

    def validate_bsread_config(self, configuration):
        if configuration is None:
            raise ValueError("bsread configuration cannot be None.")

    def validate_configs_dependencies(self, writer_config, backend_config, detector_config, bsread_config):
        pass

    def interpret_status(self, statuses):

        _logger.debug("Interpreting statuses: %s", statuses)

        writer = statuses["writer"]
        backend = statuses["backend"]
        detector = statuses["detector"]
        bsread = statuses["bsread"]

        def cmp(status, expected_value):

            _logger.debug("Comparing status '%s' with expected status '%s'.", status, expected_value)

            if status == ClientDisableWrapper.STATUS_DISABLED:
                return True

            if isinstance(expected_value, (tuple, list)):
                return status in expected_value
            else:
                return status == expected_value

        # If no other conditions match.
        status = IntegrationStatus.ERROR

        if cmp(writer, False) and cmp(detector, "idle") and cmp(backend, "INITIALIZED") and cmp(bsread, False):
            status = IntegrationStatus.INITIALIZED

        elif cmp(writer, False) and cmp(detector, "idle") and cmp(backend, "CONFIGURED") and cmp(bsread, False):
            status = IntegrationStatus.CONFIGURED

        elif cmp(writer, True) and cmp(detector, ("running", "waiting")) and cmp(backend, "OPEN") and cmp(bsread, True):
            status = IntegrationStatus.RUNNING

        elif cmp(writer, True) and cmp(detector, "idle") and cmp(backend, "OPEN") and cmp(bsread, True):
            status = IntegrationStatus.DETECTOR_STOPPED

        elif cmp(writer, False) and cmp(detector, "idle") and cmp(backend, "OPEN") and cmp(bsread, False):
            status = IntegrationStatus.FINISHED

        elif cmp(writer, False) and cmp(detector, "idle") and cmp(backend, "OPEN") and cmp(bsread, True):
            status = IntegrationStatus.BSREAD_STILL_RUNNING

        _logger.debug("Statuses interpreted as '%s'.", status)

        return status



