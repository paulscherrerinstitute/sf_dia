[![Build Status](https://travis-ci.org/paulscherrerinstitute/sf_dia.svg?branch=master)](https://travis-ci.org/paulscherrerinstitute/sf_dia)

# SwissFEL Jungfrau detector integration

The following README is useful for controlling the Jungfrau deployment at SF.

The detector integration is made up from the following components:

- Detector integration API (running on sf-daq-1)
    - https://github.com/datastreaming/detector_integration_api
- Detector client (running on sf-daq-1)
    - https://github.com/slsdetectorgroup/slsDetectorPackage
- Backend server (running on sf-daq-1)
    - https://git.psi.ch/HPDI/dafl-eiger
- Writer process (running on sf-daq-1)
    - https://github.com/paulscherrerinstitute/sf_cpp_h5_writer
    
# Table of content
1. [Quick introduction](#quick)
    1. [Python client](#quick_python)
    2. [Rest API](#quick_rest)
2. [State machine](#state_machine)
3. [DIA configuration parameters](#dia_configuration_parameters)
    1. [Detector configuration](#dia_configuration_parameters_detector)
    2. [Backend configuration](#dia_configuration_parameters_backend)
    3. [Writer configuration](#dia_configuration_parameters_writer)
4. [sf-daq-1 (DIA, backend, writer, bsread server)](#deployment_info_daq_1)

<a id="quick"></a>
## Quick introduction

**DIA Address 1 (Bernina):** http://sf-daq-1:10000 

**DIA Address 2 (Alvra):** http://sf-daq-2:10000 

All the examples in this document will be given using **DIA Address 1 (Bernina)**.

To get a feeling on how to use the DIA, you can use the following example to start and write a test file.

You can control the DIA via the Python client or over the REST api directly.

**More documentation about the DIA can be found on its repository** (referenced above).

**Note**: The writer needs additional parameters to write the SF file format. You probably do not care about this, so you 
can use the DEBUG_FORMAT_PARAMETERS parameters for now.

<a id="quick_python"></a>
### Python client

To use the Python client you need to source our central Python:
```bash
source /opt/gfa/python
```
or you can install it using conda:
```bash
conda install -c paulscherrerinstitute detector_integration_api
```

```python
# Just some mock value for the file format.
DEBUG_FORMAT_PARAMETERS = {
    "general/created": "today",
    "general/user": "p16582",
    "general/process": "dia",
    "general/instrument": "jungfrau"
}

# Import the client.
from detector_integration_api import DetectorIntegrationClient

# Connect to the Eiger 9M DIA.
client = DetectorIntegrationClient("http://sf-daq-1:10000")

# Make sure the status of the DIA is initialized.
client.reset()

# Write 1000 frames, as user id 11057 (gac-x12saop), to file "/sf/bernina/data/raw/p16582/test_dia.h5".
writer_config = {"n_frames": 1000, "user_id": 16582, "output_file": "/sf/bernina/data/raw/p16582/test_dia.h5"}

# Expect 1000, 16 bit frames.
backend_config = {"bit_depth": 16, "n_frames": 1000}

# Acquire 1000, 16 bit images.
detector_config = {"dr": 16, "frames": 1000, "exptime": 0.0001}

bsread_config = {"output_file": "/sf/bernina/data/raw/p16582/test_bsread.h5", "user_id": 16582}

# Add format parameters to writer. In this case, we use the debugging one.
writer_config.update(DEBUG_FORMAT_PARAMETERS)

configuration = {"writer": writer_config,
                 "backend": backend_config,
                 "detector": detector_config,
                 "bsread": bsread_config}

# Set the configs.
client.set_config(configuration)

# Start the acquisition.
client.start()

# Get the current acquisition status (it should be "IntegrationStatus.RUNNING")
client.get_status()

# Block until the acquisition has finished (this is optional).
client.wait_for_status("IntegrationStatus.FINISHED")

```

<a id="quick_rest"></a>
### Rest API

The direct calls to the REST Api will be shown with cURL. 

Responses from the server are always JSONs. The "state" attribute in the JSON response is:

- **"ok"**: The server processed your request successfully
    - Response example: {"state": "ok", "status": "IntegrationStatus.INITIALIZED"}
- **"error"**: An error happened on the server. The field **"status"** will tell you what is the problem.
    - Response example: {"state": "error", "status": "Specify config JSON with 3 root elements..."}

**Note**: Most of the writer parameters in the **config** calls are just for the file format. Only the first 3 are 
important right now:

- n_frames (10 in this example)
- output_file (/sf/bernina/data/raw/p16582/dia_test.h5 in this example)
- user_id (16582: p16582 in this example)

**Tip**: You can get a user id by running:
```bash
# Get the id for user p16582
id -u p16582
```

**Note 2** Most of the bsread writer parameters in the config calls are set in a list and are static. Only the first 2 
are important right now:

- output_file (/sf/bernina/data/raw/p16582/bsread_test.h5 in this example)
- user_id (16582: p16582 in this example)

```bash
# Make sure the status of the DIA is initialized.
curl -X POST http://sf-daq-:10000/api/v1/reset

# Write 1000 frames, as user id 11057 (gac-x12saop), to file "/sls/X12SA/Data10/gac-x12saop/tmp/dia_test.h5".
curl -X PUT http://sf-daq-1:10000/api/v1/config -H "Content-Type: application/json" -d '
{"backend": {"bit_depth": 16, "n_frames": 10},
 "detector": {"dr": 16, "frames": 10, "exptime": 0.001},
 "writer": {
  "n_frames": 10,
  "output_file": "/sf/bernina/data/raw/p16582/test_dia.h5",
  "user_id": 11057,
  
  "general/created": "today",
  "general/user": "p11057",
  "general/process": "dia",
  "general/instrument": "jungfrau"
 },
 "bsread": {
  "output_file": "/sf/bernina/data/raw/p16582/test_bsread.h5", 
  "user_id": 16582
 }
}'

# Start the acquisition.
curl -X POST http://sf-daq-1:10000/api/v1/start

# Get integration status.
curl -X GET http://sf-daq-1:10000/api/v1/status

# Stop the acquisition. This should be called only in case of emergency:
#   by default it should stop then the selected number of images is collected.
curl -X POST http://sf-daq-1:10000/api/v1/stop
```

<a id="state_machine"></a>
## State machine

The table below describes the possible states of the integration and the methods that cause a transition 
(this are also the methods that are allowed for a defined state).

Methods that do not modify the state machine are not described in this table, as they can be executed in every state.

| State | State description | Transition method | Next state |
|-------|-------------------|-------------------|------------|
| IntegrationStatus.INITIALIZED | Integration ready for configuration. |||
| | | set_config | IntegrationStatus.CONFIGURED |
| | | set_last_config | IntegrationStatus.CONFIGURED |
| | | update_config | IntegrationStatus.CONFIGURED |
| | | stop | IntegrationStatus.INITIALIZED |
| | | reset | IntegrationStatus.INITIALIZED |
| IntegrationStatus.CONFIGURED | Acquisition configured. |||
| | | start | IntegrationStatus.RUNNING |
| | | set_config | IntegrationStatus.CONFIGURED |
| | | set_last_config | IntegrationStatus.CONFIGURED |
| | | update_config | IntegrationStatus.CONFIGURED |
| | | stop | IntegrationStatus.INITIALIZED |
| | | reset | IntegrationStatus.INITIALIZED |
| IntegrationStatus.RUNNING | Acquisition running. |||
| | | stop | IntegrationStatus.INITIALIZED |
| | | reset | IntegrationStatus.INITIALIZED |
| IntegrationStatus.DETECTOR_STOPPED | Waiting for backend and writer to finish. |||
| | | stop | IntegrationStatus.INITIALIZED |
| | | reset | IntegrationStatus.INITIALIZED |
| IntegrationStatus.BSREAD_STILL_RUNNING | Waiting for bsread writer to finish. |||
| | | stop | IntegrationStatus.INITIALIZED |
| | | reset | IntegrationStatus.INITIALIZED |
| IntegrationStatus.FINISHED | Acquisition completed. |||
| | | reset | IntegrationStatus.INITIALIZED |
| IntegrationStatus.ERROR | Something went wrong. |||
| | | stop | IntegrationStatus.INITIALIZED |
| | | reset | IntegrationStatus.INITIALIZED |

A short summary would be:

- You always need to configure the integration before starting the acquisition.
- You cannot change the configuration while the acquisition is running or there is an error.
- The stop method can be called in every state, but it stop the acquisition only if it is running.
- Whatever happens, you have the reset method that returns you in the initial state.
- When the detector stops sending data, the status is DETECTOR_STOPPED. Call STOP to close the backend and stop the 
writing.
- When there is only the bsread writer still active, the status is BSREAD_STILL_RUNNING.
- When the detector stops sending data, the backend, writer, and bsread writer have completed, 
the status is FINISHED.

<a id="dia_configuration_parameters"></a>
## DIA configuration parameters

The following are the parameters in the DIA.

<a id="dia_configuration_parameters_detector"></a>
### Detector configuration
The mandatory attributes for the detector configuration are:

- *"frames"*: Number of frames to acquire.
- *"dr"*: Dynamic range - number of bits (16, 32 etc.)
- *"exptime"* - Exposure time.

In addition, any attribute that the detector supports can be passed here. Please refer to the detector manual for a 
complete list and explanation of the attributes.

An example of a valid detector config:
```json
{
  "frames": 1000,
  "dr": 32,
  "exptime": 0.0001
}
```

<a id="dia_configuration_parameters_backend"></a>
### Backend configuration
Available and at the same time mandatory backend attributes:

- *"bit_depth"*: Dynamic range - number of bits (16, 32 etc.)
- *"n_frames"*: Number of frames per acquisition.

**Warning**: Please note that this 2 attributes must match the information you provided to the detector:

- (backend) bit_depth == (detector) dr
- (backend) n_frames == (detector) frames

If this is not the case, the configuration will fail.

An example of a valid detector config:
```json
{
  "bit_depth": 16,
  "n_frames": 1000
}
```

<a id="dia_configuration_parameters_writer"></a>
### Writer configuration
Due to the data format used for the SF acquisition, the writer configuration has additional properties. 
It is divided into 2 parts:

- Writer related config (config used by the writer itself to write the data to disk)
- SF file format config (config used to write the file in the SF format)

An example of a valid writer config would be:
```json
{
    "output_file": "/tmp/dia_test.h5",
    "n_frames": 1000, 
    "user_id": 0, 
    

    "general/created": "today",
    "general/user": "p11057",
    "general/process": "dia",
    "general/instrument": "jungfrau"
}
```

**Warning**: Please note that this attribute must match the information you provided to the detector:

- (writer) n_frames == (detector) frames

If this is not the case, the configuration will fail.

#### Writer related config
To configure the writer, you must specify:

- *"output\_file"*: Location where the file will be written.
- *"n_frames"*: Number of frames to acquire.
- *"user_id"*: Under which user to run the writer.

In addition to this properties, a valid config must also have the parameters needed for the SF file format.

#### SF file format config

The following fields are required to write a valid SF formatted file. 
On the right side is the path inside the HDF5 file where the value will be stored.

- *"general/created"* : "/general/created",
- *"general/user"*: "/general/user",
- *"general/process*": "/general/process",
- *"general/instrument*": "/general/instrument"

### Bsread configuration
Mandatory attributes for the bsread configuration are:

- *"output_file"*: Location where the file will be written.
- *"user_id"*: Under which user to run the writer.
- *"general/created"* : SF file format config
- *"general/user"*: SF file format config
- *"general/process*": SF file format config
- *"general/instrument*": SF file format config

An example of a valid bsread config would be:
```json
{
    "output_file": "/tmp/dia_test.h5",
    "user_id": 0,
    
    "general/created": "today",
    "general/user": "p11057",
    "general/process": "dia",
    "general/instrument": "jungfrau"
}
```

#### SF file format config

The following fields are required to write a valid SF formatted file. 
On the right side is the path inside the HDF5 file where the value will be stored.

- *"general/created"* : "/general/created",
- *"general/user"*: "/general/user",
- *"general/process*": "/general/process",
- *"general/instrument*": "/general/instrument"

<a id="deployment_info"></a>
## Deployment information

In this section we will describe the current deployment, server by server.

There are 2 servers:

- sf-daq-1: Bernina deployment.
- sf-daq-2: Alvra deployment.

This 2 deployments are identical. In this document we will describe only sf-daq-1.

<a id="deployment_info_daq_1"></a>
## sf-daq-1 (DIA, backend, writer, bsread writer)
We are running all the services on sf-daq-1. Listening addresses:

- Detector integration API: **http://sf-daq-1:10000**
- bsread writer: **http://sf-daq-1:8083**
- Backend: **http://sf-daq-1:8080**

All services are run using **systemd** (/etc/systemd/system/):

- detector_backend.service
- dia.service
- bsread.service

The services invokes the startup file **/home/dbe/start_*.sh**.

The service can be controlled with the following commands (using sudo or root):
- **systemctl start dia.service** (start the backend)
- **systemctl stop dia.service** (stop the backend)
- **journalctl -u dia.service -f** (check the dia logs)

### Writer
The writer is spawn on request from the DIA. To do that, DIA uses the startup file **/home/dbe/start_writer.sh**.

Each time the writer is spawn, a separate log file is generated in **/var/log/h5_zmq_writer/**.

**Note**: You must create this folder (/var/log/h5_zmq_writer/) before running DIA.