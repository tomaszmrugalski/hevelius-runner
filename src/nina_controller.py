
# This NINAController implementation includes:
# 1. Process Management:
#   - Starts NINA with sequence files
#   - Monitors process execution
#   - Handles process output and errors
#   - Graceful shutdown with fallback to force kill
# 2. Safety Features:
#   - Prevents multiple instances
#   - Proper resource cleanup
#   - Process tree termination
# 3. Error handling and logging
# 4. Monitoring:
#   - Real-time output processing
#   - Status callback support
#   - Error logging
# 5. Resource cleanup


import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Callable
import psutil

class NINAController:
    def __init__(self, config: Dict[str, str]):
        """
        Initialize the NINA controller.
        
        Args:
            config: Dictionary containing NINA configuration
        """
        self.nina_path = Path(config['executable_path'])
        self.logger = logging.getLogger(__name__)
        self.process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._status_callback: Optional[Callable[[str], None]] = None

    def start_sequence(self, sequence_path: str, status_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Start NINA with a sequence file.
        
        Args:
            sequence_path: Path to the sequence file
            status_callback: Optional callback function for status updates
            
        Returns:
            bool: True if NINA was started successfully
        """
        if self.is_running():
            self.logger.error("NINA is already running")
            return False

        if not self.nina_path.exists():
            self.logger.error(f"NINA executable not found at: {self.nina_path}")
            return False

        try:
            sequence_path = Path(sequence_path)
            if not sequence_path.exists():
                self.logger.error(f"Sequence file not found: {sequence_path}")
                return False

            self._status_callback = status_callback
            self._stop_event.clear()

            # Start NINA with the sequence file
            cmd = [str(self.nina_path), "-s", str(sequence_path)]
            self.logger.info(f"Starting NINA with command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # Windows-specific
            )

            # Start monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_process,
                name="NINAMonitor",
                daemon=True
            )
            self._monitor_thread.start()

            return True

        except Exception as e:
            self.logger.error(f"Failed to start NINA: {str(e)}")
            return False

    def stop(self):
        """Stop NINA and clean up resources."""
        self._stop_event.set()
        
        if self.process:
            try:
                # Try graceful termination first
                self._terminate_process_tree(self.process.pid)
                
                # Wait for process to end
                self.process.wait(timeout=30)
                
            except subprocess.TimeoutExpired:
                self.logger.warning("NINA didn't terminate gracefully, forcing shutdown")
                self._kill_process_tree(self.process.pid)
            except Exception as e:
                self.logger.error(f"Error stopping NINA: {str(e)}")
            finally:
                self.process = None

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None

    def is_running(self) -> bool:
        """
        Check if NINA is currently running.
        
        Returns:
            bool: True if NINA is running
        """
        if self.process:
            return self.process.poll() is None
        return False

    def _monitor_process(self):
        """Monitor NINA process and handle output."""
        if not self.process:
            return

        while not self._stop_event.is_set() and self.is_running():
            try:
                # Read output line by line
                if self.process.stdout:
                    line = self.process.stdout.readline()
                    if line:
                        self._handle_nina_output(line.strip())
                
                # Check for errors
                if self.process.stderr:
                    error = self.process.stderr.readline()
                    if error:
                        self.logger.error(f"NINA error: {error.strip()}")

                time.sleep(0.1)  # Prevent CPU overuse

            except Exception as e:
                self.logger.error(f"Error monitoring NINA process: {str(e)}")
                break

        # Process ended or stop requested
        self._cleanup()

    def _handle_nina_output(self, output: str):
        """
        Handle output from NINA process.
        
        Args:
            output: Output line from NINA
        """
        self.logger.debug(f"NINA output: {output}")
        
        if self._status_callback:
            try:
                self._status_callback(output)
            except Exception as e:
                self.logger.error(f"Error in status callback: {str(e)}")

    def _terminate_process_tree(self, pid: int):
        """
        Terminate a process and all its children gracefully.
        
        Args:
            pid: Process ID to terminate
        """
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            # Terminate children first
            for child in children:
                child.terminate()
            
            # Terminate parent
            parent.terminate()
            
            # Wait for processes to terminate
            psutil.wait_procs(children + [parent], timeout=5)
            
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self.logger.error(f"Error terminating process tree: {str(e)}")

    def _kill_process_tree(self, pid: int):
        """
        Forcefully kill a process and all its children.
        
        Args:
            pid: Process ID to kill
        """
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            
            # Kill children first
            for child in children:
                child.kill()
            
            # Kill parent
            parent.kill()
            
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self.logger.error(f"Error killing process tree: {str(e)}")

    def _cleanup(self):
        """Clean up resources after NINA process ends."""
        if self.process:
            try:
                # Close file handles
                if self.process.stdout:
                    self.process.stdout.close()
                if self.process.stderr:
                    self.process.stderr.close()
                
                # Get return code
                return_code = self.process.poll()
                if return_code is not None:
                    self.logger.info(f"NINA process ended with return code: {return_code}")
                
            except Exception as e:
                self.logger.error(f"Error during cleanup: {str(e)}")
            finally:
                self.process = None 