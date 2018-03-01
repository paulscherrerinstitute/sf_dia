from enum import Enum
from logging import getLogger

from detector_integration_api.utils import ClientDisableWrapper

_logger = getLogger(__name__)


class IntegrationStatus(Enum):
    INITIALIZED = "initialized",
    CONFIGURED = "configured",
    RUNNING = "running",
    DETECTOR_STOPPED = "detector_stopped",
    BSREAD_STILL_RUNNING = "bsread_still_running",
    FINISHED = "finished"
    ERROR = "error"


E_ACCOUNT_USER_ID_RANGE = [10000, 29999]


MANDATORY_WRITER_CONFIG_PARAMETERS = ["n_frames", "user_id", "output_file"]
MANDATORY_BACKEND_CONFIG_PARAMETERS = ["bit_depth", "n_frames"]
MANDATORY_DETECTOR_CONFIG_PARAMETERS = ["dr", "exptime", "cycles"]
MANDATORY_BSREAD_CONFIG_PARAMETERS = ["output_file", "user_id"]

FILE_FORMAT_INPUT_PARAMETERS = {
    "general/created": str,
    "general/user": str,
    "general/process": str,
    "general/instrument": str
}


def validate_writer_config(configuration):
    if not configuration:
        raise ValueError("Writer configuration cannot be empty.")

    writer_cfg_params = MANDATORY_WRITER_CONFIG_PARAMETERS + list(FILE_FORMAT_INPUT_PARAMETERS.keys())

    # Check if all mandatory parameters are present.
    if not all(x in configuration for x in writer_cfg_params):
        missing_parameters = [x for x in writer_cfg_params if x not in configuration]
        raise ValueError("Writer configuration missing mandatory parameters: %s" % missing_parameters)

    unexpected_parameters = [x for x in configuration.keys() if x not in writer_cfg_params]
    if unexpected_parameters:
        raise ValueError("Received unexpected parameters for writer: %s" % unexpected_parameters)

    # Check if all format parameters are of correct type.
    wrong_parameter_types = ""
    for parameter_name, parameter_type in FILE_FORMAT_INPUT_PARAMETERS.items():
        if not isinstance(configuration[parameter_name], parameter_type):
            wrong_parameter_types += "\tWriter parameter '%s' expected of type '%s', but received of type '%s'.\n" % \
                                     (parameter_name, parameter_type, type(configuration[parameter_name]))

    if wrong_parameter_types:
        raise ValueError("Received parameters of invalid type:\n%s", wrong_parameter_types)

    user_id = configuration["user_id"]
    if user_id < E_ACCOUNT_USER_ID_RANGE[0] or user_id > E_ACCOUNT_USER_ID_RANGE[1]:
        raise ValueError("Provided user_id %d outside of specified range [%d-%d]." % (user_id,
                                                                                      E_ACCOUNT_USER_ID_RANGE[0],
                                                                                      E_ACCOUNT_USER_ID_RANGE[1]))

    # Check if the filename ends with h5.
    if configuration["output_file"][-3:] != ".h5":
        configuration["output_file"] += ".h5"


def validate_backend_config(configuration):
    if not configuration:
        raise ValueError("Backend configuration cannot be empty.")

    if not all(x in configuration for x in MANDATORY_BACKEND_CONFIG_PARAMETERS):
        missing_parameters = [x for x in MANDATORY_BACKEND_CONFIG_PARAMETERS if x not in configuration]
        raise ValueError("Backend configuration missing mandatory parameters: %s" % missing_parameters)


def validate_detector_config(configuration):
    if not configuration:
        raise ValueError("Detector configuration cannot be empty.")

    if not all(x in configuration for x in MANDATORY_DETECTOR_CONFIG_PARAMETERS):
        missing_parameters = [x for x in MANDATORY_DETECTOR_CONFIG_PARAMETERS if x not in configuration]
        raise ValueError("Detector configuration missing mandatory parameters: %s" % missing_parameters)


def validate_bsread_config(configuration):
    if not configuration:
        raise ValueError("Writer configuration cannot be empty.")

    bsread_cfg_params = MANDATORY_BSREAD_CONFIG_PARAMETERS + list(FILE_FORMAT_INPUT_PARAMETERS.keys())

    # Check if all mandatory parameters are present.
    if not all(x in configuration for x in bsread_cfg_params):
        missing_parameters = [x for x in bsread_cfg_params if x not in configuration]
        raise ValueError("Backend configuration missing mandatory parameters: %s" % missing_parameters)

    unexpected_parameters = [x for x in configuration.keys() if x not in bsread_cfg_params]
    if unexpected_parameters:
        raise ValueError("Received unexpected parameters for writer: %s" % unexpected_parameters)

    # Check if all format parameters are of correct type.
    wrong_parameter_types = ""
    for parameter_name, parameter_type in FILE_FORMAT_INPUT_PARAMETERS.items():
        if not isinstance(configuration[parameter_name], parameter_type):
            wrong_parameter_types += "\tBsread parameter '%s' expected of type '%s', but received of type '%s'.\n" % \
                                     (parameter_name, parameter_type, type(configuration[parameter_name]))

    if wrong_parameter_types:
        raise ValueError("Received parameters of invalid type:\n%s", wrong_parameter_types)

    user_id = configuration["user_id"]
    if user_id < E_ACCOUNT_USER_ID_RANGE[0] or user_id > E_ACCOUNT_USER_ID_RANGE[1]:
        raise ValueError("Provided user_id %d outside of specified range [%d-%d]." % (user_id,
                                                                                      E_ACCOUNT_USER_ID_RANGE[0],
                                                                                      E_ACCOUNT_USER_ID_RANGE[1]))

    # Check if the filename ends with h5.
    if configuration["output_file"][-3:] != ".h5":
        configuration["output_file"] += ".h5"


def validate_configs_dependencies(writer_config, backend_config, detector_config, bsread_config):
    if backend_config["bit_depth"] != detector_config["dr"]:
        raise ValueError("Invalid config. Backend 'bit_depth' set to '%s', but detector 'dr' set to '%s'."
                         " They must be equal."
                         % (backend_config["bit_depth"], detector_config["dr"]))

    if backend_config["n_frames"] != detector_config["cycles"]:
        raise ValueError("Invalid config. Backend 'n_frames' set to '%s', but detector 'cycles' set to '%s'. "
                         "They must be equal." % (backend_config["n_frames"], detector_config["cycles"]))

    if writer_config["n_frames"] != backend_config["cycles"]:
        raise ValueError("Invalid config. Backend 'n_frames' set to '%s', but writer 'n_frames' set to '%s'. "
                         "They must be equal." % (backend_config["n_frames"], writer_config["n_frames"]))


def interpret_status(statuses):

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
    interpreted_status = IntegrationStatus.ERROR

    if cmp(writer, "stopped") and cmp(detector, "idle") and cmp(backend, "INITIALIZED") and cmp(bsread, "stopped"):
        interpreted_status = IntegrationStatus.INITIALIZED

    elif cmp(writer, "stopped") and cmp(detector, "idle") and cmp(backend, "CONFIGURED") and cmp(bsread, "stopped"):
        interpreted_status = IntegrationStatus.CONFIGURED

    elif cmp(writer, ("receiving", "writing")) and cmp(detector, ("running", "waiting")) and \
            cmp(backend, "OPEN") and cmp(bsread, ("writing", "waiting")):
        interpreted_status = IntegrationStatus.RUNNING

    elif cmp(writer, ("receiving", "writing")) and cmp(detector, "idle") and \
            cmp(backend, "OPEN") and cmp(bsread, ("writing", "waiting", "stopped")):
        interpreted_status = IntegrationStatus.DETECTOR_STOPPED

    elif cmp(writer, ("finished", "stopped")) and cmp(detector, "idle") and \
            cmp(backend, "OPEN") and cmp(bsread, ("writing", "waiting")):
        interpreted_status = IntegrationStatus.BSREAD_STILL_RUNNING

    elif cmp(writer, ("finished", "stopped")) and cmp(detector, "idle") and cmp(backend, "OPEN") \
            and cmp(bsread, "stopped"):
        interpreted_status = IntegrationStatus.FINISHED

    _logger.debug("Statuses interpreted as '%s'.", interpreted_status)

    return interpreted_status
