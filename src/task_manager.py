import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import copy

class TaskManager:
    def __init__(self, config: Dict[str, str]):
        """
        Initialize TaskManager with configuration.
        
        Args:
            config: Dictionary containing path configurations
        """
        self.template_dir = Path(config['template_dir'])
        self.output_dir = Path(config['output_dir'])
        self.logger = logging.getLogger(__name__)
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_template(self, observatory_id: str) -> Dict[str, Any]:
        """
        Load JSON template for specific observatory.
        
        Args:
            observatory_id: Identifier for the observatory
            
        Returns:
            Dictionary containing the template
            
        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        template_path = self.template_dir / f"{observatory_id}_template.json"
        
        if not template_path.exists():
            self.logger.error(f"Template not found for observatory: {observatory_id}")
            raise FileNotFoundError(f"Template file not found: {template_path}")
            
        try:
            with open(template_path, 'r') as f:
                template = json.load(f)
            self.logger.info(f"Loaded template for observatory: {observatory_id}")
            return template
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON template: {str(e)}")
            raise

    def prepare_sequence_file(self, tasks: List[Dict[str, Any]], 
                            observatory_id: str, date: str) -> str:
        """
        Prepare sequence file for NINA from tasks.
        
        Args:
            tasks: List of observation tasks
            observatory_id: Identifier for the observatory
            date: Date string in YYYY-MM-DD format
            
        Returns:
            Path to the generated sequence file
        """
        try:
            template = self.load_template(observatory_id)
            sequence = copy.deepcopy(template)
            
            # Customize sequence based on tasks
            sequence['Targets'] = []
            for task in tasks:
                target = self._create_target_from_task(task)
                sequence['Targets'].append(target)
            
            # Add metadata
            sequence['MetaData'] = {
                'Date': date,
                'ObservatoryId': observatory_id,
                'GeneratedAt': datetime.utcnow().isoformat()
            }
            
            # Save sequence file
            output_path = self.output_dir / f"sequence_{observatory_id}_{date}.json"
            with open(output_path, 'w') as f:
                json.dump(sequence, f, indent=2)
                
            self.logger.info(f"Generated sequence file: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Failed to prepare sequence file: {str(e)}")
            raise

    def _create_target_from_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert task to NINA target format.
        
        Args:
            task: Dictionary containing task details
            
        Returns:
            Dictionary containing target configuration for NINA
        """
        try:
            target = {
                'Name': task['name'],
                'RA': task['ra'],
                'Dec': task['dec'],
                'Rotation': task.get('rotation', 0),
                'Filters': task.get('filters', []),
                'Exposures': task.get('exposures', []),
                'TaskId': task['task_id'],  # Store task_id for later reference
                'CustomProperties': task.get('custom_properties', {})
            }
            return target
        except KeyError as e:
            self.logger.error(f"Missing required field in task: {str(e)}")
            raise ValueError(f"Invalid task format: missing {str(e)}")

    def get_task_ids_from_sequence(self, sequence_path: str) -> List[str]:
        """
        Extract task IDs from a sequence file.
        
        Args:
            sequence_path: Path to the sequence file
            
        Returns:
            List of task IDs
        """
        try:
            with open(sequence_path, 'r') as f:
                sequence = json.load(f)
            
            task_ids = [target['TaskId'] for target in sequence.get('Targets', [])]
            return task_ids
            
        except Exception as e:
            self.logger.error(f"Failed to extract task IDs: {str(e)}")
            raise

    def is_sequence_complete(self, sequence_path: str) -> bool:
        """
        Check if all tasks in a sequence are complete.
        
        Args:
            sequence_path: Path to the sequence file
            
        Returns:
            bool: True if all tasks are complete
        """
        try:
            with open(sequence_path, 'r') as f:
                sequence = json.load(f)
            
            return all(target.get('Completed', False) 
                      for target in sequence.get('Targets', []))
                      
        except Exception as e:
            self.logger.error(f"Failed to check sequence completion: {str(e)}")
            raise 