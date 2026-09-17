import html, secrets, time
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .database import init_db, connect
from .pricing import PricingInput, calcular_preco
from .fiscal import contexto_fiscal, aliquota_efetiva_cadastrada
from .marketplaces.mercadolivre import *
app=FastAPI(title='PrecificaEcom'); init_db()
CSS='''body{font-family:Segoe UI,Arial;background:#f4f6f8;margin:0;color:#1f2937}.wrap{max-width:1050px;margin:28px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 12px #0001;margin-bottom:18px}h1{margin:0 0 8px}.muted{color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;font-weight:600;margin-bottom:5px}input,select,textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px}button,.btn{display:inline-block;padding:12px 18px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700;cursor:pointer;text-decoration:none}.result{font-size:34px;font-weight:800}.warn,.info,.ok{padding:12px;border-radius:8px;margin:10px 0}.warn{background:#fff7ed;color:#9a3412}.info{background:#eff6ff;color:#1e40af}.ok{background:#ecfdf5;color:#166534}.nav{display:flex;gap:14px;margin-bottom:15px;flex-wrap:wrap}.nav a{color:#334155;text-decoration:none;font-weight:600}.cat{padding:12px;border:1px solid #cbd5e1;border-radius:9px;margin:8px 0}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
def page(b): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>PrecificaEcom</title><style>{CSS}</style></head><body><div class='wrap'><div class='nav'><a href='/precificar'>Precificar</a><a href='/anuncio-similar'>Anúncio similar</a><a href='/'>Empresa</a><a href='/mercadolivre'>Mercado Livre</a></div>{b}</div></body></html>")
def ml_cfg():
 c=connect();r=c.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone();c.close();return r
def ensure_ml_token():
 cfg=ml_cfg()
 if not cfg or not cfg['access_token']: return cfg
 try:e=float(cfg['token_expires_at'] or 0)
 except:e=0
 if e and time.time()>=e-120 and cfg['refresh_token'] and cfg['client_secret']:
  t=refresh_access_token(cfg['client_id'],cfg['client_secret'],cfg['refresh_token']);c=connect();c.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,token_expires_at=? WHERE marketplace='ML'",(t.get('access_token',''),t.get('refresh_token',cfg['refresh_token']),str(time.time()+int(t.get('expires_in',21600)))));c.commit();c.close();cfg=ml_cfg()
 return cfg
@app.get('/')
def home(): return RedirectResponse('/precificar')
@app.get('/mercadolivre')
def ml_config():
 cfg=ml_cfg();st=f"Conectado: {cfg['seller_nickname'] or cfg['user_id']}" if cfg and cfg['access_token'] else 'Ainda não conectado';btn="<a class='btn' href='/mercadolivre/conectar'>Conectar Mercado Livre</a>" if cfg and cfg['client_secret'] else ''
 return page(f"<div class='card'><h1>Mercado Livre</h1><div class='info'>{html.escape(st)}</div><form method='post' action='/mercadolivre/credenciais'><label>Client Secret</label><input type='password' name='client_secret' required><br><br><button>Salvar Secret localmente</button></form><br>{btn}</div>")
@app.post('/mercadolivre/credenciais')
def creds(client_secret:str=Form(...)):
 c=connect();c.execute("UPDATE marketplace_config SET client_secret=? WHERE marketplace='ML'",(client_secret.strip(),));c.commit();c.close();return RedirectResponse('/mercadolivre',303)
@app.get('/mercadolivre/conectar')
def connect_ml():
 cfg=ml_cfg();v,ch=generate_pkce();s=secrets.token_urlsafe(32);c=connect();c.execute("DELETE FROM oauth_sessions WHERE marketplace='ML'");c.execute("INSERT INTO oauth_sessions(state,marketplace,code_verifier) VALUES(?,?,?)",(s,'ML',v));c.commit();c.close();return RedirectResponse(authorization_url(cfg['client_id'],cfg['redirect_uri'],s,ch),302)
@app.get('/mercadolivre/oauth/callback')
def callback(code:str='',state:str='',error:str=''):
 if error:return page(f"<div class='warn'>{html.escape(error)}</div>")
 c=connect();sess=c.execute("SELECT * FROM oauth_sessions WHERE state=?",(state,)).fetchone();cfg=c.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone();c.close()
 if not sess:return page("<div class='warn'>Sessão OAuth inválida.</div>")
 try:t=exchange_code(cfg['client_id'],cfg['client_secret'],cfg['redirect_uri'],code,sess['code_verifier']);u=me(t['access_token'])
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 c=connect();c.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,user_id=?,seller_nickname=?,token_expires_at=? WHERE marketplace='ML'",(t.get('access_token',''),t.get('refresh_token',''),str(u.get('id','')),u.get('nickname',''),str(time.time()+int(t.get('expires_in',21600)))));c.execute("DELETE FROM oauth_sessions WHERE state=?",(state,));c.commit();c.close();return page("<div class='ok'>Mercado Livre conectado.</div><a class='btn' href='/precificar'>Continuar</a>")
@app.get('/precificar')
def precificar():
 return page("<div class='card'><h1>Precificar</h1><p>Localize a categoria usando NCM + nome do produto.</p><form method='post' action='/categoria-sugerir'><div class='grid'><div><label>NCM</label><input name='ncm' required maxlength='8'></div><div><label>Produto</label><input name='product_name' required></div></div><br><button>Buscar categoria</button></form></div><div class='card'><h2>Ou use um anúncio similar</h2><a class='btn' href='/anuncio-similar'>Pesquisar pelo link</a></div>")
@app.post('/categoria-sugerir')
def suggest(ncm:str=Form(...),product_name:str=Form(...)):
 try:cfg=ensure_ml_token();cats=predict_categories(cfg['access_token'],product_name,3)
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 cards=''.join(f"<div class='cat'><b>{html.escape(x['category_name'])}</b> — {x['category_id']}<form method='get' action='/criar-anuncio'><input type='hidden' name='category_id' value='{x['category_id']}'><input type='hidden' name='title' value='{html.escape(product_name)}'><button>Usar e criar anúncio</button></form></div>" for x in cats);return page(f"<div class='card'><h1>Categorias sugeridas</h1>{cards}</div>")
@app.get('/anuncio-similar')
def similar():return page("<div class='card'><h1>Anúncio similar</h1><form method='post'><label>Link ou MLB</label><input name='url' required><br><br><button>Pesquisar</button></form></div>")
@app.post('/anuncio-similar')
def similar_post(url:str=Form(...)):
 try:cfg=ensure_ml_token();i=item_details(cfg['access_token'],url);cat=category_details(cfg['access_token'],i['category_id']);path=' → '.join(x.get('name','') for x in cat.get('path_from_root',[]))
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 return page(f"<div class='card'><h1>Referência encontrada</h1><p><b>{html.escape(i['title'] or '')}</b></p><p>{html.escape(path)}</p><p>Categoria: {i['category_id']}</p><div class='info'>A referência serve para categoria e estrutura. Fotos e textos do outro vendedor não serão copiados.</div><form method='get' action='/criar-anuncio'><input type='hidden' name='category_id' value='{i['category_id']}'><input type='hidden' name='title' value='{html.escape(i['title'] or '')}'><button>Criar meu anúncio nesta categoria</button></form></div>")
@app.get('/criar-anuncio')
def create_form(category_id:str,title:str=''):
 try:cfg=ensure_ml_token();attrs=required_attributes(cfg['access_token'],category_id)
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 fields=''
 for a in attrs:
  aid=html.escape(a.get('id',''));name=html.escape(a.get('name',aid));vals=a.get('values') or []
  if vals and len(vals)<=80:
   opts="<option value=''>Selecione</option>"+''.join(f"<option value='{html.escape(str(v.get('id','')))}'>{html.escape(str(v.get('name','')))}</option>" for v in vals);fields+=f"<div><label>{name}</label><select name='attr_{aid}'>{opts}</select></div>"
  else:fields+=f"<div><label>{name}</label><input name='attr_{aid}'></div>"
 return page(f'''<div class='card'><h1>Criar anúncio</h1><div class='info'>Categoria {html.escape(category_id)}. Preencha os dados do seu próprio produto. A publicação só ocorrerá após clicar no botão final.</div><form method='post' action='/publicar-anuncio'><input type='hidden' name='category_id' value='{html.escape(category_id)}'><div class='grid'><div><label>Título</label><input name='title' value='{html.escape(title)}' required></div><div><label>Preço (R$)</label><input type='number' step='.01' min='.01' name='price' required></div><div><label>Estoque</label><input type='number' min='1' name='quantity' value='1' required></div><div><label>Tipo de anúncio</label><select name='listing_type_id'><option value='gold_special'>Clássico</option><option value='gold_pro'>Premium</option></select></div><div><label>Condição</label><select name='condition'><option value='new'>Novo</option><option value='used'>Usado</option></select></div><div><label>URL da sua imagem principal</label><input name='picture_url' placeholder='https://...' required></div>{fields}</div><br><label>Descrição do seu produto</label><textarea name='description' rows='6'></textarea><br><br><div class='warn'><b>Atenção:</b> o botão abaixo cria um anúncio real na conta Mercado Livre conectada.</div><button>PUBLICAR ANÚNCIO NO MERCADO LIVRE</button></form></div>''')
@app.post('/publicar-anuncio')
async def publish(request:Request):
 form=await request.form();cfg=ensure_ml_token();cid=str(form.get('category_id',''));attrs_meta=required_attributes(cfg['access_token'],cid);attrs=[]
 for a in attrs_meta:
  val=str(form.get('attr_'+a.get('id',''),'')).strip()
  if val:
   values=a.get('values') or [];match=next((v for v in values if str(v.get('id'))==val),None);attrs.append({"id":a['id'],"value_id":val} if match else {"id":a['id'],"value_name":val})
 payload={"site_id":"MLB","title":str(form.get('title','')).strip(),"category_id":cid,"price":float(form.get('price')),"currency_id":"BRL","available_quantity":int(form.get('quantity')),"buying_mode":"buy_it_now","listing_type_id":str(form.get('listing_type_id')),"condition":str(form.get('condition')),"pictures":[{"source":str(form.get('picture_url')).strip()}],"attributes":attrs}
 try:item=create_item(cfg['access_token'],payload)
 except Exception as e:return page(f"<div class='warn'><h2>Publicação não realizada</h2><pre style='white-space:pre-wrap'>{html.escape(str(e))}</pre><p>Revise os campos/atributos exigidos pela categoria e tente novamente.</p></div>")
 return page(f"<div class='ok'><h1>Anúncio publicado</h1><p>ID: <b>{html.escape(str(item.get('id','')))}</b></p><p>{html.escape(str(item.get('permalink','')))}</p></div>")
