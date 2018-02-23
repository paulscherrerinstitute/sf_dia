import json

import bottle
import os
from detector_integration_api.rest_api.rest_server import register_rest_interface
from detector_integration_api.tests.utils import MockBackendClient, MockDetectorClient, MockCppWriterClient, \
    MockMflowNodesClient


def get_test_bsread_integration_manager(manager_module):
    backend_client = MockBackendClient()
    detector_client = MockDetectorClient()
    writer_client = MockCppWriterClient()
    bsread_client = MockMflowNodesClient()

    manager = manager_module.IntegrationManager(backend_client, writer_client, detector_client, bsread_client)

    return manager


def start_test_bsread_integration_server(host, port, manager_module):
    backend_client = MockBackendClient()
    writer_client = MockCppWriterClient()
    detector_client = MockDetectorClient()
    bsread_client = MockMflowNodesClient()

    integration_manager = manager_module.IntegrationManager(writer_client=writer_client,
                                                            backend_client=backend_client,
                                                            detector_client=detector_client,
                                                            bsread_client=bsread_client)
    app = bottle.Bottle()
    register_rest_interface(app=app, integration_manager=integration_manager)

    bottle.run(app=app, host=host, port=port)


def get_valid_config():

    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sf_config.json")
    with open(filename) as input_file:
        configuration = json.load(input_file)

    return configuration
