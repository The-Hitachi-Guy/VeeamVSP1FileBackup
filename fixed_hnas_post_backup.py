#!/usr/bin/env python3
"""
Hitachi HNAS Post-Backup Script for Veeam
This script manages file system snapshots on Hitachi HNAS after backup operations.
Can optionally clean up snapshots based on retention policy.
Requires Hitachi HNAS REST API v9.4 (HNAS Platform 15.4.8300 or higher)
"""

import os
import sys
import json
import time
import logging
import requests
import urllib3
from datetime import datetime, timedelta
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
        
        log_file = os.path.join(log_dir, f"hnas_post_backup_{datetime.now().strftime('%Y%m%d')}.log")
        
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
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            response = self.session.get(
                f"{self.base_url}/file-devices",
                headers=headers,
                auth=auth,
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

    def delete_smb_share(self, share_object_id):
        """Delete SMB share using v9.4 API"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
                
            self.logger.info(f"Deleting SMB share with object ID: {share_object_id}")
            
            response = self.session.delete(
                f"{self.base_url}/filesystem-shares/cifs/{share_object_id}",
                headers=headers,
                auth=auth,
                timeout=60
            )
            response.raise_for_status()
            
            self.logger.info(f"Successfully deleted SMB share: {share_object_id}")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"SMB share '{share_object_id}' not found (may have been already deleted)")
                return True
            else:
                self.logger.error(f"HTTP error deleting SMB share: {e.response.status_code} - {e.response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to delete SMB share: {e}")
            return False
            
    def get_snapshot_info(self, snapshot_object_id):
        """Get information about a specific snapshot"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            response = self.session.get(
                f"{self.base_url}/filesystem-snapshots/{snapshot_object_id}",
                headers=headers,
                auth=auth,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get snapshot info: {e}")
            return None
            
    def delete_snapshot(self, snapshot_object_id):
        """Delete a filesystem snapshot using v9.4 API"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
                
            self.logger.info(f"Deleting snapshot with object ID: {snapshot_object_id}")
            
            response = self.session.delete(
                f"{self.base_url}/filesystem-snapshots/{snapshot_object_id}",
                headers=headers,
                auth=auth,
                timeout=60
            )
            response.raise_for_status()
            
            self.logger.info(f"Successfully deleted snapshot: {snapshot_object_id}")
            return True
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Snapshot '{snapshot_object_id}' not found (may have been already deleted)")
                return True
            else:
                self.logger.error(f"HTTP error deleting snapshot: {e.response.status_code} - {e.response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to delete snapshot: {e}")
            return False
            
    def get_virtual_server_smb_shares(self, virtual_server_id, share_name_prefix):
        """Get SMB shares for a virtual server that match the prefix"""
        try:
            headers = {'X-Api-Key': self.password} if self.username == 'apikey' else {}
            auth = None if self.username == 'apikey' else HTTPBasicAuth(self.username, self.password)
            
            response = self.session.get(
                f"{self.base_url}/virtual-servers/{virtual_server_id}/cifs",
                headers=headers,
                auth=auth,
                timeout=30
            )
            response.raise_for_status()
            shares_data = response.json()
            
            # Filter shares that match our naming pattern
            matching_shares = []
            for share in shares_data.get('filesystemShares', []):
                share_name = share.get('name', '')
                if share_name.startswith(share_name_prefix):
                    matching_shares.append(share)
            
            return matching_shares
        except Exception as e:
            self.logger.error(f"Failed to get SMB shares: {e}")
            return []
            
    def get_filesystem_snapshots(self, filesystem_id, app_search_id="null"):
        """Get all snapshots for a filesystem using v9.4 API"""
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
            snapshots_data = response.json()
            return snapshots_data.get('snapshots', [])
        except Exception as e:
            self.logger.error(f"Failed to list snapshots: {e}")
            return []
            
    def cleanup_old_snapshots(self, filesystem_id, app_search_id, retention_days):
        """Clean up old snapshots based on retention policy"""
        try:
            snapshots = self.get_filesystem_snapshots(filesystem_id, app_search_id)
            if not snapshots:
                return 0
                
            cutoff_time = int((datetime.now() - timedelta(days=retention_days)).timestamp())
            deleted_count = 0
            
            for snapshot in snapshots:
                # Check if snapshot is older than retention period
                creation_time = snapshot.get('creationTime', 0)
                if isinstance(creation_time, str):
                    try:
                        creation_time = int(creation_time)
                    except ValueError:
                        self.logger.warning(f"Invalid creation time format for snapshot: {snapshot.get('displayName', 'unknown')}")
                        continue
                
                if creation_time < cutoff_time:
                    snapshot_object_id = snapshot.get('objectId')
                    if snapshot_object_id and self.delete_snapshot(snapshot_object_id):
                        deleted_count += 1
                        
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error during snapshot cleanup: {e}")
            return 0
            
    def cleanup_old_smb_shares(self, virtual_server_id, share_name_prefix, retention_days):
        """Clean up old SMB shares based on retention policy"""
        try:
            shares = self.get_virtual_server_smb_shares(virtual_server_id, share_name_prefix)
            if not shares:
                return 0
                
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0
            
            for share in shares:
                share_name = share.get('name', '')
                
                # Extract timestamp from share name (format: prefix_YYYYMMDD_HHMMSS)
                try:
                    parts = share_name.split('_')
                    if len(parts) >= 3:
                        date_part = parts[-2]  # YYYYMMDD
                        time_part = parts[-1]  # HHMMSS
                        timestamp_str = f"{date_part}_{time_part}"
                        share_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if share_date < cutoff_date:
                            share_object_id = share.get('objectId')
                            if share_object_id and self.delete_smb_share(share_object_id):
                                deleted_count += 1
                                
                except ValueError:
                    # Skip shares with unexpected naming format
                    self.logger.warning(f"Skipping SMB share with unexpected name format: {share_name}")
                    continue
                    
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error during SMB share cleanup: {e}")
            return 0

def validate_backup_result():
    """Check if the Veeam backup job completed successfully"""
    # Veeam sets environment variables with job results
    job_result = os.environ.get('VEEAM_JOB_RESULT', 'Unknown')
    session_result = os.environ.get('VEEAM_SESSION_RESULT', 'Unknown')
    
    # Possible values: Success, Warning, Failed
    if job_result in ['Success', 'Warning']:
        return True, job_result
    else:
        return False, job_result

def main():
    """Main execution function"""
    # Check backup result first
    backup_success, result = validate_backup_result()
    
    # Configuration
    config = {
        'hnas_host': os.environ.get('HNAS_HOST', ''),
        'username': os.environ.get('HNAS_USERNAME', ''),
        'password': os.environ.get('HNAS_PASSWORD', ''),
        'verify_ssl': os.environ.get('HNAS_VERIFY_SSL', 'false').lower() == 'true',
        'cleanup_on_success': os.environ.get('HNAS_CLEANUP_ON_SUCCESS', 'false').lower() == 'true',
        'cleanup_on_failure': os.environ.get('HNAS_CLEANUP_ON_FAILURE', 'true').lower() == 'true',
        'retention_days': int(os.environ.get('HNAS_RETENTION_DAYS', '7')),
        'app_search_id': os.environ.get('HNAS_APP_SEARCH_ID', 'veeam'),
        'smb_share_name': os.environ.get('HNAS_SMB_SHARE_NAME', 'VeeamNASBackup')
    }
    
    # Validate configuration
    if not all([config['hnas_host'], config['username'], config['password']]):
        print("ERROR: Missing required configuration. Set HNAS_HOST, HNAS_USERNAME, and HNAS_PASSWORD environment variables.")
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
    
    hnas.logger.info(f"Backup job result: {result}")
    
    # Load snapshot information from pre-backup script
    snapshot_info_file = os.environ.get('VEEAM_SNAPSHOT_INFO', 'C:\\VeeamScripts\\hnas_snapshot_info.json')
    
    created_snapshots = []
    if os.path.exists(snapshot_info_file):
        try:
            with open(snapshot_info_file, 'r') as f:
                snapshot_data = json.load(f)
                created_snapshots = snapshot_data.get('snapshots', [])
                hnas.logger.info(f"Loaded information for {len(created_snapshots)} snapshots from pre-backup script")
        except Exception as e:
            hnas.logger.error(f"Failed to load snapshot information: {e}")
    else:
        hnas.logger.warning(f"Snapshot info file not found: {snapshot_info_file}")
    
    # Decide whether to clean up snapshots based on backup result and configuration
    should_cleanup = (
        (backup_success and config['cleanup_on_success']) or
        (not backup_success and config['cleanup_on_failure'])
    )
    
    deleted_count = 0
    
    if should_cleanup and created_snapshots:
        hnas.logger.info("Cleaning up snapshots and SMB shares created during this backup session...")
        
        for snapshot_info in created_snapshots:
            # Delete SMB share first if it exists
            smb_share_object_id = snapshot_info.get('smb_share_object_id')
            if smb_share_object_id:
                hnas.logger.info(f"Deleting SMB share: {snapshot_info.get('smb_share_name', 'Unknown')}")
                hnas.delete_smb_share(smb_share_object_id)
            
            # Then delete the snapshot
            snapshot_object_id = snapshot_info.get('snapshot_object_id')
            if snapshot_object_id:
                if hnas.delete_snapshot(snapshot_object_id):
                    deleted_count += 1
    
    # Perform retention-based cleanup for old snapshots and SMB shares (regardless of current backup result)
    if config['retention_days'] > 0:
        hnas.logger.info(f"Performing retention-based cleanup (keeping snapshots newer than {config['retention_days']} days)...")
        
        # Get unique filesystems and virtual servers from created snapshots or environment variable
        filesystems = set()
        virtual_servers = set()
        
        if created_snapshots:
            filesystems.update(snap.get('filesystem_id') for snap in created_snapshots if snap.get('filesystem_id'))
            # Get virtual servers by looking up filesystem info
            for filesystem_id in filesystems:
                fs_info = hnas.get_filesystem_info(filesystem_id)
                if fs_info:
                    vs_id = fs_info.get('filesystem', {}).get('virtualServerId')
                    if vs_id:
                        virtual_servers.add(vs_id)
        else:
            # Fallback to environment variable - resolve names to IDs if needed
            env_filesystems = os.environ.get('HNAS_FILESYSTEMS', '').split(',')
            for fs_input in env_filesystems:
                fs_input = fs_input.strip()
                if not fs_input:
                    continue
                    
                # Check if input looks like a filesystem ID or name
                if len(fs_input) == 32 and all(c in '0123456789ABCDEFabcdef' for c in fs_input):
                    # Input looks like a filesystem ID
                    filesystems.add(fs_input)
                    # Get virtual server for this filesystem
                    fs_info = hnas.get_filesystem_info(fs_input)
                    if fs_info:
                        vs_id = fs_info.get('filesystem', {}).get('virtualServerId')
                        if vs_id:
                            virtual_servers.add(vs_id)
                else:
                    # Input is a filesystem name, look up the ID
                    fs_info = hnas.get_filesystem_by_name(fs_input)
                    if fs_info:
                        filesystem_id = fs_info.get('filesystemId')
                        vs_id = fs_info.get('virtualServerId')
                        if filesystem_id:
                            filesystems.add(filesystem_id)
                        if vs_id:
                            virtual_servers.add(vs_id)
        
        # Clean up old snapshots
        for filesystem_id in filesystems:
            cleanup_count = hnas.cleanup_old_snapshots(
                filesystem_id, 
                config['app_search_id'], 
                config['retention_days']
            )
            if cleanup_count > 0:
                hnas.logger.info(f"Cleaned up {cleanup_count} old snapshots from filesystem '{filesystem_id}'")
        
        # Clean up old SMB shares
        for virtual_server_id in virtual_servers:
            cleanup_count = hnas.cleanup_old_smb_shares(
                virtual_server_id,
                config['smb_share_name'],
                config['retention_days']
            )
            if cleanup_count > 0:
                hnas.logger.info(f"Cleaned up {cleanup_count} old SMB shares from virtual server '{virtual_server_id}'")
    
    # Clean up snapshot info file if successful cleanup
    if should_cleanup and os.path.exists(snapshot_info_file):
        try:
            os.remove(snapshot_info_file)
            hnas.logger.info("Cleaned up snapshot information file")
        except Exception as e:
            hnas.logger.warning(f"Failed to clean up snapshot info file: {e}")
    
    hnas.logger.info(f"Post-backup script completed. Processed {len(created_snapshots)} snapshots from this session.")
    
    if should_cleanup:
        print(f"SUCCESS: Cleaned up {deleted_count} snapshots and associated SMB shares from current backup session.")
    else:
        print(f"SUCCESS: Post-backup processing completed. Snapshots and SMB shares retained based on configuration.")

if __name__ == "__main__":
    main()
