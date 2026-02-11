"""
Log retrieval and processing module for failed processes
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import gzip
from datetime import datetime


class LogRetriever:
    """Handles retrieval and filtering of process logs"""
    
    def __init__(self, logs_dir: str):
        self.logs_dir = Path(logs_dir)
        if not self.logs_dir.exists():
            raise FileNotFoundError(f"Logs directory not found: {logs_dir}")
    
    def find_log_file(self, process_uuid: str, start_time: datetime) -> Optional[Path]:
        """
        Find the log file for a specific process UUID
        Log file pattern: YYYY-MM-DDTHH-MM-SS_perception_api.log
        
        Strategy:
        1. Find log files from the same date as start_time
        2. Check if they contain the process_uuid
        """
        # Format the date for log file matching
        # Logs use: 2026-02-06T03-08-14_perception_api.log
        date_str = start_time.strftime('%Y-%m-%d')
        
        print(f"   Searching for logs from {date_str}...")
        
        # Find all log files from that date
        pattern = f"{date_str}T*_perception_api.log"
        matching_files = list(self.logs_dir.glob(pattern))
        
        if not matching_files:
            print(f"   ⚠️  No log files found matching pattern: {pattern}")
            return None
        
        print(f"   Found {len(matching_files)} log file(s) from {date_str}")
        
        # Search each file for the process UUID
        for log_file in sorted(matching_files):
            # Parse log file timestamp to check if it's around the start_time
            try:
                # Extract timestamp from filename: 2026-02-06T03-08-14
                filename = log_file.stem  # Remove .log extension
                timestamp_str = filename.split('_')[0]  # Get the datetime part
                log_time = datetime.strptime(timestamp_str, '%Y-%m-%dT%H-%M-%S')
                
                # Only check files that started before or around the process start time
                # (with 1 hour buffer)
                time_diff = (start_time - log_time).total_seconds()
                if time_diff < -3600 or time_diff > 86400:  # -1h to +24h window
                    continue
                
            except Exception as e:
                print(f"   Warning: Could not parse timestamp from {log_file.name}: {e}")
                # Still check the file if we can't parse the timestamp
            
            # Check if this log file contains the process UUID
            if self._contains_uuid(log_file, process_uuid):
                print(f"   ✅ Found log file: {log_file.name}")
                return log_file
        
        print(f"   ⚠️  Process UUID {process_uuid} not found in any log files")
        return None
    
    def _contains_uuid(self, log_file: Path, process_uuid: str) -> bool:
        """Check if log file contains the process UUID"""
        try:
            if log_file.suffix == '.gz':
                with gzip.open(log_file, 'rt') as f:
                    for line in f:
                        if process_uuid in line:
                            return True
            else:
                with open(log_file, 'r') as f:
                    for line in f:
                        if process_uuid in line:
                            return True
        except Exception as e:
            print(f"Warning: Could not read {log_file}: {e}")
        return False
    
    def extract_process_logs(self, log_file: Path, process_uuid: str) -> List[str]:
        """
        Extract all log lines related to a specific process UUID
        """
        if not log_file or not log_file.exists():
            return []
        
        process_lines = []
        
        try:
            if log_file.suffix == '.gz':
                with gzip.open(log_file, 'rt') as f:
                    process_lines = [line for line in f if process_uuid in line]
            else:
                with open(log_file, 'r') as f:
                    process_lines = [line for line in f if process_uuid in line]
            
            print(f"📝 Extracted {len(process_lines)} log lines for {process_uuid}")
            return process_lines
            
        except Exception as e:
            print(f"❌ Error reading log file {log_file}: {e}")
            return []
    
    def extract_error_summary(self, log_lines: List[str], max_lines: int = 50) -> str:
        """
        Extract error summary from log lines
        Focuses on ERROR, EXCEPTION, TRACEBACK, etc.
        """
        if not log_lines:
            return "No log data available"
        
        # Patterns to identify important log lines
        important_patterns = [
            r'ERROR',
            r'EXCEPTION',
            r'TRACEBACK',
            r'CRITICAL',
            r'FATAL',
            r'Failed',
            r'Exception:',
        ]
        
        important_lines = []
        for line in log_lines:
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in important_patterns):
                important_lines.append(line)
        
        # If we have important lines, use those; otherwise use last N lines
        if important_lines:
            result_lines = important_lines[-max_lines:]
            header = f"=== Error Summary ({len(important_lines)} error lines found) ===\n\n"
        else:
            result_lines = log_lines[-max_lines:]
            header = f"=== Last {len(result_lines)} log lines ===\n\n"
        
        return header + "".join(result_lines)
    
    def save_process_log(self, process_uuid: str, log_content: str, output_dir: Path) -> Path:
        """
        Save extracted process logs to a file
        Returns the path to the saved file
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"{process_uuid}_{timestamp}.log"
        
        with open(output_file, 'w') as f:
            f.write(log_content)
        
        print(f"💾 Saved process log to: {output_file}")
        return output_file
    
    def get_failed_process_logs(
        self, 
        failed_processes: List[Dict[str, Any]], 
        output_dir: Optional[Path] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get logs for all failed processes
        Returns dict mapping process_uuid to log info
        """
        if output_dir is None:
            output_dir = Path.home() / "failed_process_logs"
        
        results = {}
        
        for process in failed_processes:
            process_uuid = process['process_uuid']
            start_time = process['start_time']
            
            print(f"\n🔍 Searching logs for process: {process_uuid}")
            
            # Find log file
            log_file = self.find_log_file(process_uuid, start_time)
            
            if not log_file:
                print(f"⚠️  No log file found for {process_uuid}")
                results[process_uuid] = {
                    'found': False,
                    'log_file': None,
                    'summary': 'Log file not found',
                    'saved_path': None
                }
                continue
            
            # Extract process logs
            log_lines = self.extract_process_logs(log_file, process_uuid)
            
            # Create summary
            summary = self.extract_error_summary(log_lines)
            full_log = "".join(log_lines)
            
            # Save to file
            saved_path = self.save_process_log(process_uuid, full_log, output_dir)
            
            results[process_uuid] = {
                'found': True,
                'log_file': str(log_file),
                'summary': summary,
                'full_log': full_log,
                'saved_path': str(saved_path),
                'line_count': len(log_lines)
            }
        
        return results


if __name__ == "__main__":
    # Test log retrieval
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    logs_dir = os.getenv('LOGS_DIR', '/var/log')
    
    print(f"Testing log retrieval from: {logs_dir}\n")
    
    # Example usage
    try:
        retriever = LogRetriever(logs_dir)
        
        # Test with a sample process
        test_process = {
            'process_uuid': 'test-uuid-123',
            'start_time': datetime.now()
        }
        
        log_file = retriever.find_log_file(
            test_process['process_uuid'],
            test_process['start_time']
        )
        
        if log_file:
            print(f"Found log file: {log_file}")
        else:
            print("No log file found (this is expected if testing)")
            
    except FileNotFoundError as e:
        print(f"Note: {e}")
        print("This is normal if the logs directory doesn't exist yet")