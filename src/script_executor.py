
# This ScriptExecutor implementation includes:
# 1. Support for both Python and shell scripts
# 2. Thread-safe execution of scripts
# 3. Queue-based handling of script execution requests
# 4. Proper argument passing to scripts
# 5. Comprehensive logging and error handling
# Key features:
#   - Scripts run in separate threads to avoid blocking the main application
#   - Queue-based system to handle multiple execution requests
#   - Support for different script types (startup, night start/end, post-task)
#   - Proper cleanup and resource management
#   - Flexible argument passing to scripts

import logging
import subprocess
import threading
import sys
from pathlib import Path
from typing import Dict, Optional, List
from queue import Queue
import importlib.util

class ScriptExecutor:
    def __init__(self, config: Dict[str, str]):
        """
        Initialize the script executor.
        
        Args:
            config: Dictionary containing script paths
        """
        self.scripts_config = config
        self.logger = logging.getLogger(__name__)
        self.running_threads: Dict[str, threading.Thread] = {}
        self.script_queues: Dict[str, Queue] = {}

    def execute_script(self, script_type: str, args: Optional[Dict] = None) -> bool:
        """
        Execute a script of specified type in a separate thread.
        
        Args:
            script_type: Type of script to execute (startup, night_start, night_end, post_task)
            args: Optional arguments to pass to the script
            
        Returns:
            bool: True if script execution was initiated successfully
        """
        script_path = self.scripts_config.get(f'{script_type}_script')
        if not script_path or not Path(script_path).exists():
            self.logger.warning(f"Script not configured or not found for type: {script_type}")
            return False

        try:
            # Create a queue for this script type if it doesn't exist
            if script_type not in self.script_queues:
                self.script_queues[script_type] = Queue()

            # Create and start the thread if it's not already running
            if script_type not in self.running_threads or not self.running_threads[script_type].is_alive():
                thread = threading.Thread(
                    target=self._script_worker,
                    args=(script_type, script_path),
                    name=f"ScriptExecutor-{script_type}",
                    daemon=True
                )
                self.running_threads[script_type] = thread
                thread.start()

            # Put the arguments in the queue
            self.script_queues[script_type].put(args or {})
            return True

        except Exception as e:
            self.logger.error(f"Failed to execute {script_type} script: {str(e)}")
            return False

    def _script_worker(self, script_type: str, script_path: str):
        """
        Worker function that processes script execution requests.
        
        Args:
            script_type: Type of script being executed
            script_path: Path to the script
        """
        queue = self.script_queues[script_type]
        
        while True:
            try:
                args = queue.get()
                self._execute_single_script(script_path, args)
                queue.task_done()
            except Exception as e:
                self.logger.error(f"Error in script worker for {script_type}: {str(e)}")

    def _execute_single_script(self, script_path: str, args: Dict):
        """
        Execute a single script with the given arguments.
        
        Args:
            script_path: Path to the script
            args: Arguments to pass to the script
        """
        try:
            script_path = Path(script_path)
            
            if script_path.suffix == '.py':
                self._execute_python_script(script_path, args)
            else:
                self._execute_shell_script(script_path, args)
                
        except Exception as e:
            self.logger.error(f"Failed to execute script {script_path}: {str(e)}")

    def _execute_python_script(self, script_path: Path, args: Dict):
        """
        Execute a Python script by importing it as a module.
        
        Args:
            script_path: Path to the Python script
            args: Arguments to pass to the script
        """
        try:
            # Import the script as a module
            spec = importlib.util.spec_from_file_location(
                script_path.stem,
                script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load script: {script_path}")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[script_path.stem] = module
            spec.loader.exec_module(module)

            # Execute the main function if it exists
            if hasattr(module, 'main'):
                self.logger.info(f"Executing Python script: {script_path}")
                module.main(args)
            else:
                self.logger.warning(f"No main() function found in {script_path}")

        except Exception as e:
            self.logger.error(f"Error executing Python script {script_path}: {str(e)}")
            raise

    def _execute_shell_script(self, script_path: Path, args: Dict):
        """
        Execute a shell script using subprocess.
        
        Args:
            script_path: Path to the shell script
            args: Arguments to pass to the script
        """
        try:
            # Convert arguments to command-line format
            cmd_args = self._convert_args_to_cmd(args)
            cmd = [str(script_path)] + cmd_args

            self.logger.info(f"Executing shell script: {' '.join(cmd)}")
            
            # Execute the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout:
                self.logger.info(f"Script output: {result.stdout}")
            if result.stderr:
                self.logger.warning(f"Script stderr: {result.stderr}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Script execution failed: {e.stderr}")
            raise
        except Exception as e:
            self.logger.error(f"Error executing shell script {script_path}: {str(e)}")
            raise

    def _convert_args_to_cmd(self, args: Dict) -> List[str]:
        """
        Convert dictionary arguments to command-line arguments.
        
        Args:
            args: Dictionary of arguments
            
        Returns:
            List of command-line argument strings
        """
        cmd_args = []
        for key, value in args.items():
            if isinstance(value, bool):
                if value:
                    cmd_args.append(f"--{key}")
            else:
                cmd_args.extend([f"--{key}", str(value)])
        return cmd_args

    def stop_all(self):
        """Stop all running script threads."""
        for script_type, thread in self.running_threads.items():
            if thread.is_alive():
                self.logger.info(f"Stopping script executor for {script_type}")
                self.script_queues[script_type].put(None)  # Signal to stop
                thread.join(timeout=5) 