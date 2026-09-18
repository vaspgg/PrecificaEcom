import html, secrets, time, urllib.parse
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .database import init_db, connect
from .marketplaces.mercadolivre import *
from .pricing import PricingInput, calcular_preco
from .fiscal import contexto_fiscal, aliquota_efetiva_cadastrada
app=FastAPI(title='PrecificaEcom'); init_db()
CSS='''body{font-family:Segoe UI,Arial;background:#f4f6f8;margin:0;color:#1f2937}.wrap{max-width:1050px;margin:28px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 12px #0001;margin-bottom:18px}h1{margin:0 0 8px}.muted{color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;font-weight:600;margin-bottom:5px}input,select,textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px}button,.btn{display:inline-block;padding:12px 18px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700;cursor:pointer;text-decoration:none}.warn,.info,.ok{padding:12px;border-radius:8px;margin:10px 0}.warn{background:#fff7ed;color:#9a3412}.info{background:#eff6ff;color:#1e40af}.ok{background:#ecfdf5;color:#166534}.nav{display:flex;gap:14px;margin-bottom:15px;flex-wrap:wrap}.nav a{color:#334155;text-decoration:none;font-weight:600}.cat{padding:12px;border:1px solid #cbd5e1;border-radius:9px;margin:8px 0}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
def page(b): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>PrecificaEcom</title><style>{CSS}</style></head><body><div class='wrap'><div class='nav'><a href='/precificar'>Precificar</a><a href='/anuncio-similar'>Anúncio similar</a><a href='/empresa'>Empresa</a><a href='/mercadolivre'>Mercado Livre</a></div>{b}</div></body></html>")
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
 ident=u.get('identification') or {};addr=u.get('address') or {};company=u.get('company') or {};seller_name=company.get('corporate_name') or company.get('brand_name') or (' '.join(x for x in [u.get('first_name',''),u.get('last_name','')] if x)).strip() or u.get('nickname','')
 c=connect();c.execute("UPDATE marketplace_config SET access_token=?,refresh_token=?,user_id=?,seller_nickname=?,token_expires_at=?,seller_name=?,seller_document_type=?,seller_document=?,seller_state=?,seller_city=? WHERE marketplace='ML'",(t.get('access_token',''),t.get('refresh_token',''),str(u.get('id','')),u.get('nickname',''),str(time.time()+int(t.get('expires_in',21600))),seller_name,ident.get('type',''),ident.get('number',''),str(addr.get('state','')),str(addr.get('city',''))))
 if seller_name:c.execute("UPDATE empresa SET nome=CASE WHEN nome='' THEN ? ELSE nome END WHERE id=1",(seller_name,))
 c.execute("DELETE FROM oauth_sessions WHERE state=?",(state,));c.commit();c.close();return page("<div class='ok'>Mercado Livre conectado e dados cadastrais disponíveis foram sincronizados.</div><a class='btn' href='/empresa'>Revisar empresa</a> <a class='btn' href='/precificar'>Precificar</a>")
def pricing_form(title='',ncm='',category_id='',source='manual',marketplace='ML',listing_type_id='gold_special',price_ref=0,uf_destino=''):
 c=connect();e=c.execute("SELECT * FROM empresa WHERE id=1").fetchone();c.close()
 uf_origem=e['uf'] if e else 'MG';regime=e['regime'] if e else 'SIMPLES';receita=float(e['receita_12m'] or 0) if e else 0
 uf_destino=(uf_destino or uf_origem).upper()[:2]
 regras=contexto_fiscal(regime,uf_origem,uf_destino,ncm,receita) if ncm else contexto_fiscal(regime,uf_origem,uf_destino,'',receita)
 imposto=aliquota_efetiva_cadastrada(regras)
 comissao=0.0;tarifa=0.0;fee_note=''
 if marketplace=='ML' and category_id and price_ref and float(price_ref)>0:
  try:
   cfg=ensure_ml_token();fee=listing_price(cfg['access_token'] if cfg else None,float(price_ref),category_id,listing_type_id)
   comissao=float(fee.get('percentage_fee') or 0);tarifa=float(fee.get('fixed_fee') or 0);fee_note=f"Taxas consultadas no Mercado Livre para preço de referência R$ {float(price_ref):.2f}."
  except Exception as ex: fee_note="Não foi possível consultar a tarifa do Mercado Livre: "+str(ex)
 elif marketplace=='SHOPEE': fee_note="Shopee: informe a comissão/tarifa efetiva da sua conta enquanto não houver integração autenticada de tarifas."
 else: fee_note="Informe um preço de referência para consultar automaticamente a tarifa do Mercado Livre."
 ml_sel='selected' if marketplace=='ML' else '';sh_sel='selected' if marketplace=='SHOPEE' else '';cl_sel='selected' if listing_type_id=='gold_special' else '';pr_sel='selected' if listing_type_id=='gold_pro' else ''
 fiscal_note=f"Empresa: {html.escape(regime)} | origem {html.escape(uf_origem)} → destino {html.escape(uf_destino)}. Imposto preenchido pelas regras fiscais validadas existentes no banco."
 return page(f"""<div class='card'><h1>Precificação</h1><p class='muted'>Produto: <b>{html.escape(title or 'Não informado')}</b>{' | NCM: <b>'+html.escape(ncm)+'</b>' if ncm else ''}{' | Categoria ML: <b>'+html.escape(category_id)+'</b>' if category_id else ''}</p><form method='get' action='/tabela-precificacao'><input type='hidden' name='title' value='{html.escape(title)}'><input type='hidden' name='ncm' value='{html.escape(ncm)}'><input type='hidden' name='category_id' value='{html.escape(category_id)}'><div class='grid'><div><label>Plataforma de venda</label><select name='marketplace'><option value='ML' {ml_sel}>Mercado Livre</option><option value='SHOPEE' {sh_sel}>Shopee</option></select></div><div><label>Tipo de anúncio</label><select name='listing_type_id'><option value='gold_special' {cl_sel}>Clássico</option><option value='gold_pro' {pr_sel}>Premium</option></select></div><div><label>Preço de venda / referência (R$)</label><input type='number' step='.01' min='.01' name='price_ref' value='{float(price_ref or 0) if price_ref else ''}' required></div><div><label>UF destino</label><input name='uf_destino' maxlength='2' value='{html.escape(uf_destino)}' required></div></div><br><button>Consultar taxas e impostos</button></form><div class='info'>{html.escape(fee_note)}</div><div class='info'>{fiscal_note}</div></div><div class='card'><h2>Custos e margem</h2><form method='post' action='/calcular-preco'><input type='hidden' name='title' value='{html.escape(title)}'><input type='hidden' name='ncm' value='{html.escape(ncm)}'><input type='hidden' name='category_id' value='{html.escape(category_id)}'><div class='grid'><div><label>Custo do produto (R$)</label><input type='number' step='.01' min='0' name='custo_produto' required></div><div><label>Embalagem (R$)</label><input type='number' step='.01' min='0' name='embalagem' value='0'></div><div><label>Outros custos (R$)</label><input type='number' step='.01' min='0' name='outros_custos' value='0'></div><div><label>Frete pago pelo vendedor (R$)</label><input type='number' step='.01' min='0' name='frete_vendedor' value='0'></div><div><label>Tarifa fixa marketplace (R$)</label><input type='number' step='.01' min='0' name='tarifa_fixa' value='{tarifa:.2f}'></div><div><label>Impostos (%)</label><input type='number' step='.01' min='0' name='imposto_pct' value='{imposto:.4f}'></div><div><label>Comissão marketplace (%)</label><input type='number' step='.01' min='0' name='comissao_pct' value='{comissao:.4f}'></div><div><label>Ads (%)</label><input type='number' step='.01' min='0' name='ads_pct' value='0'></div><div><label>Margem desejada (%)</label><input type='number' step='.01' min='0' name='margem_pct' value='20' required></div></div><br><button>Calcular preço de venda</button></form></div>""")
@app.get('/precificar')
def precificar(): return page("<div class='card'><h1>Precificar</h1><p>Informe o NCM, o nome do produto ou os dois. Nenhum dos dois campos é obrigatório individualmente.</p><form method='post' action='/categoria-sugerir'><div class='grid'><div><label>NCM</label><input name='ncm' maxlength='8' placeholder='Opcional'></div><div><label>Produto</label><input name='product_name' placeholder='Opcional'></div></div><br><button>Continuar para precificação</button></form></div><div class='card'><h2>Ou use um anúncio similar</h2><a class='btn' href='/anuncio-similar'>Pesquisar pelo link</a></div>")
@app.post('/categoria-sugerir')
def suggest(ncm:str=Form(''),product_name:str=Form('')):
 ncm=''.join(ch for ch in ncm if ch.isdigit())[:8];product_name=product_name.strip()
 if not ncm and not product_name:return page("<div class='warn'>Informe pelo menos o NCM ou o nome do produto.</div><a class='btn' href='/precificar'>Voltar</a>")
 if not product_name:return pricing_form('',ncm,'','ncm')
 try:
  cfg=ensure_ml_token();cats=predict_categories(cfg['access_token'] if cfg else None,product_name,3)
 except Exception:
  return pricing_form(product_name,ncm,'','nome')
 if not cats:return pricing_form(product_name,ncm,'','nome')
 cards=''.join(f"<div class='cat'><b>{html.escape(x['category_name'])}</b> — {html.escape(x['category_id'])}<form method='get' action='/tabela-precificacao'><input type='hidden' name='category_id' value='{html.escape(x['category_id'])}'><input type='hidden' name='title' value='{html.escape(product_name)}'><input type='hidden' name='ncm' value='{html.escape(ncm)}'><button>Usar categoria na precificação</button></form></div>" for x in cats)
 return page(f"<div class='card'><h1>Categorias sugeridas</h1><p>Escolha a categoria mais adequada. O próximo passo é a tabela de precificação, não a publicação do anúncio.</p>{cards}<br><a class='btn' href='/tabela-precificacao?title={urllib.parse.quote(product_name)}&ncm={urllib.parse.quote(ncm)}'>Continuar sem categoria</a></div>")

@app.get('/tabela-precificacao')
def tabela_precificacao(title:str='',ncm:str='',category_id:str='',marketplace:str='ML',listing_type_id:str='gold_special',price_ref:float=0,uf_destino:str=''): return pricing_form(title,ncm,category_id,'manual',marketplace,listing_type_id,price_ref,uf_destino)

@app.post('/calcular-preco')
def calcular(custo_produto:float=Form(...),embalagem:float=Form(0),outros_custos:float=Form(0),frete_vendedor:float=Form(0),tarifa_fixa:float=Form(0),imposto_pct:float=Form(0),comissao_pct:float=Form(0),ads_pct:float=Form(0),margem_pct:float=Form(...),title:str=Form(''),ncm:str=Form(''),category_id:str=Form('')):
 try:r=calcular_preco(PricingInput(custo_produto,embalagem,outros_custos,frete_vendedor,tarifa_fixa,imposto_pct,comissao_pct,ads_pct,margem_pct))
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 return page(f"<div class='card'><h1>Resultado da precificação</h1><p><b>{html.escape(title or 'Produto')}</b></p><div class='grid'><div class='ok'><b>Preço de venda</b><br>R$ {r['preco']:.2f}</div><div class='ok'><b>Lucro estimado</b><br>R$ {r['lucro']:.2f} ({r['margem_real']:.2f}%)</div><div class='info'>Custos fixos: R$ {r['custos_fixos']:.2f}</div><div class='info'>Impostos: R$ {r['imposto']:.2f} | Comissão: R$ {r['comissao']:.2f} | Ads: R$ {r['ads']:.2f}</div></div><br><a class='btn' href='/tabela-precificacao?title={urllib.parse.quote(title)}&ncm={urllib.parse.quote(ncm)}&category_id={urllib.parse.quote(category_id)}'>Recalcular</a></div>")

@app.get('/empresa')
def empresa():
 c=connect();e=c.execute("SELECT * FROM empresa WHERE id=1").fetchone();c.close();opts=''.join(f"<option value='{x}' {'selected' if e['regime']==x else ''}>{n}</option>" for x,n in [('MEI','MEI'),('SIMPLES','Simples Nacional'),('PRESUMIDO','Lucro Presumido'),('REAL','Lucro Real')])
 return page(f"<div class='card'><h1>Empresa</h1><form method='post'><div class='grid'><div><label>Nome / Razão social</label><input name='nome' value='{html.escape(e['nome'] or '')}'></div><div><label>UF</label><input name='uf' maxlength='2' value='{html.escape(e['uf'] or '')}'></div><div><label>Regime tributário</label><select name='regime'>{opts}</select></div><div><label>Receita bruta 12 meses (R$)</label><input type='number' step='.01' min='0' name='receita_12m' value='{float(e['receita_12m'] or 0)}'></div></div><br><button>Salvar empresa</button></form><div class='info'>O Mercado Livre pode fornecer dados cadastrais da conta, mas o regime tributário deve ser confirmado aqui quando não vier de uma fonte fiscal confiável.</div></div>")

@app.post('/empresa')
def empresa_salvar(nome:str=Form(''),uf:str=Form(''),regime:str=Form('SIMPLES'),receita_12m:float=Form(0)):
 c=connect();c.execute("UPDATE empresa SET nome=?,uf=?,regime=?,receita_12m=? WHERE id=1",(nome.strip(),uf.strip().upper()[:2],regime,receita_12m));c.commit();c.close();return RedirectResponse('/empresa',303)
@app.get('/anuncio-similar')
def similar():return page("<div class='card'><h1>Anúncio similar</h1><p class='muted'>Cole a URL completa do produto ou o código MLB do anúncio. Links de catálogo com parâmetro wid também são aceitos.</p><form method='post'><label>Link ou MLB</label><input name='url' required><br><br><button>Pesquisar</button></form></div>")
@app.post('/anuncio-similar')
def similar_post(url:str=Form(...)):
 try:
  cfg=ensure_ml_token();i=item_details(cfg['access_token'] if cfg else None,url);cat=category_details(cfg['access_token'] if cfg else None,i['category_id']);path=' → '.join(x.get('name','') for x in cat.get('path_from_root',[]))
 except Exception as e:return page(f"<div class='warn'><b>Não foi possível consultar o anúncio.</b><br>{html.escape(str(e))}<br><br>Se o link for de uma página de catálogo, confirme se ele contém <b>wid=MLB...</b> ou informe diretamente o código MLB do anúncio.</div>")
 return pricing_form(i['title'] or '','',i['category_id'],'link','ML',i.get('listing_type_id') or 'gold_special',float(i.get('price') or 0),'')
@app.get('/criar-anuncio')
def create_form(category_id:str,title:str=''):
 try:cfg=ensure_ml_token();attrs=category_attributes(cfg['access_token'],category_id)
 except Exception as e:return page(f"<div class='warn'>{html.escape(str(e))}</div>")
 fields=''
 for a in attrs:
  aid=html.escape(a.get('id',''));name=html.escape(a.get('name',aid));vals=a.get('values') or [];req=' *' if a.get('required') else ''
  if vals and len(vals)<=80:
   opts="<option value=''>Selecione</option>"+''.join(f"<option value='{html.escape(str(v.get('id','')))}'>{html.escape(str(v.get('name','')))}</option>" for v in vals);fields+=f"<div><label>{name}{req}</label><select name='attr_{aid}'>{opts}</select></div>"
  else:fields+=f"<div><label>{name}{req}</label><input name='attr_{aid}'></div>"
 return page(f'''<div class='card'><h1>Criar anúncio</h1><div class='info'>Categoria {html.escape(category_id)}. Preencha os dados do seu próprio produto.</div><form method='post' action='/publicar-anuncio'><input type='hidden' name='category_id' value='{html.escape(category_id)}'><div class='grid'><div><label>Título</label><input name='title' value='{html.escape(title)}' required></div><div><label>Preço (R$)</label><input type='number' step='.01' min='.01' name='price' required></div><div><label>Estoque</label><input type='number' min='1' name='quantity' value='1' required></div><div><label>Tipo de anúncio</label><select name='listing_type_id'><option value='gold_special'>Clássico</option><option value='gold_pro'>Premium</option></select></div><div><label>Condição</label><select name='condition'><option value='new'>Novo</option><option value='used'>Usado</option></select></div><div><label>URL da sua imagem principal</label><input name='picture_url' placeholder='https://...' required></div>{fields}</div><br><div class='warn'><b>Atenção:</b> o botão abaixo cria um anúncio real na conta conectada.</div><button>PUBLICAR ANÚNCIO NO MERCADO LIVRE</button></form></div>''')
@app.post('/publicar-anuncio')
async def publish(request:Request):
 form=await request.form();cfg=ensure_ml_token();cid=str(form.get('category_id',''));attrs_meta=category_attributes(cfg['access_token'],cid);attrs=[]
 for a in attrs_meta:
  val=str(form.get('attr_'+a.get('id',''),'')).strip()
  if val:
   values=a.get('values') or [];match=next((v for v in values if str(v.get('id'))==val),None);attrs.append({"id":a['id'],"value_id":val} if match else {"id":a['id'],"value_name":val})
 payload={"site_id":"MLB","title":str(form.get('title','')).strip(),"category_id":cid,"price":float(form.get('price')),"currency_id":"BRL","available_quantity":int(form.get('quantity')),"buying_mode":"buy_it_now","listing_type_id":str(form.get('listing_type_id')),"condition":str(form.get('condition')),"pictures":[{"source":str(form.get('picture_url')).strip()}],"attributes":attrs}
 try:item=create_item(cfg['access_token'],payload)
 except Exception as e:return page(f"<div class='warn'><h2>Publicação não realizada</h2><pre style='white-space:pre-wrap'>{html.escape(str(e))}</pre></div>")
 return page(f"<div class='ok'><h1>Anúncio publicado</h1><p>ID: <b>{html.escape(str(item.get('id','')))}</b></p><p>{html.escape(str(item.get('permalink','')))}</p></div>")
