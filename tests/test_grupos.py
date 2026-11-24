"""Formatos de mensagem dos grupos (textos de exemplo no mesmo formato, valores fictícios)."""
from datetime import datetime, timezone

from coletor import grupos, milheiro, telegram

Q = datetime(2026, 11, 24, 14, 0, tzinfo=timezone.utc)

NACIONAL = """🗺 Rota: 🛫 Campinas (VCP) 🛬 Natal (NAT)
💳 Programa: Smiles
💰 Custo: 14k milhas o trecho + taxas
🔁 Trajeto: Ida e volta
💺 Cabine: Econômica
📅 Data: 20/03 a 31/03/2027"""

EXECUTIVA = """🇧🇷 São Paulo ✈️ Buenos Aires 🇦🇷
Rota: São Paulo (GRU) → Buenos Aires (EZE)
Programa: Smiles
Companhia aérea: Turkish Airlines
Cabine: Executiva
Trajeto: Ida e volta
Custo: 66,5k milhas Smiles por pessoa, por trecho + taxas
DATAS DE IDA — GRU → EZE
Março/2027: 3 (2), 10 (1)"""

RESUMO = """Resumo do Balcão — 26/09/2026
Latam — R$ 24,81 por mil · 30.641.489 milhas
Smiles — R$ 15,40 por mil · 14.481.759 milhas
Azul — R$ 13,68 por mil · 4.718.100 milhas
Ibéria — R$ 49,10 por mil · 300.000 milhas"""

OFERTA = "Interessado em COMPRAR 80.000 milhas #Smiles, 3 pax, paga: R$ 16.00/K  Total: R$ 1.280"


def test_emissao_nacional():
    e = grupos.ler_emissao(NACIONAL, Q, "tg://1/2")
    assert (e["origem"]["iata"], e["destino"]["iata"], e["programa"], e["milhas"], e["por_trecho"]) == \
        ("VCP", "NAT", "smiles", 14000, True)
    assert e["origem"]["cidade"] == "Campinas" and e["cabine"] == "Econômica"
    assert e["datas"].startswith("20/03")


def test_emissao_executiva_com_companhia():
    e = grupos.ler_emissao(EXECUTIVA, Q, "tg://1/3")
    assert (e["origem"]["iata"], e["destino"]["iata"], e["milhas"], e["cabine"], e["companhia"]) == \
        ("GRU", "EZE", 66500, "Executiva", "Turkish Airlines")
    assert "Março/2027" in e["datas"]


def test_programas_variados():
    assert grupos._programa("TudoAzul") == "azul"
    assert grupos._programa("Tudo Azul") == "azul"
    assert grupos._programa("LatamPass") == "latam"
    assert grupos._programa("Qatar Airways Privilege Club") == "qatar"
    assert grupos._programa("Atmos Rewards (Alaska Airlines) e Finnair Plus") is None


def test_resumo_e_ofertas_do_balcao():
    assert grupos.ler_resumo_balcao(RESUMO) == {"latam": 24.81, "smiles": 15.40, "azul": 13.68, "iberia": 49.10}
    assert grupos.ler_oferta_balcao(OFERTA) == ("smiles", 16.0)
    assert grupos.mercado_por_ofertas([("smiles", 16), ("smiles", 15.5), ("smiles", 15), ("azul", 13)]) == {"smiles": 15.5}


def test_mercado_automatico_vence_manual_mais_antigo():
    auto = {"smiles": {"valor": 15.0, "fonte": "Resumo", "data": "2026-11-25"}}
    assert milheiro.mercado_atual(auto)["smiles"]["valor"] == 15.0
    velho = {"smiles": {"valor": 99, "fonte": "x", "data": "2020-01-01"}}
    assert milheiro.mercado_atual(velho)["smiles"]["valor"] == 15.5


def test_mensagem_de_passagem():
    e = grupos.ler_emissao(NACIONAL, Q, "tg://1/2")
    txt = telegram.formatar_emissao(e)
    assert "Campinas (VCP) → Natal (NAT)" in txt and "14 mil milhas Smiles o trecho" in txt
    assert "20/03" in txt and "tg://" not in txt


def test_avios_na_referencia():
    ref = milheiro.referencias([], datetime(2026, 11, 24).date())
    # Esfera a R$ 30 com paridade 2:1 → R$ 60 por mil Avios; Livelo 3,5:1 → R$ 105
    assert ref["programas"]["iberia"]["aquisicao"] == {"valor": 60.0, "via": "esfera", "bonus": 0}


def test_interessa_recife():
    e = grupos.ler_emissao(NACIONAL.replace("Natal (NAT)", "Recife (REC)"), Q, "x")
    assert grupos.interessa(e)
    assert not grupos.interessa(grupos.ler_emissao(NACIONAL, Q, "y"))


def test_alerta_esfera_iberia_com_paridade():
    from coletor import bonus
    p = bonus.extrair("Esfera oferece 25% de bônus nas transferências de pontos para o Iberia Club até 30 de novembro",
                      "z", Q, "T")
    assert (p["programa"], p["origem"], p["percentual"]) == ("iberia", "esfera", 25)
    ref = milheiro.referencias([p], Q.date())
    txt = telegram.formatar(p, ref)
    # R$ 30 por mil Esfera ÷ 1,25 ÷ 0,5 = R$ 48 por 1.000 Avios, abaixo do mercado de R$ 50
    assert "1.000 Avios saem por ~R$ 48,00 (paridade 2:1)" in txt and "Abaixo do preço de mercado" in txt
    assert ref["programas"]["iberia"]["aquisicao"]["valor"] == 48.0
