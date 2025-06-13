#### SMB Share Creation Failed
**Error**: "Failed to create SMB share"
**Solutions**:
- Verify the virtual server supports CIFS/SMB protocol
- Check if the filesystem is mounted and accessible
- Ensure sufficient permissions for share creation
- Verify the snapshot path exists (\.snapshot\snapshot_name)# Hitachi HNAS Veeam Integration Setup Guide

This guide provides instructions for setting up Python-based pre and post backup scripts for Veeam Backup & Replication with Hitachi HNAS storage using REST APIs.

## Prerequisites

### Hardware/Software Requirements
- Hitachi NAS Platform with firmware 15.4.8300 or higher (for REST API v9.4 support)
- Veeam Backup & Replication 9.5 or later
- Python 3.6 or later installed on Veeam Backup Server
- Network connectivity between Veeam server and HNAS management interface on port 8444 (HTTPS)

### Python Dependencies
Install required Python packages on the Veeam Backup Server:

```bash
pip install requests urllib3
```

### HNAS Configuration
1. Ensure REST API is enabled on your HNAS system (enabled by default on firmware 15.4.8300+)
2. Create an API key using the CLI: `apikey-create "veeam-backup"` (recommended)
   - Alternatively, create a service account with appropriate permissions for snapshot operations
3. Note the filesystem IDs (not labels) you want to include in snapshot-based backups
4. Verify TCP port 8444 is accessible from the Veeam server to the HNAS management interface

## Installation Steps

### 1. Create Script Directory
Create a dedicated directory for the scripts on your Veeam Backup Server:

```cmd
mkdir C:\VeeamScripts
mkdir C:\VeeamScripts\Logs
```

### 2. Deploy Scripts
Save the provided Python scripts to the script directory:
- `hnas_pre_backup.py` - Pre-backup script
- `hnas_post_backup.py` - Post-backup script

### 3. Set Execute Permissions
Ensure the scripts are executable and accessible by the Veeam Backup Service account.

### 4. Configure Environment Variables
Create a batch file or PowerShell script to set environment variables and call the Python scripts:

#### Example: `hnas_pre_backup.bat`
```batch
@echo off
REM Hitachi HNAS Configuration
set HNAS_HOST=your-hnas-hostname-or-ip
set HNAS_USERNAME=apikey
set HNAS_PASSWORD=your-api-key-here
set HNAS_FILESYSTEMS=Filesystem1,Filesystem2,Filesystem3
set HNAS_APP_SEARCH_ID=veeam
set HNAS_RETENTION_INTERVAL=3600
set HNAS_VERIFY_SSL=false
set VEEAM_LOG_DIR=C:\VeeamScripts\Logs
set VEEAM_SNAPSHOT_INFO=C:\VeeamScripts\hnas_snapshot_info.json

REM Execute Python script
python C:\VeeamScripts\hnas_pre_backup.py
```

#### Example: `hnas_post_backup.bat`
```batch
@echo off
REM Hitachi HNAS Configuration
set HNAS_HOST=your-hnas-hostname-or-ip
set HNAS_USERNAME=apikey
set HNAS_PASSWORD=your-api-key-here
set HNAS_CLEANUP_ON_SUCCESS=false
set HNAS_CLEANUP_ON_FAILURE=true
set HNAS_RETENTION_DAYS=7
set HNAS_APP_SEARCH_ID=veeam
set HNAS_SMB_SHARE_NAME=VeeamNASBackup
set HNAS_VERIFY_SSL=false
set VEEAM_LOG_DIR=C:\VeeamScripts\Logs
set VEEAM_SNAPSHOT_INFO=C:\VeeamScripts\hnas_snapshot_info.json

REM Execute Python script
python C:\VeeamScripts\hnas_post_backup.py
```

## Configuration Parameters

### Required Parameters
| Parameter | Description | Example |
|-----------|-------------|---------|
| `HNAS_HOST` | HNAS hostname or IP address | `hnas.company.com` |
| `HNAS_USERNAME` | Either 'apikey' for API key auth or username | `apikey` |
| `HNAS_PASSWORD` | API key (recommended) or user password | `xIAdbgTNVP.Nj2TOgxiOYgpTu2kjzEGS4QmIJIeLmF3aXKg6FhY9vC` |
| `HNAS_FILESYSTEMS` | Comma-separated list of filesystem names or IDs | `Filesystem1,Filesystem2` or `7B263DFD1D71E65A0000000000000000,7B263DFD1D71E65B0000000000000000` |

### Optional Parameters
| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `HNAS_APP_SEARCH_ID` | Application prefix for snapshot names | `veeam` | Any string |
| `HNAS_RETENTION_INTERVAL` | Snapshot retention in seconds (0=no retention) | `0` | Any integer |
| `HNAS_CREATE_SMB_SHARE` | Create SMB shares for snapshots | `true` | `true`, `false` |
| `HNAS_SMB_SHARE_NAME` | Base name for SMB shares (timestamp will be appended) | `VeeamNASBackup` | Any valid share name |
| `HNAS_VERIFY_SSL` | Verify SSL certificates | `false` | `true`, `false` |
| `HNAS_CLEANUP_ON_SUCCESS` | Delete snapshots after successful backup | `false` | `true`, `false` |
| `HNAS_CLEANUP_ON_FAILURE` | Delete snapshots after failed backup | `true` | `true`, `false` |
| `HNAS_RETENTION_DAYS` | Days to retain old snapshots | `7` | Any integer |
| `VEEAM_LOG_DIR` | Directory for log files | `C:\VeeamScripts\Logs` | Any valid path |
| `VEEAM_SNAPSHOT_INFO` | Path for snapshot metadata file | `C:\VeeamScripts\hnas_snapshot_info.json` | Any valid path |

## Veeam Job Configuration

### 1. Create or Edit Backup Job
1. Open Veeam Backup & Replication Console
2. Create a new backup job or edit an existing one
3. Configure your backup source (VMs, file shares, etc.)

### 2. Configure Advanced Settings
1. In the backup job wizard, click **Advanced**
2. Navigate to the **Scripts** tab
3. Configure as follows:
   - **Run the following script before the job**: Check this option
   - **Browse** and select: `C:\VeeamScripts\hnas_pre_backup.bat`
   - **Run the following script after the job**: Check this option
   - **Browse** and select: `C:\VeeamScripts\hnas_post_backup.bat`

### 3. Job Schedule and Options
Configure your backup job schedule and other settings as normal.

## Security Considerations

### Credential Management
- **Environment Variables**: Consider using encrypted credential storage instead of plain text
- **Service Accounts**: Create dedicated HNAS service accounts with minimal required permissions
- **Password Security**: Store passwords in Veeam credential manager or Windows Credential Store
- **SSL/TLS**: Enable SSL verification in production environments with proper certificates

### HNAS Permissions
The HNAS user account or API key needs the following minimum permissions:
- Read access to filesystem and virtual server information
- Create/delete snapshot permissions
- Create/delete CIFS/SMB share permissions
- Access to REST API endpoints (port 8444)

For API keys, you can restrict access using API key groups:
```bash
# Create API key group for backup operations
apikey-group-create --name backup-ops --add-api-calls getFilesystems,getFilesystem,createFilesystemSnapshot,deleteFilesystemSnapshot,getFilesystemSnapshots,createFilesystemShare,deleteFilesystemShare,getFilesystemShares

# Restrict API key to backup operations only
apikey-restrict --description veeam-backup --apikey-groups backup-ops
```

### Network Security
- Ensure HNAS management interface is on a secure network
- Use firewall rules to restrict access to HNAS from only the Veeam server
- Consider using HTTPS with proper certificate validation

## Troubleshooting

### Common Issues

#### Connection Problems
**Error**: "Failed to connect to HNAS"
**Solutions**:
- Verify HNAS hostname/IP is correct and reachable
- Check if REST API is enabled on HNAS
- Validate username/password credentials
- Ensure firewall allows connections to HNAS management interface

#### Authentication Failures
**Error**: "HTTP 401 Unauthorized"
**Solutions**:
- Verify HNAS username and password
- Check if account is locked or expired
- Ensure account has necessary permissions for snapshot operations

#### Filesystem Not Found
**Error**: "Could not find filesystem with name"
**Solutions**:
- Verify filesystem names are correct (case-sensitive)
- Use `GET /v9/storage/filesystems` to list available filesystems
- Ensure filesystems are mounted and accessible
- Check if you have permissions to access the filesystem

#### Script Execution Issues
**Error**: Script fails to run in Veeam
**Solutions**:
- Check Python is installed and in system PATH
- Verify script file permissions
- Review Veeam job logs for detailed error messages
- Test scripts manually from command line

### Log Analysis
Check the following log locations:
- Script logs: `C:\VeeamScripts\Logs\hnas_*_backup_YYYYMMDD.log`
- Veeam job logs: Veeam Console → History → Job Session Details
- Windows Event Log: Application and System logs

### Testing Scripts
Test the scripts manually before using with Veeam:

```cmd
# Set environment variables
set HNAS_HOST=your-hnas-ip
set HNAS_USERNAME=apikey
set HNAS_PASSWORD=your-api-key
set HNAS_FILESYSTEMS=Filesystem1,Filesystem2

# Test pre-backup script
python C:\VeeamScripts\hnas_pre_backup.py

# Check if snapshots were created
# Test post-backup script
python C:\VeeamScripts\hnas_post_backup.py
```

## Advanced Configuration

### Custom Snapshot Naming
Modify the snapshot naming convention by changing the `app_search_id` and timestamp format in the scripts:

```python
# In hnas_pre_backup.py, modify this section:
if config['app_search_id']:
    snapshot_name = f"{config['app_search_id']}_{filesystem_name}_{timestamp}"
else:
    snapshot_name = f"veeam_{filesystem_name}_{timestamp}"

# Example custom format:
snapshot_name = f"VBR_{job_name}_{filesystem_name}_{timestamp}"
```

### Multiple Filesystem Support
The scripts now support both filesystem names and IDs. You can mix both in the same configuration:

```python
# Example configuration for mixed filesystem identifiers
filesystems_config = {
    'Filesystem1': {'type': 'name'},
    '7B263DFD1D71E65A0000000000000000': {'type': 'id'},
    'Production_Data': {'type': 'name'}
}
```

### Integration with Veeam PowerShell
You can also call these Python scripts from PowerShell for better Veeam integration:

```powershell
# hnas_pre_backup.ps1
$env:HNAS_HOST = "your-hnas-ip"
$env:HNAS_USERNAME = "apikey"
$env:HNAS_PASSWORD = "your-api-key"
$env:HNAS_FILESYSTEMS = "Filesystem1,Filesystem2"

$result = & python "C:\VeeamScripts\hnas_pre_backup.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Pre-backup script failed"
    exit 1
}
```

### Monitoring and Alerting
Consider implementing additional monitoring:
- Email notifications on script failures
- Integration with monitoring systems (SCOM, Nagios, etc.)
- Custom performance counters for snapshot operations

## API Reference

### Key HNAS REST API Endpoints Used

#### Device Information
```
GET /api/v7/device
```

#### Filesystem Operations
```
GET /v9/storage/filesystems
GET /v9/storage/filesystems/{filesystemId}
```

#### Snapshot Operations
```
GET /v9/storage/filesystem-snapshots/{filesystemId}/{appSearchId}
POST /v9/storage/filesystem-snapshots
GET /v9/storage/filesystem-snapshots/{snapshotObjectId}
DELETE /v9/storage/filesystem-snapshots/{snapshotObjectId}
```

### Example API Payloads

#### Create Snapshot
```json
{
    "filesystemId": "7B263DFD1D71E65A0000000000000000",
    "displayName": "veeam_Filesystem1_20250610_143022",
    "appSearchId": "veeam",
    "retentionInterval": 3600
}
```

## Best Practices

### Performance Considerations
- Limit the number of concurrent snapshot operations
- Monitor HNAS performance during backup windows
- Consider staggering backup jobs to reduce storage load

### Snapshot Management
- Implement proper retention policies to prevent storage exhaustion
- Monitor snapshot space consumption
- Use descriptive snapshot names for easier management

### Backup Strategy
- Test restore procedures regularly using snapshots
- Combine with traditional backup methods for comprehensive protection
- Document snapshot schedules and retention policies

### Change Management
- Test script modifications in non-production environments first
- Maintain version control for script changes
- Document any customizations made to the base scripts

## Support and Maintenance

### Regular Tasks
- Review and rotate log files
- Monitor script execution success rates
- Update scripts when HNAS firmware is upgraded
- Validate backup and restore procedures

### Version Compatibility
- HNAS Platform 15.4.8300+ required for REST API v9.4
- Test scripts with new HNAS firmware versions before upgrading
- Monitor Hitachi documentation for API changes

For additional support, consult:
- Hitachi Vantara documentation portal
- Veeam Backup & Replication user guide
- Your storage and backup administrators