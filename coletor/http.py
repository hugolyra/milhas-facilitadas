"""Cliente HTTP educado: um pedido por domínio a cada N segundos, cache por ETag/Last-Modified."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import config

ESTADO = Path(__file__).resolve().parent.parent / "data" / "http_cache.json"
_ultimo_acesso: dict[str, float] = {}


def _carregar() -> dict:
    try:
        return json.loads(ESTADO.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salvar(estado: dict) -> None:
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), "utf-8")


def baixar(url: str) -> str | None:
    """Retorna o corpo se mudou desde a última vez; None se não mudou ou falhou."""
    dominio = urlparse(url).netloc
    espera = config.INTERVALO_POR_DOMINIO - (time.monotonic() - _ultimo_acesso.get(dominio, -1e9))
    if espera > 0:
        time.sleep(espera)

    estado = _carregar()
    meta = estado.get(url, {})
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    if meta.get("etag"):
        req.add_header("If-None-Match", meta["etag"])
    if meta.get("modificado"):
        req.add_header("If-Modified-Since", meta["modificado"])

    try:
        with urllib.request.urlopen(req, timeout=config.TIMEOUT) as r:
            corpo = r.read().decode("utf-8", "replace")
            estado[url] = {"etag": r.headers.get("ETag"), "modificado": r.headers.get("Last-Modified")}
            _salvar(estado)
            return corpo
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None
        if e.code in (403, 429, 503):
            print(f"[aviso] {dominio} respondeu {e.code}; pulando esta rodada")
        else:
            print(f"[erro] {url}: HTTP {e.code}")
        return None
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"[erro] {url}: {e}")
        return None
    finally:
        _ultimo_acesso[dominio] = time.monotonic()
