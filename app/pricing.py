from dataclasses import dataclass

@dataclass
class PricingInput:
    custo_produto: float
    embalagem: float
    outros_custos: float
    frete_vendedor: float
    tarifa_fixa: float
    imposto_pct: float
    comissao_pct: float
    ads_pct: float
    margem_desejada_pct: float

def calcular_preco(i: PricingInput):
    custos_fixos=i.custo_produto+i.embalagem+i.outros_custos+i.frete_vendedor+i.tarifa_fixa
    variaveis=(i.imposto_pct+i.comissao_pct+i.ads_pct+i.margem_desejada_pct)/100
    if variaveis>=1: raise ValueError("A soma de impostos, comissão, Ads e margem deve ser menor que 100%.")
    preco=custos_fixos/(1-variaveis)
    imposto=preco*i.imposto_pct/100; comissao=preco*i.comissao_pct/100; ads=preco*i.ads_pct/100
    lucro=preco-custos_fixos-imposto-comissao-ads
    return {"preco":round(preco,2),"custos_fixos":round(custos_fixos,2),"imposto":round(imposto,2),"comissao":round(comissao,2),"ads":round(ads,2),"lucro":round(lucro,2),"margem_real":round(lucro/preco*100 if preco else 0,2)}
