from logging import getLogger

import epics
from detector_integration_api.client.detector_cli_client import DetectorClient

_logger = getLogger(__name__)

DEFAULT_CAPUT_TIMEOUT = 3


class DetectorTimingClient(DetectorClient):

    def __init__(self, timing_pv, start_event_code, stop_event_code, caput_timeout=None):
        self.timing_pv = timing_pv
        self.start_event_code = start_event_code
        self.stop_event_code = stop_event_code

        if caput_timeout is None:
            self.caput_timeout = DEFAULT_CAPUT_TIMEOUT
        else:
            self.caput_timeout = caput_timeout

        _logger.info("Starting detector client with timing_pv '%s', start code %d, stop code %d.",
                     self.timing_pv, self.start_event_code, self.stop_event_code)

    def start(self):

        super(DetectorTimingClient, self).start()

        _logger.debug("Executing start command: caput %s %d", self.timing_pv, self.start_event_code)

        epics.caput(self.timing_pv, self.start_event_code, wait=True, timeout=self.caput_timeout)

    def stop(self):

        super(DetectorTimingClient, self).stop()

        _logger.debug("Executing stop command: caput %s %d", self.timing_pv, self.stop_event_code)

        epics.caput(self.timing_pv, self.stop_event_code, wait=True, timeout=self.caput_timeout)
