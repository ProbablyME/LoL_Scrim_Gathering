# LoL Scrim Draft Analyzer

A Python script that automatically downloads League of Legends scrim data from GRID's API, extracts draft information, and updates a Google Sheets spreadsheet with the results.

## Features

- **Automatic Data Collection**: Downloads new scrim series from GRID API
- **Draft Analysis**: Extracts champion picks, bans, and team compositions from livestats files
- **Google Sheets Integration**: Automatically updates a spreadsheet with formatted draft data
- **Progress Tracking**: Keeps track of processed scrims to avoid duplicates

## Prerequisites

- Python 3.12
- GRID API access
- Google Cloud Project with Sheets API enabled
- Google OAuth 2.0 credentials

## Required Python Packages

Install the following packages:

```bash
pip install requests pendulum grid-lol-client google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Setup Instructions

### 1. GRID API Setup

The script uses a hardcoded GRID API key. If you need your own key:
- Contact GRID to obtain API access
- Replace the `GRID_API_KEY` constant in `scrim_draft_analyzer.py`

### 2. Google Cloud Console Setup

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google Sheets API**:
   - In the Google Cloud Console, go to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it

3. **Create OAuth 2.0 Credentials**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client ID"
   - Choose "Desktop application" as the application type
   - Set the authorized redirect URI to: `http://localhost`
   - Download the credentials file

4. **Save Credentials File**:
   - Rename the downloaded file to `credentials.json`
   - Place it in the same directory as `scrim_draft_analyzer.py`

### 3. File Structure

Your directory should contain:
```
NAVI/
├── scrim_draft_analyzer.py    # Main script
├── credentials.json           # Google OAuth credentials (you create this)
├── config.json               # Auto-generated spreadsheet configuration
├── processed_scrims.json     # Auto-generated tracking file
├── token.pickle              # Auto-generated authentication token
├── scrim_analyzer.log        # Auto-generated log file
└── scrim_downloads/          # Auto-generated download directory
    ├── livestats/            # Downloaded scrim files
    └── metadata/             # Metadata files
```

## Usage

### First Run

1. Ensure `credentials.json` is in place
2. Run the script:
   ```bash
   python scrim_draft_analyzer.py
   ```

3. **Authentication Process**:
   - The script will open your web browser for Google authentication
   - Grant permissions to access your Google Sheets
   - If browser fails, the script will provide a manual authentication URL
   - Copy the authorization code from the redirect URL

4. **Spreadsheet Creation**:
   - On first run, a new Google Spreadsheet will be created
   - The spreadsheet ID will be saved to `config.json` for future runs
   - The script will display the spreadsheet URL

### Subsequent Runs

The script will automatically:
- Use the existing spreadsheet from `config.json`
- Check for new scrim series from the last 2 months
- Download only unprocessed scrim files
- Extract draft data and update the spreadsheet
- Track processed scrims in `processed_scrims.json`

## Configuration Files

### credentials.json
Google OAuth 2.0 credentials file downloaded from Google Cloud Console. Should contain:
```json
{
  "installed": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "your-client-secret",
    "redirect_uris": ["http://localhost"]
  }
}
```

### config.json (auto-generated)
Stores the Google Spreadsheet ID:
```json
{
  "spreadsheet_id": "your-spreadsheet-id"
}
```

### processed_scrims.json (auto-generated)
Tracks which scrim series have been processed:
```json
{
  "processed_series": {
    "series_id": {
      "processed_at": "2024-01-01T12:00:00",
      "file_path": "path/to/file",
      "team1": "Team Name 1",
      "team2": "Team Name 2"
    }
  },
  "last_update": "2024-01-01T12:00:00"
}
```

## Output

The script creates a Google Spreadsheet with the following columns:
- **Series ID**: Unique identifier for the scrim series
- **Date**: When the scrim was scheduled
- **Team 1 & Team 2**: Team names
- **Blue/Red Bans 1-5**: Champion bans for each team
- **Team 1/2 Picks 1-5**: Champion picks for each team

## Troubleshooting

### Authentication Issues
- Ensure `credentials.json` is properly formatted
- Check that the redirect URI in your Google Cloud credentials matches `http://localhost`
- Delete `token.pickle` and re-authenticate if needed

### Missing Dependencies
- Install required packages: `pip install requests pendulum pygrid google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client`

### API Access Issues
- Verify GRID API key is valid
- Check Google Sheets API is enabled in your Google Cloud project

### File Permissions
- Ensure the script has write permissions in the directory
- Check that downloaded files aren't being blocked by antivirus

## Logging

The script logs all activities to `scrim_analyzer.log` and console output. Check this file for detailed information about:
- Downloaded files
- Processing errors
- Authentication status
- Google Sheets updates

## Data Sources

- **GRID API**: Provides League of Legends esports data including scrim series
- **Riot Livestats**: JSON files containing real-time game state data
- **Champion Data**: Built-in mapping of champion IDs to names (up to champion ID 950)