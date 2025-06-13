#!/usr/bin/env python3
"""
Hitachi HNAS Pre-Backup Script for Veeam
This script creates file system snapshots on Hitachi HNAS before backup operations.
Requires Hitachi HNAS REST API v9.4 (HNAS Platform 15.4.8300 or higher)
"""

import os
import sys
import json
import time
import logging
import requests
import urllib3
from datetime import datetime
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class HNASSnapshotManager:
    def __init__(self, hnas_host, username, password, verify_ssl=False):
        """Initialize HNAS connection parameters"""
        self.hnas_host = hnas_host
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{hnas_host}:8444/v9/storage"
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging for the script"""
        log_dir = os.environ.get('VEEAM_LOG_DIR', 'C:\\VeeamScripts\\Logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"hnas_pre_backup_{datetime.now().strftime('%Y%m%d')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def test_connection(self):
        """Test connection to HNAS REST API"""
        try:
            response = self.session.get(
                f"{self.base_url}/file-devices",
                headers={'X-Api-Key': self.password} if self.username == 'apikey' else None,
                auth=None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password),
                timeout=30
            )
            response.raise_for_status()
            device_info = response.json()
            self.logger.info(f"Connected to HNAS: {device_info.get('name', 'Unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to HNAS: {e}")
            return False
            
    def get_all_filesystems(self):
        """Get all filesystems to find IDs by name"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            response = self.session.get(
                f"{self.base_url}/filesystems",
                headers=headers,
                auth=auth,
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('filesystems', [])
        except Exception as e:
            self.logger.error(f"Failed to get filesystems list: {e}")
            return []
    
    def get_filesystem_by_name(self, filesystem_name):
        """Find filesystem by name and return filesystem info"""
        try:
            filesystems = self.get_all_filesystems()
            for fs in filesystems:
                if fs.get('label') == filesystem_name:
                    return fs
            return None
        except Exception as e:
            self.logger.error(f"Failed to find filesystem by name: {e}")
            return None
            
    def get_filesystem_info(self, filesystem_id):
        """Get filesystem information by ID"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            response = self.session.get(
                f"{self.base_url}/filesystems/{filesystem_id}",
                headers=headers,
                auth=auth,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get filesystem info: {e}")
            return None
            
    def create_snapshot(self, filesystem_id, snapshot_name, app_search_id=None, retention_interval=None):
        """Create a filesystem snapshot using the correct v9.4 API"""
        try:
            # Prepare snapshot creation payload according to v9.4 API
            snapshot_data = {
                "filesystemId": filesystem_id,
                "displayName": snapshot_name
            }
            
            if app_search_id:
                snapshot_data["appSearchId"] = app_search_id
                
            if retention_interval:
                snapshot_data["retentionInterval"] = retention_interval
                
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
                
            self.logger.info(f"Creating snapshot '{snapshot_name}' for filesystem '{filesystem_id}'")
            
            response = self.session.post(
                f"{self.base_url}/filesystem-snapshots",
                json=snapshot_data,
                headers={**headers, 'Content-Type': 'application/json'},
                auth=auth,
                timeout=60
            )
            response.raise_for_status()
            
            snapshot_info = response.json()
            self.logger.info(f"Successfully created snapshot: {snapshot_info.get('snapshot', {}).get('displayName', snapshot_name)}")
            return snapshot_info.get('snapshot', {})
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error creating snapshot: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create snapshot: {e}")
            return None

    def create_smb_share(self, filesystem_id, snapshot_name, share_name="VeeamNASBackup"):
        """Create SMB share for snapshot access"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            # Get filesystem info to determine virtual server
            fs_info = self.get_filesystem_info(filesystem_id)
            if not fs_info:
                self.logger.error(f"Cannot get filesystem info for share creation")
                return None
                
            virtual_server_id = fs_info.get('filesystem', {}).get('virtualServerId')
            if not virtual_server_id:
                self.logger.error(f"Cannot determine virtual server for filesystem {filesystem_id}")
                return None
            
            # Create unique share name with timestamp to avoid conflicts
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_share_name = f"{share_name}_{timestamp}"
            
            # Snapshot path in Windows format
            snapshot_path = f"\\.snapshot\\{snapshot_name}"
            
            share_data = {
                "filesystemId": filesystem_id,
                "virtualServerId": virtual_server_id,
                "name": unique_share_name,
                "filesystemPath": snapshot_path,
                "comment": f"Veeam backup snapshot share created at {datetime.now().isoformat()}",
                "ensurePathExists": False,  # Snapshot should already exist
                "accessConfig": "",  # No IP restrictions by default
                "cacheOption": "MANUAL_CACHING_DOCS",
                "continuouslyAvailable": False,
                "encryptedAccess": False,
                "isABEEnabled": False,
                "isFollowGlobalSymbolicLinks": False,
                "isFollowSymbolicLinks": False,
                "isForceFileNameToLowercase": False,
                "isScanForVirusesEnabled": False,
                "maxConcurrentUsers": -1,  # Unlimited
                "snapshotOption": "SHOW_AND_ALLOW_ACCESS",
                "transferToReplicationTargetSetting": "USE_FS_DEFAULT",
                "userHomeDirectoryMode": "OFF",
                "noDefaultSecurity": False  # Allow default Everyone permissions
            }
                
            self.logger.info(f"Creating SMB share '{unique_share_name}' for snapshot '{snapshot_name}'")
            
            response = self.session.post(
                f"{self.base_url}/filesystem-shares/cifs",
                json=share_data,
                headers={**headers, 'Content-Type': 'application/json'},
                auth=auth,
                timeout=60
            )
            response.raise_for_status()
            
            share_info = response.json()
            self.logger.info(f"Successfully created SMB share: {unique_share_name}")
            return share_info.get('filesystemShare', {})
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error creating SMB share: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to create SMB share: {e}")
            return None
            
    def get_snapshots(self, filesystem_id, app_search_id="null"):
        """Get all snapshots for a filesystem"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            response = self.session.get(
                f"{self.base_url}/filesystem-snapshots/{filesystem_id}/{app_search_id}",
                headers=headers,
                auth=auth,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to list snapshots: {e}")
            return None

def main():
    """Main execution function"""
    # Configuration - these should be set via environment variables or config file
    config = {
        'hnas_host': os.environ.get('HNAS_HOST', ''),
        'username': os.environ.get('HNAS_USERNAME', ''),
        'password': os.environ.get('HNAS_PASSWORD', ''),
        'filesystems': os.environ.get('HNAS_FILESYSTEMS', '').split(','),
        'app_search_id': os.environ.get('HNAS_APP_SEARCH_ID', 'veeam'),
        'retention_interval': int(os.environ.get('HNAS_RETENTION_INTERVAL', '0')),
        'verify_ssl': os.environ.get('HNAS_VERIFY_SSL', 'false').lower() == 'true',
        'create_smb_share': os.environ.get('HNAS_CREATE_SMB_SHARE', 'true').lower() == 'true',
        'smb_share_name': os.environ.get('HNAS_SMB_SHARE_NAME', 'VeeamNASBackup')
    }
    
    # Validate configuration
    if not all([config['hnas_host'], config['username'], config['password']]):
        print("ERROR: Missing required configuration. Set HNAS_HOST, HNAS_USERNAME, and HNAS_PASSWORD environment variables.")
        sys.exit(1)
        
    if not config['filesystems'] or config['filesystems'] == ['']:
        print("ERROR: No filesystems specified. Set HNAS_FILESYSTEMS environment variable (comma-separated filesystem names or IDs).")
        sys.exit(1)
    
    # Initialize HNAS manager
    hnas = HNASSnapshotManager(
        config['hnas_host'], 
        config['username'], 
        config['password'],
        config['verify_ssl']
    )
    
    # Test connection
    if not hnas.test_connection():
        print("ERROR: Failed to connect to HNAS. Check credentials and network connectivity.")
        sys.exit(1)
    
    # Create snapshots for each filesystem
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    created_snapshots = []
    
    for filesystem_input in config['filesystems']:
        filesystem_input = filesystem_input.strip()
        if not filesystem_input:
            continue
        
        hnas.logger.info(f"Processing filesystem input: {filesystem_input}")
        
        # Check if input looks like a filesystem ID (32 hex characters) or a name
        if len(filesystem_input) == 32 and all(c in '0123456789ABCDEFabcdef' for c in filesystem_input):
            # Input looks like a filesystem ID
            filesystem_id = filesystem_input
            fs_info = hnas.get_filesystem_info(filesystem_id)
            if not fs_info:
                hnas.logger.warning(f"Could not retrieve info for filesystem ID: {filesystem_id}")
                continue
            filesystem_name = fs_info.get('filesystem', {}).get('label', filesystem_id)
        else:
            # Input is a filesystem name, look up the ID
            fs_info = hnas.get_filesystem_by_name(filesystem_input)
            if not fs_info:
                hnas.logger.warning(f"Could not find filesystem with name: {filesystem_input}")
                continue
            filesystem_id = fs_info.get('filesystemId')
            filesystem_name = fs_info.get('label', filesystem_input)
            
            if not filesystem_id:
                hnas.logger.warning(f"Found filesystem '{filesystem_input}' but no ID available")
                continue
        
        # Create snapshot name with app search ID prefix if specified
        if config['app_search_id']:
            snapshot_name = f"{config['app_search_id']}_{filesystem_name}_{timestamp}"
        else:
            snapshot_name = f"veeam_{filesystem_name}_{timestamp}"
        
        hnas.logger.info(f"Creating snapshot for filesystem '{filesystem_name}' (ID: {filesystem_id})")
        
        # Create snapshot
        snapshot = hnas.create_snapshot(
            filesystem_id, 
            snapshot_name, 
            config['app_search_id'],
            config['retention_interval'] if config['retention_interval'] > 0 else None
        )
        
        if snapshot:
            snapshot_info = {
                'filesystem_id': filesystem_id,
                'filesystem_name': filesystem_name,
                'snapshot_name': snapshot_name,
                'snapshot_object_id': snapshot.get('objectId', ''),
                'creation_time': snapshot.get('creationTime', ''),
                'app_search_id': config['app_search_id']
            }
            
            # Create SMB share for the snapshot if enabled
            if config.get('create_smb_share', True):
                hnas.logger.info(f"Creating SMB share for snapshot access...")
                smb_share = hnas.create_smb_share(filesystem_id, snapshot_name, config.get('smb_share_name', 'VeeamNASBackup'))
                
                if smb_share:
                    snapshot_info.update({
                        'smb_share_name': smb_share.get('name', ''),
                        'smb_share_object_id': smb_share.get('objectId', ''),
                        'smb_share_path': smb_share.get('path', '')
                    })
                    hnas.logger.info(f"SMB share created: {smb_share.get('name', '')} -> {smb_share.get('path', '')}")
                else:
                    hnas.logger.warning(f"Failed to create SMB share for snapshot, but snapshot was created successfully")
            
            created_snapshots.append(snapshot_info)
        else:
            hnas.logger.error(f"Failed to create snapshot for filesystem: {filesystem_name} ({filesystem_id})")
    
    # Save snapshot information for post-backup script
    snapshot_info_file = os.environ.get('VEEAM_SNAPSHOT_INFO', 'C:\\VeeamScripts\\hnas_snapshot_info.json')
    os.makedirs(os.path.dirname(snapshot_info_file), exist_ok=True)
    
    with open(snapshot_info_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'snapshots': created_snapshots,
            'config': {
                'hnas_host': config['hnas_host'],
                'app_search_id': config['app_search_id']
            }
        }, f, indent=2)
    
    hnas.logger.info(f"Pre-backup script completed. Created {len(created_snapshots)} snapshots.")
    
    if len(created_snapshots) == 0:
        print("WARNING: No snapshots were created successfully.")
        sys.exit(1)
    
    print(f"SUCCESS: Created {len(created_snapshots)} snapshots for Veeam backup.")

if __name__ == "__main__":
    main()
