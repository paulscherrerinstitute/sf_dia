import os.path
import requests
import json

from subprocess import Popen
from datetime import datetime
from logging import getLogger
from time import sleep

from detector_integration_api import config

_logger = getLogger(__name__)


class BsreadWriterClient(object):
    PROCESS_STARTUP_PARAMETERS = ("output_file", "user_id")

    def __init__(self, stream_url, writer_executable, writer_port, log_folder=None):

        self.stream_url = stream_url
        self.writer_executable = writer_executable
        self.writer_port = writer_port

        self.log_folder = None
        if log_folder is not None:

            if not os.path.exists(log_folder):
                raise ValueError("Provided Bsread log folder '%s' does not exist." % log_folder)

            self.log_folder = log_folder

        self.writer_url = config.WRITER_PROCESS_URL_FORMAT % self.writer_port

        self.writer_parameters = None

        self.process = None
        self.process_log_file = None

    @staticmethod
    def _sanitize_parameters(parameters):

        return {key: parameters[key] for key in parameters if key not in BsreadWriterClient.PROCESS_STARTUP_PARAMETERS}

    def start(self):

        if self.is_running():
            raise RuntimeError("Bsread process already running. Cannot start new one until old one is still alive.")

        if not self.writer_parameters:
            raise ValueError("Bsread parameters not set.")

        timestamp = datetime.now().strftime(config.WRITER_PROCESS_LOG_FILENAME_TIME_FORMAT)

        # If the log folder is not specified, redirect the logs to /dev/null.
        if self.log_folder is not None:
            log_filename = os.path.join(self.log_folder, "bsread_writer-%s.log" % timestamp)
        else:
            log_filename = os.devnull

        _logger.debug("Creating log file '%s'.", log_filename)
        self.process_log_file = open(log_filename, 'w')
        self.process_log_file.write("Parameters:\n%s\n" % json.dumps(self.writer_parameters, indent=4))
        self.process_log_file.flush()

        writer_command_format = "sh " + self.writer_executable + " %s %s %s %s"
        writer_command = writer_command_format % (self.stream_url,
                                                  self.writer_parameters["output_file"],
                                                  self.writer_parameters.get("user_id", -1),
                                                  self.writer_port)

        _logger.debug("Starting Bsread with command '%s'.", writer_command)
        self.process = Popen(writer_command, shell=True, stdout=self.process_log_file, stderr=self.process_log_file)

        sleep(config.WRITER_PROCESS_STARTUP_WAIT_TIME)

        process_parameters = self._sanitize_parameters(self.writer_parameters)
        _logger.debug("Setting process parameters: %s", process_parameters)

        for _ in range(config.WRITER_PROCESS_RETRY_N):

            try:
                bsread_url = self.writer_url + "/parameters"

                _logger.info("Sending to url '%s' parameters: %s", bsread_url, process_parameters)

                response = requests.post(bsread_url, json=process_parameters,
                                         timeout=config.WRITER_PROCESS_COMMUNICATION_TIMEOUT).json()

                if response["state"] != "ok":
                    continue

                break

            except Exception as e:
                _logger.debug("Exception while trying to set parameters on bsread writer", e)
                sleep(config.WRITER_PROCESS_RETRY_DELAY)
        else:
            _logger.warning("Terminating Bsread process because it did not respond in the specified time.")

            try:
                requests.get(self.writer_url + "/kill", timeout=config.WRITER_PROCESS_COMMUNICATION_TIMEOUT)
            except:
                pass

            self.process.wait(timeout=config.WRITER_PROCESS_TERMINATE_TIMEOUT)

            self.process.terminate()

            raise RuntimeError("Count not start bsread process in time. Check bsread logs.")

    def stop(self):

        _logger.debug("Stopping Bsread.")

        if self.is_running():
            requests.get(self.writer_url + "/stop", timeout=config.WRITER_PROCESS_COMMUNICATION_TIMEOUT)

            try:
                self.process.wait(timeout=config.WRITER_PROCESS_TERMINATE_TIMEOUT)

            except:
                _logger.warning("Terminating Bsread process because it did not stop in the specified time.")

                requests.get(self.writer_url + "/kill", timeout=config.WRITER_PROCESS_COMMUNICATION_TIMEOUT)

                self.process.wait(timeout=config.WRITER_PROCESS_TERMINATE_TIMEOUT)

                self.process.terminate()

                raise RuntimeError("Bsread process was terminated because it did not stop in time. "
                                   "Acquisition file maybe corrupted.")

        else:
            _logger.debug("Bsread process is not running.")

        if self.process_log_file:
            self.process_log_file.flush()
            self.process_log_file.close()

        self.process = None
        self.process_log_file = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def get_status(self):

        # Writer is running. Get status from the process.
        if self.is_running():
            status = requests.get(self.writer_url + "/status",
                                  timeout=config.WRITER_PROCESS_COMMUNICATION_TIMEOUT).json()

            return status["status"]

        return "stopped"

    def set_parameters(self, writer_parameters):
        self.writer_parameters = writer_parameters

    def reset(self):
        _logger.debug("Resetting Bsread.")

        self.stop()

        self.writer_parameters = None

    def get_statistics(self):

        if not self.is_running():
            return {}

        response = requests.get(self.writer_url + "/statistics",
                                timeout=config.WRITER_PROCESS_COMMUNICATION_TIMEOUT).json()

        return response["statistics"]
