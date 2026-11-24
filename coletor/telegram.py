"""Alertas no Telegram (Bot API, gratuita). Precisa de TELEGRAM_TOKEN e TELEGRAM_CHAT_ID."""
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request

NOMES = {"smiles": "Smiles", "azul": "Azul Fidelidade", "latam": "LATAM Pass", "livelo": "Livelo",
         "esfera": "Esfera", "accor": "ALL Accor", "todos": "todos os parceiros", "inter": "Inter Loop",
         "premmia": "Premmia", "c6": "C6 Bank", "itau": "Itaú", "bb": "Banco do Brasil", "kmv": "KM de Vantagens",
         "bradesco": "Bradesco", "caixa": "Caixa", "porto": "Porto Bank", "xp": "XP", "btg": "BTG",
         "qatar": "Qatar Privilege Club", "iberia": "Iberia", "tap": "TAP Miles&Go"}


def chave(p: dict) -> tuple:
    """Mesma promoção publicada por blogs diferentes tem a mesma chave."""
    return (p["tipo"], p.get("programa"), p.get("origem"), p.get("percentual"))


def formatar(p: dict, ref: dict | None = None, fontes: list[dict] | None = None) -> str:
    """fontes: outras publicações da mesma promoção (viram links extras numa só mensagem)."""
    fontes = fontes or [p]
    if not p.get("prazo"):
        p = {**p, "prazo": next((f["prazo"] for f in fontes if f.get("prazo")), None)}
    if not p.get("cpm"):
        p = {**p, "cpm": next((f["cpm"] for f in fontes if f.get("cpm")), None)}
    e = html.escape
    prog = NOMES.get(p.get("programa"), p.get("programa") or "?")
    if p["tipo"] == "transferencia":
        cab = f"🔁 <b>{e(prog)}</b>: até {p['percentual']}% de bônus"
        if p.get("origem"):
            cab += f" vindo de {e(NOMES.get(p['origem'], p['origem']))}"
    else:
        cab = f"🛒 <b>Compra de pontos {e(prog)}</b>"
        if p.get("percentual"):
            cab += f": até {p['percentual']}% de desconto"
    linhas = [cab]
    if p.get("milheiro"):
        linhas.append(f"Milheiro a partir de R$ {p['milheiro']:.2f}".replace(".", ","))
    custo = (ref or {}).get("custo_origem", {}).get(p.get("origem"))
    if p.get("cpm"):
        linhas.append(f"Milheiro {e(prog)} a partir de R$ {p['cpm']:.2f} (cálculo do blog)".replace(".", ",", 1))
    elif p["tipo"] == "transferencia" and custo and p.get("percentual") is not None:
        valor = custo["valor"] / (1 + p["percentual"] / 100)
        linhas.append(f"Milheiro {e(prog)} sai por ~R$ {valor:.2f} com esse bônus".replace(".", ","))
    if p.get("prazo"):
        a, m, d = p["prazo"].split("-")
        linhas.append(f"Até {d}/{m}")
    vistos = {}
    for f in fontes:
        vistos.setdefault(f["fonte"], f["link"])
    linhas.append(" · ".join(f'<a href="{e(l)}">{e(n)}</a>' for n, l in vistos.items()))
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
        # Ex.: 400 "chat not found" (ID do canal errado) ou 403 (bot não é admin do canal)
        print(f"[telegram] erro {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[telegram] falha de rede: {e}")
    return False
