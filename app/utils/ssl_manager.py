import os
import subprocess
import sys

def is_linux():
    return os.name == 'posix' and os.uname().sysname == 'Linux'

def install_certbot():
    """
    Installs certbot if not already installed.
    """
    if is_linux():
        try:
            # Check if certbot exists
            result = subprocess.run(['/usr/bin/which', 'certbot'], capture_output=True)
            if result.returncode == 0:
                print("Certbot is already installed.")
                return True
            
            print("Installing certbot...")
            subprocess.run(['/usr/bin/apt-get', 'update'], check=True)
            subprocess.run(['/usr/bin/apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'], check=True)
            return True
        except Exception as e:
            print(f"Error installing certbot: {e}")
            return False
    else:
        print("[MOCK] Would install certbot on Linux")
        return True

def request_ssl_certificate(domain, email):
    """
    Requests an SSL certificate from Let's Encrypt for the given domain.
    Returns True if successful, False otherwise.
    """
    if not domain or not email:
        print("Domain and email are required for SSL certificate")
        return False
    
    if is_linux():
        try:
            print(f"Requesting SSL certificate for {domain}...")
            
            # Set up environment with proper PATH so certbot can find nginx
            env = os.environ.copy()
            env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
            
            # Using certbot with nginx plugin (app runs as root, no sudo needed)
            result = subprocess.run([
                '/usr/bin/certbot', '--nginx',
                '-d', domain,
                '-d', f'www.{domain}',
                '--non-interactive',
                '--agree-tos',
                '--email', email,
                '--redirect'
            ], capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                print(f"SSL certificate obtained successfully for {domain}")
                return True
            else:
                print(f"Failed to obtain SSL certificate: {result.stderr}")
                print(f"stdout: {result.stdout}")
                return False
        except Exception as e:
            print(f"Error requesting SSL certificate: {e}")
            return False
    else:
        print(f"[MOCK] Would request SSL certificate for {domain} with email {email}")
        print("[MOCK] On production Linux server, this would use Let's Encrypt via certbot")
        return True

def renew_ssl_certificates():
    """
    Renews all SSL certificates that are due for renewal.
    """
    if is_linux():
        try:
            print("Checking for SSL certificates to renew...")
            result = subprocess.run(['/usr/bin/certbot', 'renew', '--quiet'], capture_output=True)
            if result.returncode == 0:
                print("SSL certificates renewed successfully")
                return True
            else:
                print(f"SSL renewal check completed with warnings")
                return True
        except Exception as e:
            print(f"Error renewing SSL certificates: {e}")
            return False
    else:
        print("[MOCK] Would renew SSL certificates on Linux")
        return True

def check_ssl_status(domain):
    """
    Checks if a domain has a valid SSL certificate.
    """
    if is_linux():
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        if os.path.exists(cert_path):
            try:
                # Check certificate expiry
                result = subprocess.run([
                    'openssl', 'x509', '-in', cert_path,
                    '-noout', '-enddate'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    return {
                        'has_ssl': True,
                        'expiry_info': result.stdout.strip()
                    }
            except Exception as e:
                print(f"Error checking SSL status: {e}")
        
        return {'has_ssl': False}
    else:
        print(f"[MOCK] Would check SSL status for {domain}")
        return {'has_ssl': False, 'mock': True}

def revoke_ssl_certificate(domain):
    """
    Revokes an SSL certificate for a domain.
    """
    if is_linux():
        try:
            print(f"Revoking SSL certificate for {domain}...")
            result = subprocess.run([
                '/usr/bin/certbot', 'revoke',
                '--cert-name', domain,
                '--delete-after-revoke'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"SSL certificate revoked for {domain}")
                return True
            else:
                print(f"Failed to revoke SSL certificate: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error revoking SSL certificate: {e}")
            return False
    else:
        print(f"[MOCK] Would revoke SSL certificate for {domain}")
        return True

def setup_ssl_auto_renewal():
    """
    Sets up automatic SSL certificate renewal via cron.
    """
    if is_linux():
        try:
            print("Setting up SSL auto-renewal...")
            # Certbot usually installs a systemd timer or cron job automatically
            # We can verify it exists
            result = subprocess.run(['/usr/bin/systemctl', 'status', 'certbot.timer'], 
                                  capture_output=True, text=True)
            
            if 'active' in result.stdout.lower():
                print("SSL auto-renewal is already configured via systemd")
                return True
            else:
                # Try to enable it
                subprocess.run(['/usr/bin/systemctl', 'enable', 'certbot.timer'], check=True)
                subprocess.run(['/usr/bin/systemctl', 'start', 'certbot.timer'], check=True)
                print("SSL auto-renewal configured successfully")
                return True
        except Exception as e:
            print(f"Note: {e}. Manual renewal may be needed.")
            return False
    else:
        print("[MOCK] Would setup SSL auto-renewal on Linux")
        return True
