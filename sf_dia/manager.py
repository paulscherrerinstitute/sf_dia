from copy import copy
from logging import getLogger

from detector_integration_api.utils import ClientDisableWrapper, check_for_target_status

from sf_dia.validation import IntegrationStatus, validate_writer_config, validate_backend_config, \
    validate_detector_config, validate_bsread_config, validate_configs_dependencies, interpret_status

from sf_dia.client.detector_pipeline import DetectorPipeline

import epics

from threading import Thread

_logger = getLogger(__name__)
_audit_logger = getLogger("audit_trail")

DEFAULT_CAPUT_TIMEOUT = 3

class IntegrationManager(object):
    def __init__(self, enabled_detectors, bsread_client, timing_pv, timing_start_code, timing_stop_code, caput_timeout=None):

        self.timing_pv         = timing_pv
        self.timing_start_code = timing_start_code
        self.timing_stop_code  = timing_stop_code
        if caput_timeout is None:
            self.caput_timeout = DEFAULT_CAPUT_TIMEOUT
        else:
            self.caput_timeout = caput_timeout

        self.enabled_detectors = {}
        for detector in enabled_detectors.keys():
             backend_client  = enabled_detectors[detector].backend_client
             writer_client   = enabled_detectors[detector].writer_client
             detector_client = enabled_detectors[detector].detector_client
             self.enabled_detectors[detector] = DetectorPipeline(ClientDisableWrapper(detector_client, True, "detector"), 
                                                                 ClientDisableWrapper(backend_client,  True, "backend"),
                                                                 ClientDisableWrapper(writer_client,   True, "writer"))
        self.bsread_client = ClientDisableWrapper(bsread_client, True, "bsread writer")

        self._last_set_backend_config = {}
        self._last_set_writer_config = {}
        self._last_set_detector_config = {}
        self._last_set_bsread_config = {}

        self.last_config_successful = False

    def start_acquisition(self, parameters):
        _audit_logger.info("Starting acquisition.")

        status = self.get_acquisition_status()
        if status != IntegrationStatus.CONFIGURED:
            raise ValueError("Cannot start acquisition in %s state. Please configure first." % status)

        _audit_logger.info("bsread_client.start()")
        self.bsread_client.start()

        _audit_logger.info("detector_pipeline.start()")
        for detector in  self.enabled_detectors.keys():
            self.enabled_detectors[detector].start()

        if parameters.get("trigger_start", True):
            _logger.debug("Executing start command: caput %s %d", self.timing_pv, self.timing_start_code)
            epics.caput(self.timing_pv, self.timing_start_code, wait=True, timeout=self.caput_timeout)
        else:
            _logger.debug("DIA prepared fully to collect data from detector, "
                          "but trigger to start detector will come from outside")

        return check_for_target_status(self.get_acquisition_status,
                                       (IntegrationStatus.RUNNING,
                                        IntegrationStatus.DETECTOR_STOPPED,
                                        IntegrationStatus.BSREAD_STILL_RUNNING,
                                        IntegrationStatus.FINISHED))

    def stop_acquisition(self):
        _audit_logger.info("Stopping acquisition.")

        status = self.get_acquisition_status()
        if status != IntegrationStatus.BSREAD_STILL_RUNNING and status != IntegrationStatus.FINISHED:
            raise ValueError("Cannot stop acquisition in %s state. Please wait for backend to finish." % status)

        _logger.debug("Executing stop command: caput %s %d", self.timing_pv, self.timing_stop_code)
        epics.caput(self.timing_pv, self.timing_stop_code, wait=True, timeout=self.caput_timeout)
 
        _audit_logger.info("detector_pipeline .stop()")
        for detector in self.enabled_detectors.keys():
            self.enabled_detectors[detector].stop()

        _audit_logger.info("bsread_client.stop()")
        self.bsread_client.stop()

        return self.reset()

    def get_acquisition_status(self):
        status = interpret_status(self.get_status_details())
        _audit_logger.info("Got_acquisition_status : %s", status)
        # There is no way of knowing if the detector is configured as the user desired.
        # We have a flag to check if the user config was passed on to the detector.
        if status == IntegrationStatus.CONFIGURED and self.last_config_successful is False:
            return IntegrationStatus.ERROR

        return status

    def get_acquisition_status_string(self):
        return str(self.get_acquisition_status())

    def get_status_details(self):
        #_audit_logger.info("Getting status details.")

        status = {} 

        for detector in self.enabled_detectors.keys():
            detector_client, backend_client, writer_client = self.enabled_detectors[detector].return_clients()
   
            writer_status = writer_client.get_status() \
                if writer_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

            backend_status = backend_client.get_status() \
                if backend_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

            detector_status = detector_client.get_status() \
                if detector_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

            status[detector] = {"detector": detector_status, "backend": backend_status, "writer": writer_status}

        bsread_status = self.bsread_client.get_status() \
            if self.bsread_client.is_client_enabled() else ClientDisableWrapper.STATUS_DISABLED

        status["bsread"] = bsread_status

        return status

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
                           "Detector config: %s\n"
                           "Bsread config: %s\n",
                           writer_config, backend_config, detector_config, bsread_config)

        # Before setting the new config, validate the provided values. All must be valid.
        for detector in self.enabled_detectors.keys():
            _audit_logger.info("Detector : %s", detector)
            detector_client, backend_client, writer_client = self.enabled_detectors[detector].return_clients()

            if writer_client.client_enabled:
                validate_writer_config(writer_config)

            if backend_client.client_enabled:
                validate_backend_config(backend_config)

            if detector_client.client_enabled:
                validate_detector_config(detector_config)

        if self.bsread_client.client_enabled:
            validate_bsread_config(bsread_config)

        validate_configs_dependencies(writer_config, backend_config, detector_config, bsread_config)

        for detector in self.enabled_detectors.keys():
            _audit_logger.info("Detector : %s", detector)
            detector_client, backend_client, writer_client = self.enabled_detectors[detector].return_clients()

            _audit_logger.info("backend_client.set_config(backend_config)")
            modified_backend_config = copy(backend_config)
            if "pede_corrections_filename" in backend_config.keys():
                modified_backend_config["pede_corrections_filename"] = backend_config["pede_corrections_filename"] + "." + detector + ".res.h5"
                _audit_logger.info("Pedestal file for detector %s will be %s", detector, modified_backend_config["pede_corrections_filename"])
            if "gain_corrections_filename" in backend_config.keys():
                modified_backend_config["gain_corrections_filename"] = backend_config["gain_corrections_filename"] + "/" + detector + "/gains.h5"
                _audit_logger.info("Gain file for detector %s will be %s", detector, modified_backend_config["gain_corrections_filename"])
            backend_client.set_config(modified_backend_config)
            self._last_set_backend_config = backend_config

            _audit_logger.info("writer_client.set_parameters(writer_config)")
            output_file = writer_config["output_file"]
            modified_writer_config = copy(writer_config)
            if output_file != "/dev/null":
                modified_writer_config["output_file"] = output_file + "." + detector + ".h5"
                _audit_logger.info("Output file for detector %s will be %s", detector, modified_writer_config["output_file"]) 
            writer_client.set_parameters(modified_writer_config)
            self._last_set_writer_config = writer_config

            _audit_logger.info("detector_client.set_config(detector_config)")
            detector_client.set_config(detector_config)
            self._last_set_detector_config = detector_config

        _audit_logger.info("bsread_client.set_parameters(bsread_config)")
        output_file = bsread_config["output_file"]
        modified_bsread_config = copy(bsread_config)
        if output_file != "/dev/null":
            modified_bsread_config["output_file"] = output_file + ".BSREAD.h5"
            _audit_logger.info("Output file for bsread will be %s", modified_bsread_config["output_file"])

        self.bsread_client.set_parameters(modified_bsread_config)
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


        for detector in self.enabled_detectors.keys():
            _audit_logger.info("Detector : %s", detector)
            detector_client, backend_client, writer_client = self.enabled_detectors[detector].return_clients()

            if "backend" in client_status:
                backend_client.set_client_enabled(client_status["backend"])
                _logger.info("(%s) Backend client enable=%s.", detector, backend_client.is_client_enabled())

            if "writer" in client_status:
                writer_client.set_client_enabled(client_status["writer"])
                _logger.info("(%s) Writer client enable=%s.", detector, writer_client.is_client_enabled())

            if "detector" in client_status:
                detector_client.set_client_enabled(client_status["detector"])
                _logger.info("(%s) Detector client enable=%s.", detector, detector_client.is_client_enabled())

        if "bsread" in client_status:
            self.bsread_client.set_client_enabled(client_status["bsread"])
            _logger.info("bsread client enable=%s.", self.bsread_client.is_client_enabled())

    def get_clients_enabled(self):
        status = {}
        status["bsread"] = self.bsread_client.is_client_enabled()
        for detector in self.enabled_detectors.keys():
            status[detector] = {"backend":  self.enabled_detectors[detector].backend_client.is_client_enabled(),
                                "writer":   self.enabled_detectors[detector].writer_client.is_client_enabled(),
                                "detector": self.enabled_detectors[detector].detector_client.is_client_enabled()}
        return status

    def reset(self):

        from time import sleep,time
        
        time0 = time()

        _audit_logger.info("Resetting integration api.")

        threads = []

        status = self.get_acquisition_status()
        time1 = time()
        if status == IntegrationStatus.RUNNING or status == IntegrationStatus.DETECTOR_STOPPED:
            raise ValueError("Cannot reset acquisition in %s state. Please wait for backend to finish." % status)

        self.last_config_successful = False

        _logger.debug("Executing stop command: caput %s %d", self.timing_pv, self.timing_stop_code)
        epics.caput(self.timing_pv, self.timing_stop_code, wait=True, timeout=self.caput_timeout)

        time2 = time()
        for detector in self.enabled_detectors.keys():
            thread = Thread(target=self.enabled_detectors[detector].reset)
            thread.start()
            threads.append(thread)
        time3 = time()

  
        thread = Thread(target=self.bsread_client.reset)
        thread.start()
        threads.append(thread)
 
        time4 = time()

        for thread in threads:
            thread.join()

        time5 = time()

        _logger.debug("----------------total reset timing %f, %f, %f, %f, %f, %f", time5-time0, time1-time0, time2-time1, time3-time2, time4-time3, time5-time4)
        return check_for_target_status(self.get_acquisition_status, IntegrationStatus.INITIALIZED)

    def kill(self):
        _audit_logger.info("Killing acquisition.")

        for detector in self.enabled_detectors.keys():
            self.enabled_detectors[detector].kill()

        _audit_logger.info("bsread_client.kill()")
        self.bsread_client.kill()

        return self.reset()

    def get_server_info(self):
        clients = {}
        for detector in self.enabled_detectors.keys():
            detector_client, backend_client, writer_client = self.enabled_detectors[detector].return_clients()
            clients[detector] = {"backend_url": backend_client.backend_url,
                                 "writer_url":  writer_client.url,
                                 "bsread_url":  bsread_client._api_address.format(url="")}  

        return {
            "clients": copy(clients),
            "clients_enabled": self.get_clients_enabled(),
            "validator": "NOT IMPLEMENTED",
            "last_config_successful": copy(self.last_config_successful)
        }

    def get_metrics(self):
        status = {}
        for detector in self.enabled_detectors.keys():
            detector_client, backend_client, writer_client = self.enabled_detectors[detector].return_clients()
            status[detector] = {"writer":   writer_client.get_statistics(),
                                "backend":  backend_client.get_metrics(),
                                "detector": {}}
        status["bsread"] = {"bsread": self.bsread_client.get_statistics()}

        # Always return a copy - we do not want this to be updated.
        return copy(status)

    def backend_client_get_status(self):
        status = {}
        for detector in self.enabled_detectors.keys():
            status[detector] = self.enabled_detectors[detector].backend_client.get_status()
        _logger.info("backend_client_get_status, status : %s", status)
        return copy(status)

    def backend_client_action(self, action):
        status = {}
        for detector in self.enabled_detectors.keys():
            status[detector] =  self.enabled_detectors[detector].backend_client.__getattribute__(action)()
        _logger.info("backend_client_action, action %s, status : %s", action, status)
        return copy(status)

    def backend_client_get_config(self):
        status = {}
        for detector in self.enabled_detectors.keys():
            status[detector] =  self.enabled_detectors[detector].backend_client._last_set_backend_config
        _logger.info("backend_client_get_config: %s", status)
        return copy(status)

    def backend_client_set_config(self, new_config):
        for detector in self.enabled_detectors.keys():
            self.enabled_detectors[detector].backend_client.set_config(new_config)

    def detector_client_set_value(self, parameter_name, parameter_value, no_verification=True):
        status = {}
        for detector in self.enabled_detectors.keys():
            self.enabled_detectors[detector].detector_client.set_value(parameter_name, parameter_value, no_verification=True)
        _logger.info("detector_client_set_value %s, %s , status %s", parameter_name, parameter_value, status)
        return copy(status)

    def detector_client_get_value(self, name):
        status = {}
        for detector in self.enabled_detectors.keys():
            self.enabled_detectors[detector].detector_client.get_value(name)
        _logger.info("detector_client_get_value %s , status %s", name, status) 
        return copy(status)

