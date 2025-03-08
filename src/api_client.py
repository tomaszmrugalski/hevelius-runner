import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import hashlib
from dataclasses import dataclass

# TODO:
# Figure out what's wrong with LetsEncrypt certificate on hevelius.borowka.space
# hints: https://stackoverflow.com/questions/79358216/python-v3-13-has-broken-email-delivery-due-to-an-ssl-change

@dataclass
class LoginResponse:
    status: bool
    token: str
    user_id: int
    firstname: str
    lastname: str
    share: float
    phone: str
    email: str
    permissions: int
    aavso_id: str
    ftp_login: str
    ftp_pass: str
    msg: str

class APIClient:
    def __init__(self, config: Dict[str, str]):
        """
        Initialize API client with configuration.
        
        Args:
            config: Dictionary containing 'base_url', 'timeout', 'username', and 'password' keys
        """
        self.base_url = config['base_url']
        self.timeout = int(config['timeout'])
        self.logger = logging.getLogger(__name__)
        # Add verify flag, defaulting to True for security
        self.verify_ssl = config.get('verify_ssl', 'true').lower() == 'true'
        self._username = config['username']
        self._password = config['password']
        self._token: Optional[str] = None

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers if token is available."""
        if self._token:
            return {'Authorization': f'Bearer {self._token}'}
        return {}

    def login(self) -> LoginResponse:
        """
        Authenticate with the API.
        
        Returns:
            LoginResponse object containing user details and token
            
        Raises:
            requests.RequestException: If the API call fails
        """
        try:
            url = urljoin(self.base_url, 'login')
            
            # Hash password with MD5
            password_hash = hashlib.md5(self._password.encode()).hexdigest()
            
            payload = {
                'username': self._username,
                'password': password_hash
            }
            
            self.logger.info(f"Authenticating user {self._username}")
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            data = response.json()
            login_response = LoginResponse(**data)
            
            if login_response.status:
                self._token = login_response.token
                self.logger.info("Authentication successful")
            else:
                self.logger.error(f"Authentication failed: {login_response.msg}")
            
            return login_response
            
        except requests.RequestException as e:
            self.logger.error(f"Login failed: {str(e)}")
            raise

    def get_version(self) -> str:
        """
        Retrieve the backend version.

        Returns:
            version string
        
        Raises:
            requests.RequestException: if the API call fails
        """
        try:
            self.logger.info(f"base_url={self.base_url}")
            url = urljoin(self.base_url, 'version')
            
            self.logger.info(f"Checking backend connectivity ({url})")
            response = requests.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl  # Add verify parameter
            )
            self.logger.debug(f"API version response: {response.text}")
            response.raise_for_status()
            
            version = response.json()['version']
            return version

        except requests.RequestException as e:
            self.logger.error(f"Failed to retrieve night plan: {str(e)}")
            raise


    def get_night_plan(self, date: str) -> List[Dict[str, Any]]:
        """
        Retrieve the night plan for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            List of task dictionaries
            
        Raises:
            requests.RequestException: If the API call fails
        """
        try:
            url = urljoin(self.base_url, 'night-plan')

            # TODO: Hardcoded scope_id=3 for now
            params = {'scope_id': 3}  # {'date': date}
            
            self.logger.info(f"Fetching night plan for date: {date}")
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers=self._get_auth_headers()  # Add authentication headers
            )
            response.raise_for_status()

            response_json = response.json()
            
            tasks = response_json['tasks']
            self.logger.info(f"Retrieved {len(tasks)} tasks for {date}")
            self.logger.debug(f"Tasks: {tasks}")
            return tasks
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to retrieve night plan: {str(e)}")
            raise

    def update_task_status(self, task_id: str, status: str, fits_files: List[str] = None) -> bool:
        """
        Update the status of a task after observation.
        
        Args:
            task_id: Unique identifier of the task
            status: New status of the task
            fits_files: Optional list of FITS file paths generated
            
        Returns:
            bool: True if update was successful
            
        Raises:
            requests.RequestException: If the API call fails
        """
        try:
            url = urljoin(self.base_url, '/task-update')
            
            payload = {
                'task_id': task_id,
                'status': status,
                'fits_files': fits_files or []
            }
            
            self.logger.info(f"Updating task {task_id} with status: {status}")
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            self.logger.info(f"Successfully updated task {task_id}")
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to update task {task_id}: {str(e)}")
            raise

    def check_task_status(self, task_id: str) -> str:
        """
        Check if a task has already been observed.
        
        Args:
            task_id: Unique identifier of the task
            
        Returns:
            str: Current status of the task
            
        Raises:
            requests.RequestException: If the API call fails
        """
        try:
            url = urljoin(self.base_url, f'/task-status/{task_id}')
            
            self.logger.info(f"Checking status for task: {task_id}")
            response = requests.get(
                url,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            status = response.json().get('status')
            self.logger.debug(f"Task {task_id} status: {status}")
            return status
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to check task status: {str(e)}")
            raise


    def connect(self):
        """Initialize connection to the API."""
        ver = self.get_version()
        self.logger.info(f"Backend ({self.base_url}) reachable, returned version is {ver}")
        
        # Login after version check
        self.login()
