# Milhas Facilitadas — coletor

Base de dados do app, a custo zero: promoções de transferência e compra de pontos, referência do milheiro, preço real em dinheiro e alertas no Telegram.

## O que cada parte faz

| Módulo | Faz | Fonte | Custo |
|---|---|---|---|
| `coletor/bonus.py` | Lê RSS dos blogs e extrai programa, origem, % de bônus, prazo e milheiro de compra | Passageiro de Primeira, Pontos pra Voar, Melhores Destinos | 0 |
| `coletor/run.py` | Vigia os sitemaps da Livelo e da Esfera e avisa quando aparece ou muda página de promoção | Sitemaps oficiais (1 pedido por site por rodada) | 0 |
| `coletor/milheiro.py` | Calcula o milheiro de cada programa: aquisição hoje, aquisição típica e preço de mercado | Promoções coletadas + `config.MERCADO` | 0 |
| `coletor/precos.py` | Preço real em dinheiro com cache de 6 h | fast-flights (Google Flights); SerpApi como reserva | 0 (250/mês na SerpApi) |
| `coletor/telegram.py` | Manda alerta de promoção ativa | Bot API do Telegram | 0 |

Saídas em `data/`: `promocoes.json`, `milheiro.json`, `cache_precos.json`.

## Como a referência do milheiro é calculada

```
milheiro do programa = custo de 1.000 pontos na origem ÷ (1 + bônus) ÷ paridade
```

- **Aquisição hoje:** usa o maior bônus **ativo**. Ex.: Livelo a R$ 30 com 100% de bônus para a Azul = R$ 15.
- **Aquisição típica:** usa a mediana dos bônus dos últimos 120 dias. Serve para quem pode esperar.
- **Custo da origem:** menor "milheiro a partir de R$ X" publicado nos últimos 60 dias; sem isso, o preço-alvo do `config.py`.
- **Mercado:** valor pago pelos balcões de venda de milhas, atualizado à mão em `config.MERCADO` com fonte e data.

Uma emissão vale a pena quando `(preço em dinheiro − taxas) ÷ milheiros` > aquisição típica.

## Regras de boa vizinhança do crawler

- Um pedido por domínio a cada 8 s; rodada a cada 2 h.
- `If-None-Match` / `If-Modified-Since`: se nada mudou, o site responde 304 e não manda conteúdo.
- Em 403, 429 ou 503 a rodada pula aquele site.
- User-agent identificado. Troque o e-mail em `config.USER_AGENT`.
- Nunca acessa área logada nem caminhos bloqueados no robots.txt.
- Leia os termos de uso de cada site antes de abrir o app ao público.

## Rodar no seu computador

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
python -m coletor.run --sem-alerta                 # coleta sem mandar Telegram
python -m coletor.precos REC EZE 2027-01-14        # preço real em dinheiro
```

## Colocar para rodar sozinho (grátis)

1. Crie um repositório **público** no GitHub e suba esta pasta. Em repositório público, o GitHub Actions não tem limite de minutos.
2. Crie o bot: no Telegram, fale com **@BotFather**, envie `/newbot` e guarde o token.
3. Crie um canal, adicione o bot como administrador e pegue o ID do canal (`@nome_do_canal` funciona).
4. No repositório: **Settings → Secrets and variables → Actions**. Crie `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID`.
5. Em **Actions**, rode o workflow `coletor` uma vez pelo botão **Run workflow**.

O workflow roda a cada 2 h, testa, coleta, manda os alertas e grava `data/` no próprio repositório. O front-end pode ler esses JSONs direto do GitHub Pages.
