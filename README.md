# Hevelius-Runner

Hevelius-Runner is an automation tool designed to execute planned astronomical observations in an observatory environment. It integrates with NINA (Nighttime Imaging 'N' Astronomy) software to automate the execution of observation sequences.

It is expected to be used with hevelius-backend, a central server that stores the observation tasks and provides the API for the runner to retrieve them.

It is a very early work in progress.

## Features

- Retrieves observation tasks from a REST API
- Generates NINA-compatible sequence files from observation tasks
- Executes observations using NINA automation
- Monitors for new FITS files and updates task status
- Supports custom scripts for various observation stages:
  - Startup
  - Night start/end
  - Post-task processing
- Configurable for different observatories

## Requirements

- Python 3.7+
- NINA (Nighttime Imaging 'N' Astronomy) software
- Windows operating system

## Installation

1. Clone the repository:

bash
git clone https://github.com/tomaszmrugalski/hevelius-runner.git
cd hevelius-runner

2. Create and activate virtual environment:

```
python -m venv venv
venv\Scripts\Activate
```

3. Install required packages:

bash
pip install -r requirements.txt

## Configuration

1. Copy `config.ini.example` to `config.ini`
2. Update the configuration with your settings:
   - Database credentials
   - API endpoints
   - Directory paths
   - NINA executable location
   - Custom script paths

## Usage

Run the application:
```bash
python src/main.py
```

The application will:
1. Load configuration
2. Execute startup scripts
3. Monitor for nighttime
4. Retrieve and execute observation tasks
5. Update task status upon completion

## Directory Structure

```
hevelius-runner/
├── config/
│   ├── config.ini
│   └── templates/
│       └── sequence_template.json
├── src/
│   ├── main.py
│   ├── config_manager.py
│   ├── api_client.py
│   ├── task_manager.py
│   ├── file_monitor.py
│   ├── script_executor.py
│   └── nina_controller.py
├── scripts/
│   ├── startup_script.py
│   ├── night_start.py
│   ├── night_end.py
│   └── post_task.py
└── requirements.txt
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your chosen license here]

## Acknowledgments

- NINA (Nighttime Imaging 'N' Astronomy) software
- [Add other acknowledgments as needed]

