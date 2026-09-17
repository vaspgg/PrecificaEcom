from fastapi import FastAPI,Form
from fastapi.responses import HTMLResponse
from .database import init_db,connect
from .pricing import PricingInput,calcular_preco
from .fiscal import contexto_fiscal,aliquota_efetiva_cadastrada

app=FastAPI(title='PrecificaEcom'); init_db()
CSS='''body{font-family:Segoe UI,Arial;background:#f4f6f8;margin:0;color:#1f2937}.wrap{max-width:980px;margin:28px auto;padding:0 20px}.card{background:white;padding:24px;border-radius:14px;box-shadow:0 2px 12px #0001;margin-bottom:18px}h1{margin:0 0 5px}.muted{color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-size:13px;font-weight:600;margin-bottom:5px}input,select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px}button{padding:12px 18px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700;cursor:pointer}.result{font-size:34px;font-weight:800}.warn{padding:12px;background:#fff7ed;border-radius:8px;color:#9a3412;margin:10px 0}.info{padding:12px;background:#eff6ff;border-radius:8px;color:#1e40af;margin:10px 0}.hide{display:none}.nav{display:flex;gap:14px;margin-bottom:15px}.nav a{color:#334155;text-decoration:none;font-weight:600}@media(max-width:650px){.grid{grid-template-columns:1fr}}'''
def page(body,script=''): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>PrecificaEcom</title><style>{CSS}</style></head><body><div class='wrap'><div class='nav'><a href='/precificar'>Precificar</a><a href='/'>Configurações da empresa</a><a href='/tarifas'>Tarifas das plataformas</a></div>{body}</div><script>{script}</script></body></html>")

@app.get('/',response_class=HTMLResponse)
def home():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); regimes=con.execute('SELECT * FROM regimes_tributarios').fetchall(); estados=con.execute('SELECT * FROM estados').fetchall(); con.close()
 ro=''.join(f"<option value='{r['codigo']}' {'selected' if r['codigo']==emp['regime'] else ''}>{r['nome']}</option>" for r in regimes); uo=''.join(f"<option value='{e['uf']}' {'selected' if e['uf']==emp['uf'] else ''}>{e['uf']} - {e['nome']}</option>" for e in estados)
 show='' if emp['regime']=='SIMPLES' else 'hide'
 body=f'''<div class='card'><h1>Configurações da empresa</h1><p class='muted'>Esses dados ficam salvos e não precisam ser preenchidos em cada precificação.</p><form method='post' action='/configurar'><div class='grid'><div><label>Empresa</label><input name='nome' value="{emp['nome']}"></div><div><label>Regime tributário</label><select id='regime' name='regime' onchange='regimeChanged()'>{ro}</select></div><div><label>UF da empresa</label><select name='uf'>{uo}</select></div><div id='rbt12' class='{show}'><label>Faturamento bruto dos últimos 12 meses — RBT12 (R$)</label><input type='number' step='.01' min='0' name='receita_12m' value="{emp['receita_12m']}"><small class='muted'>Usado no Simples Nacional para determinar a faixa e a alíquota efetiva.</small></div></div><br><button>Salvar configurações</button></form></div>'''
 script="function regimeChanged(){document.getElementById('rbt12').classList.toggle('hide',document.getElementById('regime').value!=='SIMPLES');}"
 return page(body,script)

@app.post('/configurar')
def configurar(nome:str=Form(''),regime:str=Form(...),uf:str=Form(...),receita_12m:float=Form(0)):
 if regime!='SIMPLES': receita_12m=0
 con=connect(); con.execute('UPDATE empresa SET nome=?,regime=?,uf=?,receita_12m=? WHERE id=1',(nome,regime,uf,receita_12m)); con.commit(); con.close(); return precificador()

@app.get('/tarifas',response_class=HTMLResponse)
def tarifas():
 con=connect(); rows=con.execute('SELECT t.*,m.nome marketplace_nome FROM tarifas_marketplace t JOIN marketplaces m ON m.codigo=t.marketplace WHERE t.ativo=1 ORDER BY t.marketplace,t.id').fetchall(); con.close()
 trs=''
 for r in rows:
  if r['comissao_exata_pct'] is not None: taxa=f"{r['comissao_exata_pct']:.2f}%"
  elif r['comissao_min_pct'] is not None: taxa=f"{r['comissao_min_pct']:.2f}% a {r['comissao_max_pct']:.2f}%"
  else: taxa='Dinâmica — consultar condição da conta/operação'
  trs+=f"<tr><td>{r['marketplace_nome']}</td><td>{r['nome']}</td><td>{taxa}</td><td>{r['observacao'] or ''}</td><td>{r['verificado_em']}</td></tr>"
 return page(f'''<div class='card'><h1>Tarifas das plataformas</h1><p class='muted'>Base versionada com fontes oficiais. Quando a plataforma não publica uma taxa única, o sistema marca a tarifa como dinâmica em vez de inventar um percentual.</p><div style='overflow:auto'><table style='width:100%;border-collapse:collapse'><tr><th align='left'>Plataforma</th><th align='left'>Tipo de venda</th><th align='left'>Comissão</th><th align='left'>Regra</th><th align='left'>Verificado</th></tr>{trs}</table></div></div>''')

@app.get('/precificar',response_class=HTMLResponse)
def precificador():
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); estados=con.execute('SELECT * FROM estados').fetchall(); tarifas=con.execute('SELECT t.*,m.nome marketplace_nome FROM tarifas_marketplace t JOIN marketplaces m ON m.codigo=t.marketplace WHERE t.ativo=1 ORDER BY t.marketplace,t.id').fetchall(); con.close()
 destinos=''.join(f"<option value='{e['uf']}'>{e['uf']} - {e['nome']}</option>" for e in estados)
 opts=[]
 for t in tarifas:
  meta=f"{t['comissao_min_pct'] if t['comissao_min_pct'] is not None else ''}|{t['comissao_max_pct'] if t['comissao_max_pct'] is not None else ''}|{t['comissao_exata_pct'] if t['comissao_exata_pct'] is not None else ''}|{t['tarifa_fixa'] if t['tarifa_fixa'] is not None else ''}"
  opts.append(f"<option value='{t['id']}' data-meta='{meta}'>{t['marketplace_nome']} | {t['nome']}</option>")
 rbt=f" | RBT12: R$ {emp['receita_12m']:.2f}" if emp['regime']=='SIMPLES' else ''
 body=f'''<div class='card'><h1>Nova precificação</h1><p class='muted'>Regime: <b>{emp['regime']}</b> | Origem: <b>{emp['uf']}</b>{rbt}</p><form method='post' action='/calcular'><div class='grid'><div><label>NCM</label><input name='ncm' maxlength='8' required placeholder='Ex.: 85171300'></div><div><label>UF de destino</label><select name='uf_destino'>{destinos}</select></div><div><label>Custo do produto (R$)</label><input type='number' step='.01' min='0' name='custo' required></div><div><label>Embalagem (R$)</label><input type='number' step='.01' min='0' name='embalagem' value='0'></div><div><label>Plataforma / tipo de venda</label><select id='tarifa' name='tarifa_id' onchange='tarifaChanged()'>{''.join(opts)}</select></div><div><label>Comissão efetiva da venda (%)</label><input id='comissao' type='number' step='.01' min='0' name='comissao' required><small id='taxaAjuda' class='muted'></small></div><div><label>Tarifa fixa efetiva (R$)</label><input id='tarifaFixa' type='number' step='.01' min='0' name='tarifa_fixa' value='0'><small class='muted'>Informe quando a plataforma cobrar valor fixo para esta operação.</small></div><div><label>Modalidade de frete</label><select name='frete_tipo'><option>Frete por conta do comprador</option><option>Frete grátis / vendedor paga</option><option>Subsidiado / compartilhado</option></select></div><div><label>Custo do frete para vendedor (R$)</label><input type='number' step='.01' min='0' name='frete' value='0'></div><div><label>Outros custos (R$)</label><input type='number' step='.01' min='0' name='outros' value='0'></div><div><label>Ads (% da venda)</label><input type='number' step='.01' min='0' name='ads' value='0'></div><div><label>Margem líquida desejada (%)</label><input type='number' step='.01' min='0' name='margem' value='15'></div></div><br><button>Calcular preço de venda</button></form></div><div class='info'>As tarifas variáveis são confirmadas no momento da precificação. Isso evita aplicar uma taxa incorreta quando categoria, logística, forma de pagamento ou programa comercial alteram a cobrança.</div>'''
 script="""function tarifaChanged(){const s=document.getElementById('tarifa');const m=s.options[s.selectedIndex].dataset.meta.split('|');const min=m[0],max=m[1],ex=m[2],fix=m[3];const c=document.getElementById('comissao'),a=document.getElementById('taxaAjuda'),f=document.getElementById('tarifaFixa');if(ex!==''){c.value=ex;c.readOnly=true;a.textContent='Taxa exata cadastrada.';}else{c.readOnly=false;c.value='';a.textContent=min!==''?'Faixa oficial: '+min+'% a '+max+'%. Informe a taxa da sua categoria/operação.':'Tarifa dinâmica: informe a taxa exibida pela plataforma para esta operação.';}f.value=fix!==''?fix:0;} tarifaChanged();"""
 return page(body,script)

@app.post('/calcular',response_class=HTMLResponse)
def calcular(ncm:str=Form(...),uf_destino:str=Form(...),custo:float=Form(...),embalagem:float=Form(0),tarifa_id:int=Form(...),comissao:float=Form(...),tarifa_fixa:float=Form(0),frete_tipo:str=Form(...),frete:float=Form(0),outros:float=Form(0),ads:float=Form(0),margem:float=Form(15)):
 con=connect(); emp=con.execute('SELECT * FROM empresa WHERE id=1').fetchone(); tarifa=con.execute('SELECT t.*,m.nome marketplace_nome FROM tarifas_marketplace t JOIN marketplaces m ON m.codigo=t.marketplace WHERE t.id=?',(tarifa_id,)).fetchone(); con.close()
 if not tarifa: return page("<div class='warn'>Tarifa de marketplace inválida.</div>")
 if tarifa['comissao_min_pct'] is not None and not (tarifa['comissao_min_pct'] <= comissao <= tarifa['comissao_max_pct']): return page(f"<div class='warn'>A comissão informada ({comissao:.2f}%) está fora da faixa oficial cadastrada para {tarifa['nome']} ({tarifa['comissao_min_pct']:.2f}% a {tarifa['comissao_max_pct']:.2f}%).</div>")
 regras=contexto_fiscal(emp['regime'],emp['uf'],uf_destino,ncm,emp['receita_12m']); imposto=aliquota_efetiva_cadastrada(regras)
 r=calcular_preco(PricingInput(custo,embalagem,outros,frete,tarifa_fixa,imposto,comissao,ads,margem)); pendencia='' if regras else "<div class='warn'>Atenção: nenhuma regra fiscal validada foi encontrada. O imposto usado foi 0%; não use este resultado comercialmente até configurarmos a regra fiscal.</div>"
 return page(f'''<div class='card'><h1>Preço recomendado</h1><div class='result'>R$ {r['preco']:.2f}</div><p>{tarifa['marketplace_nome']} — {tarifa['nome']} | NCM: <b>{ncm}</b> | {emp['uf']} → {uf_destino}</p><p>Regime: <b>{emp['regime']}</b> | Impostos cadastrados: {imposto:.2f}% | Comissão: {comissao:.2f}% | Tarifa fixa: R$ {tarifa_fixa:.2f} | Ads: {ads:.2f}%</p><p>Custos fixos: R$ {r['custos_fixos']:.2f} | Impostos: R$ {r['imposto']:.2f} | Comissão: R$ {r['comissao']:.2f} | Lucro: <b>R$ {r['lucro']:.2f}</b></p><p>Margem líquida: <b>{r['margem_real']:.2f}%</b></p><a href='/precificar'>Nova precificação</a></div>{pendencia}''')
