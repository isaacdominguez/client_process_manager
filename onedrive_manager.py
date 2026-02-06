"""
OneDrive Manager for finding process videos and generating sharing links
"""

import os
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from msal import PublicClientApplication, SerializableTokenCache
from dotenv import load_dotenv

load_dotenv()


class OneDriveManager:
    """Manages OneDrive operations for process videos"""
    
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.tenant_id = os.getenv('TENANT_ID')
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["Files.Read", "User.Read"]
        self.onedrive_root = os.getenv('ONEDRIVE_ROOT')
        
        self.cache_file = Path.home() / ".msal_onedrive_cache.json"
        self.token = None
        self.headers = None
        
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Microsoft Graph API"""
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
        
        print("   ✅ OneDrive authentication successful")
    
    def search_files_recursive(
        self, 
        folder_path: str, 
        search_term: str
    ) -> List[Dict[str, Any]]:
        """
        Search for files recursively in a OneDrive folder
        """
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{folder_path}:/children"
        all_files = []
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            items = response.json().get("value", [])
            
            for item in items:
                # If it's a folder, search recursively
                if "folder" in item:
                    folder_name = item["name"]
                    subfolder_path = f"{folder_path}/{folder_name}"
                    all_files.extend(
                        self.search_files_recursive(subfolder_path, search_term)
                    )
                
                # If it's a file and matches search term
                elif "file" in item:
                    if search_term.lower() in item["name"].lower():
                        all_files.append(item)
            
            return all_files
            
        except requests.exceptions.HTTPError as e:
            print(f"   ⚠️  Error searching folder {folder_path}: {e}")
            return []
    
    def find_process_video(
        self, 
        process_uuid: str, 
        api_key: str
    ) -> Optional[str]:
        """
        Find video file for a specific process UUID
        Path structure: ONEDRIVE_ROOT/{api_key}/{process_uuid}/video.mp4
        Returns the OneDrive web URL if found
        """
        print(f"   Searching OneDrive for: {process_uuid}")
        
        # Correct path: api_key/process_uuid/
        process_folder = f"{self.onedrive_root}/{api_key}/{process_uuid}"
        
        print(f"   Looking in: {process_folder}")
        
        try:
            # Get files directly in the process folder
            url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{process_folder}:/children"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            items = response.json().get("value", [])
            
            # Find video files (mp4, avi, mov, etc.)
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
            
            for item in items:
                if "file" in item:
                    file_name = item["name"].lower()
                    if any(file_name.endswith(ext) for ext in video_extensions):
                        web_url = item.get("webUrl")
                        print(f"   ✅ Found: {item['name']}")
                        return web_url
            
            print(f"   ⚠️  No video found in {process_folder}")
            return None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"   ⚠️  Folder not found: {process_folder}")
            else:
                print(f"   ⚠️  Error accessing folder: {e}")
            return None
    
    def create_sharing_link(self, item_id: str) -> Optional[str]:
        """
        Create a sharing link for a OneDrive item
        """
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/createLink"
        
        payload = {
            "type": "view",  # view-only link
            "scope": "organization"  # accessible to your organization
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            link_data = response.json()
            return link_data.get("link", {}).get("webUrl")
            
        except requests.exceptions.HTTPError as e:
            print(f"   ⚠️  Error creating sharing link: {e}")
            return None
    
    def get_files_last_24h(self) -> List[Dict[str, Any]]:
        """
        Get all files uploaded to OneDrive in last 24 hours
        This is the original functionality from your script
        """
        import datetime
        from dateutil import tz
        
        now = datetime.datetime.now(tz=tz.UTC)
        since = now - datetime.timedelta(hours=24)
        
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{self.onedrive_root}:/children"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            all_files = self._list_files_recursive(url)
            
            # Filter by creation date
            recent_files = []
            for f in all_files:
                if "file" not in f:
                    continue
                
                created = datetime.datetime.fromisoformat(
                    f["createdDateTime"].replace("Z", "+00:00")
                )
                
                if created >= since:
                    recent_files.append({
                        "name": f["name"],
                        "url": f["webUrl"],
                        "created": created
                    })
            
            return recent_files
            
        except requests.exceptions.HTTPError as e:
            print(f"   ❌ Error fetching OneDrive files: {e}")
            return []
    
    def _list_files_recursive(self, url: str) -> List[Dict[str, Any]]:
        """Helper to recursively list files"""
        files = []
        stack = [url]
        
        while stack:
            current_url = stack.pop()
            
            try:
                resp = requests.get(current_url, headers=self.headers)
                resp.raise_for_status()
                
                for item in resp.json().get("value", []):
                    if "folder" in item:
                        folder_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{item['id']}/children"
                        stack.append(folder_url)
                    elif "file" in item:
                        files.append(item)
            
            except Exception as e:
                print(f"   Warning: Error processing {current_url}: {e}")
                continue
        
        return files


if __name__ == "__main__":
    # Test OneDrive manager
    print("Testing OneDrive Manager...\n")
    
    manager = OneDriveManager()
    
    # Test search
    test_uuid = "test-uuid-123"
    test_api_key = "test-api-key"
    
    video_link = manager.find_process_video(test_uuid, test_api_key)
    
    if video_link:
        print(f"\nFound video: {video_link}")
    else:
        print("\nNo video found (expected for test)")