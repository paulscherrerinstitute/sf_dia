from detector_integration_api.client.cpp_writer_client import CppWriterClient


class SfCppWriterClient(CppWriterClient):
    def __init__(self, stream_url, writer_executable, writer_port, log_folder, broker_url, n_modules):

        super(SfCppWriterClient, self).__init__(stream_url, writer_executable, writer_port, log_folder)

        self.broker_url = broker_url
        self.n_modules = n_modules

    def get_execution_command(self):
        writer_command_format = "sh " + self.process_executable + " %s %s %s %s %s %s %s"
        writer_command = writer_command_format % (self.stream_url,
                                                  self.process_parameters["output_file"],
                                                  self.process_parameters.get("n_frames", 0),
                                                  self.process_port,
                                                  self.process_parameters.get("user_id", -1),
                                                  self.broker_url,
                                                  self.n_modules)

        return writer_command
