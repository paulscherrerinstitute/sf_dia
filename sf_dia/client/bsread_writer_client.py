from detector_integration_api.client.external_process_client import ExternalProcessClient


class BsreadWriterClient(ExternalProcessClient):
    PROCESS_STARTUP_PARAMETERS = ("output_file", "user_id")
    PROCESS_NAME = "bsread"

    def get_execution_command(self):
        writer_command_format = "sh " + self.process_executable + " %s %s %s %s"
        writer_command = writer_command_format % (self.stream_url,
                                                  self.process_parameters["output_file"],
                                                  self.process_parameters.get("user_id", -1),
                                                  self.process_port)

        return writer_command
