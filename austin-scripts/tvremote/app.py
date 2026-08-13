"""
RetroTV web remote — remote.dwings.app

Security model (defense in depth):
1. Cloudflare Access (OAuth) gates the hostname at the edge.
2. Every request here must carry a valid Cf-Access-Jwt-Assertion signed by
   Cloudflare for OUR Access app (aud + iss checked). Missing config => 403
   for everything (fails closed).
3. Buttons send fixed command IDs. IDs map to exact SSH invocations of a
   forced-command wrapper on the Pi. No user input ever reaches a shell.
4. The SSH key is restricted on the Pi (command=, no-pty, no-forwarding):
   even a full compromise of this app can only change TV channels.
"""
import os
import subprocess
import time

import jwt
import requests as rq
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from jwt.algorithms import RSAAlgorithm

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CF_TEAM_DOMAIN = os.getenv("CF_TEAM_DOMAIN", "").strip()      # e.g. myteam.cloudflareaccess.com
CF_ACCESS_AUD = os.getenv("CF_ACCESS_AUD", "").strip()        # Access app AUD tag
ALLOWED_EMAILS = {e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}

PI_TARGET = "pi@192.168.1.127"   # LAN IP: real sshd => forced command enforced
SSH_KEY = os.path.expanduser("~/.ssh/tvremote_ed25519")

# The ONLY tokens this app will ever send to the Pi.
COMMANDS = {
    "status", "mode_tv", "mode_static",
    "ch_doug", "ch_hey", "ch_pokemon", "ch_rugrats", "ch_spongebob",
    "ch_all", "ch_next", "pause", "mute",
    "sc_signal", "sc_noise", "sc_atx", "sc_ldn", "sc_bats",
    "sc_aqi", "sc_holiday", "sc_now", "sc_next",
    "passive_on", "passive_off", "broadcast_off", "broadcast_on",
}

app = Flask(__name__)

_jwks_cache = {"keys": None, "fetched": 0}


def _get_cf_keys():
    if not CF_TEAM_DOMAIN:
        return []
    now = time.time()
    if _jwks_cache["keys"] is None or now - _jwks_cache["fetched"] > 3600 * 12:
        try:
            r = rq.get(f"https://{CF_TEAM_DOMAIN}/cdn-cgi/access/certs", timeout=10)
            r.raise_for_status()
            _jwks_cache["keys"] = r.json().get("keys", [])
            _jwks_cache["fetched"] = now
        except Exception:
            pass
    return _jwks_cache["keys"] or []


def _verify_access_jwt():
    """Return verified email or None. None => 403."""
    if not CF_TEAM_DOMAIN or not CF_ACCESS_AUD:
        return None  # fail closed until configured
    token = request.headers.get("Cf-Access-Jwt-Assertion", "")
    if not token:
        return None
    for k in _get_cf_keys():
        try:
            key = RSAAlgorithm.from_jwk(k)
            claims = jwt.decode(
                token, key=key, algorithms=["RS256"],
                audience=CF_ACCESS_AUD,
                issuer=f"https://{CF_TEAM_DOMAIN}",
                options={"require": ["exp", "iat", "aud", "iss"]},
            )
            email = (claims.get("email") or "").lower()
            if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
                return None
            return email or "service-token"
        except jwt.InvalidTokenError:
            continue
        except Exception:
            continue
    return None


def _run_pi(token: str):
    """Send one whitelisted token to the Pi's forced-command wrapper."""
    p = subprocess.run(
        ["ssh", "-i", SSH_KEY,
         "-o", "BatchMode=yes",
         "-o", "ConnectTimeout=5",
         "-o", "StrictHostKeyChecking=yes",
         PI_TARGET, token],
        capture_output=True, text=True, timeout=40,
    )
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    return p.returncode == 0, out or err


@app.get("/")
def index():
    if _verify_access_jwt() is None:
        return "Forbidden", 403
    return render_template("index.html")


@app.get("/api/status")
def api_status():
    if _verify_access_jwt() is None:
        return jsonify(error="forbidden"), 403
    ok, out = _run_pi("status")
    return jsonify(ok=ok, status=out)


@app.post("/api/cmd")
def api_cmd():
    email = _verify_access_jwt()
    if email is None:
        return jsonify(error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    cmd = str(data.get("id", ""))
    if cmd not in COMMANDS:
        return jsonify(error="unknown command"), 400
    ok, out = _run_pi(cmd)
    app.logger.info("cmd=%s by=%s ok=%s", cmd, email, ok)
    return jsonify(ok=ok, output=out)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8110)
