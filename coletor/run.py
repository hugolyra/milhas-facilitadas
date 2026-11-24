"""Uma rodada do coletor: RSS -> promoções -> referência do milheiro -> sitemaps -> alertas.

Uso: python -m coletor.run [--sem-sitemap] [--sem-alerta]
Grava em data/: promocoes.json, milheiro.json, sitemap_estado.json, notificados.json
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from . import bonus, config, grupos, http, milheiro, telegram

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

    # Grupos do Telegram (só com a sessão configurada)
    emissoes = _ler("emissoes.json", [])
    mercado_auto = _ler("mercado_auto.json", {})
    novas_emissoes = []
    if "--sem-grupos" not in argv and (g := grupos.coletar()):
        for p in g["promos"]:
            promos.setdefault(p["id"], p)
        ids = {e["id"] for e in emissoes}
        novas_emissoes = [e for e in g["emissoes"] if e["id"] not in ids]
        emissoes = grupos.mesclar_emissoes(emissoes, g["emissoes"])
        if g["resumo"]:
            for prog, v in g["resumo"]["valores"].items():
                mercado_auto[prog] = {"valor": v, "fonte": "Resumo diário do balcão de milhas",
                                      "data": g["resumo"]["data"][:10]}
        for prog, v in grupos.mercado_por_ofertas(g["ofertas"]).items():
            if prog not in (g["resumo"] or {}).get("valores", {}):
                mercado_auto[prog] = {"valor": v, "fonte": "Mediana das ofertas do balcão",
                                      "data": date.today().isoformat()}
        print(f"grupos: {len(g['emissoes'])} alertas de passagem ({len(novas_emissoes)} novos), "
              f"{len(g['promos'])} promoções, mercado: {mercado_auto}")
    _gravar("emissoes.json", emissoes)
    _gravar("mercado_auto.json", mercado_auto)

    bonus.completar(list(promos.values()))
    for p in promos.values():
        p["status"] = bonus.status(p, hoje)
    _gravar("promocoes.json", promos)

    ref = milheiro.referencias(list(promos.values()), hoje, mercado_auto)
    _gravar("milheiro.json", ref)

    sm = []
    if "--sem-sitemap" not in argv:
        estado = _ler("sitemap_estado.json", {})
        sm = vigiar_sitemaps(estado)
        _gravar("sitemap_estado.json", estado)

    if "--sem-alerta" not in argv:
        enviados = set(_ler("alertas_v2.json", []))
        vigentes = [p for p in promos.values() if p["status"] in bonus.VIGENTES and p["programa"]]
        if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
            n = len({telegram.chave(p) for p in vigentes})
            telegram.enviar(f"✅ Coletor funcionando: {n} promoções vigentes agora.")
        grupos: dict[tuple, list[dict]] = {}
        for p in sorted(vigentes, key=lambda x: x["publicado"]):
            grupos.setdefault(telegram.chave(p), []).append(p)
        for grupo in grupos.values():
            if any(p["id"] in enviados for p in grupo):
                enviados.update(p["id"] for p in grupo)  # já avisada por outro blog
                continue
            if telegram.enviar(telegram.formatar(grupo[0], ref, grupo)):
                enviados.update(p["id"] for p in grupo)  # só marca se o Telegram confirmou
        enviadas_e = set(_ler("emissoes_enviadas.json", []))
        for e in novas_emissoes:
            if grupos.interessa(e) and e["id"] not in enviadas_e and telegram.enviar(telegram.formatar_emissao(e)):
                enviadas_e.add(e["id"])
        _gravar("emissoes_enviadas.json", sorted(enviadas_e))
        for linha in sm[:5]:
            telegram.enviar(f"📄 Página oficial nova/alterada\n{linha}")
        _gravar("alertas_v2.json", sorted(enviados))


if __name__ == "__main__":
    main()
