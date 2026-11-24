from datetime import date
from pathlib import Path

from coletor import bonus, milheiro, telegram

XML = (Path(__file__).parent / "fixtures" / "feed.xml").read_text("utf-8")
HOJE = date(2026, 11, 24)


def promos():
    return {p["link"].rsplit("/", 1)[1]: p for p in bonus.ler_rss(XML, "Teste")}


def test_ignora_posts_que_nao_sao_promocao():
    assert "jetsmart" not in promos()
    assert "pink" not in promos() and "azul-viagens" not in promos()
    assert len(promos()) == 9


def test_transferencia_livelo_azul():
    p = promos()["azul-livelo-130"]
    assert (p["tipo"], p["programa"], p["origem"], p["percentual"]) == ("transferencia", "azul", "livelo", 130)
    assert p["prazo"] == "2026-11-06"
    assert bonus.status(p, HOJE) == "encerrada"


def test_ate_hoje_e_sem_origem_vira_todos():
    p = promos()["azul-90"]
    assert p["prazo"] == "2026-11-19" and p["origem"] == "todos"


def test_data_em_barra_e_c6():
    p = promos()["smiles-c6"]
    assert (p["programa"], p["origem"], p["prazo"]) == ("smiles", "c6", "2026-11-24")
    assert bonus.status(p, HOJE) == "ativa"


def test_compra_de_pontos_e_milheiro_invertido():
    ps = promos()
    assert ps["livelo-57"]["tipo"] == "compra" and ps["livelo-57"]["programa"] == "livelo"
    assert ps["livelo-57"]["prazo"] == "2026-11-15"
    assert ps["turbo"]["milheiro"] == 29.40 and ps["turbo"]["programa"] == "livelo"


def test_referencia_do_milheiro():
    ref = milheiro.referencias(list(promos().values()), HOJE)
    # custo Livelo cai para 29,40 (Turbo, últimos 60 dias)
    assert ref["custo_origem"]["livelo"]["valor"] == 29.40
    # LATAM: 27% Livelo (29,40/1,27=23,15) e 30% Esfera (30/1,3=23,08) ativos -> vence Esfera
    assert ref["programas"]["latam"]["aquisicao"] == {"valor": 23.08, "via": "esfera", "bonus": 30}
    # Azul: o CPM de R$ 15,32 publicado pelo blog (Premmia) entra como aquisição de hoje
    assert ref["programas"]["azul"]["aquisicao"] == {"valor": 15.32, "via": "premmia", "bonus": 120}
    # típico Azul via Livelo: mediana(130 Livelo, 90 todos) = 110% sobre 29,40 (Inter e Premmia não contam)
    assert ref["programas"]["azul"]["aquisicao_tipica"]["valor"] == round(29.40 / 2.10, 2)


def test_avaliar_emissao():
    r = milheiro.avaliar_emissao(1520, 160, 26500, 16.0)
    assert r["rende_por_milheiro"] == 51.32 and r["vale_a_pena"]


def test_mensagem_telegram_escapa_html():
    p = promos()["smiles-c6"]
    txt = telegram.formatar(p, milheiro.referencias(list(promos().values()), HOJE))
    assert "Smiles" in txt and "70%" in txt and "24/11" in txt and "<a href=" in txt


def test_titulos_reais_de_24_11_2026():
    ps = promos()
    assert (ps["azul-premmia"]["origem"], ps["azul-premmia"]["cpm"], ps["azul-premmia"]["percentual"]) == ("premmia", 15.32, 120)
    assert (ps["azul-inter"]["programa"], ps["azul-inter"]["origem"]) == ("azul", "inter")
    p = ps["latam-livelo"]
    assert (p["programa"], p["origem"], p["percentual"], p["prazo"]) == ("latam", "livelo", 27, "2026-11-24")


def test_ultimas_horas_herda_programa_e_fica_provavel():
    from datetime import datetime
    base = {"tipo": "transferencia", "origem": "livelo", "percentual": 27, "prazo": None}
    a = bonus.extrair("Últimas horas para ganhar 27% de bônus nas transferências de pontos Livelo",
                      "u", datetime.fromisoformat("2026-11-24T17:30:29+00:00"), "T")
    b = {**base, "programa": "latam", "publicado": "2026-11-23T22:44:54+00:00"}
    bonus.completar([a, b])
    assert a["programa"] == "latam" and a["prazo"] == "2026-11-24"
    assert bonus.status(b, HOJE) == "provavel"
    assert bonus.status(b, date(2026, 11, 30)) == "verificar"


def test_mensagem_unica_para_mesma_promocao_em_dois_blogs():
    p1 = {"tipo": "transferencia", "programa": "latam", "origem": "livelo", "percentual": 27, "milheiro": None,
          "cpm": None, "prazo": None, "link": "https://a/1", "fonte": "Blog A"}
    p2 = {**p1, "prazo": "2026-11-24", "link": "https://b/2", "fonte": "Blog B"}
    assert telegram.chave(p1) == telegram.chave(p2)
    txt = telegram.formatar(p1, None, [p1, p2])
    assert "LATAM Pass" in txt and "Livelo" in txt and "Até 24/11" in txt
    assert "Blog A" in txt and "Blog B" in txt


def test_nome_bonito_e_cpm_do_blog():
    p = promos()["azul-premmia"]
    txt = telegram.formatar(p, None)
    assert "Premmia" in txt and "R$ 15,32" in txt
