"""Configuração central do coletor. Tudo aqui é editável sem mexer no código."""

USER_AGENT = (
    "MilhasFacilitadasBot/0.1 (+monitor de promocoes; contato: defina-seu-email@exemplo.com)"
)

# Intervalo mínimo entre requisições ao MESMO domínio (segundos).
INTERVALO_POR_DOMINIO = 8
TIMEOUT = 20

# 1ª camada: RSS dos blogs (leve, publicado em minutos após a promoção).
FEEDS = {
    "Passageiro de Primeira": "https://passageirodeprimeira.com/feed/",
    "Pontos pra Voar": "https://pontospravoar.com/feed/",
    "Melhores Destinos": "https://www.melhoresdestinos.com.br/feed",
}

# 2ª camada: sitemaps oficiais (1 requisição por site por rodada).
# Só lemos o sitemap; páginas listadas em robots.txt como Disallow nunca são acessadas.
SITEMAPS = {
    "Livelo": "https://www.livelo.com.br/sitemap/sitemap.xml",
    "Esfera": "https://www.esfera.com.vc/sitemap.xml",
}
PALAVRAS_SITEMAP = ("promo", "bonus", "bônus", "transfer", "campanha", "oferta")

# Programas de destino (milhas) e como aparecem nos títulos.
PROGRAMAS = {
    "smiles": ["smiles"],
    "azul": ["azul fidelidade", "tudoazul", "azul pelo mundo", "azul"],
    "latam": ["latam pass", "latam"],
    "accor": ["all accor", "accor"],
    "qatar": ["qatar", "privilege club"],
    "iberia": ["iberia club", "iberia plus", "iberia", "avios"],
    "tap": ["tap", "miles&go"],
}

# Origens de pontos (bancos/programas de cartão).
ORIGENS = {
    "livelo": ["livelo"],
    "esfera": ["esfera"],
    "c6": ["c6"],
    "inter": ["inter loop", "inter"],
    "premmia": ["premmia"],
    "kmv": ["km de vantagens", "kmv"],
    "bradesco": ["bradesco"],
    "caixa": ["caixa"],
    "porto": ["porto bank", "porto"],
    "xp": ["xp"],
    "btg": ["btg"],
    "itau": ["itaú", "itau"],
    "bb": ["banco do brasil", "bb"],
    "todos": ["todos os parceiros", "parceiros", "bancos"],
}

# Custo-alvo de aquisição de 1.000 pontos na ORIGEM (R$). Referência pública:
# Melhores Destinos e Melhores Cartões trabalham com preço-alvo de R$ 30 para a Livelo em 2026.
# O coletor sobrescreve com o menor "milheiro a partir de R$ X" visto nos últimos 60 dias.
CUSTO_ORIGEM_PADRAO = {"livelo": 30.0, "esfera": 30.0}

# Preço de mercado (o que os balcões de compra pagam pelo milheiro), atualizado à mão com data e fonte.
# Fonte: ofertas no balcão de milhas da comunidade VCM (Telegram) em 24/11/2026;
# o resumo diário do balcão de 26/09/2026 mostrava faixas parecidas (LATAM 24-25, Smiles 15-16, Azul 13-14).
MERCADO = {
    "iberia": {"valor": 50.0, "fonte": "Resumo do balcão (VCM), faixa 42-58", "data": "2026-09-26"},
    "smiles": {"valor": 15.5, "fonte": "Balcão de milhas (VCM)", "data": "2026-11-24"},
    "azul": {"valor": 13.0, "fonte": "Balcão de milhas (VCM)", "data": "2026-11-24"},
    "latam": {"valor": 24.0, "fonte": "Balcão de milhas (VCM)", "data": "2026-11-24"},
}

# Quais origens transferem para qual programa e quantas milhas chegam por ponto enviado.
# Aéreos nacionais: 1:1. Iberia (Avios): Esfera 2:1 (mínimo 15 mil) e Livelo 3,5:1.
TRANSFERENCIAS = {
    "smiles": {"livelo": 1.0, "esfera": 1.0},
    "azul": {"livelo": 1.0, "esfera": 1.0},
    "latam": {"livelo": 1.0, "esfera": 1.0},
    "iberia": {"livelo": 1 / 3.5, "esfera": 0.5},
}

# ---- Leitura dos grupos do Telegram (conta do usuário, via Telethon) ----
# Só roda se TELEGRAM_API_ID, TELEGRAM_API_HASH e TELEGRAM_SESSION existirem nos segredos.
GRUPOS = {
    -1001779153745: "AVDM - Alertas",          # emissões nacionais, internacionais, executiva, promoções
    -1001449628221: "VCM - Alertas Promo",     # promoções e resumo diário do balcão
    -1002500984698: "VCM - Resumo",
    -1001502516880: "VCM - Balcão de Milhas",  # ofertas de compra de milhas (preço de mercado)
}
MENSAGENS_POR_GRUPO = 80

# Alertas de passagem que vão para o Telegram do usuário: rotas que tocam estes aeroportos.
# Vazio = todas. O site mostra todas, com filtro.
AEROPORTOS_INTERESSE = ["REC"]
