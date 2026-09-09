"""Check the real HTTPS proxy with its own CA, never disable TLS validation."""
import http.cookiejar
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path
base = "https://localhost:8443"
context = ssl.create_default_context(cafile=str(Path(__file__).resolve().parent.parent / ".local/smoke-ca.crt"))
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), urllib.request.HTTPCookieProcessor(jar))
def request(path, data=None, headers=None):
    r=urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None, headers=headers or {})
    try:
        return client.open(r)
    except urllib.error.HTTPError as e:
        return e
response=request("/api/b2c/csrf")
assert response.status == 200
assert "no-store" in response.headers["Cache-Control"]
assert any(c.name == "b2c_csrftoken" and c.secure and c.has_nonstandard_attr("HttpOnly") for c in jar)
assert request("/api/b2c/me").status == 401
assert request("/api/does-not-exist").status == 404
assert request("/login").status == 200
response=request("/_allauth/browser/v1/auth/login", {"email":"none@example.com","password":"unused"}, {"Content-Type":"application/json"})
assert response.status == 403
assert json.load(response)["code"] == "csrf_failed"
print("HTTPS proxy, Secure/HttpOnly cookies, no-store, API isolation and login CSRF checks passed")
