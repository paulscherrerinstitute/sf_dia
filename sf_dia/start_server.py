import argparse
import logging

import bottle
from detector_integration_api import config
from detector_integration_api.client.backend_rest_client import BackendClient
from sf_dia.client.sf_cpp_writer_client import SfCppWriterClient
from detector_integration_api.rest_api.rest_server import register_rest_interface

from sf_dia import manager
from sf_dia.client.databuffer_writer_client import DataBufferWriterClient
from detector_integration_api.client.detector_cli_client import DetectorClient

from sf_dia.client.detector_pipeline import DetectorPipeline

_logger = logging.getLogger(__name__)

def start_integration_server(host, port, config_detectors,
                             backend_api_url, backend_stream_url, writer_port,
                             broker_url, disable_bsread,
                             timing_pv, timing_start_code, timing_stop_code,
                             writer_executable, writer_log_folder):
    _logger.info("Starting integration REST API with:"
                 "\nbroker_url: %s\n",
                 broker_url)

    _logger.info("Using writer executable '%s' and writing writer logs to '%s'.", writer_executable, writer_log_folder)


    enabled_detectors = {}

    if config_detectors != None:
        sf_config = __import__(config_detectors)
        available_detectors = sf_config.available_detectors
    else:
        available_detectors = {}
        available_detectors['JF'] =    {'detector_id': 0, 'backend_api_url': backend_api_url, 'backend_stream_url': backend_stream_url, 'writer_port': writer_port, 'n_modules': 1, 'n_bad_modules' : 0}

    for detector in available_detectors.keys():
        backend_api_url    = available_detectors[detector]['backend_api_url']
        backend_stream_url = available_detectors[detector]['backend_stream_url']
        writer_port        = available_detectors[detector]['writer_port']
        detector_id        = available_detectors[detector]['detector_id']
        n_modules          = available_detectors[detector]['n_modules']
        n_bad_modules      = available_detectors[detector]['n_bad_modules']

        _logger.info("Detector __ %s ___:\nDetector ID: %s \nBackend url: %s\nBackend stream: "
                     "%s\nWriter port: %s\nBroker url: %s\nn_modules: %s\nn_bad_modules: %s\n",
                     detector, str(detector_id), backend_api_url, backend_stream_url, str(writer_port),
                     broker_url, str(n_modules), str(n_bad_modules))

        backend_client = BackendClient(backend_api_url)
        writer_client = SfCppWriterClient(stream_url=backend_stream_url,
                                          writer_executable=writer_executable,
                                          writer_port=writer_port,
                                          log_folder=writer_log_folder + "/multiple/" + detector,
                                          broker_url=broker_url,
                                          n_modules=n_modules,
                                          n_bad_modules=n_bad_modules,
                                          detector_name=detector)

        detector_client = DetectorClient(id=detector_id)

        enabled_detectors[detector] = DetectorPipeline(detector_client, backend_client, writer_client)

    bsread_client = DataBufferWriterClient(broker_url=broker_url)

    integration_manager = manager.IntegrationManager(enabled_detectors=enabled_detectors,
                                                     bsread_client=bsread_client, timing_pv=timing_pv, timing_start_code=timing_start_code, timing_stop_code=timing_stop_code)

    _logger.info("Bsread writer disabled at startup: %s", disable_bsread)
    if disable_bsread:
        integration_manager.set_clients_enabled({"bsread": False})

    app = bottle.Bottle()
    register_rest_interface(app=app, integration_manager=integration_manager)

    try:
        bottle.run(app=app, host=host, port=port)
    finally:
        pass


def main():
    parser = argparse.ArgumentParser(description='Rest API for beamline software')
    parser.add_argument('-i', '--interface', default=config.DEFAULT_SERVER_INTERFACE,
                        help="Hostname interface to bind to")
    parser.add_argument('-p', '--port', default=config.DEFAULT_SERVER_PORT, help="Server port")
    parser.add_argument("--log_level", default=config.DEFAULT_LOGGING_LEVEL,
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        help="Log level to use.")

    parser.add_argument("-b", "--backend_url", default="http://localhost:8080",
                        help="Backend REST API url.")
    parser.add_argument("-s", "--backend_stream", default="tcp://localhost:40000",
                        help="Output stream address from the backend.")

    parser.add_argument("-w", "--writer_port", type=int, default=10001,
                        help="Writer REST API port.")
    parser.add_argument("--writer_executable", type=str, default="/home/writer/start_writer.sh",
                        help="Executable to start the writer.")
    parser.add_argument("--writer_log_folder", type=str, default="/var/log/h5_zmq_writer",
                        help="Log directory for writer logs.")

    parser.add_argument("--broker_url", default="http://localhost:10002",
                        help="Address of the bsread broker REST api.")
    parser.add_argument("--disable_bsread", action='store_true',
                        help="Disable the bsread writer at startup.")

    parser.add_argument("--timing_pv", default="SAR-CVME-TIFALL4-EVG0:SoftEvt-EvtCode-SP",
                        help="PV for triggering soft events on the timing.")
    parser.add_argument("--timing_start_code", default=254,
                        help="Timing event code to start the detector.")
    parser.add_argument("--timing_stop_code", default=255,
                        help="Timing event code to stop the detector.")
    parser.add_argument("--config_detectors",default=None,
                        help="Specify config .py file for the available detectors, see documentation for example.")

    arguments = parser.parse_args()

    # Setup the logging level.
    logging.basicConfig(level=arguments.log_level, format='[%(levelname)s] %(message)s')

    start_integration_server(host=arguments.interface,
                             port=arguments.port,
                             config_detectors=arguments.config_detectors,
                             backend_api_url=arguments.backend_url,
                             backend_stream_url=arguments.backend_stream,
                             writer_port=arguments.writer_port,
                             broker_url=arguments.broker_url,
                             disable_bsread=arguments.disable_bsread,
                             timing_pv=arguments.timing_pv,
                             timing_start_code=arguments.timing_start_code,
                             timing_stop_code=arguments.timing_stop_code,
                             writer_executable=arguments.writer_executable,
                             writer_log_folder=arguments.writer_log_folder)


if __name__ == "__main__":
    main()
