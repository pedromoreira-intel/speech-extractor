#!/usr/bin/env python3
"""
Invoice Processor for OpenClaw
Extracts invoice data and uploads to Google Sheets/Drive
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

def extract_invoice_data_ocr(pdf_path):
    """Extract invoice data using OCR"""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        
        # Convert PDF to images
        images = convert_from_path(pdf_path)
        
        # Extract text from all pages
        full_text = ""
        for img in images:
            text = pytesseract.image_to_string(img, lang='por+eng')
            full_text += text + "\n"
        
        return parse_invoice_text(full_text, pdf_path)
    
    except Exception as e:
        print(f"Error with OCR: {e}", file=sys.stderr)
        return None

def parse_invoice_text(text, pdf_path):
    """Parse invoice text to extract key data"""
    data = {
        'filename': os.path.basename(pdf_path),
        'date': None,
        'provider': None,
        'value': None,
        'raw_text': text[:500]  # Store snippet for debugging
    }
    
    # Extract date (various formats)
    date_patterns = [
        r'(\d{2}[/-]\d{2}[/-]\d{4})',  # DD/MM/YYYY or DD-MM-YYYY
        r'(\d{4}[/-]\d{2}[/-]\d{2})',  # YYYY/MM/DD or YYYY-MM-DD
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            data['date'] = match.group(1)
            break
    
    # Extract provider (look for known telecom companies)
    providers = ['MEO', 'NOS', 'Vodafone', 'NOWO', 'Lycamobile']
    for provider in providers:
        if provider.lower() in text.lower():
            data['provider'] = provider
            break
    
    # If no provider found, look for company name near top
    if not data['provider']:
        lines = text.split('\n')[:10]  # Check first 10 lines
        for line in lines:
            if len(line) > 3 and not line.isdigit():
                data['provider'] = line.strip()
                break
    
    # Extract value (look for euro amounts)
    # Priority 1: Look for "Valor a Pagar" (Amount to Pay) - Portuguese invoices
    # Handle formats: "Valor a Pagar € 81,71" or "Valor a Pagar €81 71" (with spaces)
    valor_pagar_patterns = [
        r'Valor\s+a\s+Pagar\s+€\s*(\d+)\s*[.,]?\s*(\d{2})',  # € 81,71 or €81 71
        r'Valor\s+a\s+Pagar[:\s]+(\d+[.,]\d{2})',  # 81,71 or 81.71
    ]
    
    value_found = False
    for pattern in valor_pagar_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:  # Format with spaces: "81 71"
                value = f"{match.group(1)}.{match.group(2)}"
            else:  # Format with comma/dot: "81,71"
                value = match.group(1).replace(',', '.')
            data['value'] = float(value)
            value_found = True
            break
    
    if not value_found:
        # Fallback to other patterns
        value_patterns = [
            r'Total[:\s]+(\d+[.,]\d{2})',  # Total: 123.45
            r'(\d+[.,]\d{2})\s*€',  # 123.45 € or 123,45 €
            r'€\s*(\d+[.,]\d{2})',  # € 123.45
        ]
        for pattern in value_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).replace(',', '.')
                data['value'] = float(value)
                break
    
    return data

def upload_to_google_sheets(data, spreadsheet_id=None):
    """Upload invoice data to Google Sheets"""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
        
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        
        creds = None
        token_path = os.path.expanduser('~/.openclaw/workspace/config/token.pickle')
        creds_path = os.path.expanduser('~/.openclaw/workspace/config/credentials.json')
        
        # Load existing token
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
            
            # Save token
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build service
        service = build('sheets', 'v4', credentials=creds)
        
        # Create spreadsheet if needed
        if not spreadsheet_id:
            spreadsheet_id = create_expenses_spreadsheet(service)
        
        # Append row
        values = [[
            data['date'],
            data['provider'],
            data['value'],
            data['filename']
        ]]
        
        body = {'values': values}
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='Sheet1!A:D',
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        
        return spreadsheet_id
    
    except Exception as e:
        print(f"Error uploading to Sheets: {e}", file=sys.stderr)
        return None

def upload_to_google_drive(pdf_path, folder_name='Expenses'):
    """Upload PDF to Google Drive folder"""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import pickle
        
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        creds = None
        token_path = os.path.expanduser('~/.openclaw/workspace/config/drive_token.pickle')
        creds_path = os.path.expanduser('~/.openclaw/workspace/config/credentials.json')
        
        # Load/refresh token (same as Sheets)
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        service = build('drive', 'v3', credentials=creds)
        
        # Find or create folder
        folder_id = find_or_create_folder(service, folder_name)
        
        # Upload file
        file_metadata = {
            'name': os.path.basename(pdf_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(pdf_path, mimetype='application/pdf')
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return file.get('webViewLink')
    
    except Exception as e:
        print(f"Error uploading to Drive: {e}", file=sys.stderr)
        return None

def find_or_create_folder(service, folder_name):
    """Find or create a Google Drive folder"""
    # Search for folder
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    
    folders = results.get('files', [])
    
    if folders:
        return folders[0]['id']
    
    # Create folder
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

def create_expenses_spreadsheet(service):
    """Create a new expenses tracking spreadsheet"""
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
    print(f"Created spreadsheet: {result['spreadsheetUrl']}")
    return result['spreadsheetId']

def main():
    if len(sys.argv) < 2:
        print("Usage: invoice_processor.py <pdf_path> [spreadsheet_id]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    spreadsheet_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Processing invoice: {pdf_path}")
    
    # Extract data
    data = extract_invoice_data_ocr(pdf_path)
    if not data:
        print("Failed to extract invoice data")
        sys.exit(1)
    
    print(f"Extracted data: {json.dumps(data, indent=2)}")
    
    # Upload to Sheets
    sheet_id = upload_to_google_sheets(data, spreadsheet_id)
    if sheet_id:
        print(f"✓ Added to Google Sheets: {sheet_id}")
    
    # Upload PDF to Drive
    drive_link = upload_to_google_drive(pdf_path, 'Expenses')
    if drive_link:
        print(f"✓ Uploaded to Drive: {drive_link}")

if __name__ == "__main__":
    main()
