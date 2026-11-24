"""Leitura dos grupos de milhas no Telegram com a conta do usuário (Telethon).

O que sai daqui:
- data/emissoes.json: alertas de passagem em milhas (rota, programa, custo, cabine, datas)
- data/mercado_auto.json: preço do milheiro no balcão, lido do resumo diário ou das ofertas
- promoções de transferência/compra: entram no mesmo promocoes.json do RSS

Só roda com os segredos TELEGRAM_API_ID, TELEGRAM_API_HASH e TELEGRAM_SESSION.
A sessão dá acesso à conta: nunca imprima nem grave esse valor.
"""
import asyncio
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from statistics import median

from . import bonus, config

PROG_ALIAS = {"smiles": "smiles", "latam": "latam", "latampass": "latam", "latam pass": "latam",
              "tudoazul": "azul", "tudo azul": "azul", "azul": "azul", "azul pelo mundo": "azul",
              "azul fidelidade": "azul", "iberia": "iberia", "ibéria": "iberia", "iberia club": "iberia",
              "tap": "tap", "qatar": "qatar", "qatar airways privilege club": "qatar", "all accor": "accor"}

RE_AEROPORTO = re.compile(r"([A-Za-zÀ-ÿ'. ]+?)\s*\(([A-Z]{3})(?:/[A-Z]{3})?\)")
RE_CAMPO = {
    "programa": re.compile(r"Programas?:\s*([^\n|]+)", re.I),
    "custo": re.compile(r"Custo:\s*([^\n|]+)", re.I),
    "trajeto": re.compile(r"Trajeto:\s*([^\n|]+)", re.I),
    "cabine": re.compile(r"Cabine:\s*([^\n|]+)", re.I),
    "companhia": re.compile(r"Companhia a[ée]rea:\s*([^\n|]+)", re.I),
}
RE_MILHAS = re.compile(r"(\d+(?:[.,]\d+)?)\s*[kK]")
RE_RESUMO = re.compile(r"(Latam|Smiles|Azul|Tap|Ib[eé]ria)\s*[—-]\s*R\$\s*(\d{1,3},\d{2})\s*por mil", re.I)
RE_OFERTA = re.compile(r"COMPRAR\s+[\d.]+\s+milhas\s+#([A-Za-zÀ-ÿ ]+?),.*?paga:\s*R\$\s*(\d{1,3}(?:[.,]\d{1,2})?)/K", re.I | re.S)


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def _programa(txt: str) -> str | None:
    t = _norm(txt.split(" e ")[0].split("(")[0])
    for k, v in sorted(PROG_ALIAS.items(), key=lambda kv: -len(kv[0])):
        if _norm(k) in t:
            return v
    return None


def ler_emissao(texto: str, quando: datetime, link: str) -> dict | None:
    """Alerta no formato 'Rota: X (AAA) Y (BBB) | Programa | Custo | Trajeto | Cabine | Datas'."""
    if "Rota" not in texto or "Custo" not in texto:
        return None
    linha_rota = texto[texto.index("Rota"):].split("\n")[0]
    aeros = RE_AEROPORTO.findall(linha_rota)
    if len(aeros) < 2:
        aeros = RE_AEROPORTO.findall(texto)[:2]
    if len(aeros) < 2:
        return None
    campos = {k: (m.group(1).strip() if (m := r.search(texto)) else None) for k, r in RE_CAMPO.items()}
    milhas = None
    if campos["custo"] and (m := RE_MILHAS.search(campos["custo"])):
        milhas = int(float(m.group(1).replace(",", ".")) * 1000)
    por_trecho = bool(campos["custo"] and re.search(r"trecho", campos["custo"], re.I))
    m = re.search(r"\bdatas?\b", texto, re.I)
    datas = re.sub(r"^datas?\s*:?\s*", "", texto[m.start():], flags=re.I).strip() if m else ""
    return {
        "id": link,
        "origem": {"cidade": aeros[0][0].strip(" :"), "iata": aeros[0][1]},
        "destino": {"cidade": aeros[1][0].strip(" :"), "iata": aeros[1][1]},
        "programa": _programa(campos["programa"] or ""),
        "programa_texto": campos["programa"],
        "companhia": campos["companhia"],
        "milhas": milhas,
        "por_trecho": por_trecho,
        "custo_texto": campos["custo"],
        "trajeto": campos["trajeto"],
        "cabine": (campos["cabine"] or "Econômica").strip(),
        "datas": datas[:600],
        "publicado": quando.isoformat(),
    }


def ler_resumo_balcao(texto: str) -> dict:
    """'Latam — R$ 24,81 por mil' → {'latam': 24.81, ...}"""
    out = {}
    for nome, valor in RE_RESUMO.findall(texto):
        prog = _programa(nome)
        if prog:
            out[prog] = float(valor.replace(",", "."))
    return out


def ler_oferta_balcao(texto: str) -> tuple[str, float] | None:
    if (m := RE_OFERTA.search(texto)) and (prog := _programa(m.group(1))):
        return prog, float(m.group(2).replace(",", "."))
    return None


def mercado_por_ofertas(ofertas: list[tuple[str, float]]) -> dict:
    por = {}
    for prog, v in ofertas:
        por.setdefault(prog, []).append(v)
    return {p: round(median(v), 2) for p, v in por.items() if len(v) >= 3}


async def _coletar(api_id: int, api_hash: str, sessao: str) -> dict:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    resultado = {"emissoes": [], "promos": [], "resumo": {}, "ofertas": []}
    async with TelegramClient(StringSession(sessao), api_id, api_hash) as cli:
        await cli.get_dialogs(limit=200)  # carrega os grupos na sessão para resolver os IDs
        for chat_id, nome in config.GRUPOS.items():
            try:
                msgs = await cli.get_messages(chat_id, limit=config.MENSAGENS_POR_GRUPO)
            except Exception as e:  # grupo saiu, sem acesso etc.
                print(f"[grupos] {nome}: {type(e).__name__}")
                continue
            for msg in msgs:
                texto = msg.message or ""
                if not texto:
                    continue
                quando = msg.date if msg.date.tzinfo else msg.date.replace(tzinfo=timezone.utc)
                link = f"tg://{abs(chat_id)}/{msg.id}"
                if (e := ler_emissao(texto, quando, link)):
                    resultado["emissoes"].append(e)
                elif "Resumo" in texto and "Balc" in texto and (r := ler_resumo_balcao(texto)):
                    if not resultado["resumo"] or quando.isoformat() > resultado["resumo"]["data"]:
                        resultado["resumo"] = {"valores": r, "data": quando.isoformat()}
                elif (o := ler_oferta_balcao(texto)):
                    resultado["ofertas"].append(o)
                else:
                    primeira = texto.strip().split("\n")[0][:300]
                    if (p := bonus.extrair(primeira, link, quando, "Comunidade")):
                        resultado["promos"].append(p)
            print(f"[grupos] {nome}: {len(msgs)} mensagens lidas")
    return resultado


def coletar() -> dict | None:
    api_id, api_hash, sessao = (os.environ.get(k) for k in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION"))
    if not (api_id and api_hash and sessao):
        print("[grupos] sem sessão do Telegram configurada; pulando os grupos")
        return None
    try:
        return asyncio.run(_coletar(int(api_id), api_hash, sessao))
    except Exception as e:
        print(f"[grupos] falha: {type(e).__name__}: {str(e)[:200]}")
        return None


def mesclar_emissoes(antigas: list[dict], novas: list[dict], dias: int = 45) -> list[dict]:
    por_id = {e["id"]: e for e in antigas}
    por_id.update({e["id"]: e for e in novas})
    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    return sorted((e for e in por_id.values() if e["publicado"] >= limite),
                  key=lambda e: e["publicado"], reverse=True)[:300]


def interessa(e: dict) -> bool:
    alvo = config.AEROPORTOS_INTERESSE
    return not alvo or e["origem"]["iata"] in alvo or e["destino"]["iata"] in alvo
