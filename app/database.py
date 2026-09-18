from pathlib import Path
import os
import sqlite3

APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "PrecificaEcom"
DB = APP_DIR / "precifica.db"
ML_CLIENT_ID = "2683154375357518"
ML_REDIRECT_URI = "https://precificaecom-oauth.dsm-desing.workers.dev/mercadolivre/callback"

UFS = [("AC","Acre"),("AL","Alagoas"),("AP","Amapá"),("AM","Amazonas"),("BA","Bahia"),("CE","Ceará"),("DF","Distrito Federal"),("ES","Espírito Santo"),("GO","Goiás"),("MA","Maranhão"),("MT","Mato Grosso"),("MS","Mato Grosso do Sul"),("MG","Minas Gerais"),("PA","Pará"),("PB","Paraíba"),("PR","Paraná"),("PE","Pernambuco"),("PI","Piauí"),("RJ","Rio de Janeiro"),("RN","Rio Grande do Norte"),("RS","Rio Grande do Sul"),("RO","Rondônia"),("RR","Roraima"),("SC","Santa Catarina"),("SP","São Paulo"),("SE","Sergipe"),("TO","Tocantins")]
REGIMES = [("MEI","MEI"),("SIMPLES","Simples Nacional"),("PRESUMIDO","Lucro Presumido"),("REAL","Lucro Real")]
MARKETPLACE_RULES = [
    ("ML","CLASSICO","Anúncio Clássico",10.0,14.0,None,None,1,"A taxa final deve ser consultada na API por categoria, preço, anúncio e logística.","https://developers.mercadolivre.com.br/pt_br/comissao-por-vender","2026-09-17"),
    ("ML","PREMIUM","Anúncio Premium",15.0,19.0,None,None,1,"A taxa final deve ser consultada na API por categoria, preço, anúncio e logística.","https://developers.mercadolivre.com.br/pt_br/comissao-por-vender","2026-09-17"),
    ("SHOPEE","MARKETPLACE","Marketplace Shopee",None,None,None,None,1,"Tarifa dinâmica; manter confirmação da taxa efetiva da conta.","https://help.shopee.com.br/portal/4/article/77113","2026-09-17"),
    ("PROPRIO","DIRETA","Venda própria",0.0,0.0,0.0,0.0,0,"Sem tarifa de marketplace.","","2026-09-17"),
]

def connect():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; con.execute("PRAGMA foreign_keys=ON"); return con

def _add_column(con, table, column, definition):
    cols={r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols: con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def init_db():
    con=connect()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS estados(uf TEXT PRIMARY KEY,nome TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS regimes_tributarios(codigo TEXT PRIMARY KEY,nome TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS empresa(id INTEGER PRIMARY KEY CHECK(id=1),nome TEXT DEFAULT '',uf TEXT NOT NULL DEFAULT 'MG',regime TEXT NOT NULL DEFAULT 'SIMPLES',receita_12m REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS produtos(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT UNIQUE,descricao TEXT NOT NULL,ncm TEXT NOT NULL,cest TEXT,origem_mercadoria INTEGER DEFAULT 0,custo REAL NOT NULL DEFAULT 0,embalagem REAL NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS regras_fiscais(id INTEGER PRIMARY KEY AUTOINCREMENT,regime TEXT NOT NULL,uf_origem TEXT,uf_destino TEXT,ncm_prefixo TEXT,tipo TEXT NOT NULL,aliquota REAL,valor_fixo REAL DEFAULT 0,vigencia_inicio TEXT,vigencia_fim TEXT,fonte TEXT,observacao TEXT,ativo INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS faixas_simples(id INTEGER PRIMARY KEY AUTOINCREMENT,anexo TEXT NOT NULL,receita_de REAL NOT NULL,receita_ate REAL NOT NULL,aliquota_nominal REAL NOT NULL,parcela_deduzir REAL NOT NULL,vigencia_inicio TEXT,vigencia_fim TEXT);
    CREATE TABLE IF NOT EXISTS marketplaces(codigo TEXT PRIMARY KEY,nome TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tarifas_marketplace(id INTEGER PRIMARY KEY AUTOINCREMENT,marketplace TEXT NOT NULL,codigo TEXT NOT NULL,nome TEXT NOT NULL,comissao_min_pct REAL,comissao_max_pct REAL,comissao_exata_pct REAL,tarifa_fixa REAL,dinamica INTEGER NOT NULL DEFAULT 1,observacao TEXT,fonte_url TEXT,verificado_em TEXT,ativo INTEGER NOT NULL DEFAULT 1,UNIQUE(marketplace,codigo));
    CREATE TABLE IF NOT EXISTS marketplace_config(marketplace TEXT PRIMARY KEY,access_token TEXT DEFAULT '',refresh_token TEXT DEFAULT '',user_id TEXT DEFAULT '',updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS oauth_sessions(state TEXT PRIMARY KEY,marketplace TEXT NOT NULL,code_verifier TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS historico_precificacao(id INTEGER PRIMARY KEY AUTOINCREMENT,criado_em TEXT DEFAULT CURRENT_TIMESTAMP,produto_id INTEGER,regime TEXT,uf_origem TEXT,uf_destino TEXT,modalidade TEXT,custo_total REAL,impostos_pct REAL,comissao_pct REAL,tarifa_fixa REAL,frete REAL,ads_pct REAL,margem_pct REAL,preco_calculado REAL);
    ''')
    _add_column(con,"marketplace_config","client_id","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","client_secret","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","redirect_uri","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","token_expires_at","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","seller_nickname","TEXT DEFAULT ''")
    _add_column(con,"marketplace_config","seller_name","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","seller_document_type","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","seller_document","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","seller_state","TEXT DEFAULT ''"); _add_column(con,"marketplace_config","seller_city","TEXT DEFAULT ''")
    con.executemany("INSERT OR IGNORE INTO estados(uf,nome) VALUES(?,?)",UFS); con.executemany("INSERT OR IGNORE INTO regimes_tributarios(codigo,nome) VALUES(?,?)",REGIMES)
    con.execute("INSERT OR IGNORE INTO empresa(id,nome,uf,regime,receita_12m) VALUES(1,'','MG','SIMPLES',0)"); con.executemany("INSERT OR IGNORE INTO marketplaces(codigo,nome) VALUES(?,?)",[("ML","Mercado Livre"),("SHOPEE","Shopee"),("PROPRIO","Venda própria")])
    con.execute("INSERT OR IGNORE INTO marketplace_config(marketplace,client_id,redirect_uri) VALUES('ML',?,?)",(ML_CLIENT_ID,ML_REDIRECT_URI)); con.execute("UPDATE marketplace_config SET client_id=?,redirect_uri=? WHERE marketplace='ML'",(ML_CLIENT_ID,ML_REDIRECT_URI))
    con.executemany('''INSERT INTO tarifas_marketplace(marketplace,codigo,nome,comissao_min_pct,comissao_max_pct,comissao_exata_pct,tarifa_fixa,dinamica,observacao,fonte_url,verificado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(marketplace,codigo) DO UPDATE SET nome=excluded.nome,comissao_min_pct=excluded.comissao_min_pct,comissao_max_pct=excluded.comissao_max_pct,comissao_exata_pct=excluded.comissao_exata_pct,tarifa_fixa=excluded.tarifa_fixa,dinamica=excluded.dinamica,observacao=excluded.observacao,fonte_url=excluded.fonte_url,verificado_em=excluded.verificado_em''', MARKETPLACE_RULES)
    con.commit(); con.close()
