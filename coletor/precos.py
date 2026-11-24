"""Preço real em dinheiro, custo zero.

Ordem: cache (6 h) -> fast-flights (Google Flights, gratuito, não oficial) -> SerpApi (250/mês grátis,
só se SERPAPI_KEY existir). Toda resposta leva a hora da consulta: a tela mostra "verificado às HH:MM".
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache_precos.json"
VALIDADE = timedelta(hours=6)
_ultima = 0.0


def link_google(origem: str, destino: str, data: str) -> str:
    q = f"Voos de {origem} para {destino} em {data} só ida"
    return "https://www.google.com/travel/flights?hl=pt-BR&curr=BRL&q=" + urllib.parse.quote(q)


def _cache() -> dict:
    try:
        return json.loads(CACHE.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _via_fast_flights(origem, destino, data, adultos):
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
    global _ultima
    time.sleep(max(0, 5 - (time.monotonic() - _ultima)))  # no máximo 1 busca a cada 5 s
    _ultima = time.monotonic()
    q = create_query(flights=[FlightQuery(date=data, from_airport=origem, to_airport=destino)],
                     trip="one-way", passengers=Passengers(adults=adultos), language="pt-BR", currency="BRL")
    voos = []
    for f in get_flights(q):
        voos.append({
            "preco": f.price, "cias": f.airlines, "paradas": max(0, len(f.flights) - 1),
            "trechos": [f"{s.from_airport.code}-{s.to_airport.code}" for s in f.flights],
            "duracao_min": sum(s.duration for s in f.flights),
        })
    return voos


def _via_serpapi(origem, destino, data, adultos):
    chave = os.environ.get("SERPAPI_KEY")
    if not chave:
        return None
    params = {"engine": "google_flights", "departure_id": origem, "arrival_id": destino,
              "outbound_date": data, "type": "2", "adults": adultos, "currency": "BRL",
              "hl": "pt", "api_key": chave}
    with urllib.request.urlopen("https://serpapi.com/search.json?" + urllib.parse.urlencode(params),
                                timeout=30) as r:
        js = json.load(r)
    voos = []
    for f in js.get("best_flights", []) + js.get("other_flights", []):
        voos.append({"preco": f.get("price"), "cias": sorted({s["airline"] for s in f["flights"]}),
                     "paradas": len(f["flights"]) - 1,
                     "trechos": [f'{s["departure_airport"]["id"]}-{s["arrival_airport"]["id"]}' for s in f["flights"]],
                     "duracao_min": f.get("total_duration")})
    return voos


def preco_dinheiro(origem: str, destino: str, data: str, adultos: int = 1) -> dict:
    chave = f"{origem}-{destino}-{data}-{adultos}"
    cache = _cache()
    if (c := cache.get(chave)) and datetime.now() - datetime.fromisoformat(c["verificado_em"]) < VALIDADE:
        return c
    voos, fonte = None, None
    try:
        voos, fonte = _via_fast_flights(origem, destino, data, adultos), "Google Flights (fast-flights)"
    except Exception as e:  # biblioteca não oficial: pode quebrar quando o Google muda
        print(f"[aviso] fast-flights falhou: {e}")
    if not voos:
        try:
            voos, fonte = _via_serpapi(origem, destino, data, adultos), "Google Flights (SerpApi)"
        except Exception as e:
            print(f"[aviso] SerpApi falhou: {e}")
    resultado = {"voos": sorted(voos or [], key=lambda v: v["preco"] or 1e9), "fonte": fonte,
                 "verificado_em": datetime.now().isoformat(timespec="minutes"),
                 "link": link_google(origem, destino, data)}
    if voos:
        cache[chave] = resultado
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), "utf-8")
    return resultado


if __name__ == "__main__":
    import sys
    o, d, dt = (sys.argv[1:4] + ["REC", "EZE", "2027-01-14"][len(sys.argv[1:4]):])
    print(json.dumps(preco_dinheiro(o, d, dt), ensure_ascii=False, indent=2))
