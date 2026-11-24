"""Roda uma rodada completa sem rede, para pegar erros de integração."""
from pathlib import Path

from coletor import http, run

XML = (Path(__file__).parent / "fixtures" / "feed.xml").read_text("utf-8")


def test_rodada_completa_sem_rede(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DATA", tmp_path)
    monkeypatch.setattr(http, "baixar", lambda url: XML if "feed" in url else None)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    for k in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_SESSION"):
        monkeypatch.delenv(k, raising=False)
    run.main(["--sem-sitemap"])
    for nome in ("promocoes.json", "milheiro.json", "emissoes.json", "mercado_auto.json", "alertas_v2.json"):
        assert (tmp_path / nome).exists(), nome
