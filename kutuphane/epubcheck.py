"""W3C epubcheck ile resmî denetim. Java ve epubcheck.jar imajda kurulu (EPUBCHECK ortam değişkeni)."""
import json
import os
import subprocess
import tempfile

JAR = os.environ.get("EPUBCHECK", "/opt/epubcheck-5.4.0/epubcheck.jar")


def var_mi():
    return os.path.exists(JAR)


def denetle(epub_yolu):
    """{'hata': n, 'uyari': n, 'mesajlar': [...]} ya da denetlenemediyse {'hata': None, ...}."""
    if not var_mi():
        return {"hata": None, "uyari": None, "mesajlar": ["epubcheck kurulu değil"]}
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        rapor = f.name
    try:
        subprocess.run(["java", "-jar", JAR, epub_yolu, "--json", rapor], capture_output=True, text=True,
                       timeout=600)
        d = json.load(open(rapor, encoding="utf-8"))
        mesajlar = [f"{m.get('severity')}: {m.get('message')} ({(m.get('locations') or [{}])[0].get('path', '')})"
                    for m in d.get("messages", []) if m.get("severity") in ("FATAL", "ERROR", "WARNING")]
        c = d.get("checker", {})
        return {"hata": c.get("nFatal", 0) + c.get("nError", 0), "uyari": c.get("nWarning", 0),
                "mesajlar": mesajlar[:50], "surum": c.get("checkerVersion")}
    except Exception as e:  # denetim yapılamadı: EPUB yine de üretilmiş olur
        return {"hata": None, "uyari": None, "mesajlar": [f"denetlenemedi: {e}"]}
    finally:
        if os.path.exists(rapor):
            os.remove(rapor)
