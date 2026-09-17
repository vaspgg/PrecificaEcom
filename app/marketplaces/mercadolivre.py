import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
import urllib.error

API_BASE = "https://api.mercadolibre.com"
AUTH_BASE = "https://auth.mercadolivre.com.br/authorization"
SITE_ID = "MLB"
CURRENCY_ID = "BRL"

class MercadoLivreAPIError(RuntimeError):
    pass

def _request(url, method="GET", access_token=None, data=None):
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        response = exc.read().decode("utf-8", errors="replace")
        raise MercadoLivreAPIError(f"Mercado Livre HTTP {exc.code}: {response[:700]}") from exc
    except Exception as exc:
        raise MercadoLivreAPIError(f"Falha ao comunicar com Mercado Livre: {exc}") from exc

def _get(path, access_token, params=None):
    query = urllib.parse.urlencode(params or {})
    url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
    return _request(url, access_token=access_token)

def generate_pkce():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge

def authorization_url(client_id, redirect_uri, state, code_challenge):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return AUTH_BASE + "?" + urllib.parse.urlencode(params)

def exchange_code(client_id, client_secret, redirect_uri, code, code_verifier):
    return _request(f"{API_BASE}/oauth/token", method="POST", data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    })

def refresh_access_token(client_id, client_secret, refresh_token):
    return _request(f"{API_BASE}/oauth/token", method="POST", data={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })

def me(access_token):
    return _get("/users/me", access_token)

def listing_price(access_token, price, category_id, listing_type_id, logistic_type="not_specified", shipping_mode="not_specified"):
    params = {
        "price": f"{float(price):.2f}",
        "currency_id": CURRENCY_ID,
        "category_id": category_id.strip(),
        "listing_type_id": listing_type_id,
        "logistic_type": logistic_type,
        "shipping_mode": shipping_mode,
    }
    data = _get(f"/sites/{SITE_ID}/listing_prices", access_token, params)
    if isinstance(data, list):
        match = next((x for x in data if x.get("listing_type_id") == listing_type_id), data[0] if data else None)
    else:
        match = data
    if not match:
        raise MercadoLivreAPIError("A API não retornou tarifa para os parâmetros informados.")
    details = match.get("sale_fee_details") or {}
    return {
        "listing_type_id": match.get("listing_type_id"),
        "listing_type_name": match.get("listing_type_name"),
        "sale_fee_amount": float(match.get("sale_fee_amount") or 0),
        "percentage_fee": float(details.get("percentage_fee") or 0),
        "fixed_fee": float(details.get("fixed_fee") or 0),
        "financing_add_on_fee": float(details.get("financing_add_on_fee") or 0),
        "gross_amount": float(details.get("gross_amount") or 0),
        "raw": match,
    }
