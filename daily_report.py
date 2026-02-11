"""
Main Daily Client Process Report Generator (Without Logging)

This script:
1. Connects to database and retrieves last 24h processes
2. Filters out test API keys (from folders_2_skip.txt)
3. Categorizes processes by status (finished, failed, etc.)
4. For finished processes: retrieves OneDrive video links
5. Generates and sends comprehensive email report
"""

import os
import sys
import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set
from dotenv import load_dotenv

# Import our custom modules
from db_connection import get_db_connection, DatabaseConnection
from onedrive_manager import OneDriveManager
from email_report import EmailReportGenerator

load_dotenv()


def load_skip_apikeys(skip_file: Path = Path("folders_2_skip.txt")) -> Set[str]:
    """
    Load API keys to skip from folders_2_skip.txt
    Returns set of API keys that should be filtered out (test accounts)
    """
    if not skip_file.exists():
        print(f"ℹ️  Skip file not found: {skip_file}")
        return set()
    
    skip_apikeys = set()
    with open(skip_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):  # Skip empty lines and comments
                skip_apikeys.add(line)
    
    if skip_apikeys:
        print(f"📋 Loaded {len(skip_apikeys)} API keys to skip from {skip_file}")
        for apikey in skip_apikeys:
            print(f"   ⏭️  Skipping: {apikey}")
    
    return skip_apikeys


class DailyReportOrchestrator:
    """Main orchestrator for daily client process reports"""
    
    def __init__(self):
        self.db = None
        self.onedrive_manager = None
        self.email_generator = None
        
        # Config from .env
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')
        self.output_dir = Path.home() / "daily_reports" / datetime.datetime.now().strftime('%Y%m%d')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load API keys to skip (test accounts)
        self.skip_apikeys = load_skip_apikeys()
        
    def initialize(self):
        """Initialize all components"""
        print("🚀 Initializing Daily Report System\n")
        
        # Database connection
        print("1️⃣  Connecting to database...")
        self.db = get_db_connection()
        
        # Log retriever
        print("2️⃣  Setting up log retriever...")
        logs_dir = os.getenv('LOGS_DIR')
        if logs_dir and os.path.exists(logs_dir):
            try:
                from log_retriever import LogRetriever
                self.log_retriever = LogRetriever(logs_dir)
                print(f"   ✅ Log retriever configured: {logs_dir}")
            except Exception as e:
                print(f"   ⚠️  Could not initialize log retriever: {e}")
                self.log_retriever = None
        else:
            print(f"   ⚠️  LOGS_DIR not configured or not accessible: {logs_dir}")
            print("   ℹ️  Failed process logs will not be included")
            self.log_retriever = None
        
        # OneDrive manager
        print("3️⃣  Connecting to OneDrive...")
        self.onedrive_manager = OneDriveManager()
        
        # Email generator
        print("4️⃣  Setting up email generator...")
        self.email_generator = EmailReportGenerator()
        
        print("\n✅ All components initialized\n")
    
    def fetch_processes(self) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
        """Fetch and categorize processes from database"""
        print("=" * 80)
        print("📊 FETCHING PROCESS DATA")
        print("=" * 80 + "\n")
        
        # Get all processes from database
        all_processes = self.db.get_last_24h_processes()
        
        # Filter out processes with test API keys
        if self.skip_apikeys:
            original_count = len(all_processes)
            all_processes = [
                p for p in all_processes 
                if p.get('api_key') not in self.skip_apikeys
            ]
            filtered_count = original_count - len(all_processes)
            if filtered_count > 0:
                print(f"🔍 Filtered out {filtered_count} test process(es)")
        
        # Categorize remaining processes
        categorized = self.db.categorize_processes(all_processes)
        
        return all_processes, categorized
    
    def process_failed_processes(self, failed_processes: List[Dict]) -> Dict[str, Any]:
        """Process all failed processes: retrieve logs if available"""
        print("\n" + "=" * 80)
        print("❌ PROCESSING FAILED PROCESSES")
        print("=" * 80 + "\n")
        
        if not failed_processes:
            print("✅ No failed processes found!")
            return {}
        
        print(f"⚠️  Found {len(failed_processes)} failed process(es)\n")
        
        # If log retriever is available, get logs
        if self.log_retriever:
            print("📝 Retrieving error logs...")
            failed_logs = self.log_retriever.get_failed_process_logs(
                failed_processes,
                output_dir=self.output_dir / "failed_logs"
            )
        else:
            print("ℹ️  Log retrieval not configured - reporting basic info only\n")
            # Return basic info without log extraction
            failed_logs = {}
            for process in failed_processes:
                process_uuid = process['process_uuid']
                failed_logs[process_uuid] = {
                    'found': False,
                    'log_file': None,
                    'summary': 'Log retrieval not configured',
                    'saved_path': None
                }
                print(f"   📝 {process['name']} - {process_uuid}")
        
        return failed_logs
    
    def process_finished_processes(self, finished_processes: List[Dict]) -> Dict[str, Any]:
        """Process all finished processes: get OneDrive links"""
        print("\n" + "=" * 80)
        print("✅ PROCESSING FINISHED PROCESSES")
        print("=" * 80 + "\n")
        
        if not finished_processes:
            print("ℹ️  No finished processes found")
            return {}
        
        # Get OneDrive links for finished processes
        finished_data = {}
        
        for process in finished_processes:
            process_uuid = process['process_uuid']
            client_name = process['name']
            api_key = process.get('api_key')
            
            if not api_key:
                print(f"\n⚠️  No API key found for client: {client_name}")
                print(f"   Skipping OneDrive search for {process_uuid}")
                finished_data[process_uuid] = {
                    'client_name': client_name,
                    'api_key': None,
                    'video_link': None,
                    'process': process
                }
                continue
            
            print(f"\n🔍 Processing: {client_name} (API key: {api_key}) - {process_uuid}")
            
            # Search for video in OneDrive using API key
            video_link = self.onedrive_manager.find_process_video(
                process_uuid=process_uuid,
                api_key=api_key
            )
            
            finished_data[process_uuid] = {
                'client_name': client_name,
                'api_key': api_key,
                'video_link': video_link,
                'process': process
            }
        
        return finished_data
    
    def generate_and_send_report(
        self,
        categorized_processes: Dict[str, List[Dict]],
        failed_logs: Dict[str, Any],
        finished_data: Dict[str, Any]
    ):
        """Generate comprehensive report and send via email"""
        print("\n" + "=" * 80)
        print("📧 GENERATING AND SENDING EMAIL REPORT")
        print("=" * 80 + "\n")
        
        # Generate report
        report = self.email_generator.generate_report(
            categorized_processes=categorized_processes,
            failed_logs=failed_logs,
            finished_data=finished_data
        )
        
        # Send email
        self.email_generator.send_report(
            report=report,
            recipient_email=self.notification_email
        )
        
        print("\n✅ Report sent successfully!")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.db:
            self.db.disconnect()
    
    def run(self):
        """Main execution flow"""
        try:
            # Initialize
            self.initialize()
            
            # Fetch process data
            all_processes, categorized = self.fetch_processes()
            
            # Process failed processes (without logs)
            failed_logs = self.process_failed_processes(categorized['failed'])
            
            # Process finished processes
            finished_data = self.process_finished_processes(categorized['finished'])
            
            # Generate and send report
            self.generate_and_send_report(categorized, failed_logs, finished_data)
            
            print("\n" + "=" * 80)
            print("🎉 DAILY REPORT GENERATION COMPLETE")
            print("=" * 80 + "\n")
            
        except Exception as e:
            print(f"\n❌ Error during report generation: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        finally:
            self.cleanup()


def main():
    """Entry point"""
    print("\n" + "=" * 80)
    print("CLIENT PROCESS DAILY REPORT")
    print(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")
    
    orchestrator = DailyReportOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()