#!/usr/bin/env python3
import sys
import os
import pickle
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Load credentials
token_path = os.path.expanduser('~/.openclaw/workspace/config/token.pickle')
with open(token_path, 'rb') as token:
    creds = pickle.load(token)

# Build service
service = build('sheets', 'v4', credentials=creds)

# Data to add
date = '23/01/2026'
provider = 'MEO'
value = 81.71
filename = 'FT A 858833544.pdf'

# Find or create spreadsheet
# Check if spreadsheet ID is saved
spreadsheet_id_file = os.path.expanduser('~/.openclaw/workspace/config/expenses_sheet_id.txt')

if os.path.exists(spreadsheet_id_file):
    with open(spreadsheet_id_file, 'r') as f:
        spreadsheet_id = f.read().strip()
    print(f"Using existing spreadsheet: {spreadsheet_id}")
else:
    # Create new spreadsheet
    spreadsheet = {
        'properties': {'title': 'Expenses Tracker'},
        'sheets': [{
            'properties': {'title': 'Sheet1'},
            'data': [{
                'rowData': [{
                    'values': [
                        {'userEnteredValue': {'stringValue': 'Date'}},
                        {'userEnteredValue': {'stringValue': 'Provider'}},
                        {'userEnteredValue': {'stringValue': 'Value'}},
                        {'userEnteredValue': {'stringValue': 'Filename'}}
                    ]
                }]
            }]
        }]
    }
    
    result = service.spreadsheets().create(body=spreadsheet).execute()
    spreadsheet_id = result['spreadsheetId']
    
    # Save spreadsheet ID
    with open(spreadsheet_id_file, 'w') as f:
        f.write(spreadsheet_id)
    
    print(f"Created new spreadsheet: {result['spreadsheetUrl']}")

# Append data
values = [[date, provider, value, filename]]
body = {'values': values}

service.spreadsheets().values().append(
    spreadsheetId=spreadsheet_id,
    range='Sheet1!A:D',
    valueInputOption='USER_ENTERED',
    body=body
).execute()

print(f"✓ Added to Google Sheets:")
print(f"  Date: {date}")
print(f"  Provider: {provider}")
print(f"  Value: €{value}")
print(f"  File: {filename}")
print(f"\nView spreadsheet:")
print(f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
