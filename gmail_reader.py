#!/usr/bin/env python3
"""
Gmail IMAP Reader for OpenClaw
Securely connects to Gmail and provides email reading capabilities
"""

import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys
import json
from datetime import datetime, timedelta

# Gmail IMAP settings
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# Gmail SMTP settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def get_credentials():
    """Get Gmail credentials from environment or keychain"""
    # For now, using stored app password
    # TODO: Move to macOS Keychain for better security
    return {
        'email': 'pedromoreira.intel@gmail.com',
        'password': 'mxwznqnjophmlaky'  # Stored without spaces
    }

def connect_gmail(email_address, password):
    """Connect to Gmail via IMAP"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_address, password)
        return mail
    except Exception as e:
        print(f"Error connecting to Gmail: {e}", file=sys.stderr)
        return None

def decode_mime_header(header):
    """Decode MIME encoded email header"""
    if header is None:
        return ""
    decoded = decode_header(header)
    result = []
    for part, encoding in decoded:
        if isinstance(part, bytes):
            result.append(part.decode(encoding or 'utf-8', errors='ignore'))
        else:
            result.append(part)
    return ''.join(result)

def get_email_body(msg):
    """Extract email body from message"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition"))
            
            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            pass
    
    return body.strip()

def search_emails(mail, query="ALL", limit=10):
    """Search emails with query"""
    try:
        mail.select("INBOX")
        status, messages = mail.search(None, query)
        
        if status != "OK":
            return []
        
        email_ids = messages[0].split()
        email_ids = email_ids[-limit:]  # Get last N emails
        email_ids.reverse()  # Newest first
        
        emails = []
        for email_id in email_ids:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK":
                continue
            
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject = decode_mime_header(msg["Subject"])
                    from_ = decode_mime_header(msg["From"])
                    date = msg["Date"]
                    body = get_email_body(msg)
                    
                    emails.append({
                        'id': email_id.decode(),
                        'from': from_,
                        'subject': subject,
                        'date': date,
                        'body': body[:500] + ('...' if len(body) > 500 else '')  # Truncate long bodies
                    })
        
        return emails
    
    except Exception as e:
        print(f"Error searching emails: {e}", file=sys.stderr)
        return []

def download_attachments(mail, email_id, download_dir="/tmp/email_attachments"):
    """Download attachments from an email"""
    import os
    os.makedirs(download_dir, exist_ok=True)
    
    try:
        mail.select("INBOX")  # Select inbox first
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            return []
        
        attachments = []
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    
                    filename = part.get_filename()
                    if filename:
                        # Decode filename if needed
                        filename = decode_mime_header(filename)
                        filepath = os.path.join(download_dir, filename)
                        
                        # Save attachment
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        
                        attachments.append({
                            'filename': filename,
                            'path': filepath,
                            'size': os.path.getsize(filepath)
                        })
        
        return attachments
    
    except Exception as e:
        print(f"Error downloading attachments: {e}", file=sys.stderr)
        return []

def send_email(from_email, password, to_email, subject, body):
    """Send an email via Gmail SMTP"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to SMTP server
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(from_email, password)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}", file=sys.stderr)
        return False

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: gmail_reader.py <command> [args]")
        print("Commands:")
        print("  test              - Test connection")
        print("  recent [N]        - Get N recent emails (default 10)")
        print("  search <query>    - Search emails")
        print("  unread            - Get unread emails")
        print("  send <to> <subject> <body>  - Send an email")
        print("  download <email_id>  - Download attachments from email")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Get credentials
    creds = get_credentials()
    
    # Execute command
    if command == "send":
        if len(sys.argv) < 5:
            print("Error: send requires <to> <subject> <body>", file=sys.stderr)
            sys.exit(1)
        to_email = sys.argv[2]
        subject = sys.argv[3]
        body = sys.argv[4]
        
        success = send_email(creds['email'], creds['password'], to_email, subject, body)
        if success:
            print(f"✓ Email sent to {to_email}")
        else:
            print(f"✗ Failed to send email", file=sys.stderr)
            sys.exit(1)
        return
    
    # Connect to Gmail (for all other commands)
    mail = connect_gmail(creds['email'], creds['password'])
    if not mail:
        sys.exit(1)
    
    # Execute command
    if command == "test":
        print("✓ Successfully connected to Gmail!")
        mail.logout()
        
    elif command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        emails = search_emails(mail, "ALL", limit)
        print(json.dumps(emails, indent=2, ensure_ascii=False))
        mail.logout()
        
    elif command == "unread":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        emails = search_emails(mail, "UNSEEN", limit)
        print(json.dumps(emails, indent=2, ensure_ascii=False))
        mail.logout()
        
    elif command == "search":
        if len(sys.argv) < 3:
            print("Error: search requires a query", file=sys.stderr)
            sys.exit(1)
        query = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        emails = search_emails(mail, query, limit)
        print(json.dumps(emails, indent=2, ensure_ascii=False))
        mail.logout()
        
    elif command == "download":
        if len(sys.argv) < 3:
            print("Error: download requires an email ID", file=sys.stderr)
            sys.exit(1)
        email_id = sys.argv[2].encode()
        download_dir = sys.argv[3] if len(sys.argv) > 3 else "/tmp/email_attachments"
        attachments = download_attachments(mail, email_id, download_dir)
        print(json.dumps(attachments, indent=2))
        mail.logout()
        
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

def download_attachments(mail, email_id, download_dir="/tmp/email_attachments"):
    """Download attachments from an email"""
    import os
    os.makedirs(download_dir, exist_ok=True)
    
    try:
        mail.select("INBOX")  # Select inbox first
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            return []
        
        attachments = []
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    
                    filename = part.get_filename()
                    if filename:
                        # Decode filename if needed
                        filename = decode_mime_header(filename)
                        filepath = os.path.join(download_dir, filename)
                        
                        # Save attachment
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        
                        attachments.append({
                            'filename': filename,
                            'path': filepath,
                            'size': os.path.getsize(filepath)
                        })
        
        return attachments
    
    except Exception as e:
        print(f"Error downloading attachments: {e}", file=sys.stderr)
        return []
