import base64
import hashlib
import json
import re
import secrets
import urllib.parse
import urllib.request
import urllib.error

API_BASE = "https://api.mercadolibre.com"
AUTH_BASE = "https://auth.mercadolivre.com.br/authorization"
SITE_ID = "MLB"
CURRENCY_ID = "BRL"

class MercadoLivreAPIError(RuntimeError): pass

def _request(url, method="GET", access_token=None, data=None, json_data=None):
    headers={"Accept":"application/json","User-Agent":"PrecificaEcom/0.9"}
    if access_token: headers["Authorization"]=f"Bearer {access_token}"
    body=None
    if json_data is not None:
        body=json.dumps(json_data).encode("utf-8"); headers["Content-Type"]="application/json"
    elif data is not None:
        body=urllib.parse.urlencode(data).encode("utf-8"); headers["Content-Type"]="application/x-www-form-urlencoded"
    req=urllib.request.Request(url,data=body,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            raw=resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        response=exc.read().decode("utf-8",errors="replace")
        if exc.code==403 and ("PolicyAgent" in response or "PA_UNAUTHORIZED" in response):
            raise MercadoLivreAPIError("Permissão insuficiente no Mercado Livre para esta consulta. Reconecte a conta após habilitar as permissões de Produtos/Publicações no DevCenter. Detalhe: "+response[:350]) from exc
        raise MercadoLivreAPIError(f"Mercado Livre HTTP {exc.code}: {response[:700]}") from exc
    except Exception as exc:
        if isinstance(exc,MercadoLivreAPIError): raise
        raise MercadoLivreAPIError(f"Falha ao comunicar com Mercado Livre: {exc}") from exc

def _get(path, access_token=None, params=None):
    query=urllib.parse.urlencode(params or {})
    return _request(f"{API_BASE}{path}"+(f"?{query}" if query else ""),access_token=access_token)

def generate_pkce():
    verifier=secrets.token_urlsafe(64); digest=hashlib.sha256(verifier.encode("ascii")).digest(); return verifier,base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

def authorization_url(client_id,redirect_uri,state,code_challenge):
    return AUTH_BASE+"?"+urllib.parse.urlencode({"response_type":"code","client_id":client_id,"redirect_uri":redirect_uri,"state":state,"code_challenge":code_challenge,"code_challenge_method":"S256"})

def exchange_code(client_id,client_secret,redirect_uri,code,code_verifier):
    return _request(f"{API_BASE}/oauth/token",method="POST",data={"grant_type":"authorization_code","client_id":client_id,"client_secret":client_secret,"code":code,"redirect_uri":redirect_uri,"code_verifier":code_verifier})

def refresh_access_token(client_id,client_secret,refresh_token):
    return _request(f"{API_BASE}/oauth/token",method="POST",data={"grant_type":"refresh_token","client_id":client_id,"client_secret":client_secret,"refresh_token":refresh_token})

def me(access_token): return _get("/users/me",access_token)

def predict_categories(access_token,title,limit=3):
    title=(title or '').strip()
    if not title: raise MercadoLivreAPIError("Informe a descrição do produto para localizar a categoria.")
    params={"q":title,"limit":max(1,min(int(limit),8))}
    try: data=_get(f"/sites/{SITE_ID}/domain_discovery/search",access_token,params)
    except MercadoLivreAPIError: data=_get(f"/sites/{SITE_ID}/domain_discovery/search",None,params)
    return [{"category_id":x.get("category_id",""),"category_name":x.get("category_name",""),"domain_id":x.get("domain_id",""),"domain_name":x.get("domain_name","")} for x in (data or [])]

def extract_item_id(text):
    raw=urllib.parse.unquote(text or '')
    upper=raw.upper().replace('-','')
    wid=re.search(r'[?&#]WID=(MLB\d{6,})',upper)
    if wid:return wid.group(1)
    ids=re.findall(r'\bMLB\d{6,}\b',upper)
    if ids:return ids[-1]
    nums=re.findall(r'(?:WID|ITEM[_ ]?ID)[^0-9]*(\d{6,})',upper)
    return f"MLB{nums[-1]}" if nums else None

def item_details(access_token,item_or_url):
    item_id=extract_item_id(item_or_url)
    if not item_id: raise MercadoLivreAPIError("Não encontrei o código MLB do anúncio no link. Tente colar o link completo ou o código MLB do anúncio.")
    errors=[]
    for token in (None,access_token):
        try:
            data=_get(f"/items/{item_id}",token,{"include_attributes":"all"})
            return {"id":data.get("id"),"title":data.get("title"),"category_id":data.get("category_id"),"price":data.get("price"),"permalink":data.get("permalink"),"listing_type_id":data.get("listing_type_id"),"shipping":data.get("shipping") or {},"seller_id":data.get("seller_id"),"attributes":data.get("attributes") or [],"pictures":data.get("pictures") or [],"raw":data}
        except MercadoLivreAPIError as e: errors.append(str(e))
    raise MercadoLivreAPIError("Não foi possível consultar o anúncio. "+" | ".join(errors))

def category_details(access_token,category_id):
    for token in (None,access_token):
        try:return _get(f"/categories/{category_id}",token)
        except MercadoLivreAPIError as e:last=e
    raise last

def category_attributes(access_token,category_id):
    try:data=_get(f"/categories/{category_id}/attributes",access_token)
    except MercadoLivreAPIError:data=_get(f"/categories/{category_id}/attributes",None)
    result=[]
    for a in data or []:
        tags=a.get('tags') or {}
        if tags.get('required') or tags.get('conditional_required'):
            result.append({'id':a.get('id'),'name':a.get('name'),'value_type':a.get('value_type'),'values':a.get('values') or [],'required':bool(tags.get('required')),'conditional_required':bool(tags.get('conditional_required'))})
    return result

# Compatibilidade com a interface V0.7/V0.8.
def required_attributes(access_token,category_id):
    return category_attributes(access_token,category_id)

def create_item(access_token,payload):
    return _request(f"{API_BASE}/items",method="POST",access_token=access_token,json_data=payload)

def listing_price(access_token,price,category_id,listing_type_id,logistic_type="not_specified",shipping_mode="not_specified"):
    params={"price":f"{float(price):.2f}","currency_id":CURRENCY_ID,"category_id":category_id.strip(),"listing_type_id":listing_type_id,"logistic_type":logistic_type,"shipping_mode":shipping_mode}
    data=_get(f"/sites/{SITE_ID}/listing_prices",access_token,params)
    match=next((x for x in data if x.get("listing_type_id")==listing_type_id),data[0] if data else None) if isinstance(data,list) else data
    if not match:raise MercadoLivreAPIError("A API não retornou tarifa para os parâmetros informados.")
    details=match.get("sale_fee_details") or {}
    return {"listing_type_id":match.get("listing_type_id"),"listing_type_name":match.get("listing_type_name"),"sale_fee_amount":float(match.get("sale_fee_amount") or 0),"percentage_fee":float(details.get("percentage_fee") or 0),"fixed_fee":float(details.get("fixed_fee") or 0),"financing_add_on_fee":float(details.get("financing_add_on_fee") or 0),"gross_amount":float(details.get("gross_amount") or 0),"raw":match}
