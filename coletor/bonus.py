"""Lê os RSS dos blogs e extrai promoções de transferência bonificada e de compra de pontos."""
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from . import config

MESES = {m: i for i, m in enumerate(
    "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro".split(), 1)}

RE_BONUS = re.compile(r"(\d{1,3})\s?%\s*(?:de\s+)?b[oô]nus", re.I)
RE_DESCONTO = re.compile(r"(\d{1,3})\s?%\s*(?:de\s+)?(?:desconto|off)", re.I)
RE_MILHEIRO = re.compile(
    r"milheiro\s+(?:a\s+partir\s+de|por|de)?\s*R\$\s?(\d{1,3}(?:,\d{1,2})?)"
    r"|R\$\s?(\d{1,3}(?:,\d{1,2})?)\s+(?:o|por)\s+milheiro", re.I)
RE_ATE_DATA = re.compile(
    r"at[eé]\s+(?:[a-zçáéíóú-]+,?\s+)?(?:o\s+)?(?:dia\s+)?(\d{1,2})(?![\d%])(?!\s?%)"
    r"(?:/(\d{1,2}))?(?:\s+de\s+([a-zç]+))?", re.I)
RE_CPM = re.compile(r"CPM\s+(?:a\s+partir\s+de|de|por)?\s*R\$\s?(\d{1,3}(?:,\d{1,2})?)", re.I)
RE_ATE_HOJE = re.compile(r"at[eé]\s+hoje|s[oó]\s+hoje|termina(?:m)?\s+hoje|[uú]ltimo\s+dia|[uú]ltimas\s+horas", re.I)


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _achar(texto: str, tabela: dict[str, list[str]]) -> str | None:
    t = _sem_acento(texto)
    for chave, nomes in tabela.items():
        if any(re.search(r"(?<!\w)" + re.escape(_sem_acento(n).strip()) + r"(?!\w)", t) for n in nomes):
            return chave
    return None


def _prazo(texto: str, publicado: date) -> date | None:
    if RE_ATE_HOJE.search(texto):
        return publicado
    m = RE_ATE_DATA.search(texto)
    if not m:
        return None
    dia, mes_num, mes_nome = m.groups()
    mes = int(mes_num) if mes_num else MESES.get(_sem_acento(mes_nome or ""), publicado.month)
    ano = publicado.year + (1 if mes < publicado.month else 0)
    try:
        return date(ano, mes, int(dia))
    except ValueError:
        return None


def extrair(titulo: str, link: str, publicado: datetime, fonte: str) -> dict | None:
    """Transforma um post em promoção estruturada; None se não for promoção relevante."""
    t = titulo.replace("\xa0", " ")
    tipo = None
    percentual = None
    if (m := RE_BONUS.search(t)) and re.search(r"transfer", t, re.I):
        tipo, percentual = "transferencia", int(m.group(1))
    elif (m := RE_DESCONTO.search(t)) and re.search(r"compra\s+de\s+(pontos|milhas)", t, re.I):
        tipo, percentual = "compra", int(m.group(1))
    elif re.search(r"compr\w+\s+(pontos|milhas)", t, re.I) and RE_MILHEIRO.search(t):
        tipo = "compra"
    if not tipo:
        return None

    # Em "X oferece bônus nas transferências da Livelo", o 1º nome é o programa de destino.
    programa = _achar(t, config.PROGRAMAS)
    origem = _achar(t, config.ORIGENS)
    if tipo == "compra":
        programa = programa if not origem else origem  # compra de pontos Livelo/Esfera
    milheiro = RE_MILHEIRO.search(t)
    return {
        "id": link,
        "tipo": tipo,
        "programa": programa,
        "origem": (origem or "todos") if tipo == "transferencia" else None,
        "percentual": percentual,
        "milheiro": float((milheiro.group(1) or milheiro.group(2)).replace(",", ".")) if milheiro else None,
        "cpm": float(c.group(1).replace(",", ".")) if (c := RE_CPM.search(t)) else None,
        "prazo": (p.isoformat() if (p := _prazo(t, publicado.date())) else None),
        "publicado": publicado.isoformat(),
        "titulo": t,
        "link": link,
        "fonte": fonte,
    }


def ler_rss(xml: str, fonte: str) -> list[dict]:
    saida = []
    raiz = ET.fromstring(xml)
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        try:
            pub = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            pub = datetime.now()
        if promo := extrair(titulo, link, pub, fonte):
            saida.append(promo)
    return saida


DIAS_PROVAVEL = 3  # promoção sem prazo no título costuma durar poucos dias


def status(promo: dict, hoje: date) -> str:
    """ativa | provavel (sem prazo, publicada há até 3 dias) | verificar | encerrada"""
    if not promo.get("prazo"):
        pub = datetime.fromisoformat(promo["publicado"]).date()
        return "provavel" if (hoje - pub).days <= DIAS_PROVAVEL else "verificar"
    return "ativa" if date.fromisoformat(promo["prazo"]) >= hoje else "encerrada"


VIGENTES = ("ativa", "provavel")


def completar(promos: list[dict]) -> None:
    """Títulos como "Últimas horas para ganhar 27% ... Livelo" não citam o programa:
    herda de outra promoção com a mesma origem e o mesmo % publicada até 3 dias antes ou depois."""
    for p in promos:
        if p["programa"]:
            continue
        t = datetime.fromisoformat(p["publicado"])
        for q in promos:
            if (q is not p and q["programa"] and q["tipo"] == p["tipo"] and q["origem"] == p["origem"]
                    and q["percentual"] == p["percentual"]
                    and abs((datetime.fromisoformat(q["publicado"]) - t).days) <= DIAS_PROVAVEL):
                p["programa"] = q["programa"]
                break
