"""Alertas no Telegram (Bot API, gratuita). Precisa de TELEGRAM_TOKEN e TELEGRAM_CHAT_ID.

As mensagens vão para o usuário final: diretas, sem citar o blog de onde a promoção foi lida.
"""
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://hugolyra.github.io/milhas-facilitadas/"

NOMES = {"smiles": "Smiles", "azul": "Azul Fidelidade", "latam": "LATAM Pass", "livelo": "Livelo",
         "esfera": "Esfera", "accor": "ALL Accor", "todos": "todos os parceiros", "inter": "Inter Loop",
         "premmia": "Premmia", "c6": "C6 Bank", "itau": "Itaú", "bb": "Banco do Brasil", "kmv": "KM de Vantagens",
         "bradesco": "Bradesco", "caixa": "Caixa", "porto": "Porto Bank", "xp": "XP", "btg": "BTG",
         "qatar": "Qatar Privilege Club", "iberia": "Iberia", "tap": "TAP Miles&Go"}

# Site oficial de cada programa: é para lá que o usuário vai, não para o blog.
SITES = {"smiles": "https://www.smiles.com.br/", "azul": "https://www.voeazul.com.br/br/pt/programa-fidelidade",
         "latam": "https://latampass.latam.com/pt_br/", "livelo": "https://www.livelo.com.br/",
         "esfera": "https://www.esfera.com.vc/", "accor": "https://all.accor.com/"}


def chave(p: dict) -> tuple:
    """Mesma promoção publicada por blogs diferentes tem a mesma chave."""
    return (p["tipo"], p.get("programa"), p.get("origem"), p.get("percentual"))


def _reais(v: float) -> str:
    return f"R$ {v:.2f}".replace(".", ",")


def formatar(p: dict, ref: dict | None = None, fontes: list[dict] | None = None) -> str:
    """fontes: todas as publicações da mesma promoção (usadas só para completar prazo e CPM)."""
    fontes = fontes or [p]
    prazo = p.get("prazo") or next((f["prazo"] for f in fontes if f.get("prazo")), None)
    cpm = p.get("cpm") or next((f["cpm"] for f in fontes if f.get("cpm")), None)
    e = html.escape
    prog = NOMES.get(p.get("programa"), p.get("programa") or "?")

    if p["tipo"] == "transferencia":
        linhas = [f"✈️ <b>{e(prog)}: +{p['percentual']}% de bônus</b>"]
        if p.get("origem") and p["origem"] != "todos":
            linhas.append(f"Transferindo de {e(NOMES.get(p['origem'], p['origem']))}")
        else:
            linhas.append("Transferindo de bancos e parceiros")
        custo = (ref or {}).get("custo_origem", {}).get(p.get("origem"))
        if cpm:
            linhas.append(f"Milheiro a partir de {_reais(cpm)}")
        elif custo and p.get("percentual") is not None:
            linhas.append(f"Milheiro a partir de {_reais(custo['valor'] / (1 + p['percentual'] / 100))}")
    else:
        desc = f" com até {p['percentual']}% de desconto" if p.get("percentual") else ""
        linhas = [f"🛒 <b>{e(prog)}: compra de pontos{desc}</b>"]
        if p.get("milheiro"):
            linhas.append(f"Milheiro a partir de {_reais(p['milheiro'])}")

    if prazo:
        _, m, d = prazo.split("-")
        linhas.append(f"Válida até {d}/{m}")
    if p["tipo"] == "transferencia":
        linhas.append("Cadastre o CPF na página da promoção antes de transferir.")

    acoes = []
    if (u := SITES.get(p.get("programa"))):
        acoes.append(f'<a href="{e(u)}">Abrir {e(prog)}</a>')
    acoes.append(f'<a href="{SITE}">Ver todas</a>')
    linhas.append(" · ".join(acoes))
    return "\n".join(linhas)


def enviar(texto: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[telegram] sem TELEGRAM_TOKEN/TELEGRAM_CHAT_ID; mensagem não enviada:\n" + texto)
        return False
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto, "parse_mode": "HTML",
                                    "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", dados, timeout=20) as r:
            return json.load(r).get("ok", False)
    except urllib.error.HTTPError as e:
        # Ex.: 400 "chat not found" (ID errado) ou 403 (bot bloqueado ou sem permissão)
        print(f"[telegram] erro {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[telegram] falha de rede: {e}")
    return False
