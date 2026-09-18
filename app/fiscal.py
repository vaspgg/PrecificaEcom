from .database import connect

ANEXO_I_COMERCIO = [
    (180000.00, 4.00, 0.00),
    (360000.00, 7.30, 5940.00),
    (720000.00, 9.50, 13860.00),
    (1800000.00, 10.70, 22500.00),
    (3600000.00, 14.30, 87300.00),
    (4800000.00, 19.00, 378000.00),
]

def contexto_fiscal(regime,uf_origem,uf_destino,ncm,receita_12m=0):
    con=connect()
    rows=con.execute("""SELECT * FROM regras_fiscais WHERE ativo=1 AND regime=? AND (uf_origem IS NULL OR uf_origem=?) AND (uf_destino IS NULL OR uf_destino=?) ORDER BY LENGTH(COALESCE(ncm_prefixo,'')) DESC""",(regime,uf_origem,uf_destino)).fetchall(); con.close()
    return [dict(r) for r in rows if not r['ncm_prefixo'] or (ncm and ncm.startswith(r['ncm_prefixo']))]

def simples_comercio_aliquota_efetiva(receita_12m):
    r=float(receita_12m or 0)
    if r<=0:return None
    for limite,aliq,pd in ANEXO_I_COMERCIO:
        if r<=limite:return round(((r*(aliq/100.0)-pd)/r)*100.0,4)
    return None

def calcular_imposto(regime,regras,receita_12m=0):
    regime=(regime or '').upper()
    # MEI recolhe DAS em valor mensal fixo; não transformar automaticamente
    # esse valor em percentual por venda.
    if regime=='MEI':
        return None,'MEI: DAS mensal fixo; o imposto por venda não deve ser estimado como percentual sem critério de rateio.'
    if regime=='SIMPLES':
        a=simples_comercio_aliquota_efetiva(receita_12m)
        if a is not None:return a,'Simples Nacional: alíquota efetiva calculada pelo Anexo I (comércio) a partir da RBT12.'
        return None,'Simples Nacional: informe a Receita Bruta dos últimos 12 meses na tela Empresa para calcular a alíquota efetiva.'
    tipos=("DAS","ICMS","DIFAL","FCP","PIS","COFINS","IRPJ","CSLL","IPI")
    vals=[float(r['aliquota'] or 0) for r in regras if r['tipo'] in tipos and r['aliquota'] is not None]
    if vals:return round(sum(vals),4),'Alíquota obtida das regras fiscais cadastradas para o regime/UF/NCM.'
    # Baseline federal para comércio. Tributos estaduais e monofásicos/ST continuam
    # dependendo das regras por NCM/UF e não são inventados aqui.
    if regime=='PRESUMIDO':
        # PIS 0,65 + COFINS 3,00 + IRPJ (8% x 15%) + CSLL (12% x 9%)
        return 5.93,'Lucro Presumido/comércio: baseline federal estimado de 5,93% (PIS 0,65% + COFINS 3% + IRPJ 1,20% + CSLL 1,08%). ICMS/FCP/ST/DIFAL/IPI, adicional de IRPJ e regimes especiais dependem do produto/operação.'
    if regime=='REAL':
        # No Lucro Real IRPJ/CSLL incidem sobre lucro, não sobre faturamento.
        # PIS/COFINS são não cumulativos e possuem créditos; não é correto somar
        # 15%+9% ao preço de venda como se fossem tributos sobre receita.
        return 9.25,'Lucro Real: baseline bruto de PIS/COFINS 9,25% (1,65% + 7,6%), antes dos créditos. IRPJ/CSLL incidem sobre o lucro e ICMS/FCP/ST/DIFAL/IPI dependem da operação; ajuste com as regras fiscais cadastradas.'
    return None,'Não há regra fiscal validada cadastrada para esta combinação de regime, UF e NCM.'

def aliquota_efetiva_cadastrada(regras):
    tipos=("DAS","ICMS","DIFAL","FCP","PIS","COFINS","IRPJ","CSLL","IPI")
    return round(sum(float(r['aliquota'] or 0) for r in regras if r['tipo'] in tipos),4)
