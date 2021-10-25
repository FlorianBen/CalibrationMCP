# ConditioningMCP

This Python script automates the conditioning process of the MCP.
Under the hood, the script do the following:
1. It creates a conditioning process for each MCP
2. Read the conditioning states from a sequence file
3. Connect to the EPICS variables
4. Perform the conditioning
5. Record data during each step

The process can also send mail for each step.
If an error occurs, then the process is cancelled, shuts down the power supply and send an email.

## Prerequisites

The script requires few dependencies:
- Python 3.6+
- EPICS Channel Access library is installed
- pyepics 

## Before using

First, the power supply IOC must be available. Use caget command to check if the PV are accessible.

Then, a sequence file should be created at the root directory. 
The file uses a CSV format each line define a conditioning step. A sequence file is provided in this repository is suitable for double MCP from Photonis.

Finally, check in the program the desired power supply channel on which conditioning will be performed. Modify at convenience. 

## Usage

To use the script, simply run the file app.py with a Python interpreter.
```python
python3 app.py -s sequence_file.csv 0 1
```
Here, the script is called and will use sequence_file.csv passed with the `-s` option. The script will perform the conditioning on the channels `0` and `1`.

A log file is created in the root directory. One can use tail command to monitor the progress:
```
tail -f MPOD_0.log
```

## Output

A directory is created for each. In this directory, the program will create measurement files with CSV format for each step.
