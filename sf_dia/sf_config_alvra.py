# Alvra configuration:
available_detectors = {}

# 4p5M detector
available_detectors['JF02T09V01'] = {'detector_id': 1, 'backend_api_url': 'http://localhost:8082', 'backend_stream_url': 'tcp://localhost:40002', 
                                     'writer_port': 10012, 'n_modules': 9, 'n_bad_modules' : 1}
# 16M detector
#available_detectors['JF06T32V01'] = {'detector_id': 2, 'backend_api_url': 'http://localhost:8086', 'backend_stream_url': 'tcp://localhost:40006', 
#                                     'writer_port': 10016, 'n_modules': 32, 'n_bad_modules' : 1}
# 16M detector 8 modules around central beampipe
#available_detectors['JF06T08V01'] = {'detector_id': 2, 'backend_api_url': 'http://localhost:8086', 'backend_stream_url': 'tcp://localhost:40006', 
#                                     'writer_port': 10016, 'n_modules': 8, 'n_bad_modules' : 0}


