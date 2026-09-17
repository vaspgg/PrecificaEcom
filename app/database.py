from pathlib import Path
import os
import sqlite3

APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "PrecificaEcom"
DB = APP_DIR / "precifica.db"

UFS = [("AC","Acre"),("AL","Alagoas"),("AP","Amapá"),("AM","Amazonas"),("BA","Bahia"),("CE","Ceará"),("DF","Distrito Federal"),("ES","Espírito Santo"),("GO","Goiás"),("MA","Maranhão"),("MT","Mato Grosso"),("MS","Mato Grosso do Sul"),("MG","Minas Gerais"),("PA","Pará"),("PB","Paraíba"),("PR","Paraná"),("PE","Pernambuco"),("PI","Piauí"),("RJ","Rio de Janeiro"),("RN","Rio Grande do Norte"),("RS","Rio Grande do Sul"),("RO","Rondônia"),("RR","Roraima"),("SC","Santa Catarina"),("SP","São Paulo"),("SE","Sergipe"),("TO","Tocantins")]
REGIMES = [("MEI","MEI"),("SIMPLES","Simples Nacional"),("PRESUMIDO","Lucro Presumido"),("REAL","Lucro Real")]

def connect():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row; con.execute("PRAGMA foreign_keys=ON"); return con

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
    CREATE TABLE IF NOT EXISTS modalidades_venda(id INTEGER PRIMARY KEY AUTOINCREMENT,marketplace TEXT NOT NULL,nome TEXT NOT NULL,comissao_pct REAL NOT NULL DEFAULT 0,tarifa_fixa REAL NOT NULL DEFAULT 0,ativo INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS historico_precificacao(id INTEGER PRIMARY KEY AUTOINCREMENT,criado_em TEXT DEFAULT CURRENT_TIMESTAMP,produto_id INTEGER,regime TEXT,uf_origem TEXT,uf_destino TEXT,modalidade TEXT,custo_total REAL,impostos_pct REAL,comissao_pct REAL,tarifa_fixa REAL,frete REAL,ads_pct REAL,margem_pct REAL,preco_calculado REAL);
    ''')
    con.executemany("INSERT OR IGNORE INTO estados(uf,nome) VALUES(?,?)",UFS)
    con.executemany("INSERT OR IGNORE INTO regimes_tributarios(codigo,nome) VALUES(?,?)",REGIMES)
    con.execute("INSERT OR IGNORE INTO empresa(id,nome,uf,regime,receita_12m) VALUES(1,'','MG','SIMPLES',0)")
    con.executemany("INSERT OR IGNORE INTO marketplaces(codigo,nome) VALUES(?,?)",[("ML","Mercado Livre"),("SHOPEE","Shopee"),("PROPRIO","Venda própria")])
    if con.execute("SELECT COUNT(*) c FROM modalidades_venda").fetchone()["c"]==0:
        con.executemany("INSERT INTO modalidades_venda(marketplace,nome,comissao_pct,tarifa_fixa) VALUES(?,?,?,?)",[("ML","Mercado Livre - configurar taxa",0,0),("SHOPEE","Shopee - configurar taxa",0,0),("PROPRIO","Venda própria",0,0)])
    con.commit(); con.close()
