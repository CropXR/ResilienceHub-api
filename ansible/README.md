# Django Deployment with Ansible

This package contains all the necessary files to deploy your Django application to a production server with Ansible.

## Files Included

- `deploy.yml` - The main Ansible playbook
- `inventory.ini.example` - Server inventory template (copy to `inventory.ini`)
- `vars.yml.example` - Variables template (copy to `vars.yml`)
- `deploy.sh` - Helper script to run the deployment

## Initial Setup

1. **Copy the template files:**
   ```bash
   cp ansible/inventory.ini.example ansible/inventory.ini
   cp ansible/playbooks/vars.yml.example ansible/playbooks/vars.yml
   ```

2. **Generate secure secrets:**
   ```bash
   python -c 'import secrets; print("Django Secret Key:", secrets.token_urlsafe(50))'
   python -c 'import secrets; print("Admin Password:", secrets.token_urlsafe(32))'
   ```

3. **Edit the files with your actual values** (these files are gitignored for security)

## Quick Start

The easiest way to deploy is using the included helper script:

```bash
chmod +x setup.sh
./setup.sh
```

This script will:
1. Check if Ansible is installed and install it if needed
2. Generate a secure Django secret key
3. Ask for your server details, domain, and GitHub repository
4. Create the necessary configuration files
5. Optionally run the deployment

## Manual Setup

If you prefer to set things up manually:

1. Update `inventory.ini` with your server IP and SSH user
2. Update `vars.yml` with your specific settings:
   - `domain_name`: Your domain name
   - `github_repo`: Your GitHub repository URL
   - `django_secret_key`: Generate a secure key with `python -c 'import secrets; print(secrets.token_urlsafe(50))'`

3. Run the Ansible playbook:
   ```bash
   ansible-playbook -i inventory.ini deploy.yml
   ```

## What Gets Deployed

The deployment includes:

- Nginx as the web server
- Gunicorn as the application server
- Automatic SQLite database backups
- Easy deployment script for updates
- Environment variables for production settings
- Static and media file serving
- Service configuration for system startup

## After Deployment

Once deployed, you can:

1. Access your site at your domain
2. Update your application when needed:
   ```bash
   ssh your-user@your-server
   sudo -u www-data /opt/resiliencehub/deploy.sh
   ```

3. View logs:
   ```bash
   sudo tail -f /var/log/resiliencehub/error.log
   ```

## SSL Setup

The deployment prepares your server for SSL. After deployment, run:

```bash
ssh your-user@your-server
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Customization

If you need to customize the deployment further, modify the `deploy.yml` playbook. The file is well-commented to help you understand each section.

## Troubleshooting

If you encounter issues:

1. Check the Gunicorn logs: `sudo journalctl -u gunicorn-resiliencehub`
2. Check the Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Verify environment variables: `cat /opt/resiliencehub/.env`

## Security Notes

1. The deployment sets up secure Django settings
2. The `.env` file permissions are restricted to the application user
3. SSL should be configured after the initial deployment