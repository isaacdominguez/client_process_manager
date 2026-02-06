"""
Email Report Generator for Daily Client Process Reports
"""

import os
import requests
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
from msal import PublicClientApplication, SerializableTokenCache
from dotenv import load_dotenv

load_dotenv()


class EmailReportGenerator:
    """Generates and sends HTML email reports"""
    
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.tenant_id = os.getenv('TENANT_ID')
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["Mail.Send", "User.Read"]
        
        self.cache_file = Path.home() / ".msal_mail_cache.json"
        self.token = None
        self.headers = None
        self.user_email = None
        
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Microsoft Graph API for sending emails"""
        cache = SerializableTokenCache()
        if self.cache_file.exists():
            cache.deserialize(self.cache_file.read_text())
        
        app = PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=cache
        )
        
        accounts = app.get_accounts()
        token = None
        
        if accounts:
            print(f"   Using cached account: {accounts[0]['username']}")
            self.user_email = accounts[0]['username']
            token = app.acquire_token_silent(self.scopes, account=accounts[0])
        
        if not token:
            print("   No cached token, initiating device flow...")
            flow = app.initiate_device_flow(scopes=self.scopes)
            if "user_code" not in flow:
                raise RuntimeError("Failed to start device flow")
            print("\n" + "=" * 60)
            print(flow["message"])
            print("=" * 60 + "\n")
            token = app.acquire_token_by_device_flow(flow)
        
        if "access_token" not in token:
            raise RuntimeError(f"Auth failed: {token}")
        
        if cache.has_state_changed:
            self.cache_file.write_text(cache.serialize())
        
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "Content-Type": "application/json"
        }
        
        print("   ✅ Email authentication successful")
    
    def generate_report(
        self,
        categorized_processes: Dict[str, List[Dict]],
        failed_logs: Dict[str, Any],
        finished_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate HTML and text versions of the report
        """
        now = datetime.now()
        
        # Generate HTML report
        html_body = self._generate_html_report(
            categorized_processes,
            failed_logs,
            finished_data,
            now
        )
        
        # Generate plain text report (fallback)
        text_body = self._generate_text_report(
            categorized_processes,
            failed_logs,
            finished_data,
            now
        )
        
        subject = f"Daily Client Process Report - {now.strftime('%Y-%m-%d')}"
        
        return {
            'subject': subject,
            'html_body': html_body,
            'text_body': text_body
        }
    
    def _generate_html_report(
        self,
        categorized: Dict[str, List[Dict]],
        failed_logs: Dict[str, Any],
        finished_data: Dict[str, Any],
        timestamp: datetime
    ) -> str:
        """Generate HTML formatted report"""
        
        # Summary counts
        total_processes = sum(len(procs) for procs in categorized.values())
        failed_count = len(categorized['failed'])
        finished_count = len(categorized['finished'])
        running_count = len(categorized['running'])
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .summary {{ background: #ecf0f1; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .section {{ margin: 20px 0; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
        .process-card {{ background: #fff; border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .failed {{ border-left: 4px solid #e74c3c; }}
        .finished {{ border-left: 4px solid #27ae60; }}
        .running {{ border-left: 4px solid #f39c12; }}
        .log-snippet {{ background: #2c3e50; color: #ecf0f1; padding: 10px; border-radius: 3px; font-family: monospace; font-size: 12px; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #3498db; color: white; }}
        .status-badge {{ padding: 3px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; }}
        .badge-failed {{ background: #e74c3c; color: white; }}
        .badge-finished {{ background: #27ae60; color: white; }}
        .badge-running {{ background: #f39c12; color: white; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Daily Client Process Report</h1>
        <p>Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="summary">
        <h2>📈 Summary</h2>
        <table>
            <tr>
                <th>Total Processes</th>
                <th>✅ Finished</th>
                <th>❌ Failed</th>
                <th>⏳ Running</th>
            </tr>
            <tr>
                <td><strong>{total_processes}</strong></td>
                <td><span class="status-badge badge-finished">{finished_count}</span></td>
                <td><span class="status-badge badge-failed">{failed_count}</span></td>
                <td><span class="status-badge badge-running">{running_count}</span></td>
            </tr>
        </table>
    </div>
"""
        
        # Failed Processes Section
        if categorized['failed']:
            html += """
    <div class="section">
        <h2 class="section-title">❌ Failed Processes</h2>
"""
            for process in categorized['failed']:
                uuid = process['process_uuid']
                log_info = failed_logs.get(uuid, {})
                
                html += f"""
        <div class="process-card failed">
            <h3>{process['name']}</h3>
            <table>
                <tr><td><strong>Process UUID:</strong></td><td>{uuid}</td></tr>
                <tr><td><strong>Status:</strong></td><td>{process['status_name']}</td></tr>
                <tr><td><strong>Start Time:</strong></td><td>{process['start_time']}</td></tr>
                <tr><td><strong>Source:</strong></td><td>{process.get('source_alias', 'N/A')}</td></tr>
            </table>
"""
                
                if log_info.get('found'):
                    summary = log_info.get('summary', '').replace('\n', '<br>')
                    html += f"""
            <h4>🔍 Error Summary:</h4>
            <div class="log-snippet">{summary}</div>
            <p><small>Full log available at: {log_info.get('saved_path', 'N/A')}</small></p>
"""
                else:
                    html += """
            <p><em>⚠️ Log file not found</em></p>
"""
                
                html += """
        </div>
"""
            html += """
    </div>
"""
        
        # Finished Processes Section
        if categorized['finished']:
            html += """
    <div class="section">
        <h2 class="section-title">✅ Finished Processes</h2>
"""
            for process in categorized['finished']:
                uuid = process['process_uuid']
                data = finished_data.get(uuid, {})
                video_link = data.get('video_link')
                
                html += f"""
        <div class="process-card finished">
            <h3>{process['name']}</h3>
            <table>
                <tr><td><strong>Process UUID:</strong></td><td>{uuid}</td></tr>
                <tr><td><strong>Status:</strong></td><td>{process['status_name']}</td></tr>
                <tr><td><strong>Start Time:</strong></td><td>{process['start_time']}</td></tr>
                <tr><td><strong>Stop Time:</strong></td><td>{process.get('stop_time', 'N/A')}</td></tr>
                <tr><td><strong>Duration:</strong></td><td>{process.get('elapsed_time_min', 'N/A')} min</td></tr>
                <tr><td><strong>Source:</strong></td><td>{process.get('source_alias', 'N/A')}</td></tr>
"""
                
                if video_link:
                    html += f"""
                <tr><td><strong>📹 Video:</strong></td><td><a href="{video_link}">View in OneDrive</a></td></tr>
"""
                else:
                    html += """
                <tr><td><strong>📹 Video:</strong></td><td><em>Not found in OneDrive</em></td></tr>
"""
                
                html += """
            </table>
        </div>
"""
            html += """
    </div>
"""
        
        # Running Processes Section
        if categorized['running']:
            html += """
    <div class="section">
        <h2 class="section-title">⏳ Running Processes</h2>
"""
            for process in categorized['running']:
                html += f"""
        <div class="process-card running">
            <h3>{process['name']}</h3>
            <table>
                <tr><td><strong>Process UUID:</strong></td><td>{process['process_uuid']}</td></tr>
                <tr><td><strong>Status:</strong></td><td>{process['status_name']}</td></tr>
                <tr><td><strong>Start Time:</strong></td><td>{process['start_time']}</td></tr>
                <tr><td><strong>Elapsed:</strong></td><td>{process.get('elapsed_time_min', 'N/A')} min</td></tr>
            </table>
        </div>
"""
            html += """
    </div>
"""
        
        html += """
    <div class="section">
        <p style="color: #7f8c8d; font-size: 12px;">
            <em>This is an automated report generated by the Client Process Monitoring System.</em>
        </p>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_text_report(
        self,
        categorized: Dict[str, List[Dict]],
        failed_logs: Dict[str, Any],
        finished_data: Dict[str, Any],
        timestamp: datetime
    ) -> str:
        """Generate plain text version of report"""
        
        lines = []
        lines.append("=" * 80)
        lines.append("DAILY CLIENT PROCESS REPORT")
        lines.append(f"Generated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)
        lines.append("")
        
        # Summary
        total = sum(len(procs) for procs in categorized.values())
        lines.append(f"Total Processes: {total}")
        lines.append(f"  ✅ Finished: {len(categorized['finished'])}")
        lines.append(f"  ❌ Failed: {len(categorized['failed'])}")
        lines.append(f"  ⏳ Running: {len(categorized['running'])}")
        lines.append("")
        
        # Failed processes
        if categorized['failed']:
            lines.append("-" * 80)
            lines.append("FAILED PROCESSES")
            lines.append("-" * 80)
            for process in categorized['failed']:
                lines.append(f"\nClient: {process['name']}")
                lines.append(f"UUID: {process['process_uuid']}")
                lines.append(f"Status: {process['status_name']}")
                lines.append(f"Start: {process['start_time']}")
                
                log_info = failed_logs.get(process['process_uuid'], {})
                if log_info.get('found'):
                    lines.append(f"Log: {log_info.get('saved_path', 'N/A')}")
            lines.append("")
        
        # Finished processes
        if categorized['finished']:
            lines.append("-" * 80)
            lines.append("FINISHED PROCESSES")
            lines.append("-" * 80)
            for process in categorized['finished']:
                data = finished_data.get(process['process_uuid'], {})
                lines.append(f"\nClient: {process['name']}")
                lines.append(f"UUID: {process['process_uuid']}")
                lines.append(f"Duration: {process.get('elapsed_time_min', 'N/A')} min")
                
                if data.get('video_link'):
                    lines.append(f"Video: {data['video_link']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def send_report(self, report: Dict[str, str], recipient_email: str = None):
        """Send email report via Microsoft Graph API"""
        
        if recipient_email is None:
            recipient_email = self.user_email
        
        print(f"   Sending report to: {recipient_email}")
        
        url = "https://graph.microsoft.com/v1.0/me/sendMail"
        
        payload = {
            "message": {
                "subject": report['subject'],
                "body": {
                    "contentType": "HTML",
                    "content": report['html_body']
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": recipient_email
                        }
                    }
                ]
            },
            "saveToSentItems": True
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            print("   ✅ Email sent successfully!")
        
        except requests.exceptions.HTTPError as e:
            print(f"   ❌ Failed to send email: {e}")
            print(f"   Response: {response.text}")
            raise


if __name__ == "__main__":
    # Test email generator
    print("Testing Email Generator...\n")
    
    generator = EmailReportGenerator()
    
    # Create sample report
    sample_categorized = {
        'finished': [],
        'failed': [],
        'running': [],
        'other': []
    }
    
    report = generator.generate_report(sample_categorized, {}, {})
    
    print("\nSample report subject:", report['subject'])
    print("\nHTML length:", len(report['html_body']))
    print("Text length:", len(report['text_body']))