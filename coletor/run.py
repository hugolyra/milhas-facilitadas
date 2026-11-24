"""Uma rodada do coletor: RSS -> promoções -> referência do milheiro -> sitemaps -> alertas.

Uso: python -m coletor.run [--sem-sitemap] [--sem-alerta]
Grava em data/: promocoes.json, milheiro.json, sitemap_estado.json, notificados.json
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from . import bonus, config, http, milheiro, telegram

DATA = Path(__file__).resolve().parent.parent / "data"


def _ler(nome, padrao):
    try:
        return json.loads((DATA / nome).read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def _gravar(nome, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / nome).write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")


def coletar_rss(acumulado: dict) -> int:
    novos = 0
    for fonte, url in config.FEEDS.items():
        xml = http.baixar(url)
        if not xml:
            continue
        try:
            for p in bonus.ler_rss(xml, fonte):
                if p["id"] not in acumulado:
                    novos += 1
                acumulado[p["id"]] = p
        except ET.ParseError as e:
            print(f"[erro] RSS inválido em {fonte}: {e}")
    return novos


def vigiar_sitemaps(estado: dict) -> list[str]:
    """Devolve URLs de promoção novas ou alteradas nos sitemaps oficiais."""
    mudou = []
    for site, url in config.SITEMAPS.items():
        xml = http.baixar(url)
        if not xml:
            continue
        for loc, lastmod in re.findall(r"<loc>(.*?)</loc>\s*(?:<lastmod>(.*?)</lastmod>)?", xml):
            if not any(k in loc.lower() for k in config.PALAVRAS_SITEMAP):
                continue
            if estado.get(loc) != lastmod:
                if loc in estado or lastmod:
                    mudou.append(f"{site}: {loc}")
                estado[loc] = lastmod
    return mudou


def main(argv=None):
    argv = argv or sys.argv[1:]
    hoje = date.today()
    promos = _ler("promocoes.json", {})
    print(f"novas promoções no RSS: {coletar_rss(promos)}")
    bonus.completar(list(promos.values()))
    for p in promos.values():
        p["status"] = bonus.status(p, hoje)
    _gravar("promocoes.json", promos)

    ref = milheiro.referencias(list(promos.values()), hoje)
    _gravar("milheiro.json", ref)

    sm = []
    if "--sem-sitemap" not in argv:
        estado = _ler("sitemap_estado.json", {})
        sm = vigiar_sitemaps(estado)
        _gravar("sitemap_estado.json", estado)

    if "--sem-alerta" not in argv:
        enviados = set(_ler("notificados.json", []))
        for p in promos.values():
            if p["status"] in bonus.VIGENTES and p["programa"] and p["id"] not in enviados:
                telegram.enviar(telegram.formatar(p, ref))
                enviados.add(p["id"])
        for linha in sm[:5]:
            telegram.enviar(f"📄 Página oficial nova/alterada\n{linha}")
        _gravar("notificados.json", sorted(enviados))


if __name__ == "__main__":
    main()
