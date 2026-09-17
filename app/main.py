from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from .database import init_db, connect
from .pricing import PricingInput, calcular_preco
from .fiscal import contexto_fiscal, aliquota_efetiva_cadastrada
from .marketplaces.mercadolivre import listing_price, me, MercadoLivreAPIError

app=FastAPI(title='PrecificaEcom'); init_db()
CSS='''body{font-family:Segoe UI,Arial;background:#f4f6f8;margin:0;color:#1f2937}.wrap{max-width:980px;margin:28px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 12px #0001;margin-bottom:18px}h1{margin:0 0 5px}.muted{color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;font-weight:600;margin-bottom:5px}input,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px}button{padding:12px 18px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700;cursor:pointer}.result{font-size:34px;font-weight:800}.warn{padding:12px;background:#fff7ed;border-radius:8px;color:#9a3412;margin:10px 0}.info{padding:12px;background:#eff6ff;border-radius:8px;color:#1e40af;margin:10px 0}.ok{padding:12px;background:#ecfdf5;border-radius:8px;color:#166534;margin:10px 0}.hide{display:none}.nav{display:flex;gap:14px;margin-bottom:15px;flex-wrap:wrap}.nav a{color:#334155;text-decoration:none;font-weight:600}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
def page(body,script=''): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>PrecificaEcom</title><style>{CSS}</style></head><body><div class='wrap'><div class='nav'><a href='/precificar'>Precificar</a><a href='/'>Empresa</a><a href='/mercadolivre'>Mercado Livre</a><a href='/tarifas'>Tarifas</a></div>{body}</div><script>{script}</script></body></html>")

@app.get('/',response_class=HTMLResponse)
def home():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); regimes=con.execute('SELECT * FROM regimes_tributarios').fetchall(); estados=con.execute('SELECT * FROM estados').fetchall(); con.close()
 ro=''.join(f"<option value='{r['codigo']}' {'selected' if r['codigo']==emp['regime'] else ''}>{r['nome']}</option>" for r in regimes); uo=''.join(f"<option value='{e['uf']}' {'selected' if e['uf']==emp['uf'] else ''}>{e['uf']} - {e['nome']}</option>" for e in estados); show='' if emp['regime']=='SIMPLES' else 'hide'
 body=f'''<div class='card'><h1>Configurações da empresa</h1><form method='post' action='/configurar'><div class='grid'><div><label>Empresa</label><input name='nome' value="{emp['nome']}"></div><div><label>Regime tributário</label><select id='regime' name='regime' onchange='regimeChanged()'>{ro}</select></div><div><label>UF da empresa</label><select name='uf'>{uo}</select></div><div id='rbt12' class='{show}'><label>Faturamento bruto dos últimos 12 meses — RBT12 (R$)</label><input type='number' step='.01' min='0' name='receita_12m' value="{emp['receita_12m']}"><small class='muted'>Usado no Simples Nacional para determinar a faixa e a alíquota efetiva.</small></div></div><br><button>Salvar configurações</button></form></div>'''
 return page(body,"function regimeChanged(){document.getElementById('rbt12').classList.toggle('hide',document.getElementById('regime').value!=='SIMPLES');}")

@app.post('/configurar')
def configurar(nome:str=Form(''),regime:str=Form(...),uf:str=Form(...),receita_12m:float=Form(0)):
 if regime!='SIMPLES': receita_12m=0
 con=connect(); con.execute('UPDATE empresa SET nome=?,regime=?,uf=?,receita_12m=? WHERE id=1',(nome,regime,uf,receita_12m)); con.commit(); con.close(); return precificador()

@app.get('/mercadolivre',response_class=HTMLResponse)
def mercadolivre_config():
 con=connect(); cfg=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close(); status="Não conectado"
 if cfg and cfg['access_token']:
  try:
   user=me(cfg['access_token']); status=f"Conectado: usuário Mercado Livre #{user.get('id','')} — {user.get('nickname','')}"
  except Exception: status="Token salvo, mas não foi possível validar. Pode estar expirado."
 return page(f'''<div class='card'><h1>Integração Mercado Livre</h1><div class='info'>{status}</div><p class='muted'>Nesta etapa o token fica armazenado somente no banco local do PrecificaEcom. Não publique tokens no GitHub.</p><form method='post' action='/mercadolivre/token'><label>Access token</label><input type='password' name='access_token' value='' placeholder='APP_USR-...' required><br><br><button>Salvar e testar conexão</button></form></div><div class='card'><h2>O que a integração consulta</h2><p>O PrecificaEcom usa o endpoint oficial de listing prices do site MLB para obter a comissão e a tarifa fixa reais conforme preço, categoria, tipo de anúncio e logística.</p></div>''')

@app.post('/mercadolivre/token',response_class=HTMLResponse)
def mercadolivre_token(access_token:str=Form(...)):
 token=access_token.strip()
 try: user=me(token)
 except MercadoLivreAPIError as exc: return page(f"<div class='warn'><b>Não foi possível conectar.</b><br>{str(exc)}</div><a href='/mercadolivre'>Voltar</a>")
 con=connect(); con.execute("UPDATE marketplace_config SET access_token=?,user_id=?,updated_at=CURRENT_TIMESTAMP WHERE marketplace='ML'",(token,str(user.get('id','')))); con.commit(); con.close()
 return page(f"<div class='ok'><b>Mercado Livre conectado.</b><br>Conta: {user.get('nickname','')} — ID {user.get('id','')}</div><a href='/precificar'>Ir para precificação</a>")

@app.get('/tarifas',response_class=HTMLResponse)
def tarifas():
 con=connect(); rows=con.execute('SELECT t.*,m.nome marketplace_nome FROM tarifas_marketplace t JOIN marketplaces m ON m.codigo=t.marketplace WHERE t.ativo=1 ORDER BY t.marketplace,t.id').fetchall(); con.close(); trs=''
 for r in rows:
  taxa=f"{r['comissao_exata_pct']:.2f}%" if r['comissao_exata_pct'] is not None else (f"{r['comissao_min_pct']:.2f}% a {r['comissao_max_pct']:.2f}%" if r['comissao_min_pct'] is not None else 'Dinâmica')
  trs+=f"<tr><td>{r['marketplace_nome']}</td><td>{r['nome']}</td><td>{taxa}</td><td>{r['observacao'] or ''}</td></tr>"
 return page(f"<div class='card'><h1>Tarifas das plataformas</h1><table style='width:100%'><tr><th align='left'>Plataforma</th><th align='left'>Tipo</th><th align='left'>Comissão</th><th align='left'>Regra</th></tr>{trs}</table></div>")

@app.get('/precificar',response_class=HTMLResponse)
def precificador():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); estados=con.execute('SELECT * FROM estados').fetchall(); cfg=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close(); destinos=''.join(f"<option value='{e['uf']}'>{e['uf']} - {e['nome']}</option>" for e in estados); conectado=bool(cfg and cfg['access_token'])
 mlmsg="<div class='ok'>API Mercado Livre configurada: comissão será consultada automaticamente.</div>" if conectado else "<div class='warn'>Mercado Livre ainda não conectado. <a href='/mercadolivre'>Configurar conexão</a>.</div>"
 body=f'''<div class='card'><h1>Nova precificação</h1><p class='muted'>Regime: <b>{emp['regime']}</b> | Origem: <b>{emp['uf']}</b></p>{mlmsg}<form method='post' action='/calcular-ml'><div class='grid'><div><label>NCM</label><input name='ncm' maxlength='8' required></div><div><label>UF destino</label><select name='uf_destino'>{destinos}</select></div><div><label>Custo produto (R$)</label><input type='number' step='.01' min='0' name='custo' required></div><div><label>Embalagem (R$)</label><input type='number' step='.01' min='0' name='embalagem' value='0'></div><div><label>Categoria Mercado Livre</label><input name='category_id' placeholder='Ex.: MLB1055' required></div><div><label>Tipo de anúncio</label><select name='listing_type_id'><option value='gold_special'>Clássico</option><option value='gold_pro'>Premium</option></select></div><div><label>Logística</label><select name='logistic_type'><option value='drop_off'>Drop Off</option><option value='cross_docking'>Coleta</option><option value='xd_drop_off'>Places</option><option value='self_service'>Flex</option><option value='fulfillment'>Full</option><option value='not_specified'>Não especificado</option></select></div><div><label>Modo de envio</label><select name='shipping_mode'><option value='me2'>Mercado Envios 2</option><option value='me1'>Mercado Envios 1</option><option value='custom'>Personalizado</option><option value='not_specified'>Não especificado</option></select></div><div><label>Frete pago pelo vendedor (R$)</label><input type='number' step='.01' min='0' name='frete' value='0'></div><div><label>Outros custos (R$)</label><input type='number' step='.01' min='0' name='outros' value='0'></div><div><label>Ads (%)</label><input type='number' step='.01' min='0' name='ads' value='0'></div><div><label>Margem líquida desejada (%)</label><input type='number' step='.01' min='0' name='margem' value='15'></div></div><br><button>Calcular com API Mercado Livre</button></form></div><div class='info'>Como a tarifa do Mercado Livre depende do preço, o sistema faz iterações: estima o preço, consulta a API, recalcula e repete até estabilizar.</div>'''
 return page(body)

@app.post('/calcular-ml',response_class=HTMLResponse)
def calcular_ml(ncm:str=Form(...),uf_destino:str=Form(...),custo:float=Form(...),embalagem:float=Form(0),category_id:str=Form(...),listing_type_id:str=Form(...),logistic_type:str=Form('not_specified'),shipping_mode:str=Form('not_specified'),frete:float=Form(0),outros:float=Form(0),ads:float=Form(0),margem:float=Form(15)):
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); cfg=con.execute("SELECT * FROM marketplace_config WHERE marketplace='ML'").fetchone(); con.close()
 if not cfg or not cfg['access_token']: return page("<div class='warn'>Conecte o Mercado Livre antes de calcular.</div>")
 regras=contexto_fiscal(emp['regime'],emp['uf'],uf_destino,ncm,emp['receita_12m']); imposto=aliquota_efetiva_cadastrada(regras); preco=max(custo+embalagem+frete+outros,1)*1.5; fee=None; r=None
 try:
  for _ in range(8):
   fee=listing_price(cfg['access_token'],preco,category_id,listing_type_id,logistic_type,shipping_mode)
   percentual=fee['percentage_fee']; fixa=fee['fixed_fee']
   novo=calcular_preco(PricingInput(custo,embalagem,outros,frete,fixa,imposto,percentual,ads,margem))
   if abs(novo['preco']-preco)<0.02: r=novo; break
   preco=novo['preco']; r=novo
 except MercadoLivreAPIError as exc: return page(f"<div class='warn'><b>Erro na consulta ao Mercado Livre.</b><br>{str(exc)}</div><a href='/precificar'>Voltar</a>")
 pendencia='' if regras else "<div class='warn'>Regra fiscal ainda não cadastrada: imposto considerado 0%. O resultado não deve ser usado comercialmente até concluirmos a base fiscal.</div>"
 return page(f'''<div class='card'><h1>Preço recomendado — Mercado Livre</h1><div class='result'>R$ {r['preco']:.2f}</div><p>Categoria: <b>{category_id}</b> | Anúncio: <b>{fee['listing_type_name'] or listing_type_id}</b></p><p>Tarifa consultada diretamente na API: <b>{fee['percentage_fee']:.2f}%</b> | Tarifa fixa: <b>R$ {fee['fixed_fee']:.2f}</b> | Custo de venda retornado na última consulta: <b>R$ {fee['sale_fee_amount']:.2f}</b></p><p>Impostos cadastrados: {imposto:.2f}% | Ads: {ads:.2f}% | Lucro projetado: <b>R$ {r['lucro']:.2f}</b> | Margem: <b>{r['margem_real']:.2f}%</b></p><a href='/precificar'>Nova precificação</a></div>{pendencia}''')
