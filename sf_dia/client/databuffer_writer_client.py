import requests
from logging import getLogger
from time import sleep

from detector_integration_api import config

_logger = getLogger(__name__)


class DataBufferWriterClient(object):
    PROCESS_NAME = "databuffer_writer"

    def __init__(self, broker_url):
        self.broker_url = broker_url

    def _send_request_to_process(self, requests_method, url, request_json=None, return_response=False):
        for _ in range(config.EXTERNAL_PROCESS_RETRY_N):

            try:
                response = requests_method(url=url, json=request_json,
                                           timeout=config.EXTERNAL_PROCESS_COMMUNICATION_TIMEOUT).json()

                if response["state"] != "ok":
                    _logger.debug("Error while trying to communicate with the %s process. Retrying." %
                                  self.PROCESS_NAME, response)

                    sleep(config.EXTERNAL_PROCESS_RETRY_DELAY)
                    continue

                if return_response:
                    return response
                else:
                    return True

            except:
                sleep(config.EXTERNAL_PROCESS_RETRY_DELAY)

        return False

    def start(self):
        _logger.info("Start of databuffer writer. Noop - already running.")
        pass

    def _kill(self):
        _logger.warning("Terminating process %s. Data files might be corrupted." % self.PROCESS_NAME)

        self._send_request_to_process(requests.get, self.broker_url + "/kill")

        try:
            self.process.wait(timeout=config.EXTERNAL_PROCESS_TERMINATE_TIMEOUT)
        except:
            self.process.terminate()

    def stop(self):

        _logger.debug("Sending stop command to the process %s." % self.PROCESS_NAME)

        if not self._send_request_to_process(requests.get, self.broker_url + "/stop"):
            raise ValueError("Process %s is running but cannot send stop command." % self.PROCESS_NAME)

    def get_status(self):

        status = self._send_request_to_process(requests.get,
                                               self.broker_url + "/status",
                                               return_response=True)

        if status is False:
            raise ValueError("Cannot get status of process %s ." % self.PROCESS_NAME)

        return status["status"]

    def set_parameters(self, process_parameters):

        _logger.debug("Setting process %s parameters: %s", self.PROCESS_NAME, process_parameters)

        if not self._send_request_to_process(requests.post, self.process_url + "/parameters",
                                             request_json=process_parameters):
            _logger.warning("Terminating %s process because it did not respond in the specified time." %
                            self.PROCESS_NAME)
            self.stop()

            raise RuntimeError("Could not set %s process parameters in time. Check logs." % self.PROCESS_NAME)

    def reset(self):

        _logger.debug("Resetting process %s.", self.PROCESS_NAME)

        self.stop()

    def get_statistics(self):

        statistics = self._send_request_to_process(requests.get,
                                                   self.broker_url + "/statistics",
                                                   return_response=True)

        if statistics is False:
            raise ValueError("Process %s is running but cannot get statistics." % self.PROCESS_NAME)

        return statistics

    def kill(self):
        self._send_request_to_process(requests.get, self.broker_url + "/kill")
