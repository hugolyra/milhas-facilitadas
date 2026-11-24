"""Referência do milheiro: três números por programa, cada um com fonte e data.

- aquisicao: quanto custa produzir 1.000 milhas hoje = custo da origem / (1 + bônus) / paridade
- aquisicao_tipica: o mesmo usando a mediana dos bônus vistos nos últimos 120 dias (para quem pode esperar)
- mercado: quanto os balcões pagam (liquidez), atualizado manualmente em config.MERCADO
Uma emissão é "boa" quando o valor obtido por milheiro supera a aquisição típica.
"""
from datetime import date, datetime, timedelta
from statistics import median

from . import config
from .bonus import status


def custo_origem(promos: list[dict], hoje: date) -> dict[str, dict]:
    """Menor milheiro de compra visto nos últimos 60 dias por origem; senão o padrão do config."""
    saida = {k: {"valor": v, "fonte": "preço-alvo 2026 (config)", "data": None}
             for k, v in config.CUSTO_ORIGEM_PADRAO.items()}
    limite = hoje - timedelta(days=60)
    for p in promos:
        if p["tipo"] != "compra" or not p.get("milheiro") or p.get("programa") not in saida:
            continue
        quando = datetime.fromisoformat(p["publicado"]).date()
        if quando >= limite and p["milheiro"] < saida[p["programa"]]["valor"]:
            saida[p["programa"]] = {"valor": p["milheiro"], "fonte": p["link"], "data": quando.isoformat()}
    return saida


def _bonus(promos, programa, origem, hoje, dias=None, so_ativas=False):
    vals = []
    for p in promos:
        if p["tipo"] != "transferencia" or p["programa"] != programa or p["percentual"] is None:
            continue
        if p["origem"] not in (origem, "todos"):
            continue
        if so_ativas and status(p, hoje) != "ativa":
            continue
        if dias and datetime.fromisoformat(p["publicado"]).date() < hoje - timedelta(days=dias):
            continue
        vals.append(p["percentual"])
    return vals


def referencias(promos: list[dict], hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    origem = custo_origem(promos, hoje)
    saida = {}
    for prog, rotas in config.TRANSFERENCIAS.items():
        melhor_agora, melhor_tipica = None, None
        for org, paridade in rotas.items():
            base = origem[org]["valor"]
            ativos = _bonus(promos, prog, org, hoje, so_ativas=True)
            hist = _bonus(promos, prog, org, hoje, dias=120)
            agora = base / (1 + max(ativos, default=0) / 100) / paridade
            tipica = base / (1 + (median(hist) if hist else 0) / 100) / paridade
            if melhor_agora is None or agora < melhor_agora[0]:
                melhor_agora = (agora, org, max(ativos, default=0))
            if melhor_tipica is None or tipica < melhor_tipica[0]:
                melhor_tipica = (tipica, org, median(hist) if hist else 0)
        # CPM já calculado pelos blogs para promoções ativas deste programa (ex.: "CPM a partir de R$ 15,32")
        cpms = [(p["cpm"], p["origem"], p["percentual"]) for p in promos
                if p.get("cpm") and p["programa"] == prog and status(p, hoje) != "encerrada"]
        if cpms and min(cpms)[0] < melhor_agora[0]:
            melhor_agora = min(cpms)
        saida[prog] = {
            "aquisicao": {"valor": round(melhor_agora[0], 2), "via": melhor_agora[1], "bonus": melhor_agora[2]},
            "aquisicao_tipica": {"valor": round(melhor_tipica[0], 2), "via": melhor_tipica[1],
                                 "bonus_mediano": melhor_tipica[2]},
            "mercado": config.MERCADO.get(prog),
        }
    return {"gerado_em": hoje.isoformat(), "custo_origem": origem, "programas": saida}


def avaliar_emissao(preco_dinheiro: float, taxas: float, milhas: int, ref_milheiro: float) -> dict:
    """Quanto cada milheiro 'rende' nesta emissão e se vale a pena."""
    rende = (preco_dinheiro - taxas) / (milhas / 1000)
    return {"rende_por_milheiro": round(rende, 2), "referencia": ref_milheiro,
            "vale_a_pena": rende > ref_milheiro}
