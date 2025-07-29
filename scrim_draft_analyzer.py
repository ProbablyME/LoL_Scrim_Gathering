#!/usr/bin/env python3
"""
Comprehensive script to:
1. Download new scrim data incrementally
2. Analyze draft information
3. Update Google Sheets with results
"""

import os
import sys
import json
import time
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
from itertools import permutations

# Constants
GRID_API_KEY = "e5ikERczUjDeO6ReBanLlyZ4sc07dKNIOtVJcexP"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TRACKING_FILE = "processed_scrims.json"
DOWNLOADS_DIR = Path("./scrim_downloads")
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"

# Add local packages to path (handle both Windows and Linux)
possible_paths = [
    os.path.expanduser('~/.local/lib/python3.12/site-packages'),  # Linux
    os.path.expanduser('~/AppData/Roaming/Python/Python312/site-packages'),  # Windows
    os.path.expanduser('~/AppData/Local/Programs/Python/Python312/Lib/site-packages'),  # Windows
]

for path in possible_paths:
    if os.path.exists(path):
        sys.path.insert(0, path)

# Import required libraries
import requests
import pendulum
from pygrid.client import GridClient
from pygrid.central_data.enums import OrderDirection, SeriesType

# Google Sheets imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scrim_analyzer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)



# Champion ID to name mapping (complete list from Riot Data Dragon)
CHAMPION_NAMES = {
    1: "Annie", 2: "Olaf", 3: "Galio", 4: "Twisted Fate", 5: "Xin Zhao", 6: "Urgot", 7: "LeBlanc", 8: "Vladimir", 
    9: "Fiddlesticks", 10: "Kayle", 11: "Master Yi", 12: "Alistar", 13: "Ryze", 14: "Sion", 15: "Sivir", 16: "Soraka", 
    17: "Teemo", 18: "Tristana", 19: "Warwick", 20: "Nunu & Willump", 21: "Miss Fortune", 22: "Ashe", 23: "Tryndamere", 
    24: "Jax", 25: "Morgana", 26: "Zilean", 27: "Singed", 28: "Evelynn", 29: "Twitch", 30: "Karthus", 31: "Cho'Gath", 
    32: "Amumu", 33: "Rammus", 34: "Anivia", 35: "Shaco", 36: "Dr. Mundo", 37: "Sona", 38: "Kassadin", 39: "Irelia", 
    40: "Janna", 41: "Gangplank", 42: "Corki", 43: "Karma", 44: "Taric", 45: "Veigar", 48: "Trundle", 50: "Swain", 
    51: "Caitlyn", 53: "Blitzcrank", 54: "Malphite", 55: "Katarina", 56: "Nocturne", 57: "Maokai", 58: "Renekton", 
    59: "Jarvan IV", 60: "Elise", 61: "Orianna", 62: "Wukong", 63: "Brand", 64: "Lee Sin", 67: "Vayne", 68: "Rumble", 
    69: "Cassiopeia", 72: "Skarner", 74: "Heimerdinger", 75: "Nasus", 76: "Nidalee", 77: "Udyr", 78: "Poppy", 
    79: "Gragas", 80: "Pantheon", 81: "Ezreal", 82: "Mordekaiser", 83: "Yorick", 84: "Akali", 85: "Kennen", 86: "Garen", 
    89: "Leona", 90: "Malzahar", 91: "Talon", 92: "Riven", 96: "Kog'Maw", 98: "Shen", 99: "Lux", 101: "Xerath", 
    102: "Shyvana", 103: "Ahri", 104: "Graves", 105: "Fizz", 106: "Volibear", 107: "Rengar", 110: "Varus", 
    111: "Nautilus", 112: "Viktor", 113: "Sejuani", 114: "Fiora", 115: "Ziggs", 117: "Lulu", 119: "Draven", 
    120: "Hecarim", 121: "Kha'Zix", 122: "Darius", 126: "Jayce", 127: "Lissandra", 131: "Diana", 133: "Quinn", 
    134: "Syndra", 136: "Aurelion Sol", 141: "Kayn", 142: "Zoe", 143: "Zyra", 145: "Kai'Sa", 147: "Seraphine", 
    150: "Gnar", 154: "Zac", 157: "Yasuo", 161: "Vel'Koz", 163: "Taliyah", 164: "Camille", 166: "Akshan", 
    200: "Bel'Veth", 201: "Braum", 202: "Jhin", 203: "Kindred", 221: "Zeri", 222: "Jinx", 223: "Tahm Kench", 
    233: "Briar", 234: "Viego", 235: "Senna", 236: "Lucian", 238: "Zed", 240: "Kled", 245: "Ekko", 246: "Qiyana", 
    254: "Vi", 266: "Aatrox", 267: "Nami", 268: "Azir", 350: "Yuumi", 360: "Samira", 412: "Thresh", 420: "Illaoi", 
    421: "Rek'Sai", 427: "Ivern", 429: "Kalista", 432: "Bard", 497: "Rakan", 498: "Xayah", 516: "Ornn", 517: "Sylas", 
    518: "Neeko", 523: "Aphelios", 526: "Rell", 555: "Pyke", 711: "Vex", 777: "Yone", 799: "Ambessa", 875: "Sett", 
    876: "Lillia", 887: "Gwen", 888: "Renata Glasc", 893: "Aurora", 895: "Nilah", 897: "K'Sante", 901: "Smolder", 
    902: "Milio", 910: "Hwei", 950: "Naafiri"
}

class ScrimDraftAnalyzer:
    def __init__(self, spreadsheet_id: Optional[str] = None):
        self.grid_client = GridClient(GRID_API_KEY)
        self.spreadsheet_id = spreadsheet_id
        self.sheets_service = None
        self.processed_scrims = self.load_processed_scrims()
        self.champion_role_data = self.load_champion_data()
        
        # Create directories
        DOWNLOADS_DIR.mkdir(exist_ok=True)
        (DOWNLOADS_DIR / "livestats").mkdir(exist_ok=True)
        (DOWNLOADS_DIR / "metadata").mkdir(exist_ok=True)
        
    def load_champion_data(self) -> Dict[str, List[str]]:
        """Load champion role data from champion-data.json."""
        champion_file = Path("champion-data.json")
        if champion_file.exists():
            with open(champion_file, 'r') as f:
                data = json.load(f)
                # Create a mapping from champion name to roles
                champion_roles = {}
                for champ in data:
                    # Normalize champion names (remove spaces, apostrophes)
                    name = champ['name'].replace("'", "").replace(" ", "")
                    # Map role names to our format
                    roles = []
                    for role in champ['roles']:
                        if role == 'Top':
                            roles.append('top')
                        elif role == 'Jgl':
                            roles.append('jungle')
                        elif role == 'Mid':
                            roles.append('mid')
                        elif role == 'Adc':
                            roles.append('adc')
                        elif role == 'Sup':
                            roles.append('supp')
                    champion_roles[name.lower()] = roles
                return champion_roles
        logger.warning("champion-data.json not found, using fallback role detection")
        return {}
    
    def load_processed_scrims(self) -> Dict[str, Any]:
        """Load the tracking data for processed scrims."""
        if Path(TRACKING_FILE).exists():
            with open(TRACKING_FILE, 'r') as f:
                return json.load(f)
        return {"processed_series": {}, "last_update": None}
    
    def save_processed_scrims(self):
        """Save the tracking data."""
        self.processed_scrims["last_update"] = datetime.now().isoformat()
        with open(TRACKING_FILE, 'w') as f:
            json.dump(self.processed_scrims, f, indent=2)
    
    def authenticate_google_sheets(self):
        """Authenticate with Google Sheets API."""
        creds = None
        
        # Token file stores the user's access and refresh tokens
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    logger.error(f"Missing {CREDENTIALS_FILE}. Please download it from Google Cloud Console.")
                    logger.info("Visit: https://console.cloud.google.com/apis/credentials")
                    logger.info("Create a new OAuth 2.0 Client ID and download the credentials.")
                    return False
                
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                print("\n" + "="*60)
                print("GOOGLE AUTHENTICATION REQUIRED")
                print("="*60)
                
                # Use localhost redirect URI matching your credentials.json
                try:
                    creds = flow.run_local_server(port=80, open_browser=True)
                    print("✅ Authentication successful!")
                except Exception as e:
                    print(f"❌ Authentication failed: {e}")
                    print("Trying alternative method...")
                    try:
                        # Fallback: manual URL with proper redirect
                        flow.redirect_uri = 'http://localhost'
                        auth_url, _ = flow.authorization_url(prompt='consent')
                        print(f"\nOpen this URL in your browser:")
                        print(f"{auth_url}")
                        print("\nAfter authentication, copy the 'code' parameter from the redirect URL")
                        auth_code = input("Paste the authorization code here: ").strip()
                        flow.fetch_token(code=auth_code)
                        creds = flow.credentials
                        print("✅ Authentication successful!")
                    except Exception as e2:
                        print(f"❌ Authentication failed: {e2}")
                        return False
            
            # Save the credentials for the next run
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        try:
            self.sheets_service = build('sheets', 'v4', credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to build sheets service: {e}")
            return False
    
    def create_spreadsheet(self, title: str = "LoL Scrim Draft Analysis") -> str:
        """Create a new Google Spreadsheet and return its ID."""
        if not self.sheets_service:
            if not self.authenticate_google_sheets():
                raise Exception("Failed to authenticate with Google Sheets")
        
        spreadsheet = {
            'properties': {
                'title': title
            },
            'sheets': [{
                'properties': {
                    'title': 'Draft Data',
                    'gridProperties': {
                        'rowCount': 1000,
                        'columnCount': 30
                    }
                }
            }]
        }
        
        try:
            spreadsheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet, fields='spreadsheetId').execute()
            self.spreadsheet_id = spreadsheet.get('spreadsheetId')
            logger.info(f"Created new spreadsheet: https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}")
            return self.spreadsheet_id
        except HttpError as error:
            logger.error(f"An error occurred creating spreadsheet: {error}")
            raise
    
    def download_new_scrims(self) -> List[Dict[str, Any]]:
        """Download new scrim series that haven't been processed yet."""
        logger.info("Checking for new scrim series...")
        
        # Calculate date range
        end_date = pendulum.now()
        start_date = end_date.subtract(months=2)
        
        try:
            # Query for scrim series
            series_list = self.grid_client.get_all_series(
                order=OrderDirection.DESC,
                title_ids=["3"],  # League of Legends
                gte=start_date.to_iso8601_string(),
                lte=end_date.to_iso8601_string(),
                game_types=[SeriesType.SCRIM]
            )
            
            logger.info(f"Found {len(series_list)} total scrim series")
            
            # Filter for new series
            new_series = []
            for edge in series_list:
                series = edge.node if hasattr(edge, 'node') else edge
                series_id = str(getattr(series, 'id', 'Unknown'))
                
                if series_id not in self.processed_scrims["processed_series"]:
                    new_series.append({
                        'edge': edge,
                        'series': series,
                        'id': series_id
                    })
            
            logger.info(f"Found {len(new_series)} new scrim series to process")
            
            # Download files for new series
            session = requests.Session()
            downloaded_files = []
            
            for series_info in new_series:
                series_id = series_info['id']
                series = series_info['series']
                
                try:
                    # Get available files
                    files_response = self.grid_client.get_available_files(series_id)
                    if files_response.status_code != 200:
                        logger.warning(f"Failed to get files for series {series_id}")
                        continue
                    
                    files_data = files_response.json()
                    available_files = files_data.get('files', [])
                    
                    # Filter for riot livestats files
                    riot_livestats_files = [
                        f for f in available_files 
                        if 'riot' in f.get('description', '').lower() and 
                           'livestats' in f.get('description', '').lower()
                    ]
                    
                    for file_info in riot_livestats_files:
                        filename = f"series_{series_id}_{file_info.get('id', 'unknown')}.jsonl"
                        local_path = DOWNLOADS_DIR / "livestats" / filename
                        
                        if local_path.exists():
                            logger.info(f"File already exists: {filename}")
                            downloaded_files.append({
                                'series_id': series_id,
                                'series': series,
                                'file_path': local_path,
                                'already_existed': True
                            })
                            continue
                        
                        # Download the file
                        download_url = file_info.get('fullURL', '')
                        headers = {'X-API-Key': GRID_API_KEY}
                        
                        logger.info(f"Downloading: {filename}")
                        response = session.get(download_url, headers=headers, stream=True, timeout=30)
                        response.raise_for_status()
                        
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(local_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        downloaded_files.append({
                            'series_id': series_id,
                            'series': series,
                            'file_path': local_path,
                            'already_existed': False
                        })
                        
                        time.sleep(0.5)  # Rate limiting
                        
                except Exception as e:
                    logger.error(f"Error processing series {series_id}: {e}")
                    continue
            
            return downloaded_files
            
        except Exception as e:
            logger.error(f"Error fetching scrim series: {e}")
            return []
    
    def get_champion_name(self, champion_id: int) -> str:
        """Get champion name by ID with fallback to dynamic lookup."""
        # First try the static mapping
        if champion_id in CHAMPION_NAMES:
            return CHAMPION_NAMES[champion_id]
        
        # If not found, log a warning and return a placeholder
        logger.warning(f"Unknown champion ID: {champion_id}. Please update CHAMPION_NAMES dictionary.")
        return f"Unknown_Champion_{champion_id}"
    
    def assign_team_roles(self, team_champions: List[Tuple[int, str, int]]) -> Dict[int, str]:
        """
        Assign roles to an entire team optimally based on champion preferences.
        
        Args:
            team_champions: List of (participant_id, champion_name, champion_id) tuples
            
        Returns:
            Dict mapping participant_id to role
        """
        # Required roles for a team
        required_roles = ['top', 'jungle', 'mid', 'adc', 'supp']
        
        # Build champion role preferences
        champion_roles = {}
        participant_ids = []
        
        for pid, champ_name, champ_id in team_champions:
            participant_ids.append(pid)
            # Get normalized champion name
            if champ_name == "Nunu & Willump":
                normalized_name = "nunu"
            elif champ_name == "Renata Glasc":
                normalized_name = "renata"
            elif champ_name == "Tahm Kench":
                normalized_name = "tahmkench"
            elif champ_name == "Twisted Fate":
                normalized_name = "twistedfate"
            elif champ_name == "Xin Zhao":
                normalized_name = "xinzhao"
            elif champ_name == "Master Yi":
                normalized_name = "masteryi"
            elif champ_name == "Miss Fortune":
                normalized_name = "missfortune"
            elif champ_name == "Dr. Mundo":
                normalized_name = "drmundo"
            elif champ_name == "Jarvan IV":
                normalized_name = "jarvaniv"
            elif champ_name == "Cho'Gath":
                normalized_name = "chogath"
            elif champ_name == "Kai'Sa":
                normalized_name = "kaisa"
            elif champ_name == "Kha'Zix":
                normalized_name = "khazix"
            elif champ_name == "Kog'Maw":
                normalized_name = "kogmaw"
            elif champ_name == "Lee Sin":
                normalized_name = "leesin"
            elif champ_name == "Bel'Veth":
                normalized_name = "belveth"
            elif champ_name == "Rek'Sai":
                normalized_name = "reksai"
            elif champ_name == "Vel'Koz":
                normalized_name = "velkoz"
            elif champ_name == "K'Sante":
                normalized_name = "ksante"
            elif champ_name == "Aurelion Sol":
                normalized_name = "aurelionsol"
            elif champ_name == "Wukong":
                normalized_name = "monkeyking"
            else:
                normalized_name = champ_name.replace("'", "").replace(" ", "").lower()
            
            # Get possible roles from champion data
            if normalized_name in self.champion_role_data:
                champion_roles[pid] = self.champion_role_data[normalized_name]
            else:
                # Fallback to hardcoded role if available
                role = self.get_champion_role(champ_id)
                if role != "unknown":
                    champion_roles[pid] = [role]
                else:
                    champion_roles[pid] = []
        
        # Score function for role assignment
        def calculate_assignment_score(assignment):
            score = 0
            for pid, role in assignment.items():
                # Check if champion can play this role
                if pid in champion_roles and champion_roles[pid]:
                    if role in champion_roles[pid]:
                        # Higher score for primary role (first in list)
                        role_index = champion_roles[pid].index(role)
                        score += (10 - role_index * 2)  # 10 for primary, 8 for secondary, etc.
                        
                        # Bonus for position matching
                        if (pid in [1, 6] and role == 'top') or \
                           (pid in [2, 7] and role == 'jungle') or \
                           (pid in [3, 8] and role == 'mid') or \
                           (pid in [4, 9] and role == 'adc') or \
                           (pid in [5, 10] and role == 'supp'):
                            score += 3
                    else:
                        # Champion can't play this role, but might be forced to
                        score += 1
                else:
                    # No role data, use position hint
                    if (pid in [1, 6] and role == 'top') or \
                       (pid in [2, 7] and role == 'jungle') or \
                       (pid in [3, 8] and role == 'mid') or \
                       (pid in [4, 9] and role == 'adc') or \
                       (pid in [5, 10] and role == 'supp'):
                        score += 5
                    else:
                        score += 2
            return score
        
        # Try all possible role assignments
        best_assignment = {}
        best_score = -1
        
        # Generate all permutations of role assignments
        for perm in permutations(required_roles):
            assignment = dict(zip(participant_ids, perm))
            score = calculate_assignment_score(assignment)
            if score > best_score:
                best_score = score
                best_assignment = assignment
        
        # For any champion where the assigned role doesn't match their possible roles,
        # and they have no roles in champion_roles, return empty string
        final_assignment = {}
        for pid, role in best_assignment.items():
            if pid in champion_roles and champion_roles[pid]:
                if role not in champion_roles[pid]:
                    # Champion data exists but role doesn't match - ambiguous
                    final_assignment[pid] = ""
                else:
                    final_assignment[pid] = role
            else:
                # No champion data, use the assigned role
                final_assignment[pid] = role
                
        return final_assignment
    
    def get_champion_role_from_data(self, champion_name: str, participant_id: int) -> str:
        """Get champion's role from champion-data.json, considering position context."""
        # Normalize the champion name
        # Handle special cases
        if champion_name == "Nunu & Willump":
            normalized_name = "nunu"
        elif champion_name == "Renata Glasc":
            normalized_name = "renata"
        elif champion_name == "Tahm Kench":
            normalized_name = "tahmkench"
        elif champion_name == "Twisted Fate":
            normalized_name = "twistedfate"
        elif champion_name == "Xin Zhao":
            normalized_name = "xinzhao"
        elif champion_name == "Master Yi":
            normalized_name = "masteryi"
        elif champion_name == "Miss Fortune":
            normalized_name = "missfortune"
        elif champion_name == "Dr. Mundo":
            normalized_name = "drmundo"
        elif champion_name == "Jarvan IV":
            normalized_name = "jarvaniv"
        elif champion_name == "Cho'Gath":
            normalized_name = "chogath"
        elif champion_name == "Kai'Sa":
            normalized_name = "kaisa"
        elif champion_name == "Kha'Zix":
            normalized_name = "khazix"
        elif champion_name == "Kog'Maw":
            normalized_name = "kogmaw"
        elif champion_name == "Lee Sin":
            normalized_name = "leesin"
        elif champion_name == "Bel'Veth":
            normalized_name = "belveth"
        elif champion_name == "Rek'Sai":
            normalized_name = "reksai"
        elif champion_name == "Vel'Koz":
            normalized_name = "velkoz"
        elif champion_name == "K'Sante":
            normalized_name = "ksante"
        elif champion_name == "Aurelion Sol":
            normalized_name = "aurelionsol"
        elif champion_name == "Wukong":
            normalized_name = "monkeyking"
        else:
            normalized_name = champion_name.replace("'", "").replace(" ", "").lower()
        
        if normalized_name in self.champion_role_data:
            roles = self.champion_role_data[normalized_name]
            
            # If only one role, return it
            if len(roles) == 1:
                return roles[0]
            
            # If multiple roles, try to determine based on participant position
            # Positions: 1,6=top | 2,7=jungle | 3,8=mid | 4,9=adc | 5,10=supp
            if participant_id in [1, 6] and 'top' in roles:
                return 'top'
            elif participant_id in [2, 7] and 'jungle' in roles:
                return 'jungle'
            elif participant_id in [3, 8] and 'mid' in roles:
                return 'mid'
            elif participant_id in [4, 9] and 'adc' in roles:
                return 'adc'
            elif participant_id in [5, 10] and 'supp' in roles:
                return 'supp'
            
            # If ambiguous (multiple roles but none match expected position), return empty
            return ""
        
        return "unknown"
    
    def get_champion_role(self, champion_id: int) -> str:
        """Get champion's primary role based on champion ID (fallback method)."""
        # Champion role mappings based on typical competitive play
        champion_roles = {
            # Top lane champions
            14: "top",    # Sion
            36: "top",    # Dr. Mundo
            266: "top",   # Aatrox
            114: "top",   # Fiora
            92: "top",    # Riven
            58: "top",    # Renekton
            75: "top",    # Nasus
            150: "top",   # Gnar
            83: "top",    # Yorick
            86: "top",    # Garen
            78: "jungle", # Poppy (flex jungle/top)
            54: "top",    # Malphite
            80: "top",    # Pantheon
            98: "top",    # Shen
            516: "top",   # Ornn
            122: "top",   # Darius
            240: "top",   # Kled
            48: "top",    # Trundle
            126: "top",   # Jayce
            799: "top",   # Ambessa
            
            # Jungle champions
            56: "jungle", # Nocturne
            104: "jungle", # Graves
            121: "jungle", # Kha'Zix
            64: "jungle",  # Lee Sin
            113: "jungle", # Sejuani
            60: "jungle",  # Elise
            107: "jungle", # Rengar
            154: "jungle", # Zac
            11: "jungle",  # Master Yi
            120: "jungle", # Hecarim
            427: "jungle", # Ivern
            203: "jungle", # Kindred
            421: "jungle", # Rek'Sai
            233: "jungle", # Briar
            
            # Mid lane champions
            163: "mid",   # Taliyah  
            99: "mid",    # Lux
            1: "mid",     # Annie
            103: "mid",   # Ahri  
            134: "mid",   # Syndra
            34: "mid",    # Anivia
            61: "mid",    # Orianna
            157: "mid",   # Yasuo
            238: "mid",   # Zed
            268: "mid",   # Azir
            142: "mid",   # Zoe
            127: "mid",   # Lissandra
            7: "mid",     # LeBlanc
            38: "mid",    # Kassadin
            245: "mid",   # Ekko
            84: "mid",    # Akali
            131: "mid",   # Diana
            517: "mid",   # Sylas
            910: "mid",   # Hwei
            893: "mid",   # Aurora (new mid champion)
            
            # ADC champions  
            145: "adc",   # Kai'Sa
            523: "adc",   # Aphelios
            22: "adc",    # Ashe
            51: "adc",    # Caitlyn
            81: "adc",    # Ezreal
            222: "adc",   # Jinx
            21: "adc",    # Miss Fortune
            18: "adc",    # Tristana
            236: "adc",   # Lucian
            119: "adc",   # Draven
            110: "adc",   # Varus
            96: "adc",    # Kog'Maw
            202: "adc",   # Jhin
            429: "adc",   # Kalista
            498: "adc",   # Xayah
            221: "adc",   # Zeri
            895: "adc",   # Nilah
            901: "adc",   # Smolder
            
            # Support champions
            32: "supp",   # Ammu
            117: "supp",  # Lulu
            12: "supp",   # Alistar
            40: "supp",   # Janna
            16: "supp",   # Soraka
            89: "supp",   # Leona
            412: "supp",  # Thresh
            111: "supp",  # Nautilus
            432: "supp",  # Bard
            267: "supp",  # Nami
            25: "supp",   # Morgana
            37: "supp",   # Sona
            223: "supp",  # Tahm Kench
            201: "supp",  # Braum
            143: "supp",  # Zyra
            555: "supp",  # Pyke
            497: "supp",  # Rakan
            526: "supp",  # Rell
            235: "supp",  # Senna
            350: "supp",  # Yuumi
            888: "supp",  # Renata Glasc
            902: "supp",  # Milio
        }
        
        return champion_roles.get(champion_id, "unknown")
    
    def determine_role(self, participant_id: int, spell1: int, spell2: int, team_key: str, champion_id: int = 0, champion_name: str = "") -> str:
        """Determine player role based on champion and participant ID."""
        
        # Primary: Use champion-data.json if available
        if champion_name and self.champion_role_data:
            role = self.get_champion_role_from_data(champion_name, participant_id)
            if role != "unknown":
                return role
        
        # Secondary: Use hardcoded champion-based role detection
        if champion_id > 0:
            champion_role = self.get_champion_role(champion_id)
            if champion_role != "unknown":
                return champion_role
        
        # Fallback: Standard participant ID mapping (1-based from game data)
        # Based on the actual game data: 1,6=top | 2,7=jungle | 3,8=mid | 4,9=adc | 5,10=supp
        if participant_id in [1, 6]:
            return "top"
        elif participant_id in [2, 7]:
            return "jungle"
        elif participant_id in [3, 8]:
            return "mid"
        elif participant_id in [4, 9]:
            return "adc"
        elif participant_id in [5, 10]:
            return "supp"
        else:
            return "unknown"
    
    def extract_draft_from_file(self, file_path: Path) -> Dict[str, Any]:
        """Extract draft information from a JSONL file."""
        draft_events = []
        seen_bans = set()
        player_champions = {}
        team_names = set()
        winning_team = None
        team_one_name = None
        team_two_name = None
        
        # Collect team compositions for role assignment
        team_one_composition = {}  # participant_id -> (champion_name, champion_id)
        team_two_composition = {}  # participant_id -> (champion_name, champion_id)
        team_one_players = {}  # participant_id -> player_name
        team_two_players = {}  # participant_id -> player_name
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line)
                        
                        # Check for game end event
                        if data.get('rfc461Schema') == 'game_end':
                            winning_team_id = data.get('winningTeam')
                            if winning_team_id == 100:
                                winning_team = 'teamOne'
                            elif winning_team_id == 200:
                                winning_team = 'teamTwo'
                            continue
                        
                        # Skip if not champion select state
                        if data.get('gameState') not in ['CHAMP_SELECT', 'PRE_CHAMP_SELECT']:
                            continue
                        
                        current_pick_turn = data.get('pickTurn', 0)
                        timestamp = data.get('rfc460Timestamp', '')
                        
                        # Extract team names from teamOne and teamTwo
                        if 'teamOne' in data and data['teamOne'] and not team_one_name:
                            for player in data['teamOne']:
                                display_name = player.get('displayName', '')
                                if ' ' in display_name:
                                    team_one_name = display_name.split()[0]
                                    team_names.add(team_one_name)
                                    break
                        
                        if 'teamTwo' in data and data['teamTwo'] and not team_two_name:
                            for player in data['teamTwo']:
                                display_name = player.get('displayName', '')
                                if ' ' in display_name:
                                    team_two_name = display_name.split()[0]
                                    team_names.add(team_two_name)
                                    break
                        
                        # Check for new bans
                        current_bans = data.get('bannedChampions', [])
                        for ban in current_bans:
                            ban_key = (ban['championID'], ban['pickTurn'], ban['teamID'])
                            if ban_key not in seen_bans:
                                seen_bans.add(ban_key)
                                champion_name = self.get_champion_name(ban['championID'])
                                team = "Blue" if ban['teamID'] == 100 else "Red"
                                draft_events.append({
                                    'type': 'ban',
                                    'pickTurn': ban['pickTurn'],
                                    'champion': champion_name,
                                    'championID': ban['championID'],
                                    'team': team,
                                    'timestamp': timestamp,
                                    'line': line_num
                                })
                        
                        # Check for picks
                        for team_key in ['teamOne', 'teamTwo']:
                            if team_key in data:
                                # Use the actual team name based on which key we're processing
                                if team_key == 'teamOne':
                                    team_name = team_one_name or 'TeamOne'
                                    team_side = 'Blue'
                                else:
                                    team_name = team_two_name or 'TeamTwo'
                                    team_side = 'Red'
                                
                                for player in data[team_key]:
                                    participant_id = player['participantID']
                                    champion_id = player['championID']
                                    
                                    if champion_id > 0:
                                        if participant_id not in player_champions:
                                            player_champions[participant_id] = champion_id
                                            champion_name = self.get_champion_name(champion_id)
                                            
                                            # Store composition for later role assignment
                                            if team_key == 'teamOne':
                                                team_one_composition[participant_id] = (champion_name, champion_id)
                                                team_one_players[participant_id] = player['displayName']
                                            else:
                                                team_two_composition[participant_id] = (champion_name, champion_id)
                                                team_two_players[participant_id] = player['displayName']
                                            
                                            draft_events.append({
                                                'type': 'pick',
                                                'pickTurn': player['pickTurn'],
                                                'champion': champion_name,
                                                'championID': champion_id,
                                                'player': player['displayName'],
                                                'team': team_name,
                                                'team_key': team_key,
                                                'team_side': team_side,
                                                'participant_id': participant_id,
                                                'role': 'TBD',  # Will be assigned later
                                                'timestamp': timestamp,
                                                'line': line_num
                                            })
                                        elif player_champions[participant_id] != champion_id:
                                            # Champion swap
                                            player_champions[participant_id] = champion_id
                                            champion_name = self.get_champion_name(champion_id)
                                            
                                            # Update composition
                                            if team_key == 'teamOne':
                                                team_one_composition[participant_id] = (champion_name, champion_id)
                                            else:
                                                team_two_composition[participant_id] = (champion_name, champion_id)
                                            
                                            # Update existing pick
                                            for event in draft_events:
                                                if (event['type'] == 'pick' and 
                                                    event['player'] == player['displayName']):
                                                    event['champion'] = champion_name
                                                    event['championID'] = champion_id
                                                    event['timestamp'] = timestamp
                                                    event['line'] = line_num
                                                    break
                        
                    except json.JSONDecodeError:
                        continue
            
            # Assign roles to teams based on optimal composition
            if team_one_composition:
                team_one_list = [(pid, comp[0], comp[1]) for pid, comp in team_one_composition.items()]
                team_one_roles = self.assign_team_roles(team_one_list)
                
                # Update draft events with assigned roles
                for event in draft_events:
                    if event['type'] == 'pick' and event['team_key'] == 'teamOne':
                        pid = event['participant_id']
                        if pid in team_one_roles:
                            event['role'] = team_one_roles[pid]
            
            if team_two_composition:
                team_two_list = [(pid, comp[0], comp[1]) for pid, comp in team_two_composition.items()]
                team_two_roles = self.assign_team_roles(team_two_list)
                
                # Update draft events with assigned roles
                for event in draft_events:
                    if event['type'] == 'pick' and event['team_key'] == 'teamTwo':
                        pid = event['participant_id']
                        if pid in team_two_roles:
                            event['role'] = team_two_roles[pid]
            
            # Sort events by pickTurn
            draft_events.sort(key=lambda x: x['pickTurn'])
            
            # Extract team compositions
            blue_bans = [e for e in draft_events if e['type'] == 'ban' and e['team'] == 'Blue']
            red_bans = [e for e in draft_events if e['type'] == 'ban' and e['team'] == 'Red']
            
            # Get picks by team_key (teamOne/teamTwo)
            team_one_picks = [e for e in draft_events if e['type'] == 'pick' and e.get('team_key') == 'teamOne']
            team_two_picks = [e for e in draft_events if e['type'] == 'pick' and e.get('team_key') == 'teamTwo']
            
            # Determine winner based on winning_team
            winner = None
            if winning_team:
                if winning_team == 'teamOne':
                    winner = team_one_name or 'Blue Team'
                elif winning_team == 'teamTwo':
                    winner = team_two_name or 'Red Team'
            
            return {
                'events': draft_events,
                'blue_bans': [b['champion'] for b in blue_bans],
                'red_bans': [b['champion'] for b in red_bans],
                'team1': {
                    'name': team_one_name or 'Team1',
                    'picks': [(p['player'], p['champion'], p['role']) for p in team_one_picks]
                },
                'team2': {
                    'name': team_two_name or 'Team2', 
                    'picks': [(p['player'], p['champion'], p['role']) for p in team_two_picks]
                },
                'winner': winner
            }
            
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None
    
    def format_draft_for_sheets(self, series_id: str, series_data: Any, draft_data: Dict[str, Any]) -> List[List[Any]]:
        """Format draft data for Google Sheets row."""
        if not draft_data:
            return []
        
        # Extract series metadata
        series_date = getattr(series_data, 'start_time_scheduled', 'Unknown')
        if series_date != 'Unknown':
            try:
                series_date = pendulum.parse(series_date).format('YYYY-MM-DD HH:mm')
            except:
                pass
        
        # Format team data
        team1 = draft_data['team1']
        team2 = draft_data['team2']
        
        # Get bans and picks with proper ordering
        blue_bans = draft_data['blue_bans']
        red_bans = draft_data['red_bans']
        blue_picks = [p[1] for p in team1['picks']]
        red_picks = [p[1] for p in team2['picks']]
        
        # Get roles for each pick
        blue_roles = [p[2] for p in team1['picks']]
        red_roles = [p[2] for p in team2['picks']]
        
        # Create row data in the requested order:
        # Blue ban 1, red ban 1, blue ban 2, red ban 2, blue ban 3, red ban 3,
        # blue pick 1, red pick 1 and 2, blue pick 2 and 3, red pick 3,
        # red ban 4, blue ban 4, red ban 5, blue ban 5,
        # red pick 4, blue pick 4 and 5, red pick 5
        row = [
            series_id,
            series_date,
            team1['name'],
            team2['name'],
            # First ban phase (1-3)
            blue_bans[0] if len(blue_bans) > 0 else '',  # Blue ban 1
            red_bans[0] if len(red_bans) > 0 else '',   # Red ban 1
            blue_bans[1] if len(blue_bans) > 1 else '',  # Blue ban 2
            red_bans[1] if len(red_bans) > 1 else '',   # Red ban 2
            blue_bans[2] if len(blue_bans) > 2 else '',  # Blue ban 3
            red_bans[2] if len(red_bans) > 2 else '',   # Red ban 3
            # First pick phase
            blue_picks[0] if len(blue_picks) > 0 else '',  # Blue pick 1
            red_picks[0] if len(red_picks) > 0 else '',   # Red pick 1
            red_picks[1] if len(red_picks) > 1 else '',   # Red pick 2
            blue_picks[1] if len(blue_picks) > 1 else '',  # Blue pick 2
            blue_picks[2] if len(blue_picks) > 2 else '',  # Blue pick 3
            red_picks[2] if len(red_picks) > 2 else '',   # Red pick 3
            # Second ban phase (4-5)
            red_bans[3] if len(red_bans) > 3 else '',   # Red ban 4
            blue_bans[3] if len(blue_bans) > 3 else '',  # Blue ban 4
            red_bans[4] if len(red_bans) > 4 else '',   # Red ban 5
            blue_bans[4] if len(blue_bans) > 4 else '',  # Blue ban 5
            # Second pick phase
            red_picks[3] if len(red_picks) > 3 else '',   # Red pick 4
            blue_picks[3] if len(blue_picks) > 3 else '',  # Blue pick 4
            blue_picks[4] if len(blue_picks) > 4 else '',  # Blue pick 5
            red_picks[4] if len(red_picks) > 4 else '',   # Red pick 5
            # Winner
            draft_data.get('winner', ''),  # Winner column
            # Role columns
            blue_roles[0] if len(blue_roles) > 0 else '',  # Blue Role 1
            blue_roles[1] if len(blue_roles) > 1 else '',  # Blue Role 2
            blue_roles[2] if len(blue_roles) > 2 else '',  # Blue Role 3
            blue_roles[3] if len(blue_roles) > 3 else '',  # Blue Role 4
            blue_roles[4] if len(blue_roles) > 4 else '',  # Blue Role 5
            red_roles[0] if len(red_roles) > 0 else '',   # Red Role 1
            red_roles[1] if len(red_roles) > 1 else '',   # Red Role 2
            red_roles[2] if len(red_roles) > 2 else '',   # Red Role 3
            red_roles[3] if len(red_roles) > 3 else '',   # Red Role 4
            red_roles[4] if len(red_roles) > 4 else '',   # Red Role 5
        ]
        
        return row
    
    def update_google_sheets(self, draft_rows: List[List[Any]]):
        """Update Google Sheets with draft data."""
        if not self.spreadsheet_id:
            logger.error("No spreadsheet ID provided")
            return
        
        if not self.sheets_service:
            if not self.authenticate_google_sheets():
                logger.error("Failed to authenticate with Google Sheets")
                return
        
        try:
            # Prepare header row - matching the new column order
            headers = [
                'Series ID', 'Date', 'Blue Team', 'Red Team',
                'Blue Ban 1', 'Red Ban 1', 'Blue Ban 2', 'Red Ban 2', 'Blue Ban 3', 'Red Ban 3',
                'Blue Pick 1', 'Red Pick 1', 'Red Pick 2', 'Blue Pick 2', 'Blue Pick 3', 'Red Pick 3',
                'Red Ban 4', 'Blue Ban 4', 'Red Ban 5', 'Blue Ban 5',
                'Red Pick 4', 'Blue Pick 4', 'Blue Pick 5', 'Red Pick 5',
                'Winner',
                'Blue Role 1', 'Blue Role 2', 'Blue Role 3', 'Blue Role 4', 'Blue Role 5',
                'Red Role 1', 'Red Role 2', 'Red Role 3', 'Red Role 4', 'Red Role 5'
            ]
            
            # Get current data to find where to append
            range_name = 'Draft Data!A:A'
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=range_name).execute()
            values = result.get('values', [])
            
            # If sheet is empty, add headers
            if not values:
                values_to_update = [headers] + draft_rows
                range_name = 'Draft Data!A1'
            else:
                # Append new rows
                start_row = len(values) + 1
                values_to_update = draft_rows
                range_name = f'Draft Data!A{start_row}'
            
            # Update the sheet
            body = {
                'values': values_to_update
            }
            
            result = self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"Updated {result.get('updatedRows', 0)} rows in Google Sheets")
            
            # Format the sheet
            self.format_spreadsheet()
            
        except HttpError as error:
            logger.error(f"An error occurred updating sheets: {error}")
    
    def format_spreadsheet(self):
        """Apply formatting to the spreadsheet."""
        try:
            requests = [
                # Freeze header row
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": 0,
                            "gridProperties": {
                                "frozenRowCount": 1
                            }
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                },
                # Bold header row
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "textFormat": {
                                    "bold": True
                                }
                            }
                        },
                        "fields": "userEnteredFormat.textFormat.bold"
                    }
                },
                # Auto-resize columns
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": 0,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": 35
                        }
                    }
                }
            ]
            
            body = {'requests': requests}
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
        except HttpError as error:
            logger.error(f"An error occurred formatting sheets: {error}")
    
    def run(self):
        """Main execution function."""
        logger.info("Starting scrim draft analyzer...")
        
        # Download new scrims
        new_files = self.download_new_scrims()
        
        if not new_files:
            logger.info("No new scrims to process")
            return
        
        # Process each new file
        draft_rows = []
        
        for file_info in new_files:
            if file_info['already_existed']:
                continue
                
            series_id = file_info['series_id']
            file_path = file_info['file_path']
            series_data = file_info['series']
            
            logger.info(f"Processing draft from: {file_path.name}")
            
            # Extract draft data
            draft_data = self.extract_draft_from_file(file_path)
            
            if draft_data:
                # Format for sheets
                row = self.format_draft_for_sheets(series_id, series_data, draft_data)
                if row:
                    draft_rows.append(row)
                
                # Mark as processed
                self.processed_scrims["processed_series"][series_id] = {
                    "processed_at": datetime.now().isoformat(),
                    "file_path": str(file_path),
                    "team1": draft_data['team1']['name'],
                    "team2": draft_data['team2']['name']
                }
            else:
                logger.warning(f"Failed to extract draft from {file_path.name}")
        
        # Update Google Sheets if we have new data
        if draft_rows:
            logger.info(f"Updating Google Sheets with {len(draft_rows)} new drafts")
            self.update_google_sheets(draft_rows)
        
        # Save tracking data
        self.save_processed_scrims()
        logger.info("Scrim draft analyzer completed")

def load_config():
    """Load configuration from config.json if it exists."""
    config_file = Path("config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    """Save configuration to config.json."""
    with open("config.json", 'w') as f:
        json.dump(config, f, indent=2)

def main():
    """Main entry point."""
    print("🚀 LoL Scrim Draft Analyzer")
    print("=" * 40)
    
    # Load existing config
    config = load_config()
    spreadsheet_id = config.get('spreadsheet_id')
    
    if spreadsheet_id:
        print(f"📊 Using existing spreadsheet: {spreadsheet_id}")
        print(f"🔗 https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
        
        analyzer = ScrimDraftAnalyzer(spreadsheet_id=spreadsheet_id)
        analyzer.run()
    else:
        print("📝 No existing spreadsheet found, creating new one...")
        analyzer = ScrimDraftAnalyzer()
        sheet_id = analyzer.create_spreadsheet()
        
        # Save the spreadsheet ID for future runs
        config['spreadsheet_id'] = sheet_id
        save_config(config)
        
        print(f"✅ Created new spreadsheet: {sheet_id}")
        print(f"🔗 https://docs.google.com/spreadsheets/d/{sheet_id}")
        
        analyzer.run()

if __name__ == "__main__":
    main()