#!/usr/bin/env python3
""                                                                   

                                                                                    
                                                                              
                                                                          
                                                                               
                                                                            
                   

                                                                            
                                                                                
                                                                            
                                                                               
                                                                     

                                                                               
                                                 
   
from __future__ import annotations
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URI = "https://oauth2.googleapis.com/token"
GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
_CACHE: dict[tuple[str, str], tuple[str, float]] = {}


def _b64(data: bytes) -> bytes:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def access_token(key_file: pathlib.Path, scope: str, now: float | None = None) -> str:
    ""                                                                     
    t = now if now is not None else time.time()
    hit = _CACHE.get((str(key_file), scope))
    if hit and hit[1] > t:
        return hit[0]
    try:
        info = json.loads(key_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"service-account file unreadable: {type(exc).__name__}") from None
    for field in ("client_email", "private_key"):
        if not info.get(field):
            raise RuntimeError(f"service-account file has no {field}")
    try:
        from google.auth import crypt
    except ImportError:
        raise RuntimeError("google-auth is not installed in this venv — "
                           "`./observatory.py deps` installs it") from None

    issued = int(t)
    claims = {"iss": info["client_email"], "scope": scope,
              "aud": info.get("token_uri") or TOKEN_URI,
              "iat": issued, "exp": issued + 3600}
    signer = crypt.RSASigner.from_service_account_info(info)
    signing_input = (_b64(json.dumps({"alg": "RS256", "typ": "JWT",
                                      "kid": info.get("private_key_id", "")}).encode())
                     + b"." + _b64(json.dumps(claims).encode()))
    assertion = signing_input + b"." + _b64(signer.sign(signing_input))

    body = urllib.parse.urlencode({"grant_type": GRANT,
                                   "assertion": assertion.decode()}).encode()
    req = urllib.request.Request(info.get("token_uri") or TOKEN_URI, data=body,
                                 headers={"Content-Type":
                                          "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            doc = json.loads(r.read())
    except urllib.error.HTTPError as e:
                                                                                
                                                               
        raise RuntimeError(f"google refused the service account (HTTP {e.code})") from None
    except OSError as e:
        raise RuntimeError(f"google token endpoint unreachable: {type(e).__name__}") from None
    tok = doc.get("access_token")
    if not tok:
        raise RuntimeError("google returned no access_token")
    _CACHE[(str(key_file), scope)] = (tok, t + float(doc.get("expires_in", 3600)) - 60)
    return tok
