import secrets
import time
import webbrowser
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from .database import init_db, connect
from .pricing import PricingInput, calcular_preco
from .fiscal import contexto_fiscal, aliquota_efetiva_cadastrada
from .marketplaces.mercadolivre import listing_price, me, MercadoLivreAPIError, generate_pkce, authorization_url, exchange_code, refresh_access_token

app=FastAPI(title='PrecificaEcom'); init_db()
CSS='''body{font-family:Segoe UI,Arial;background:#f4f6f8;margin:0;color:#1f2937}.wrap{max-width:980px;margin:28px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 12px #0001;margin-bottom:18px}h1{margin:0 0 5px}.muted{color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;font-weight:600;margin-bottom:5px}input,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px}button,.btn{display:inline-block;padding:12px 18px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700;cursor:pointer;text-decoration:none}.result{font-size:34px;font-weight:800}.warn{padding:12px;background:#fff7ed;border-radius:8px;color:#9a3412;margin:10px 0}.info{padding:12px;background:#eff6ff;border-radius:8px;color:#1e40af;margin:10px 0}.ok{padding:12px;background:#ecfdf5;border-radius:8px;color:#166534;margin:10px 0}.hide{display:none}.nav{display:flex;gap:14px;margin-bottom:15px;flex-wrap:wrap}.nav a{color:#334155;text-decoration:none;font-weight:600}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
def page(body,script=''): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>PrecificaEcom</title><style>{CSS}</style></head><body><div class='wrap'><div class='nav'><a href='/precificar'>Precificar</a><a href='/'>Empresa</a><a href='/mercadolivre'>Mercado Livre</a><a href='/tarifas'>Tarifas</a></div>{body}</div><script>{script}</script></body></html>")

def ml_cfg():
 con=connect(); cfg=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close(); return cfg

def ensure_ml_token():
 cfg=ml_cfg()
 if not cfg or not cfg['access_token']: return cfg
 expires=float(cfg['token_expires_at'] or 0) if str(cfg['token_expires_at'] or '').replace('.','',1).isdigit() else 0
 if expires and time.time() >= expires-120 and cfg['refresh_token'] and cfg['client_secret']:
  tok=refresh_access_token(cfg['client_id'],cfg['client_secret'],cfg['refresh_token']); con=connect(); con.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,token_expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE marketplace='ML'",(tok.get('access_token',''),tok.get('refresh_token',cfg['refresh_token']),str(time.time()+int(tok.get('expires_in',21600))))); con.commit(); con.close(); cfg=ml_cfg()
 return cfg

@app.get('/',response_class=HTMLResponse)
def home():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); regimes=con.execute('SELECT * FROM regimes_tributarios').fetchall(); estados=con.execute('SELECT * FROM estados').fetchall(); con.close(); ro=''.join(f"<option value='{r['codigo']}' {'selected' if r['codigo']==emp['regime'] else ''}>{r['nome']}</option>" for r in regimes); uo=''.join(f"<option value='{e['uf']}' {'selected' if e['uf']==emp['uf'] else ''}>{e['uf']} - {e['nome']}</option>" for e in estados); show='' if emp['regime']=='SIMPLES' else 'hide'
 return page(f'''<div class='card'><h1>Configurações da empresa</h1><form method='post' action='/configurar'><div class='grid'><div><label>Empresa</label><input name='nome' value="{emp['nome']}"></div><div><label>Regime tributário</label><select id='regime' name='regime' onchange='regimeChanged()'>{ro}</select></div><div><label>UF da empresa</label><select name='uf'>{uo}</select></div><div id='rbt12' class='{show}'><label>Faturamento bruto dos últimos 12 meses — RBT12 (R$)</label><input type='number' step='.01' min='0' name='receita_12m' value="{emp['receita_12m']}"></div></div><br><button>Salvar configurações</button></form></div>''',"function regimeChanged(){document.getElementById('rbt12').classList.toggle('hide',document.getElementById('regime').value!=='SIMPLES');}")

@app.post('/configurar')
def configurar(nome:str=Form(''),regime:str=Form(...),uf:str=Form(...),receita_12m:float=Form(0)):
 con=connect(); con.execute('UPDATE empresa SET nome=?,regime=?,uf=?,receita_12m=? WHERE id=1',(nome,regime,uf,receita_12m)); con.commit(); con.close(); return RedirectResponse('/precificar',303)

@app.get('/mercadolivre',response_class=HTMLResponse)
def mercadolivre_config():
 cfg=ml_cfg(); connected=bool(cfg and cfg['access_token']); status=f"Conectado: {cfg['seller_nickname'] or cfg['user_id']}" if connected else "Ainda não conectado"
 secret_status="Client Secret configurado localmente." if cfg and cfg['client_secret'] else "Informe o novo Client Secret gerado no DevCenter. Ele ficará somente neste computador."
 return page(f'''<div class='card'><h1>Mercado Livre</h1><div class='{'ok' if connected else 'info'}'>{status}</div><p class='muted'>Client ID: {cfg['client_id']}<br>Redirect URI: {cfg['redirect_uri']}</p><form method='post' action='/mercadolivre/credenciais'><label>Client Secret</label><input type='password' name='client_secret' placeholder='Cole o novo Secret aqui' required><br><br><button>Salvar Secret localmente</button></form><p class='muted'>{secret_status}</p>{"<a class='btn' href='/mercadolivre/conectar'>Conectar Mercado Livre</a>" if cfg and cfg['client_secret'] else ''}</div>''')

@app.post('/mercadolivre/credenciais')
def ml_credenciais(client_secret:str=Form(...)):
 con=connect(); con.execute("UPDATE marketplace_config SET client_secret=?,updated_at=CURRENT_TIMESTAMP WHERE marketplace='ML'",(client_secret.strip(),)); con.commit(); con.close(); return RedirectResponse('/mercadolivre',303)

@app.get('/mercadolivre/conectar')
def ml_conectar():
 cfg=ml_cfg()
 if not cfg or not cfg['client_secret']: return RedirectResponse('/mercadolivre',303)
 verifier,challenge=generate_pkce(); state=secrets.token_urlsafe(32); con=connect(); con.execute("DELETE FROM oauth_sessions WHERE marketplace='ML'"); con.execute("INSERT INTO oauth_sessions(state,marketplace,code_verifier) VALUES(?,?,?)",(state,'ML',verifier)); con.commit(); con.close(); url=authorization_url(cfg['client_id'],cfg['redirect_uri'],state,challenge); return RedirectResponse(url,302)

@app.get('/mercadolivre/oauth/callback',response_class=HTMLResponse)
def ml_callback(code:str='',state:str='',error:str=''):
 if error: return page(f"<div class='warn'>Autorização não concluída: {error}</div>")
 con=connect(); session=con.execute("SELECT * FROM oauth_sessions WHERE state=? AND marketplace='ML'",(state,)).fetchone(); cfg=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close()
 if not session or not code: return page("<div class='warn'>Retorno OAuth inválido ou expirado. Inicie a conexão novamente.</div>")
 try:
  tok=exchange_code(cfg['client_id'],cfg['client_secret'],cfg['redirect_uri'],code,session['code_verifier']); user=me(tok['access_token'])
 except MercadoLivreAPIError as exc: return page(f"<div class='warn'><b>Falha ao concluir OAuth.</b><br>{exc}</div>")
 con=connect(); con.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,user_id=?,seller_nickname=?,token_expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE marketplace='ML'",(tok.get('access_token',''),tok.get('refresh_token',''),str(user.get('id','')),user.get('nickname',''),str(time.time()+int(tok.get('expires_in',21600))))); con.execute("DELETE FROM oauth_sessions WHERE state=?",(state,)); con.commit(); con.close(); return page(f"<div class='ok'><b>Mercado Livre conectado com sucesso.</b><br>Conta: {user.get('nickname','')} — ID {user.get('id','')}</div><a class='btn' href='/precificar'>Ir para precificação</a>")

@app.get('/tarifas',response_class=HTMLResponse)
def tarifas():
 con=connect(); rows=con.execute('SELECT t.*,m.nome marketplace_nome FROM tarifas_marketplace t JOIN marketplaces m ON m.codigo=t.marketplace WHERE t.ativo=1 ORDER BY t.marketplace,t.id').fetchall(); con.close(); trs=''
 for r in rows:
  taxa=f"{r['comissao_exata_pct']:.2f}%" if r['comissao_exata_pct'] is not None else (f"{r['comissao_min_pct']:.2f}% a {r['comissao_max_pct']:.2f}%" if r['comissao_min_pct'] is not None else 'Dinâmica'); trs+=f"<tr><td>{r['marketplace_nome']}</td><td>{r['nome']}</td><td>{taxa}</td><td>{r['observacao'] or ''}</td></tr>"
 return page(f"<div class='card'><h1>Tarifas</h1><table style='width:100%'><tr><th align='left'>Plataforma</th><th align='left'>Tipo</th><th align='left'>Comissão</th><th align='left'>Regra</th></tr>{trs}</table></div>")

@app.get('/precificar',response_class=HTMLResponse)
def precificador():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); estados=con.execute('SELECT * FROM estados').fetchall(); con.close(); cfg=ml_cfg(); destinos=''.join(f"<option value='{e['uf']}'>{e['uf']} - {e['nome']}</option>" for e in estados); mlmsg="<div class='ok'>Mercado Livre conectado: tarifas serão consultadas pela API.</div>" if cfg and cfg['access_token'] else "<div class='warn'><a href='/mercadolivre'>Conecte o Mercado Livre</a> antes de calcular.</div>"
 return page(f'''<div class='card'><h1>Nova precificação</h1>{mlmsg}<form method='post' action='/calcular-ml'><div class='grid'><div><label>NCM</label><input name='ncm' maxlength='8' required></div><div><label>UF destino</label><select name='uf_destino'>{destinos}</select></div><div><label>Custo produto (R$)</label><input type='number' step='.01' min='0' name='custo' required></div><div><label>Embalagem (R$)</label><input type='number' step='.01' min='0' name='embalagem' value='0'></div><div><label>Categoria Mercado Livre</label><input name='category_id' placeholder='Ex.: MLB1055' required></div><div><label>Tipo de anúncio</label><select name='listing_type_id'><option value='gold_special'>Clássico</option><option value='gold_pro'>Premium</option></select></div><div><label>Logística</label><select name='logistic_type'><option value='drop_off'>Drop Off</option><option value='cross_docking'>Coleta</option><option value='xd_drop_off'>Places</option><option value='self_service'>Flex</option><option value='fulfillment'>Full</option><option value='not_specified'>Não especificado</option></select></div><div><label>Modo envio</label><select name='shipping_mode'><option value='me2'>Mercado Envios 2</option><option value='not_specified'>Não especificado</option></select></div><div><label>Frete vendedor</label><input type='number' step='.01' min='0' name='frete' value='0'></div><div><label>Outros custos</label><input type='number' step='.01' min='0' name='outros' value='0'></div><div><label>Ads (%)</label><input type='number' step='.01' min='0' name='ads' value='0'></div><div><label>Margem líquida (%)</label><input type='number' step='.01' min='0' name='margem' value='15'></div></div><br><button>Calcular com API Mercado Livre</button></form></div>''')

@app.post('/calcular-ml',response_class=HTMLResponse)
def calcular_ml(ncm:str=Form(...),uf_destino:str=Form(...),custo:float=Form(...),embalagem:float=Form(0),category_id:str=Form(...),listing_type_id:str=Form(...),logistic_type:str=Form('not_specified'),shipping_mode:str=Form('not_specified'),frete:float=Form(0),outros:float=Form(0),ads:float=Form(0),margem:float=Form(15)):
 try: cfg=ensure_ml_token()
 except MercadoLivreAPIError as exc: return page(f"<div class='warn'>Falha ao renovar conexão: {exc}</div>")
 if not cfg or not cfg['access_token']: return page("<div class='warn'>Conecte o Mercado Livre antes de calcular.</div>")
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); con.close(); regras=contexto_fiscal(emp['regime'],emp['uf'],uf_destino,ncm,emp['receita_12m']); imposto=aliquota_efetiva_cadastrada(regras); preco=max(custo+embalagem+frete+outros,1)*1.5; fee=None; r=None
 try:
  for _ in range(8):
   fee=listing_price(cfg['access_token'],preco,category_id,listing_type_id,logistic_type,shipping_mode); percentual=fee['percentage_fee']; fixa=fee['fixed_fee']; novo=calcular_preco(PricingInput(custo,embalagem,outros,frete,fixa,imposto,percentual,ads,margem)); r=novo
   if abs(novo['preco']-preco)<0.02: break
   preco=novo['preco']
 except MercadoLivreAPIError as exc: return page(f"<div class='warn'><b>Erro Mercado Livre.</b><br>{exc}</div>")
 pendencia='' if regras else "<div class='warn'>Regra fiscal ainda não cadastrada: imposto considerado 0%.</div>"
 return page(f'''<div class='card'><h1>Preço recomendado</h1><div class='result'>R$ {r['preco']:.2f}</div><p>Categoria: <b>{category_id}</b> | {fee['listing_type_name'] or listing_type_id}</p><p>Comissão API: <b>{fee['percentage_fee']:.2f}%</b> | Tarifa fixa: <b>R$ {fee['fixed_fee']:.2f}</b> | Custo de venda API: <b>R$ {fee['sale_fee_amount']:.2f}</b></p><p>Lucro projetado: <b>R$ {r['lucro']:.2f}</b> | Margem: <b>{r['margem_real']:.2f}%</b></p></div>{pendencia}''')
