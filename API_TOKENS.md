# API Token Authentication

This API uses token-based authentication for secure access to protected endpoints.

## Quick Start

### 1. Generate a Token

You have several options to generate API tokens:

#### Option A: Using the Management Command (Recommended)
```bash
# Generate or retrieve token for a user
python manage.py generate_token <username>

# Regenerate a new token (invalidates the old one)
python manage.py generate_token <username> --regenerate

# List all tokens (partial keys)
python manage.py list_tokens

# List all tokens with full keys
python manage.py list_tokens --show-keys
```

#### Option B: Via Django Admin
1. Navigate to `/admin/authtoken/token/`
2. Click "Add Token"
3. Select a user and save
4. Copy the generated token

#### Option C: Via API Endpoint
Users can obtain their token by posting credentials to the token endpoint:

```bash
curl -X POST http://localhost:8000/api/v3/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'
```

Response:
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

### 2. Use the Token

Include the token in the `Authorization` header of your API requests:

```bash
curl -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
     http://localhost:8000/api/v3/investigations/
```

## Token Endpoints

- **v3**: `/api/v3/token/`
- **v2**: `/api/v2/token/` (if enabled)
- **v1**: `/api/v1/token/` (if enabled)

## Security Best Practices

1. **Keep tokens secret**: Treat tokens like passwords
2. **Use HTTPS**: Always use HTTPS in production
3. **Rotate tokens**: Regenerate tokens periodically
4. **Limit scope**: Create separate tokens for different applications if needed
5. **Revoke unused tokens**: Delete tokens that are no longer needed

## Token Management

### Check Which Users Have Tokens

```bash
python manage.py list_tokens
```

### Regenerate a Token

```bash
python manage.py generate_token <username> --regenerate
```

### Delete a Token

Via Django Admin:
1. Go to `/admin/authtoken/token/`
2. Select the token
3. Click "Delete"

Or via Django shell:
```python
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

user = User.objects.get(username='username')
Token.objects.filter(user=user).delete()
```

## Example Usage

### Python Requests
```python
import requests

headers = {
    'Authorization': 'Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b'
}

response = requests.get('http://localhost:8000/api/v3/investigations/', headers=headers)
print(response.json())
```

### JavaScript Fetch
```javascript
const headers = {
    'Authorization': 'Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b'
};

fetch('http://localhost:8000/api/v3/investigations/', { headers })
    .then(response => response.json())
    .then(data => console.log(data));
```

### cURL
```bash
curl -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
     http://localhost:8000/api/v3/investigations/
```

## Troubleshooting

### "Invalid token" Error
- Verify the token exists in the database
- Check that the token format is correct: `Token <key>`
- Ensure the user associated with the token is active

### "Authentication credentials were not provided"
- Verify the Authorization header is included
- Check the header format: `Authorization: Token <key>`

### Token Endpoint Returns 404
- Verify the API version in the URL (`/api/v3/token/`)
- Check that `rest_framework.authtoken` is in `INSTALLED_APPS`
- Ensure migrations have been run: `python manage.py migrate`

## Configuration

Token authentication is configured in `config/settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'rest_framework.authtoken',
    # ...
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}
```
