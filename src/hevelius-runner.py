
# This is the entry point for the hevelius-runner code.
# 
# It integrates all components:
# 1. Config Manager
# 2. API Client
# 3. Task Manager
# 4. File Monitor
# 5. Script Executor
# 6. NINA Controller
# 
# It provides a complete workflow:
# 1. Startup script execution
# 2. Night time detection
# 3. Task planning and execution
# 4. FITS file monitoring
# 5. Status updates
# 6. Clean shutdown
# 
# It includes proper error handling and logging throughout
# 
# It implements the main control loop that:
# 1. Checks for night time
# 2. Processes observation plans
# 3. Monitors for new files
# 4. Handles status updates

import logging
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict

from config_manager import ConfigManager
from api_client import APIClient
from task_manager import TaskManager
from file_monitor import FileMonitor, FileMonitorThread
from script_executor import ScriptExecutor
from nina_controller import NINAController
from version import get_version

class ObservatoryAutomation:
    def __init__(self):
        """Initialize the observatory automation system."""
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.config = ConfigManager()
        self.api_client = APIClient(self.config.get_api_config())
        self.task_manager = TaskManager(self.config.get_paths_config())
        self.file_monitor = FileMonitor(self.config.get_paths_config())
        self.script_executor = ScriptExecutor(self.config.get_scripts_config())
        self.nina_controller = NINAController(self.config.get_nina_config())
        
        self.current_sequence_path = None
        self.observatory_id = "default"  # Should be configured or determined

    def setup_logging(self):
        """Configure logging for the application."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Full logging: format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(levelname)s - %(message)s',
            handlers=[
                RotatingFileHandler(
                    log_dir / 'observatory.log',
                    maxBytes=1024*1024,
                    backupCount=5
                ),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def run(self):
        """Main execution loop of the automation system."""
        try:
            self.logger.info(f"Starting havelius-runner {get_version()}")
            
            # Execute startup script
            self.script_executor.execute_script('startup')

            # Ensure the API is reachable
            self.api_client.connect()
            
            # Start file monitoring
            monitor_thread = FileMonitorThread(self.file_monitor)
            self.file_monitor.start(self.handle_new_fits_file)
            monitor_thread.start()
            
            while True:
                try:
                    current_date = datetime.now().date()
                    
                    # Check if it's night time and execute night start script
                    if self.is_night_time():
                        self.script_executor.execute_script('night_start')
                        self.process_night_plan(current_date)
                    
                    # Wait before next check
                    time.sleep(60)  # Check every minute
                    
                except KeyboardInterrupt:
                    self.logger.info("Received shutdown signal")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop: {str(e)}", exc_info=True)
                    time.sleep(300)  # Wait 5 minutes before retry
            
        finally:
            self.cleanup()

    def process_night_plan(self, date: datetime.date):
        """
        Process the observation plan for a night.
        
        Args:
            date: Date to process
        """
        try:
            # Get night plan from API
            tasks = self.api_client.get_night_plan(date.strftime("%Y-%m-%d"))
            if not tasks:
                self.logger.info("No tasks planned for tonight")
                return

            # Filter out completed tasks
            pending_tasks = [
                task for task in tasks
                if self.api_client.check_task_status(task['task_id']) != 'completed'
            ]

            if not pending_tasks:
                self.logger.info("All tasks for tonight are completed")
                return

            # Prepare sequence file
            self.current_sequence_path = self.task_manager.prepare_sequence_file(
                pending_tasks,
                self.observatory_id,
                date.strftime("%Y-%m-%d")
            )

            # Start NINA with the sequence
            if self.nina_controller.start_sequence(
                self.current_sequence_path,
                self.handle_nina_status
            ):
                self.logger.info(f"Started NINA with sequence: {self.current_sequence_path}")
            else:
                self.logger.error("Failed to start NINA")

        except Exception as e:
            self.logger.error(f"Error processing night plan: {str(e)}", exc_info=True)

    def handle_new_fits_file(self, file_path: str):
        """
        Handle newly detected FITS files.
        
        Args:
            file_path: Path to the new FITS file
        """
        try:
            # Extract task ID from file name or metadata
            task_id = self.extract_task_id_from_fits(file_path)
            if task_id:
                # Update task status
                self.api_client.update_task_status(
                    task_id,
                    "completed",
                    [file_path]
                )
                
                # Execute post-task script
                self.script_executor.execute_script('post_task', {
                    'task_id': task_id,
                    'fits_file': file_path
                })
                
        except Exception as e:
            self.logger.error(f"Error handling FITS file: {str(e)}")

    def handle_nina_status(self, status: str):
        """
        Handle status updates from NINA.
        
        Args:
            status: Status message from NINA
        """
        self.logger.info(f"NINA status: {status}")
        # Add specific status handling as needed

    def is_night_time(self) -> bool:
        """
        Check if it's currently night time for observations.
        
        Returns:
            bool: True if it's night time
        """
        # This is a simplified check - should be replaced with proper
        # astronomical twilight calculations for your location
        current_hour = datetime.now().hour
        return 18 <= current_hour or current_hour <= 6

    def extract_task_id_from_fits(self, file_path: str) -> str:
        """
        Extract task ID from FITS file name or metadata.
        
        Args:
            file_path: Path to the FITS file
            
        Returns:
            str: Task ID
        """
        # This is a placeholder - implement actual FITS header reading
        # or filename parsing based on your naming convention
        return Path(file_path).stem.split('_')[0]

    def cleanup(self):
        """Clean up resources before shutdown."""
        self.logger.info("Shutting down Observatory Automation")
        
        # Stop NINA if running
        if self.nina_controller.is_running():
            self.nina_controller.stop()
        
        # Stop file monitor
        self.file_monitor.stop()
        
        # Execute night end script
        self.script_executor.execute_script('night_end')
        
        # Stop script executor
        self.script_executor.stop_all()
        
        self.logger.info("Shutdown complete")

if __name__ == "__main__":
    app = ObservatoryAutomation()
    app.run() 