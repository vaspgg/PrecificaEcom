import json
import urllib.parse
import urllib.request
import urllib.error

API_BASE = "https://api.mercadolibre.com"
SITE_ID = "MLB"
CURRENCY_ID = "BRL"

class MercadoLivreAPIError(RuntimeError):
    pass

def _get(path, access_token, params=None):
    query = urllib.parse.urlencode(params or {})
    url = f"{API_BASE}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise MercadoLivreAPIError(f"Mercado Livre HTTP {exc.code}: {body[:500]}") from exc
    except Exception as exc:
        raise MercadoLivreAPIError(f"Falha ao consultar Mercado Livre: {exc}") from exc

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
