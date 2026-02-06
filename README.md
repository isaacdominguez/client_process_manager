# Client Process Daily Report System

Automated daily reporting system that monitors client processes, retrieves logs for failures, finds OneDrive videos for successful processes, and sends comprehensive email reports.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Daily Report Orchestrator                    │
│                      (daily_report.py)                           │
└───────┬─────────────────┬─────────────────┬─────────────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Database   │  │     Logs     │  │   OneDrive   │
│  Connection  │  │  Retriever   │  │   Manager    │
│              │  │              │  │              │
│ - Query DB   │  │ - Find logs  │  │ - Auth Graph │
│ - Get procs  │  │ - Extract    │  │ - Find video │
│ - Categorize │  │ - Summarize  │  │ - Get links  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
                         ▼
                ┌──────────────────┐
                │  Email Report    │
                │   Generator      │
                │                  │
                │ - Build HTML     │
                │ - Send via Graph │
                └──────────────────┘
                         │
                         ▼
                   📧 Email Sent
```

## 🎯 Features

1. **Database Integration**: Connects to PostgreSQL to retrieve process data from last 24 hours
2. **Failed Process Handling**: Extracts and summarizes error logs for failed processes
3. **Success Tracking**: Finds OneDrive video links for finished processes
4. **Email Reports**: Sends beautiful HTML email reports with all information
5. **Automatic Client Mapping**: Uses database to map API keys to client names (no more text files!)

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL database with process tracking
- Microsoft 365 / Azure AD account
- OneDrive with synced process videos
- Access to process log files

## 🚀 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
nano .env
```

Required variables:
```env
# Database
DB_HOST=your_postgres_host
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password

# Azure AD (from app registration)
CLIENT_ID=your_client_id
TENANT_ID=your_tenant_id

# OneDrive
ONEDRIVE_ROOT=SenseAeronautics/Videos/Client/Production_Sources_Backup

# Logs
LOGS_DIR=/path/to/your/process/logs

# Email (optional)
NOTIFICATION_EMAIL=your.email@company.com
```

### 3. Configure Test API Keys to Skip (Optional)

Create a `folders_2_skip.txt` file to exclude test/staging accounts:

```bash
cp folders_2_skip.txt.example folders_2_skip.txt
nano folders_2_skip.txt
```

Add one API key per line:
```
# Test accounts to skip
test-api-key-1
staging-account-key
internal-testing
```

Lines starting with `#` are treated as comments and ignored.

### 3. Update Database View

Make sure your database has the `processes_dashboard` view with 24-hour filter:

```sql
DROP VIEW IF EXISTS processes_dashboard;
CREATE VIEW processes_dashboard AS
SELECT
    u.name,
    (SELECT name FROM process_status ps WHERE ps.id = p.status_id) AS status_name,
    p.start_time,
    p.ping_time,
    p.stop_time,
    ROUND(EXTRACT(EPOCH FROM (p.ping_time - p.start_time)) / 60, 1) AS "Elapsed Time (min)",
    s.uri AS source_uri,
    s.alias AS source_alias,
    s.uuid AS source_uuid,
    p.uuid AS process_uuid,
    p.user_configuration
FROM
    process p
    JOIN source s ON p.source_id = s.id
    JOIN "USER" u ON u.id = s.user_id
WHERE
    p.start_time > now() - interval '24 hours'
    AND u.role_id = 2
ORDER BY
    p.start_time DESC;
```

### 4. Azure AD App Permissions

Your app registration needs these **delegated permissions**:
- `Files.Read` - Read OneDrive files
- `Mail.Send` - Send emails
- `User.Read` - Read user profile

## 📊 Project Structure

```
.
├── daily_report.py          # Main orchestrator
├── db_connection.py         # Database queries
├── log_retriever.py         # Log extraction
├── onedrive_manager.py      # OneDrive operations
├── email_report.py          # Email generation
├── requirements.txt         # Python dependencies
├── folders_2_skip.txt       # Test API keys to exclude (create from .example)
├── .env                     # Configuration (create from .env.example)
└── README.md               # This file
```

## 🏃 Usage

### Manual Execution

Run the daily report:

```bash
python daily_report.py
```

First run will prompt for device authentication:
1. You'll see a code like `ABC123XYZ`
2. Go to https://microsoft.com/devicelogin
3. Enter the code and sign in
4. Subsequent runs use cached tokens

### Automated Daily Execution

Add to crontab for daily 8am execution:

```bash
crontab -e
```

Add this line:
```cron
0 8 * * * cd /path/to/project && /usr/bin/python3 daily_report.py >> /var/log/daily_report.log 2>&1
```

## 📧 Email Report Contents

The HTML email report includes:

### Summary Section
- Total processes count
- Breakdown by status (Finished, Failed, Running)

### Failed Processes Section (if any)
- Client name
- Process UUID
- Status and timestamps
- **Error log summary** (extracted automatically)
- Link to full log file

### Finished Processes Section
- Client name
- Process UUID
- Duration
- **OneDrive video link** (if found)
- Source information

### Running Processes Section
- Currently active processes
- Elapsed time

## 🔧 Module Details

### db_connection.py
- Connects to PostgreSQL database
- Queries `processes_dashboard` view
- Categorizes processes by status
- Retrieves client API key mappings

### log_retriever.py
- Searches for process log files
- Extracts lines matching process UUID
- Creates error summaries
- Saves extracted logs to files

### onedrive_manager.py
- Authenticates with Microsoft Graph API
- Searches OneDrive recursively
- Finds videos by process UUID
- Returns web URLs for sharing

### email_report.py
- Generates beautiful HTML reports
- Creates plain text fallback
- Sends emails via Microsoft Graph API
- Handles authentication

### daily_report.py
- Orchestrates entire workflow
- Coordinates all modules
- Handles errors gracefully
- Provides detailed logging

## 🧪 Testing Individual Modules

Each module can be tested independently:

```bash
# Test database connection
python db_connection.py

# Test log retrieval
python log_retriever.py

# Test OneDrive connection
python onedrive_manager.py

# Test email generation
python email_report.py
```

## 🐛 Troubleshooting

### Database Connection Issues
```
❌ Database connection failed
```
**Solution**: Check your `.env` file has correct database credentials

### Authentication Problems
```
Need admin approval
```
**Solution**: Make sure you're using `Files.Read` (not `Files.Read.All`) and admin has granted consent

### Log Files Not Found
```
⚠️ No log file found for process UUID
```
**Solution**: 
- Verify `LOGS_DIR` in `.env` points to correct location
- Check log file naming pattern in `log_retriever.py`
- Ensure process logs include the process UUID

### OneDrive Videos Not Found
```
⚠️ No video found for process
```
**Solution**:
- Verify video files are synced to OneDrive
- Check folder structure matches `ONEDRIVE_ROOT`
- Ensure video filenames contain process UUID

## 📝 Customization

### Modify Log Search Pattern

Edit `log_retriever.py`, function `find_log_file()`:

```python
patterns = [
    f"*{process_uuid}*.log",      # Your custom pattern
    f"app_{date}*.log",           # Add more patterns
]
```

### Change Email Template

Edit `email_report.py`, function `_generate_html_report()` to customize the HTML template.

### Adjust Time Window

To change from 24 hours to different duration:

1. Update database view interval
2. Modify `daily_report.py` if needed

## 🔐 Security Notes

- `.env` file contains sensitive credentials - **never commit to git**
- Add `.env` to `.gitignore`
- Token cache files (`.msal_*.json`) are stored in user home directory
- Log files may contain sensitive information - handle appropriately

## 📅 Maintenance

### Clear Token Cache

If authentication issues occur, clear the cache:

```bash
rm ~/.msal_onedrive_cache.json
rm ~/.msal_mail_cache.json
```

Next run will re-authenticate.

### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

## 🤝 Support

For issues or questions:
1. Check troubleshooting section
2. Review module test outputs
3. Check log files for detailed errors

## 📜 License

Internal use only - Sense Aeronautics

---

**Generated**: 2026-02-06
**Version**: 1.0