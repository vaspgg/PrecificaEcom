import base64, hashlib, json, re, secrets, urllib.parse, urllib.request, urllib.error
API_BASE="https://api.mercadolibre.com"; AUTH_BASE="https://auth.mercadolivre.com.br/authorization"; SITE_ID="MLB"; CURRENCY_ID="BRL"
class MercadoLivreAPIError(RuntimeError): pass

def _request(url,method="GET",access_token=None,data=None,json_data=None):
 headers={"Accept":"application/json","User-Agent":"PrecificaEcom/0.7"}; body=None
 if access_token: headers["Authorization"]=f"Bearer {access_token}"
 if json_data is not None: body=json.dumps(json_data).encode(); headers["Content-Type"]="application/json"
 elif data is not None: body=urllib.parse.urlencode(data).encode(); headers["Content-Type"]="application/x-www-form-urlencoded"
 try:
  with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=headers,method=method),timeout=25) as r: return json.loads(r.read().decode())
 except urllib.error.HTTPError as e:
  msg=e.read().decode(errors="replace"); raise MercadoLivreAPIError(f"Mercado Livre HTTP {e.code}: {msg[:1200]}") from e
 except Exception as e: raise MercadoLivreAPIError(f"Falha ao comunicar com Mercado Livre: {e}") from e

def _get(path,access_token=None,params=None):
 q=urllib.parse.urlencode(params or {}); return _request(f"{API_BASE}{path}"+(f"?{q}" if q else ""),access_token=access_token)
def generate_pkce():
 v=secrets.token_urlsafe(64); return v,base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
def authorization_url(client_id,redirect_uri,state,challenge): return AUTH_BASE+"?"+urllib.parse.urlencode({"response_type":"code","client_id":client_id,"redirect_uri":redirect_uri,"state":state,"code_challenge":challenge,"code_challenge_method":"S256"})
def exchange_code(client_id,client_secret,redirect_uri,code,verifier): return _request(f"{API_BASE}/oauth/token","POST",data={"grant_type":"authorization_code","client_id":client_id,"client_secret":client_secret,"code":code,"redirect_uri":redirect_uri,"code_verifier":verifier})
def refresh_access_token(client_id,client_secret,refresh_token): return _request(f"{API_BASE}/oauth/token","POST",data={"grant_type":"refresh_token","client_id":client_id,"client_secret":client_secret,"refresh_token":refresh_token})
def me(token): return _get("/users/me",token)
def predict_categories(token,title,limit=3):
 d=_get(f"/sites/{SITE_ID}/domain_discovery/search",token,{"q":title.strip(),"limit":max(1,min(int(limit),8))}); return [{"category_id":x.get("category_id",""),"category_name":x.get("category_name",""),"domain_name":x.get("domain_name","")} for x in d or []]
def extract_item_id(text):
 text=(text or '').upper().replace('-',''); ids=re.findall(r'\bMLB\d{6,}\b',text)
 if ids:return ids[-1]
 nums=re.findall(r'(?:WID|ITEM[_ ]?ID)[^0-9]*(\d{6,})',text); return f"MLB{nums[-1]}" if nums else None
def item_details(token,text):
 iid=extract_item_id(text)
 if not iid: raise MercadoLivreAPIError("Não encontrei código MLB no link.")
 d=_get(f"/items/{iid}",token,{"include_attributes":"all"}); return {"id":d.get("id"),"title":d.get("title"),"category_id":d.get("category_id"),"price":d.get("price"),"permalink":d.get("permalink"),"listing_type_id":d.get("listing_type_id"),"pictures":d.get("pictures") or [],"attributes":d.get("attributes") or [],"shipping":d.get("shipping") or {},"raw":d}
def category_details(token,cid): return _get(f"/categories/{cid}",token)
def category_attributes(token,cid): return _get(f"/categories/{cid}/attributes",token)
def required_attributes(token,cid):
 attrs=category_attributes(token,cid); return [a for a in attrs if (a.get("tags") or {}).get("required") or (a.get("tags") or {}).get("new_required")]
def create_item(token,payload): return _request(f"{API_BASE}/items","POST",access_token=token,json_data=payload)
def listing_price(token,price,cid,listing_type_id,logistic_type="not_specified",shipping_mode="not_specified"):
 p={"price":f"{float(price):.2f}","currency_id":CURRENCY_ID,"category_id":cid.strip(),"listing_type_id":listing_type_id,"logistic_type":logistic_type,"shipping_mode":shipping_mode}; d=_get(f"/sites/{SITE_ID}/listing_prices",token,p); m=next((x for x in d if x.get("listing_type_id")==listing_type_id),d[0] if d else None) if isinstance(d,list) else d
 if not m: raise MercadoLivreAPIError("A API não retornou tarifa.")
 x=m.get("sale_fee_details") or {}; return {"listing_type_id":m.get("listing_type_id"),"listing_type_name":m.get("listing_type_name"),"sale_fee_amount":float(m.get("sale_fee_amount") or 0),"percentage_fee":float(x.get("percentage_fee") or 0),"fixed_fee":float(x.get("fixed_fee") or 0),"raw":m}
