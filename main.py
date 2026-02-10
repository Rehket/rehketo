from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, OAuth2AuthorizationCodeBearer
import jwt
import logging
from dotenv import load_dotenv
from os import getenv
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


security = HTTPBearer()

load_dotenv()

CLIENT_ID=getenv("CLIENT_ID")
TENANT_ID=getenv("TENANT_ID")

AUTHORITY=f"https://login.microsoftonline.com/{TENANT_ID}"
JWKS_URL=f"{AUTHORITY}/discovery/v2.0/keys"
ISSUER=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
SCOPES = {
        f"api://{CLIENT_ID}/Chat.Write": "Write Chats",
        f"api://{CLIENT_ID}/Chat.Read": "Read Chats",
    }


_jwks_client = jwt.PyJWKClient(JWKS_URL)



oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize",
    tokenUrl=f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
    scopes=SCOPES,
    auto_error=False
)

def validate_token( 
    request: Request,
    oauth2_token: str | None = Depends(oauth2_scheme)
    ) -> Dict:

    token = oauth2_token
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            raise HTTPException(status_code=401, detail="Missing Token")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token Expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}")


def require_role(required_role: str):
    def role_checker(token_data: dict = Depends(validate_token)):
        roles = token_data.get("roles", [])
        if required_role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return token_data
    return role_checker


def require_scope(required_scope: str):
    def scope_checker(token_data: dict = Depends(validate_token)):
        # Scopes are in space-delimited string in scp claim
        scopes = token_data.get("scp", "").split()
        if required_scope not in scopes:
            raise HTTPException(status_code=403, detail="Insufficient scope")
    return scope_checker


app = FastAPI(
    title="Rehketo API",
    swagger_ui_init_oauth={
        "client_id": CLIENT_ID,
        "scopes": " ".join(SCOPES.keys()),
        "usePkceWithAuthorizationCodeGrant": True
    },
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect"
)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/secret_hello")
async def read_secret(user: dict = Depends(require_role("Chat.User"))):
    return {"secret": "tee hee"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )