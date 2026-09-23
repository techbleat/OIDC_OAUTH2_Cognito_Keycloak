import os
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from jose import jwt, JWTError

from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

from urllib.parse import urlencode

from html import escape

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="dev-secret-change-me"
)


# =========================================================
# SELECT IDENTITY PROVIDER
# =========================================================

AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "cognito").lower()

oauth = OAuth()


# =========================================================
# KEYCLOAK
# =========================================================

if AUTH_PROVIDER == "keycloak":

    REALM = os.getenv("KEYCLOAK_REALM", "banking")
    CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "banking-app")

    KEYCLOAK_PUBLIC_URL = os.getenv(
        "KEYCLOAK_PUBLIC_URL",
        "http://localhost:8080"
    )

    KEYCLOAK_INTERNAL_URL = os.getenv(
        "KEYCLOAK_INTERNAL_URL",
        "http://keycloak:8080"
    )

    LOGOUT_URL = os.getenv(
        "LOGOUT_URL",
        "http://localhost:9000/logged-out"
    )  

    oauth.register(
        name="oidc",
        client_id=CLIENT_ID,

        authorize_url=(
            f"{KEYCLOAK_PUBLIC_URL}/realms/{REALM}"
            "/protocol/openid-connect/auth"
        ),

        access_token_url=(
            f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}"
            "/protocol/openid-connect/token"
        ),

        jwks_uri=(
            f"{KEYCLOAK_INTERNAL_URL}/realms/{REALM}"
            "/protocol/openid-connect/certs"
        ),

        client_kwargs={
            "scope": "openid profile email"
        }

    )


# =========================================================
# AWS COGNITO
# =========================================================

elif AUTH_PROVIDER == "cognito":

    REGION = os.getenv(
        "COGNITO_REGION",
        "eu-west-2"
    )

    USER_POOL_ID = os.getenv(
        "COGNITO_USER_POOL_ID",
        "eu-west-2_MEXDkdeio"
    )

    CLIENT_ID = os.getenv(
        "COGNITO_CLIENT_ID",
        "7j4mg6ejkajtcere7rilcf8qik"
    )

    CLIENT_SECRET = os.getenv(
        "COGNITO_CLIENT_SECRET"
    )

    ISSUER = (
        f"https://cognito-idp.{REGION}.amazonaws.com/"
        f"{USER_POOL_ID}"
    )

    METADATA_URL = (
        f"{ISSUER}/.well-known/openid-configuration"
    )
    COGNITO_DOMAIN = os.getenv(
        "COGNITO_DOMAIN"
    ) 

    LOGOUT_URL = os.getenv(
        "LOGOUT_URL",
        "http://localhost:9000/logged-out"
    )   

    oauth.register(
        name="oidc",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,

        server_metadata_url=METADATA_URL,

        client_kwargs={
            "scope": "openid email"
        }
    )

else:
    raise RuntimeError(
        f"Unsupported AUTH_PROVIDER: {AUTH_PROVIDER}"
    )

def decode_token(token: str):
    try:
        claims = jwt.get_unverified_claims(token)
        return claims
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {exc}"
        ) from exc


def verify_token(authorization: Optional[str]):
    print(authorization)

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header"
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token"
        )

    return decode_token(token)

def verify_token_v2(authorization: Optional[str]):
    print(authorization)

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header"
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token"
        )

    try:
        jwks = requests.get(
            JWKS_URL,
            timeout=5
        ).json()

        token_header = jwt.get_unverified_header(token)

        kid = token_header["kid"]

        key = next(
            key
            for key in jwks["keys"]
            if key["kid"] == kid
        )

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={
                "verify_aud": False
            }
        )

        return payload

    except Exception as exc:
        print("TOKEN ERROR:", exc)

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
     
def require_role(user, required_role):

    realm_access = user.get("realm_access", {})
    roles = realm_access.get("roles", [])

    if required_role not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{required_role}' required"
        )


@app.get("/")
def home(request: Request):

    user = request.session.get("user")

    # -----------------------------
    # NOT LOGGED IN
    # -----------------------------
    if not user:

        provider_name = (
            "AWS Cognito"
            if AUTH_PROVIDER == "cognito"
            else "Keycloak"
        )

        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Secure Banking</title>

            <style>
                * {{
                    box-sizing: border-box;
                }}

                body {{
                    margin: 0;
                    font-family:
                        -apple-system,
                        BlinkMacSystemFont,
                        "Segoe UI",
                        Roboto,
                        Arial,
                        sans-serif;

                    background:
                        linear-gradient(
                            135deg,
                            #f4f7fb 0%,
                            #eef4ff 100%
                        );

                    color: #172033;
                    min-height: 100vh;
                }}

                .navbar {{
                    height: 72px;
                    background: white;
                    border-bottom: 1px solid #e5e7eb;

                    display: flex;
                    align-items: center;
                    justify-content: space-between;

                    padding: 0 7%;
                }}

                .brand {{
                    font-size: 21px;
                    font-weight: 750;
                    color: #175cd3;
                }}

                .secure {{
                    font-size: 13px;
                    color: #667085;
                }}

                .hero {{
                    min-height: calc(100vh - 72px);

                    display: flex;
                    justify-content: center;
                    align-items: center;

                    padding: 50px 20px;
                }}

                .login-card {{
                    width: 100%;
                    max-width: 540px;

                    background: white;

                    border: 1px solid #eaecf0;
                    border-radius: 20px;

                    padding: 50px;

                    box-shadow:
                        0 20px 50px rgba(16,24,40,.08);

                    text-align: center;
                }}

                .shield {{
                    width: 65px;
                    height: 65px;

                    margin: 0 auto 25px;

                    border-radius: 18px;

                    display: flex;
                    align-items: center;
                    justify-content: center;

                    background: #eaf2ff;
                    color: #175cd3;

                    font-size: 30px;
                }}

                h1 {{
                    margin: 0 0 12px;
                    font-size: 32px;
                }}

                .description {{
                    color: #667085;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }}

                .login-button {{
                    display: block;
                    width: 100%;

                    padding: 14px;

                    background: #175cd3;
                    color: white;

                    border-radius: 9px;

                    text-decoration: none;
                    font-weight: 650;

                    transition: .2s;
                }}

                .login-button:hover {{
                    background: #134ca8;
                    transform: translateY(-1px);
                }}

                .provider {{
                    margin-top: 25px;
                    padding-top: 20px;

                    border-top: 1px solid #eee;

                    color: #667085;
                    font-size: 13px;
                }}

                .provider strong {{
                    color: #344054;
                }}

                .zero-trust {{
                    margin-top: 20px;
                    font-size: 12px;
                    color: #98a2b3;
                }}

            </style>
        </head>

        <body>

            <nav class="navbar">

                <div class="brand">
                    SecureBank
                </div>

                <div class="secure">
                    🔒 Secure Banking
                </div>

            </nav>

            <main class="hero">

                <div class="login-card">

                    <div class="shield">
                        🛡
                    </div>

                    <h1>Welcome to SecureBank</h1>

                    <div class="description">
                        Access your secure banking dashboard
                        using your verified digital identity.
                    </div>

                    <a
                        class="login-button"
                        href="/login"
                    >
                        Sign in securely
                    </a>

                    <div class="provider">

                        Authentication provided by

                        <strong>
                            {provider_name}
                        </strong>

                    </div>

                    <div class="zero-trust">
                        Never Trust. Always Verify.
                    </div>

                </div>

            </main>

        </body>
        </html>
        """)


    # -----------------------------
    # LOGGED IN
    # -----------------------------

    username = (
        user.get("preferred_username")
        or user.get("email")
        or user.get("cognito:username")
        or "User"
    )

    provider_name = (
        "AWS Cognito"
        if AUTH_PROVIDER == "cognito"
        else "Keycloak"
    )

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>

    <head>

        <title>Secure Banking Dashboard</title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;

                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Roboto,
                    Arial,
                    sans-serif;

                background: #f4f7fb;
                color: #172033;
            }}

            .navbar {{
                height: 72px;
                background: white;

                border-bottom: 1px solid #e5e7eb;

                display: flex;
                align-items: center;
                justify-content: space-between;

                padding: 0 7%;
            }}

            .brand {{
                color: #175cd3;
                font-size: 21px;
                font-weight: 750;
            }}

            .nav-right {{
                display: flex;
                align-items: center;
                gap: 18px;
            }}

            .identity {{
                font-size: 13px;
                color: #667085;
            }}

            .identity strong {{
                color: #344054;
            }}

            .logout {{
                text-decoration: none;

                color: #344054;

                border: 1px solid #d0d5dd;

                padding: 8px 14px;

                border-radius: 8px;

                font-size: 13px;
                font-weight: 600;
            }}

            .container {{
                max-width: 1050px;

                margin: 55px auto;

                padding: 0 25px;
            }}

            .welcome {{
                margin-bottom: 35px;
            }}

            .welcome h1 {{
                margin-bottom: 8px;
                font-size: 32px;
            }}

            .welcome p {{
                color: #667085;
                margin: 0;
            }}

            .verified {{
                display: inline-block;

                margin-top: 16px;

                padding: 7px 12px;

                background: #ecfdf3;
                color: #027a48;

                border-radius: 20px;

                font-size: 13px;
                font-weight: 600;
            }}

            .grid {{
                display: grid;

                grid-template-columns:
                    repeat(2, 1fr);

                gap: 22px;
            }}

            .card {{
                background: white;

                border: 1px solid #eaecf0;

                border-radius: 14px;

                padding: 28px;

                text-decoration: none;

                color: inherit;

                box-shadow:
                    0 5px 20px rgba(16,24,40,.04);

                transition: .2s;
            }}

            .card:hover {{
                transform: translateY(-3px);

                box-shadow:
                    0 12px 30px rgba(16,24,40,.08);

                border-color: #c7d7fe;
            }}

            .icon {{
                width: 48px;
                height: 48px;

                display: flex;
                align-items: center;
                justify-content: center;

                border-radius: 12px;

                background: #eaf2ff;

                font-size: 23px;

                margin-bottom: 20px;
            }}

            .card h3 {{
                margin: 0 0 8px;
                font-size: 19px;
            }}

            .card p {{
                color: #667085;

                margin: 0;

                font-size: 14px;
                line-height: 1.5;
            }}

            .arrow {{
                margin-top: 20px;

                color: #175cd3;

                font-weight: 600;

                font-size: 14px;
            }}

            .security {{
                margin-top: 30px;

                background: #f8faff;

                border: 1px solid #dbe7ff;

                padding: 20px;

                border-radius: 12px;

                display: flex;

                justify-content: space-between;
                align-items: center;
            }}

            .security-title {{
                font-weight: 650;
                margin-bottom: 4px;
            }}

            .security-text {{
                color: #667085;
                font-size: 13px;
            }}

            .provider-badge {{
                background: #eaf2ff;
                color: #175cd3;

                padding: 7px 12px;

                border-radius: 20px;

                font-size: 12px;
                font-weight: 650;
            }}

            @media(max-width: 700px) {{

                .grid {{
                    grid-template-columns: 1fr;
                }}

                .identity {{
                    display: none;
                }}

                .security {{
                    align-items: flex-start;
                    gap: 15px;
                    flex-direction: column;
                }}

            }}

        </style>

    </head>

    <body>

        <nav class="navbar">

            <div class="brand">
                SecureBank
            </div>

            <div class="nav-right">

                <div class="identity">

                    Signed in as
                    <strong>
                        {username}
                    </strong>

                </div>

                <a
                    href="/logout"
                    class="logout"
                >
                    Logout
                </a>

            </div>

        </nav>


        <main class="container">

            <section class="welcome">

                <h1>
                    Welcome, {username}
                </h1>

                <p>
                    Your secure banking dashboard
                </p>

                <div class="verified">
                    ✓ Identity verified
                </div>

            </section>


            <section class="grid">

                <a
                    href="/balance"
                    class="card"
                >

                    <div class="icon">
                        £
                    </div>

                    <h3>
                        Account Balance
                    </h3>

                    <p>
                        View your account details
                        and current available balance.
                    </p>

                    <div class="arrow">
                        View balance →
                    </div>

                </a>


                <a
                    href="/profile"
                    class="card"
                >

                    <div class="icon">
                        👤
                    </div>

                    <h3>
                        My Profile
                    </h3>

                    <p>
                        View your verified identity
                        and authentication information.
                    </p>

                    <div class="arrow">
                        View profile →
                    </div>

                </a>

            </section>


            <section class="security">

                <div>

                    <div class="security-title">
                        🔒 Secure Session
                    </div>

                    <div class="security-text">
                        Your identity has been verified
                        using OpenID Connect.
                    </div>

                </div>

                <div class="provider-badge">
                    {provider_name}
                </div>

            </section>

        </main>

    </body>

    </html>
    """)

@app.get("/home")
def home(request: Request):

    user = request.session.get("user")

    if not user:
        return HTMLResponse(
            """
            <h1>Banking App</h1>
            <p>You are not logged in.</p>
            <a href="/login">Login with Keycloak</a>
            """
        )

    username = user.get("preferred_username")

    return HTMLResponse(
        f"""
        <h1>Banking App</h1>

        <p>Logged in as: <b>{username}</b></p>

        <p><a href="/balance">View balance</a></p>

        <p><a href="/logout">Logout</a></p>
        """
    )

# =========================================================
# PROFILE
# =========================================================

@app.get("/profile")
def profile(request: Request):

    user = request.session.get("user")

    if not user:
        return RedirectResponse("/login")

    return HTMLResponse(
        pretty_page(
            "Your Profile",
            user,
            AUTH_PROVIDER
        )
    )

@app.get("/login")
async def login(request: Request):

    redirect_uri = str(request.url_for("callback"))

    print("\n========== OIDC DEBUG ==========", flush=True)
    print("AUTH_PROVIDER :", AUTH_PROVIDER, flush=True)
    print("CLIENT_ID     :", CLIENT_ID, flush=True)
    print("REDIRECT_URI  :", redirect_uri, flush=True)
    # print("METADATA_URL  :", METADATA_URL, flush=True)
    print("================================\n", flush=True)

    response = await oauth.oidc.authorize_redirect(
        request,
        redirect_uri
    )

    print(
        "AUTHORIZATION URL:",
        response.headers.get("location"),
        flush=True
    )

    return response

@app.get("/callback")
async def callback(request: Request):

    token = await oauth.oidc.authorize_access_token(request)

    user = token.get("userinfo")

    request.session["user"] = dict(user)

    request.session["access_token"] = token["access_token"]
    
    print("ID TOKEN:", token.get("id_token"), flush=True)
    print("ACCESS TOKEN:", token.get("access_token"), flush=True)

    return RedirectResponse("/")


@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/balance-old")
def balance(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    print(authorization)

    claims = verify_token(authorization)
    return {
        "balance": 4000
    }


@app.get("/balance")
def balance(request: Request):

    user = request.session.get("user")

    if not user:
        return RedirectResponse("/login")

    username = (
        user.get("preferred_username")
        or user.get("email")
        or user.get("cognito:username")
        or "Unknown"
    )

    data = {
        "Account Holder": username,
        "Account Type": "Current Account",
        "Currency": "GBP",
        "Available Balance": "£5,000.00",
        "Authentication": "Verified",
    }

    return HTMLResponse(
        pretty_page(
            "Account Balance",
            data,
            AUTH_PROVIDER
        )
    )

# =========================================================
# LOGOUT
# =========================================================
@app.get("/logged-out")
def logged_out():
    return HTMLResponse("""
        <h2>You have been logged out</h2>
        <p>Your application and Cognito sessions have been cleared.</p>
        <a href="/login">Login again</a>
    """)


@app.get("/logout")
def logout(request: Request):

    # Get this BEFORE clearing the session
    id_token = request.session.get("id_token")

    print("ID TOKEN AVAILABLE:", bool(id_token), flush=True)

    # Now clear local FastAPI session

    # Clear FastAPI session
    request.session.clear()

    if AUTH_PROVIDER == "cognito":

        params = urlencode({
            "client_id": CLIENT_ID,
            "logout_uri": LOGOUT_URL
        })

        logout_url = (
            f"{COGNITO_DOMAIN}/logout?{params}"
        )

        print("COGNITO LOGOUT URL:", logout_url, flush=True)

        return RedirectResponse(logout_url)

        # -------------------------
    # KEYCLOAK LOGOUT
    # -------------------------
    if AUTH_PROVIDER == "keycloak":

        params = {
            "client_id": CLIENT_ID,
            "post_logout_redirect_uri": LOGOUT_URL
        }

        # Recommended when available
        if id_token:
            params["id_token_hint"] = id_token

        logout_url = (
            f"{KEYCLOAK_PUBLIC_URL}"
            f"/realms/{REALM}"
            f"/protocol/openid-connect/logout?"
            f"{urlencode(params)}"
        )

        print("KEYCLOAK LOGOUT URL:", logout_url, flush=True)

        return RedirectResponse(logout_url)

    return RedirectResponse("/logged-out")




def pretty_page(title, data, provider=None):

    rows = ""

    for key, value in data.items():

        # Make lists/dicts readable
        if isinstance(value, (list, dict)):
            value = str(value)

        rows += f"""
        <div class="row">
            <div class="key">{escape(str(key))}</div>
            <div class="value">{escape(str(value))}</div>
        </div>
        """

    provider_html = ""

    if provider:
        provider_html = f"""
        <div class="provider">
            Identity Provider:
            <strong>{escape(provider.upper())}</strong>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{escape(title)}</title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                font-family:
                    -apple-system,
                    BlinkMacSystemFont,
                    "Segoe UI",
                    Roboto,
                    Arial,
                    sans-serif;

                background: #f4f7fb;
                color: #172033;
            }}

            .page {{
                max-width: 900px;
                margin: 60px auto;
                padding: 0 25px;
            }}

            .header {{
                margin-bottom: 25px;
            }}

            .header h1 {{
                margin: 0 0 8px;
                font-size: 32px;
            }}

            .subtitle {{
                color: #667085;
                font-size: 15px;
            }}

            .provider {{
                display: inline-block;
                margin-top: 15px;
                padding: 7px 13px;
                background: #e8f1ff;
                color: #175cd3;
                border-radius: 20px;
                font-size: 13px;
            }}

            .card {{
                background: white;
                border-radius: 14px;
                box-shadow:
                    0 8px 30px rgba(0,0,0,.06);
                overflow: hidden;
                border: 1px solid #eaecf0;
            }}

            .row {{
                display: grid;
                grid-template-columns: 220px 1fr;
                border-bottom: 1px solid #eee;
                min-height: 55px;
            }}

            .row:last-child {{
                border-bottom: none;
            }}

            .key {{
                padding: 17px 20px;
                background: #fafbfc;
                font-weight: 600;
                color: #475467;
            }}

            .value {{
                padding: 17px 20px;
                overflow-wrap: anywhere;
            }}

            .actions {{
                margin-top: 25px;
                display: flex;
                gap: 12px;
            }}

            .btn {{
                text-decoration: none;
                padding: 11px 18px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }}

            .home {{
                background: #175cd3;
                color: white;
            }}

            .logout {{
                background: white;
                color: #344054;
                border: 1px solid #d0d5dd;
            }}

            @media(max-width: 650px) {{

                .page {{
                    margin-top: 30px;
                }}

                .row {{
                    grid-template-columns: 1fr;
                }}

                .key {{
                    padding-bottom: 5px;
                    background: white;
                }}

                .value {{
                    padding-top: 5px;
                }}
            }}

        </style>
    </head>

    <body>

        <div class="page">

            <div class="header">

                <h1>{escape(title)}</h1>

                <div class="subtitle">
                    Secure Banking Application
                </div>

                {provider_html}

            </div>

            <div class="card">

                {rows}

            </div>

            <div class="actions">

                <a class="btn home" href="/">
                    ← Back to Home
                </a>

                <a class="btn logout" href="/logout">
                    Logout
                </a>

            </div>

        </div>

    </body>
    </html>
    """
    

