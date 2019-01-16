# Alvra configuration:
available_detectors = {}

# 4p5M detector
available_detectors['JF02T09V01'] = {'detector_id': 1, 'backend_api_url': 'http://localhost:8080', 'backend_stream_url': 'tcp://localhost:40000', 
                                     'writer_port': 10010, 'n_modules': 9, 'n_bad_modules' : 1, 'use_taskset' : False }
# 16M detector
#available_detectors['JF06T32V01'] = {'detector_id': 2, 'backend_api_url': 'http://localhost:8080', 'backend_stream_url': 'tcp://localhost:40000', 
#                                     'writer_port': 10010, 'n_modules': 32, 'n_bad_modules' : 1, 'use_taskset' : False }

