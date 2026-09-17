import html, secrets, time
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from .database import init_db, connect
from .pricing import PricingInput, calcular_preco
from .fiscal import contexto_fiscal, aliquota_efetiva_cadastrada
from .marketplaces.mercadolivre import listing_price, me, MercadoLivreAPIError, generate_pkce, authorization_url, exchange_code, refresh_access_token, predict_categories, item_details, category_details

app=FastAPI(title='PrecificaEcom'); init_db()
CSS='''body{font-family:Segoe UI,Arial;background:#f4f6f8;margin:0;color:#1f2937}.wrap{max-width:1050px;margin:28px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 12px #0001;margin-bottom:18px}h1{margin:0 0 8px}.muted{color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;font-weight:600;margin-bottom:5px}input,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px}button,.btn{display:inline-block;padding:12px 18px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700;cursor:pointer;text-decoration:none}.btn2{background:#475569}.result{font-size:34px;font-weight:800}.warn,.info,.ok{padding:12px;border-radius:8px;margin:10px 0}.warn{background:#fff7ed;color:#9a3412}.info{background:#eff6ff;color:#1e40af}.ok{background:#ecfdf5;color:#166534}.nav{display:flex;gap:14px;margin-bottom:15px;flex-wrap:wrap}.nav a{color:#334155;text-decoration:none;font-weight:600}.cat{padding:12px;border:1px solid #cbd5e1;border-radius:9px;margin:8px 0}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
def page(body,script=''): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>PrecificaEcom</title><style>{CSS}</style></head><body><div class='wrap'><div class='nav'><a href='/precificar'>Precificar</a><a href='/anuncio-similar'>Anúncio similar</a><a href='/'>Empresa</a><a href='/mercadolivre'>Mercado Livre</a><a href='/tarifas'>Tarifas</a></div>{body}</div><script>{script}</script></body></html>")
def ml_cfg():
 con=connect(); r=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close(); return r
def ensure_ml_token():
 cfg=ml_cfg()
 if not cfg or not cfg['access_token']: return cfg
 try: expires=float(cfg['token_expires_at'] or 0)
 except: expires=0
 if expires and time.time()>=expires-120 and cfg['refresh_token'] and cfg['client_secret']:
  tok=refresh_access_token(cfg['client_id'],cfg['client_secret'],cfg['refresh_token']); con=connect(); con.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,token_expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE marketplace='ML'",(tok.get('access_token',''),tok.get('refresh_token',cfg['refresh_token']),str(time.time()+int(tok.get('expires_in',21600))))); con.commit(); con.close(); cfg=ml_cfg()
 return cfg

def pricing_form(category_id='',product_name='',ncm='',source=''):
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); estados=con.execute('SELECT * FROM estados').fetchall(); con.close(); destinos=''.join(f"<option value='{e['uf']}'>{e['uf']} - {e['nome']}</option>" for e in estados); src=f"<div class='ok'>{html.escape(source)}</div>" if source else ''
 return f'''<div class='card'><h1>Nova precificação</h1>{src}<form method='post' action='/calcular-ml'><div class='grid'><div><label>NCM</label><input name='ncm' maxlength='8' value='{html.escape(ncm)}' required></div><div><label>Descrição / nome do produto</label><input name='product_name' value='{html.escape(product_name)}' placeholder='Ex.: Base válvula Hydra Max 2550' required></div><div><label>UF destino</label><select name='uf_destino'>{destinos}</select></div><div><label>Custo produto (R$)</label><input type='number' step='.01' min='0' name='custo' required></div><div><label>Embalagem (R$)</label><input type='number' step='.01' min='0' name='embalagem' value='0'></div><div><label>Categoria Mercado Livre</label><input name='category_id' value='{html.escape(category_id)}' placeholder='Será sugerida automaticamente' required></div><div><label>Tipo de anúncio</label><select name='listing_type_id'><option value='gold_special'>Clássico</option><option value='gold_pro'>Premium</option></select></div><div><label>Logística</label><select name='logistic_type'><option value='drop_off'>Drop Off</option><option value='cross_docking'>Coleta</option><option value='self_service'>Flex</option><option value='fulfillment'>Full</option><option value='not_specified'>Não especificado</option></select></div><div><label>Modo envio</label><select name='shipping_mode'><option value='me2'>Mercado Envios 2</option><option value='not_specified'>Não especificado</option></select></div><div><label>Frete vendedor</label><input type='number' step='.01' min='0' name='frete' value='0'></div><div><label>Outros custos</label><input type='number' step='.01' min='0' name='outros' value='0'></div><div><label>Ads (%)</label><input type='number' step='.01' min='0' name='ads' value='0'></div><div><label>Margem líquida (%)</label><input type='number' step='.01' min='0' name='margem' value='15'></div></div><br><button>Calcular com API Mercado Livre</button></form></div>'''

@app.get('/',response_class=HTMLResponse)
def home():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); regimes=con.execute('SELECT * FROM regimes_tributarios').fetchall(); estados=con.execute('SELECT * FROM estados').fetchall(); con.close(); ro=''.join(f"<option value='{r['codigo']}' {'selected' if r['codigo']==emp['regime'] else ''}>{r['nome']}</option>" for r in regimes); uo=''.join(f"<option value='{e['uf']}' {'selected' if e['uf']==emp['uf'] else ''}>{e['uf']} - {e['nome']}</option>" for e in estados)
 return page(f"<div class='card'><h1>Empresa</h1><form method='post' action='/configurar'><div class='grid'><div><label>Empresa</label><input name='nome' value='{html.escape(emp['nome'])}'></div><div><label>Regime</label><select name='regime'>{ro}</select></div><div><label>UF</label><select name='uf'>{uo}</select></div><div><label>RBT12 — somente Simples (R$)</label><input type='number' step='.01' name='receita_12m' value='{emp['receita_12m']}'></div></div><br><button>Salvar</button></form></div>")
@app.post('/configurar')
def configurar(nome:str=Form(''),regime:str=Form(...),uf:str=Form(...),receita_12m:float=Form(0)):
 con=connect(); con.execute('UPDATE empresa SET nome=?,regime=?,uf=?,receita_12m=? WHERE id=1',(nome,regime,uf,receita_12m)); con.commit(); con.close(); return RedirectResponse('/precificar',303)

@app.get('/mercadolivre',response_class=HTMLResponse)
def ml_config():
 cfg=ml_cfg(); connected=bool(cfg and cfg['access_token']); status=f"Conectado: {cfg['seller_nickname'] or cfg['user_id']}" if connected else 'Ainda não conectado'; btn="<a class='btn' href='/mercadolivre/conectar'>Conectar Mercado Livre</a>" if cfg and cfg['client_secret'] else ''
 return page(f"<div class='card'><h1>Mercado Livre</h1><div class='{'ok' if connected else 'info'}'>{status}</div><p class='muted'>Client ID: {cfg['client_id']}<br>Redirect URI: {cfg['redirect_uri']}</p><form method='post' action='/mercadolivre/credenciais'><label>Client Secret</label><input type='password' name='client_secret' required><br><br><button>Salvar Secret localmente</button></form><br>{btn}</div>")
@app.post('/mercadolivre/credenciais')
def ml_creds(client_secret:str=Form(...)):
 con=connect(); con.execute("UPDATE marketplace_config SET client_secret=? WHERE marketplace='ML'",(client_secret.strip(),)); con.commit(); con.close(); return RedirectResponse('/mercadolivre',303)
@app.get('/mercadolivre/conectar')
def ml_connect():
 cfg=ml_cfg(); verifier,challenge=generate_pkce(); state=secrets.token_urlsafe(32); con=connect(); con.execute("DELETE FROM oauth_sessions WHERE marketplace='ML'"); con.execute("INSERT INTO oauth_sessions(state,marketplace,code_verifier) VALUES(?,?,?)",(state,'ML',verifier)); con.commit(); con.close(); return RedirectResponse(authorization_url(cfg['client_id'],cfg['redirect_uri'],state,challenge),302)
@app.get('/mercadolivre/oauth/callback',response_class=HTMLResponse)
def ml_callback(code:str='',state:str='',error:str=''):
 if error:return page(f"<div class='warn'>Autorização não concluída: {html.escape(error)}</div>")
 con=connect(); s=con.execute("SELECT * FROM oauth_sessions WHERE state=?",(state,)).fetchone(); cfg=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close()
 if not s:return page("<div class='warn'>Sessão OAuth inválida.</div>")
 try: tok=exchange_code(cfg['client_id'],cfg['client_secret'],cfg['redirect_uri'],code,s['code_verifier']); user=me(tok['access_token'])
 except MercadoLivreAPIError as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 con=connect(); con.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,user_id=?,seller_nickname=?,token_expires_at=? WHERE marketplace='ML'",(tok.get('access_token',''),tok.get('refresh_token',''),str(user.get('id','')),user.get('nickname',''),str(time.time()+int(tok.get('expires_in',21600))))); con.execute("DELETE FROM oauth_sessions WHERE state=?",(state,)); con.commit(); con.close(); return page(f"<div class='ok'>Mercado Livre conectado: {html.escape(user.get('nickname',''))}</div><a class='btn' href='/precificar'>Continuar</a>")

@app.get('/precificar',response_class=HTMLResponse)
def precificar():
 cfg=ml_cfg(); msg="<div class='ok'>API Mercado Livre conectada.</div>" if cfg and cfg['access_token'] else "<div class='warn'><a href='/mercadolivre'>Conecte o Mercado Livre</a>.</div>"
 return page(msg+"<div class='card'><h1>Localizar categoria automaticamente</h1><p class='muted'>O NCM ajuda na identificação fiscal; a API do Mercado Livre prevê a categoria a partir do nome/título do produto.</p><form method='post' action='/categoria-sugerir'><div class='grid'><div><label>NCM</label><input name='ncm' maxlength='8' required></div><div><label>Descrição / nome do produto</label><input name='product_name' placeholder='Marca, modelo e tipo do produto' required></div></div><br><button>Buscar categoria</button></form></div>"+pricing_form())

@app.post('/categoria-sugerir',response_class=HTMLResponse)
def categoria_sugerir(ncm:str=Form(...),product_name:str=Form(...)):
 try: cfg=ensure_ml_token(); cats=predict_categories(cfg['access_token'],product_name,3)
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 cards=''.join(f"<div class='cat'><b>{html.escape(c['category_name'])}</b> — {c['category_id']}<br><span class='muted'>{html.escape(c['domain_name'])}</span><form method='post' action='/categoria-usar'><input type='hidden' name='category_id' value='{c['category_id']}'><input type='hidden' name='ncm' value='{html.escape(ncm)}'><input type='hidden' name='product_name' value='{html.escape(product_name)}'><button>Usar esta categoria</button></form></div>" for c in cats)
 return page(f"<div class='card'><h1>Categorias sugeridas</h1><p>A primeira é a de maior probabilidade segundo o preditor oficial.</p>{cards}</div>")
@app.post('/categoria-usar',response_class=HTMLResponse)
def categoria_usar(category_id:str=Form(...),ncm:str=Form(...),product_name:str=Form(...)): return page(pricing_form(category_id,product_name,ncm,'Categoria selecionada pela API do Mercado Livre.'))

@app.get('/anuncio-similar',response_class=HTMLResponse)
def anuncio_similar():
 return page("<div class='card'><h1>Anunciar igual / produto similar</h1><p class='muted'>Cole o link de um anúncio do Mercado Livre. O PrecificaEcom lê o anúncio e aproveita categoria, título e tipo de anúncio como referência. Nenhum conteúdo protegido do vendedor é copiado.</p><form method='post' action='/anuncio-similar'><label>Link ou código MLB do anúncio</label><input name='url' placeholder='https://www.mercadolivre.com.br/... ou MLB123456789' required><br><br><label>Seu NCM</label><input name='ncm' maxlength='8' required><br><br><button>Pesquisar produto</button></form></div>")
@app.post('/anuncio-similar',response_class=HTMLResponse)
def anuncio_similar_buscar(url:str=Form(...),ncm:str=Form(...)):
 try:
  cfg=ensure_ml_token(); item=item_details(cfg['access_token'],url); cat=category_details(cfg['access_token'],item['category_id']); path=' → '.join(x.get('name','') for x in cat.get('path_from_root',[]))
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 source=f"Referência: {item['title']} | anúncio {item['id']} | categoria {item['category_id']}"
 return page(f"<div class='card'><h1>Produto encontrado</h1><p><b>{html.escape(item['title'] or '')}</b></p><p>Preço do anúncio: R$ {float(item['price'] or 0):.2f}</p><p>Categoria: <b>{item['category_id']}</b><br>{html.escape(path)}</p><div class='info'>Usaremos o anúncio apenas como referência de classificação. Seu preço será calculado com seus próprios custos, impostos, frete e margem.</div></div>"+pricing_form(item['category_id'],item['title'] or '',ncm,source))

@app.get('/tarifas',response_class=HTMLResponse)
def tarifas(): return page("<div class='card'><h1>Tarifas</h1><p>As tarifas do Mercado Livre são consultadas diretamente pela API durante a precificação.</p></div>")

@app.post('/calcular-ml',response_class=HTMLResponse)
def calcular_ml(ncm:str=Form(...),product_name:str=Form(''),uf_destino:str=Form(...),custo:float=Form(...),embalagem:float=Form(0),category_id:str=Form(...),listing_type_id:str=Form(...),logistic_type:str=Form('not_specified'),shipping_mode:str=Form('not_specified'),frete:float=Form(0),outros:float=Form(0),ads:float=Form(0),margem:float=Form(15)):
 try: cfg=ensure_ml_token()
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); con.close(); regras=contexto_fiscal(emp['regime'],emp['uf'],uf_destino,ncm,emp['receita_12m']); imposto=aliquota_efetiva_cadastrada(regras); preco=max(custo+embalagem+frete+outros,1)*1.5; r=fee=None
 try:
  for _ in range(8):
   fee=listing_price(cfg['access_token'],preco,category_id,listing_type_id,logistic_type,shipping_mode); novo=calcular_preco(PricingInput(custo,embalagem,outros,frete,fee['fixed_fee'],imposto,fee['percentage_fee'],ads,margem)); r=novo
   if abs(novo['preco']-preco)<.02:break
   preco=novo['preco']
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 pend='' if regras else "<div class='warn'>Base fiscal ainda incompleta: imposto considerado 0% para este caso.</div>"
 return page(f"<div class='card'><h1>Preço recomendado</h1><p>{html.escape(product_name)}</p><div class='result'>R$ {r['preco']:.2f}</div><p>Categoria: <b>{category_id}</b></p><p>Comissão API: <b>{fee['percentage_fee']:.2f}%</b> | Tarifa fixa: <b>R$ {fee['fixed_fee']:.2f}</b></p><p>Lucro: <b>R$ {r['lucro']:.2f}</b> | Margem: <b>{r['margem_real']:.2f}%</b></p></div>{pend}")
