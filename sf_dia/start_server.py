import argparse
import logging

import bottle
from detector_integration_api import config
from detector_integration_api.client.backend_rest_client import BackendClient
from detector_integration_api.client.cpp_writer_client import CppWriterClient
from detector_integration_api.rest_api.rest_server import register_rest_interface

from sf_dia import manager
from sf_dia.client.bsread_writer_client import BsreadWriterClient
from sf_dia.client.detector_timing_cli_client import DetectorTimingClient

_logger = logging.getLogger(__name__)


def start_integration_server(host, port,
                             backend_api_url, backend_stream_url, writer_port,
                             bsread_stream, bsread_port, bsread_executable, disable_bsread,
                             timing_pv, timing_start_code, timing_stop_code,
                             writer_executable, writer_log_folder):
    _logger.info("Starting integration REST API with:\nBackend url: %s\nBackend stream: "
                 "%s\nWriter port: %s\nbsread_stream: %s\n",
                 backend_api_url, backend_stream_url, str(writer_port), bsread_stream)

    _logger.info("Using writer executable '%s' and writing writer logs to '%s'.", writer_executable, writer_log_folder)

    backend_client = BackendClient(backend_api_url)
    writer_client = CppWriterClient(stream_url=backend_stream_url,
                                    writer_executable=writer_executable,
                                    writer_port=writer_port,
                                    log_folder=writer_log_folder)

    bsread_client = BsreadWriterClient(stream_url=bsread_stream,
                                       writer_executable=bsread_executable,
                                       writer_port=bsread_port,
                                       log_folder=writer_log_folder)

    detector_client = DetectorTimingClient(timing_pv, timing_start_code, timing_stop_code)

    integration_manager = manager.IntegrationManager(writer_client=writer_client,
                                                     backend_client=backend_client,
                                                     detector_client=detector_client,
                                                     bsread_client=bsread_client)

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

    parser.add_argument("--bsread_stream", default="tcp://127.0.0.1:8082",
                        help="Address of the bsread buffer stream.")
    parser.add_argument("--bsread_executable", default="/home/writer/start_bsread_writer.sh",
                        help="Executable to start the bsread writer.")
    parser.add_argument("--bsread_port", default=10002,
                        help="Bsread REST API port.")
    parser.add_argument("--disable_bsread", action='store_true',
                        help="Disable the bsread writer at startup.")

    parser.add_argument("--timing_pv", default="SAR-CVME-TIFALL4-EVG0:SoftEvt-EvtCode-SP",
                        help="PV for triggering soft events on the timing.")
    parser.add_argument("--timing_start_code", default=254,
                        help="Timing event code to start the detector.")
    parser.add_argument("--timing_stop_code", default=255,
                        help="Timing event code to stop the detector.")

    arguments = parser.parse_args()

    # Setup the logging level.
    logging.basicConfig(level=arguments.log_level, format='[%(levelname)s] %(message)s')

    start_integration_server(host=arguments.interface,
                             port=arguments.port,
                             backend_api_url=arguments.backend_url,
                             backend_stream_url=arguments.backend_stream,
                             writer_port=arguments.writer_port,
                             bsread_stream=arguments.bsread_stream,
                             bsread_port=arguments.bsread_port,
                             bsread_executable=arguments.bsread_executable,
                             disable_bsread=arguments.disable_bsread,
                             timing_pv=arguments.timing_pv,
                             timing_start_code=arguments.timing_start_code,
                             timing_stop_code=arguments.timing_stop_code,
                             writer_executable=arguments.writer_executable,
                             writer_log_folder=arguments.writer_log_folder)


if __name__ == "__main__":
    main()
