from .database import connect
from datetime import date

ANEXO_I_COMERCIO=[
 (180000.00,4.00,0.00,34.00),(360000.00,7.30,5940.00,34.00),
 (720000.00,9.50,13860.00,33.50),(1800000.00,10.70,22500.00,33.50),
 (3600000.00,14.30,87300.00,33.50),(4800000.00,19.00,378000.00,0.00)]
SUL_SUDESTE={'MG','SP','RJ','PR','SC','RS','ES'}
NORTE_NE_CO_ES={'AC','AL','AP','AM','BA','CE','DF','GO','MA','MT','MS','PA','PB','PE','PI','RN','RO','RR','SE','TO','ES'}

def contexto_fiscal(regime,uf_origem,uf_destino,ncm,receita_12m=0):
 con=connect();rows=con.execute("""SELECT * FROM regras_fiscais WHERE ativo=1 AND regime=? AND (uf_origem IS NULL OR uf_origem=?) AND (uf_destino IS NULL OR uf_destino=?) ORDER BY LENGTH(COALESCE(ncm_prefixo,'')) DESC""",(regime,uf_origem,uf_destino)).fetchall();con.close()
 return [dict(r) for r in rows if not r['ncm_prefixo'] or (ncm and ncm.startswith(r['ncm_prefixo']))]

def simples_comercio_detalhe(rbt12):
 r=float(rbt12 or 0)
 if r<=0:return None
 for limite,nom,pd,icms_share in ANEXO_I_COMERCIO:
  if r<=limite:
   efet=((r*nom/100-pd)/r)*100
   return {'total_pct':round(efet,4),'icms_das_pct':round(efet*icms_share/100,4),'federal_cpp_pct':round(efet*(100-icms_share)/100,4),'faixa_limite':limite}
 return None

def aliquota_interestadual(uf_o,uf_d,origem_mercadoria=0):
 if uf_o==uf_d:return None
 # Mercadoria importada/conteúdo importação >40% exige regra específica de origem.
 if str(origem_mercadoria) in ('1','2','3','8'):return 4.0
 if uf_o in SUL_SUDESTE and uf_d in NORTE_NE_CO_ES:return 7.0
 return 12.0

def _regras_por_tipo(regras):
 d={}
 for r in regras:
  if r.get('aliquota') is not None:d.setdefault(r['tipo'],[]).append(float(r['aliquota']))
 return {k:sum(v) for k,v in d.items()}

def calcular_imposto(regime,regras,receita_12m=0,uf_origem='',uf_destino='',ncm='',origem_mercadoria=0,consumidor_final=True,contribuinte_icms=False,aliquota_interna_destino=None,fcp_destino=None):
 regime=(regime or '').upper();rt=_regras_por_tipo(regras);partes={};avisos=[]
 if regime=='MEI':
  return None,'MEI: DAS mensal fixo. Cadastre um critério de rateio para incorporar o DAS ao custo por venda.',partes
 if regime=='SIMPLES':
  s=simples_comercio_detalhe(receita_12m)
  if not s:return None,'Simples Nacional: informe a RBT12 na tela Empresa.',partes
  partes['DAS']=s['total_pct']
  # DIFAL/FCP/ST podem existir fora do DAS conforme operação; só somar quando houver regra cadastrada.
  for t in ('DIFAL','FCP','ICMS_ST','IPI'):
   if t in rt:partes[t]=rt[t]
  total=sum(partes.values())
  return round(total,4),'Simples/Anexo I: DAS efetivo pela RBT12; tributos fora do DAS somente quando há regra específica cadastrada.',partes

 # Regimes normais: regras específicas prevalecem; baseline federal é separado.
 if regime=='PRESUMIDO':
  partes.update({'PIS':0.65,'COFINS':3.0,'IRPJ':1.20,'CSLL':1.08})
  avisos.append('IRPJ sem adicional; em 2026 há mudanças nos percentuais de presunção para receitas acima dos limites legais, que exigem apuração do período.')
 elif regime=='REAL':
  partes.update({'PIS':1.65,'COFINS':7.60})
  avisos.append('PIS/COFINS mostrados antes dos créditos. IRPJ/CSLL do Lucro Real dependem do lucro ajustado e não são tratados como percentual da venda.')
 for t,v in rt.items():
  if t in ('PIS','COFINS','IRPJ','CSLL','ICMS','DIFAL','FCP','ICMS_ST','IPI'):partes[t]=v

 # ICMS interestadual só é estimado quando não existe regra específica.
 if 'ICMS' not in partes and uf_origem and uf_destino:
  ai=aliquota_interestadual(uf_origem,uf_destino,origem_mercadoria)
  if ai is not None:partes['ICMS']=ai;avisos.append('ICMS interestadual estimado pela UF/origem da mercadoria; confirme benefícios, ST e exceções do NCM.')
 # DIFAL requer alíquota interna de destino confiável.
 if consumidor_final and not contribuinte_icms and uf_origem!=uf_destino and 'DIFAL' not in partes and aliquota_interna_destino is not None:
  ai=aliquota_interestadual(uf_origem,uf_destino,origem_mercadoria) or 0
  partes['DIFAL']=max(0,float(aliquota_interna_destino)-ai)
 if fcp_destino is not None and uf_origem!=uf_destino:partes.setdefault('FCP',float(fcp_destino))
 total=sum(partes.values())
 msg='Componentes: '+', '.join(f'{k} {v:.2f}%' for k,v in partes.items())+'.'
 if avisos:msg+=' '+' '.join(avisos)
 return round(total,4),msg,partes

def rtc_2026_info(regime):
 if (regime or '').upper()=='SIMPLES':return 'RTC 2026: alíquotas-teste de CBS/IBS não são adicionadas ao preço do Simples neste cálculo.'
 return 'RTC 2026: CBS 0,9% + IBS 0,1% são informativos/compensáveis; não são somados novamente ao custo tributário para evitar dupla contagem em 2026.'

def aliquota_efetiva_cadastrada(regras):
 return round(sum(float(r['aliquota'] or 0) for r in regras if r['tipo'] in ('DAS','ICMS','DIFAL','FCP','PIS','COFINS','IRPJ','CSLL','IPI','ICMS_ST')),4)


class FiscalProvider:
 name='interno'
 def calcular(self,**kwargs):
  regras=contexto_fiscal(kwargs.get('regime',''),kwargs.get('uf_origem',''),kwargs.get('uf_destino',''),kwargs.get('ncm',''),kwargs.get('receita_12m',0))
  imposto,nota,partes=calcular_imposto(kwargs.get('regime',''),regras,kwargs.get('receita_12m',0),kwargs.get('uf_origem',''),kwargs.get('uf_destino',''),kwargs.get('ncm',''),kwargs.get('origem_mercadoria',0),kwargs.get('consumidor_final',True),kwargs.get('contribuinte_icms',False))
  return {'provider':self.name,'imposto_pct':imposto,'nota':nota,'partes':partes,'rtc':rtc_2026_info(kwargs.get('regime',''))}

class RFBLocalProvider:
 name='rfb_local'
 def __init__(self,base_url='http://localhost:8080/api'):self.base_url=base_url.rstrip('/')
 def disponivel(self):
  import json,urllib.request
  try:
   with urllib.request.urlopen(self.base_url+'/calculadora/dados-abertos/versao',timeout=1.2) as r:
    return 200<=r.status<300
  except Exception:return False
 def versao(self):
  import json,urllib.request
  with urllib.request.urlopen(self.base_url+'/calculadora/dados-abertos/versao',timeout=3) as r:return json.loads(r.read().decode('utf-8'))

def fiscal_provider_status():
 r=RFBLocalProvider()
 if r.disponivel():
  try:return {'provider':'rfb_local','online':True,'versao':r.versao()}
  except Exception:return {'provider':'rfb_local','online':True,'versao':{}}
 return {'provider':'interno','online':False,'versao':{}}

def calcular_fiscal_hibrido(**kwargs):
 interno=FiscalProvider().calcular(**kwargs)
 status=fiscal_provider_status()
 interno['rfb_local_disponivel']=status['online'];interno['rfb_versao']=status['versao']
 # A RFB não oferece API pública online para cálculo em ERP. Quando o componente
 # oficial local estiver ativo, esta camada o detecta. O payload de regime-geral
 # será habilitado somente com os campos fiscais obrigatórios completos (cClassTrib,
 # CST, município/local da operação etc.), evitando enviar uma simulação inválida.
 if status['online']:
  interno['nota_rfb']='Calculadora oficial RFB local detectada. Dados abertos/versionamento disponíveis; cálculo RTC será ativado quando a operação tiver a classificação tributária completa.'
 else:
  interno['nota_rfb']='Calculadora oficial RFB local não detectada; usando motor fiscal interno. Instalação oficial expõe a API em localhost:8080/api.'
 return interno
