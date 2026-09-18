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
    headers={"Accept":"application/json","User-Agent":"PrecificaEcom/0.10"}
    if access_token: headers["Authorization"]=f"Bearer {access_token}"
    body=None
    if json_data is not None:
        body=json.dumps(json_data).encode("utf-8"); headers["Content-Type"]="application/json"
    elif data is not None:
        body=urllib.parse.urlencode(data).encode("utf-8"); headers["Content-Type"]="application/x-www-form-urlencoded"
    req=urllib.request.Request(url,data=body,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=20) as resp:
            raw=resp.read().decode("utf-8"); return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        response=exc.read().decode("utf-8",errors="replace")
        if exc.code==403 and ("PolicyAgent" in response or "PA_UNAUTHORIZED" in response): raise MercadoLivreAPIError("A API do Mercado Livre bloqueou a leitura direta deste recurso por política de acesso.") from exc
        raise MercadoLivreAPIError(f"Mercado Livre HTTP {exc.code}: {response[:700]}") from exc
    except Exception as exc:
        if isinstance(exc,MercadoLivreAPIError): raise
        raise MercadoLivreAPIError(f"Falha ao comunicar com Mercado Livre: {exc}") from exc

def _get(path, access_token=None, params=None):
    query=urllib.parse.urlencode(params or {}); return _request(f"{API_BASE}{path}"+(f"?{query}" if query else ""),access_token=access_token)

def generate_pkce():
    verifier=secrets.token_urlsafe(64); digest=hashlib.sha256(verifier.encode("ascii")).digest(); return verifier,base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

def authorization_url(client_id,redirect_uri,state,code_challenge): return AUTH_BASE+"?"+urllib.parse.urlencode({"response_type":"code","client_id":client_id,"redirect_uri":redirect_uri,"state":state,"code_challenge":code_challenge,"code_challenge_method":"S256"})
def exchange_code(client_id,client_secret,redirect_uri,code,code_verifier): return _request(f"{API_BASE}/oauth/token",method="POST",data={"grant_type":"authorization_code","client_id":client_id,"client_secret":client_secret,"code":code,"redirect_uri":redirect_uri,"code_verifier":code_verifier})
def refresh_access_token(client_id,client_secret,refresh_token): return _request(f"{API_BASE}/oauth/token",method="POST",data={"grant_type":"refresh_token","client_id":client_id,"client_secret":client_secret,"refresh_token":refresh_token})
def me(access_token): return _get("/users/me",access_token)

def predict_categories(access_token,title,limit=3):
    title=(title or '').strip()
    if not title: raise MercadoLivreAPIError("Informe a descrição do produto para localizar a categoria.")
    params={"q":title,"limit":max(1,min(int(limit),8))}
    try:data=_get(f"/sites/{SITE_ID}/domain_discovery/search",access_token,params)
    except MercadoLivreAPIError:data=_get(f"/sites/{SITE_ID}/domain_discovery/search",None,params)
    return [{"category_id":x.get("category_id",""),"category_name":x.get("category_name",""),"domain_id":x.get("domain_id",""),"domain_name":x.get("domain_name","")} for x in (data or [])]

def extract_item_id(text):
    raw=urllib.parse.unquote(text or ''); upper=raw.upper().replace('-','')
    wid=re.search(r'[?&#]WID=(MLB\d{6,})',upper)
    if wid:return wid.group(1)
    ids=re.findall(r'\bMLB\d{6,}\b',upper)
    if ids:return ids[-1]
    nums=re.findall(r'(?:WID|ITEM[_ ]?ID)[^0-9]*(\d{6,})',upper)
    return f"MLB{nums[-1]}" if nums else None

def extract_user_product_id(text):
    m=re.search(r'\bMLBU\d{4,}\b',urllib.parse.unquote(text or '').upper()); return m.group(0) if m else None

def title_from_product_url(text):
    try:
        path=urllib.parse.urlparse(text or '').path.strip('/'); parts=[p for p in path.split('/') if p and not re.fullmatch(r'MLBU?\d+',p,re.I)]
        if not parts:return ''
        title=urllib.parse.unquote(max(parts,key=len)).replace('-',' '); return re.sub(r'\s+',' ',title).strip()[:180]
    except Exception:return ''

def _normalize_item(data,item_id):
    return {"id":data.get("id") or item_id,"title":data.get("title"),"category_id":data.get("category_id"),"price":data.get("price"),"permalink":data.get("permalink"),"listing_type_id":data.get("listing_type_id"),"shipping":data.get("shipping") or {},"seller_id":data.get("seller_id"),"attributes":data.get("attributes") or [],"pictures":data.get("pictures") or [],"raw":data,"inferred":False}

def item_details(access_token,item_or_url):
    item_id=extract_item_id(item_or_url)
    errors=[]
    if item_id:
        attempts=[(f"/items/{item_id}",{"include_attributes":"all"},None),("/items/bulk",{"ids":item_id,"attributes":"body.id,body.title,body.category_id,body.price,body.permalink,body.listing_type_id,body.shipping,body.seller_id,body.attributes,body.pictures"},access_token)]
        for path,params,token in attempts:
            try:
                data=_get(path,token,params)
                if path=="/items/bulk":
                    row=(data or [{}])[0]; status=row.get('status_code',row.get('code'))
                    if status!=200:raise MercadoLivreAPIError(f"Consulta bulk recusada (HTTP {status}).")
                    data=row.get('body') or {}
                return _normalize_item(data,item_id)
            except MercadoLivreAPIError as e:errors.append(str(e))
    # Links de UPP/concorrentes podem ser protegidos. Usa o título visível no próprio URL
    # apenas para executar o preditor oficial de categorias, sem afirmar que leu o anúncio.
    title=title_from_product_url(item_or_url)
    if title:
        cats=predict_categories(access_token,title,3)
        if cats:
            best=cats[0]
            return {"id":item_id or extract_user_product_id(item_or_url) or "referencia-url","title":title,"category_id":best.get("category_id"),"price":None,"permalink":item_or_url,"listing_type_id":None,"shipping":{},"seller_id":None,"attributes":[],"pictures":[],"raw":{"category_candidates":cats,"direct_read_errors":errors},"inferred":True}
    if not item_id:raise MercadoLivreAPIError("Não encontrei um código MLB nem um título utilizável no link informado.")
    raise MercadoLivreAPIError("Leitura direta do anúncio indisponível e não foi possível inferir a categoria pelo título do link. "+" | ".join(errors))

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
        if tags.get('required') or tags.get('conditional_required'): result.append({'id':a.get('id'),'name':a.get('name'),'value_type':a.get('value_type'),'values':a.get('values') or [],'required':bool(tags.get('required')),'conditional_required':bool(tags.get('conditional_required'))})
    return result

def required_attributes(access_token,category_id):return category_attributes(access_token,category_id)
def create_item(access_token,payload):return _request(f"{API_BASE}/items",method="POST",access_token=access_token,json_data=payload)

def listing_price(access_token,price,category_id,listing_type_id,logistic_type="not_specified",shipping_mode="not_specified"):
    params={"price":f"{float(price):.2f}","currency_id":CURRENCY_ID,"category_id":category_id.strip(),"listing_type_id":listing_type_id,"logistic_type":logistic_type,"shipping_mode":shipping_mode}
    data=_get(f"/sites/{SITE_ID}/listing_prices",access_token,params); match=next((x for x in data if x.get("listing_type_id")==listing_type_id),data[0] if data else None) if isinstance(data,list) else data
    if not match:raise MercadoLivreAPIError("A API não retornou tarifa para os parâmetros informados.")
    details=match.get("sale_fee_details") or {}
    return {"listing_type_id":match.get("listing_type_id"),"listing_type_name":match.get("listing_type_name"),"sale_fee_amount":float(match.get("sale_fee_amount") or 0),"percentage_fee":float(details.get("percentage_fee") or 0),"fixed_fee":float(details.get("fixed_fee") or 0),"financing_add_on_fee":float(details.get("financing_add_on_fee") or 0),"gross_amount":float(details.get("gross_amount") or 0),"raw":match}


def shipping_quote(access_token,user_id,item_id=None,item_price=0,listing_type_id='gold_special',logistic_type='not_specified',shipping_mode='me2',free_shipping=True):
    """Cota o custo de frete atribuído ao vendedor usando o contexto do anúncio."""
    if not user_id: raise MercadoLivreAPIError("Conta Mercado Livre sem user_id para cotação de frete.")
    params={"item_price":f"{float(item_price):.2f}","listing_type_id":listing_type_id,"mode":shipping_mode,"logistic_type":logistic_type,"free_shipping":"true" if free_shipping else "false"}
    if item_id: params["item_id"]=item_id
    data=_get(f"/users/{user_id}/shipping_options/free",access_token,params)
    options=data if isinstance(data,list) else (data.get("options") or data.get("coverage",{}).get("all_country",{}).get("list") or [])
    if isinstance(options,dict): options=[options]
    vals=[]
    for o in options or []:
        for k in ("cost","list_cost"):
            try:
                v=float(o.get(k))
                if v>=0: vals.append(v); break
            except (TypeError,ValueError): pass
    if not vals:
        # Algumas respostas trazem o custo diretamente no objeto raiz.
        for k in ("cost","list_cost"):
            try:return float(data.get(k) or 0),data
            except (AttributeError,TypeError,ValueError): pass
        raise MercadoLivreAPIError("A API não retornou um custo de frete utilizável para este anúncio.")
    return min(vals),data
