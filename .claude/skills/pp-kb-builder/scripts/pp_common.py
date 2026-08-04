"""Shared utilities for pp-kb-builder: config loading, AAD auth, Web API HTTP, redaction.

Stdlib only (urllib) — PyYAML is the project's single third-party dependency and is
only needed by the canvas parser, not by this module.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "v9.2"
DEFAULT_CONFIG_PATH = "pp-kb.config.json"

# Keys whose values must never reach the knowledge base (case-insensitive).
SENSITIVE_KEY_PATTERN = re.compile(
    r"(\$authentication|apikey|password|secret|token|clientsecret|connectionruntimeurl)",
    re.IGNORECASE,
)
# Patterns scanned over generated output as a final safety net.
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(apikey|password|secret|clientsecret)['\"]?\s*[:=]\s*['\"]?[^\s'\",}]{4,}"),
]

ENV_OVERRIDES = {
    "dataverseUrl": "PP_DATAVERSE_URL",
    "tenantId": "PP_TENANT_ID",
    "clientId": "PP_CLIENT_ID",
    "clientSecret": "PP_CLIENT_SECRET",
}


class ConfigError(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def load_config(config_path: str | None = None) -> dict:
    """Load pp-kb.config.json, then apply PP_* environment overrides.

    Secrets (tenantId/clientId/clientSecret) come ONLY from environment variables;
    they are never read from nor written to the config file.
    """
    path = config_path or os.environ.get("PP_CONFIG", DEFAULT_CONFIG_PATH)
    cfg: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        log(f"[config] {path} not found, using defaults + environment only")

    for key, env in ENV_OVERRIDES.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]

    cfg.setdefault("labelLanguage", 1033)
    cfg.setdefault("outputDir", "./kb")
    cfg.setdefault("canvasSourcePath", "./canvas-src")
    cfg.setdefault("filters", {})
    cfg["_configPath"] = path
    return cfg


def require_auth_config(cfg: dict) -> None:
    missing = [k for k in ("tenantId", "clientId", "clientSecret", "dataverseUrl") if not cfg.get(k)]
    if missing:
        envs = [ENV_OVERRIDES[k] for k in missing]
        raise ConfigError(
            "Missing required settings: " + ", ".join(missing)
            + "\nSet environment variables: " + ", ".join(envs)
            + "\n(Secrets must live in env vars, never in the config file.)"
        )


def _http(req: urllib.request.Request, retries: int = 3, timeout: int = 60) -> bytes:
    """Execute a request through the environment proxy (HTTP_PROXY/HTTPS_PROXY),
    with simple retry on 429/5xx."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler())
    for attempt in range(1, retries + 1):
        try:
            with opener.open(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = int(e.headers.get("Retry-After", 2 * attempt))
                log(f"[http] {e.code}, retry {attempt}/{retries} in {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {e.code} for {req.full_url}\n{body.decode('utf-8', 'replace')}") from e
        except urllib.error.URLError as e:
            if attempt < retries:
                log(f"[http] {e.reason}, retry {attempt}/{retries}")
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(
                f"Cannot reach {req.full_url}: {e.reason}\n"
                "Check HTTPS_PROXY/HTTP_PROXY and outbound 443 connectivity."
            ) from e
    raise AssertionError("unreachable")


def get_token(cfg: dict) -> str:
    """client_credentials token via AAD v2 endpoint (proxied urllib)."""
    require_auth_config(cfg)
    url = f"https://login.microsoftonline.com/{cfg['tenantId']}/oauth2/v2.0/token"
    data = urllib.parse.urlencode({
        "client_id": cfg["clientId"],
        "client_secret": cfg["clientSecret"],
        "scope": cfg["dataverseUrl"].rstrip("/") + "/.default",
        "grant_type": "client_credentials",
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp = json.loads(_http(req))
    if "access_token" not in resp:
        raise RuntimeError(f"Token request failed: {json.dumps({k: v for k, v in resp.items() if k != 'access_token'})}")
    log("[auth] token acquired")
    return resp["access_token"]


def api_get(cfg: dict, token: str, path_and_query: str) -> dict:
    """GET against the Dataverse Web API. path_and_query starts after /api/data/vX/."""
    base = cfg["dataverseUrl"].rstrip("/")
    url = f"{base}/api/data/{API_VERSION}/{path_and_query}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    })
    return json.loads(_http(req))


# ---------------------------------------------------------------- redaction

def redact(obj, path: str = "", findings: list | None = None):
    """Recursively remove sensitive keys. Returns (cleaned_obj, findings)."""
    if findings is None:
        findings = []
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if SENSITIVE_KEY_PATTERN.search(str(k)):
                findings.append(f"{path}/{k}")
                continue  # drop entirely
            cleaned_v, findings = redact(v, f"{path}/{k}", findings)
            out[k] = cleaned_v
        return out, findings
    if isinstance(obj, list):
        items = []
        for i, v in enumerate(obj):
            cleaned_v, findings = redact(v, f"{path}[{i}]", findings)
            items.append(cleaned_v)
        return items, findings
    return obj, findings


def redaction_scan_text(text: str, source: str = "") -> list:
    """Final safety net: scan generated text for leaked secrets."""
    hits = []
    for pat in SENSITIVE_VALUE_PATTERNS:
        for m in pat.finditer(text):
            hits.append(f"{source}: '{m.group(0)[:40]}…'")
    return hits


def redaction_scan_dir(root: str) -> list:
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    hits.extend(redaction_scan_text(f.read(), p))
            except OSError:
                pass
    return hits


# ---------------------------------------------------------------- io helpers

def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def label_of(label_obj: dict | None, lang: int = 1033) -> str:
    """Extract a localized label; prefer `lang`, fall back to first available."""
    if not label_obj:
        return ""
    labels = label_obj.get("LocalizedLabels") or []
    for l in labels:
        if l.get("LanguageCode") == lang:
            return l.get("Label", "")
    return labels[0].get("Label", "") if labels else ""


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)
