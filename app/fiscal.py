from .database import connect

def contexto_fiscal(regime,uf_origem,uf_destino,ncm,receita_12m=0):
    con=connect()
    rows=con.execute('''SELECT * FROM regras_fiscais WHERE ativo=1 AND regime=? AND (uf_origem IS NULL OR uf_origem=?) AND (uf_destino IS NULL OR uf_destino=?) ORDER BY LENGTH(COALESCE(ncm_prefixo,'')) DESC''',(regime,uf_origem,uf_destino)).fetchall(); con.close()
    return [dict(r) for r in rows if not r['ncm_prefixo'] or (ncm and ncm.startswith(r['ncm_prefixo']))]

def aliquota_efetiva_cadastrada(regras):
    tipos=("DAS","ICMS","DIFAL","FCP","PIS","COFINS","IRPJ","CSLL","IPI")
    return round(sum(float(r['aliquota'] or 0) for r in regras if r['tipo'] in tipos),4)
