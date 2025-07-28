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
from typing import Dict, List, Any, Optional
import logging

# Constants
GRID_API_KEY = "YOUR_API_KEY"
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



# Champion ID to name mapping (from extract_draft_info.py)
CHAMPION_NAMES = {
    1: "Annie", 2: "Olaf", 3: "Galio", 4: "Twisted Fate", 5: "Xin Zhao", 6: "Urgot", 7: "LeBlanc", 8: "Vladimir", 9: "Fiddlesticks", 10: "Kayle",
    11: "Master Yi", 12: "Alistar", 13: "Ryze", 14: "Sion", 15: "Sivir", 16: "Soraka", 17: "Teemo", 18: "Tristana", 19: "Warwick", 20: "Nunu & Willump",
    21: "Miss Fortune", 22: "Ashe", 23: "Tryndamere", 24: "Jax", 25: "Morgana", 26: "Zilean", 27: "Singed", 28: "Evelynn", 29: "Twitch", 30: "Karthus",
    31: "Cho'Gath", 32: "Amumu", 33: "Rammus", 34: "Anivia", 35: "Shaco", 36: "Dr. Mundo", 37: "Sona", 38: "Kassadin", 39: "Irelia", 40: "Janna",
    41: "Gangplank", 42: "Corki", 43: "Karma", 44: "Taric", 45: "Veigar", 48: "Trundle", 50: "Swain", 51: "Caitlyn", 53: "Blitzcrank", 54: "Malphite",
    55: "Katarina", 56: "Nocturne", 57: "Maokai", 58: "Renekton", 59: "Jarvan IV", 60: "Elise", 61: "Orianna", 62: "Wukong", 63: "Brand", 64: "Lee Sin",
    67: "Vayne", 68: "Rumble", 69: "Cassiopeia", 72: "Skarner", 74: "Heimerdinger", 75: "Nasus", 76: "Nidalee", 77: "Udyr", 78: "Poppy", 79: "Gragas",
    80: "Pantheon", 81: "Ezreal", 82: "Mordekaiser", 83: "Yorick", 84: "Akali", 85: "Kennen", 86: "Garen", 89: "Leona", 90: "Malzahar", 91: "Talon",
    92: "Riven", 96: "Kog'Maw", 98: "Shen", 99: "Lux", 101: "Xerath", 102: "Shyvana", 103: "Ahri", 104: "Graves", 105: "Fizz", 106: "Volibear",
    107: "Rengar", 110: "Varus", 111: "Nautilus", 112: "Viktor", 113: "Sejuani", 114: "Fiora", 115: "Ziggs", 117: "Lulu", 119: "Draven", 120: "Hecarim",
    121: "Kha'Zix", 122: "Darius", 126: "Jayce", 127: "Lissandra", 131: "Diana", 133: "Quinn", 134: "Syndra", 136: "Aurelion Sol", 141: "Kayn", 142: "Azir",
    143: "Zyra", 145: "Kai'Sa", 147: "Seraphine", 150: "Gnar", 154: "Zac", 157: "Yasuo", 161: "Vel'Koz", 163: "Taliyah", 164: "Camille", 166: "Akshan",
    200: "Bel'Veth", 201: "Braum", 202: "Jhin", 203: "Kindred", 221: "Zeri", 222: "Jinx", 223: "Tahm Kench", 234: "Viego", 235: "Senna", 236: "Lucian",
    238: "Zed", 240: "Kled", 245: "Ekko", 246: "Qiyana", 254: "Vi", 266: "Aatrox", 267: "Nami", 268: "Azir", 350: "Yuumi", 360: "Samira", 412: "Thresh",
    420: "Illaoi", 421: "Rek'Sai", 427: "Ivern", 429: "Kalista", 432: "Bard", 497: "Rakan", 498: "Xayah", 516: "Ornn", 517: "Sylas", 518: "Neeko",
    523: "Aphelios", 526: "Rell", 555: "Pyke", 711: "Vex", 777: "Yone", 875: "Sett", 876: "Lillia", 887: "Gwen", 888: "Renata Glasc", 893: "Aurora",
    895: "Nilah", 897: "K'Sante", 901: "Smolder", 910: "Hwei", 950: "Naafiri"
}

class ScrimDraftAnalyzer:
    def __init__(self, spreadsheet_id: Optional[str] = None):
        self.grid_client = GridClient(GRID_API_KEY)
        self.spreadsheet_id = spreadsheet_id
        self.sheets_service = None
        self.processed_scrims = self.load_processed_scrims()
        
        # Create directories
        DOWNLOADS_DIR.mkdir(exist_ok=True)
        (DOWNLOADS_DIR / "livestats").mkdir(exist_ok=True)
        (DOWNLOADS_DIR / "metadata").mkdir(exist_ok=True)
        
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
        """Get champion name by ID."""
        return CHAMPION_NAMES.get(champion_id, f"Champion_{champion_id}")
    
    def extract_draft_from_file(self, file_path: Path) -> Dict[str, Any]:
        """Extract draft information from a JSONL file."""
        draft_events = []
        seen_bans = set()
        player_champions = {}
        team_names = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        data = json.loads(line)
                        
                        # Skip if not champion select state
                        if data.get('gameState') not in ['CHAMP_SELECT', 'PRE_CHAMP_SELECT']:
                            continue
                        
                        current_pick_turn = data.get('pickTurn', 0)
                        timestamp = data.get('rfc460Timestamp', '')
                        
                        # Extract team names
                        for team_key in ['teamOne', 'teamTwo']:
                            if team_key in data and data[team_key]:
                                for player in data[team_key]:
                                    display_name = player.get('displayName', '')
                                    if ' ' in display_name:
                                        team_prefix = display_name.split()[0]
                                        team_names.add(team_prefix)
                        
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
                                team_name = list(team_names)[0] if len(team_names) > 0 else team_key
                                if team_key == 'teamTwo' and len(team_names) > 1:
                                    team_name = list(team_names)[1]
                                
                                for player in data[team_key]:
                                    participant_id = player['participantID']
                                    champion_id = player['championID']
                                    
                                    if champion_id > 0:
                                        if participant_id not in player_champions:
                                            player_champions[participant_id] = champion_id
                                            champion_name = self.get_champion_name(champion_id)
                                            
                                            draft_events.append({
                                                'type': 'pick',
                                                'pickTurn': player['pickTurn'],
                                                'champion': champion_name,
                                                'championID': champion_id,
                                                'player': player['displayName'],
                                                'team': team_name,
                                                'timestamp': timestamp,
                                                'line': line_num
                                            })
                                        elif player_champions[participant_id] != champion_id:
                                            # Champion swap
                                            player_champions[participant_id] = champion_id
                                            champion_name = self.get_champion_name(champion_id)
                                            
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
            
            # Sort events by pickTurn
            draft_events.sort(key=lambda x: x['pickTurn'])
            
            # Extract team compositions
            blue_bans = [e for e in draft_events if e['type'] == 'ban' and e['team'] == 'Blue']
            red_bans = [e for e in draft_events if e['type'] == 'ban' and e['team'] == 'Red']
            
            all_picks = [e for e in draft_events if e['type'] == 'pick']
            team_names_list = list(team_names)
            
            team1_picks = []
            team2_picks = []
            
            if len(team_names_list) >= 2:
                team1_picks = [e for e in all_picks if e['team'] == team_names_list[0]]
                team2_picks = [e for e in all_picks if e['team'] == team_names_list[1]]
            
            return {
                'events': draft_events,
                'blue_bans': [b['champion'] for b in blue_bans],
                'red_bans': [b['champion'] for b in red_bans],
                'team1': {
                    'name': team_names_list[0] if team_names_list else 'Team1',
                    'picks': [(p['player'], p['champion']) for p in team1_picks]
                },
                'team2': {
                    'name': team_names_list[1] if len(team_names_list) > 1 else 'Team2',
                    'picks': [(p['player'], p['champion']) for p in team2_picks]
                }
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
        
        # Create row data
        row = [
            series_id,
            series_date,
            team1['name'],
            team2['name'],
            # Blue bans
            *draft_data['blue_bans'][:5],  # Pad to 5
            *([''] * (5 - len(draft_data['blue_bans']))),
            # Red bans
            *draft_data['red_bans'][:5],  # Pad to 5
            *([''] * (5 - len(draft_data['red_bans']))),
            # Team 1 picks (champion only)
            *[p[1] for p in team1['picks'][:5]],
            *([''] * (5 - len(team1['picks']))),
            # Team 2 picks (champion only)
            *[p[1] for p in team2['picks'][:5]],
            *([''] * (5 - len(team2['picks']))),
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
            # Prepare header row
            headers = [
                'Series ID', 'Date', 'Team 1', 'Team 2',
                'Blue Ban 1', 'Blue Ban 2', 'Blue Ban 3', 'Blue Ban 4', 'Blue Ban 5',
                'Red Ban 1', 'Red Ban 2', 'Red Ban 3', 'Red Ban 4', 'Red Ban 5',
                'Team 1 Pick 1', 'Team 1 Pick 2', 'Team 1 Pick 3', 'Team 1 Pick 4', 'Team 1 Pick 5',
                'Team 2 Pick 1', 'Team 2 Pick 2', 'Team 2 Pick 3', 'Team 2 Pick 4', 'Team 2 Pick 5'
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
                            "endIndex": 24
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