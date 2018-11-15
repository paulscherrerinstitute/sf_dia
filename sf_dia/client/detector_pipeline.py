from logging import getLogger

from detector_integration_api.client.backend_rest_client import BackendClient
from detector_integration_api.client.cpp_writer_client   import CppWriterClient
from detector_integration_api.client.detector_cli_client import DetectorClient

_logger = getLogger(__name__)

from time import time

class DetectorPipeline(object):

    def __init__(self, detector_client, backend_client, writer_client ):
        self.detector_client = detector_client
        self.backend_client  = backend_client
        self.writer_client   = writer_client

    def start(self):

        self.backend_client.open()
        self.writer_client.start()
        self.detector_client.start()

    def stop(self):

        self.detector_client.stop()
        self.backend_client.close()
        self.writer_client.stop()

    def reset(self):

        time1 = time()
        self.detector_client.stop()
        time2 = time()
        self.backend_client.reset()
        time3 = time()
        self.writer_client.reset()
        time4 = time()
        _logger.info("detector %f , backend %f , writer %f", time2-time1, time3-time2, time4-time3)

    def kill(self):

        self.detector_client.stop()
        self.backend_client.reset()
        self.writer_client.kill()

    def return_clients(self):
  
        return self.detector_client, self.backend_client, self.writer_client

