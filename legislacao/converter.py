"""Converte legislacao/originais/* (HTML ou PDF) para legislacao/md/*.md.

Ferramentas locais e de código aberto:
  - HTML -> Markdown: pandoc (https://pandoc.org)
  - PDF  -> Markdown: pymupdf4llm  (pip install pymupdf4llm)

Uso:  python legislacao/converter.py            (só converte o que mudou)
      python legislacao/converter.py --forcar
"""
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ORIG = BASE / "originais"
MD = BASE / "md"
FORCAR = "--forcar" in sys.argv


def ler_html(caminho: Path) -> str:
    """Decodifica conforme o charset declarado (o Planalto usa windows-1252)."""
    bruto = caminho.read_bytes()
    if bruto[:2] in (b"\xff\xfe", b"\xfe\xff"):          # UTF-16 com BOM (ex.: Lei 11.340 no Planalto)
        bruto = bruto[: len(bruto) // 2 * 2].decode("utf-16").encode("utf-8")
        bruto = re.sub(rb'charset\s*=\s*["\']?[\w-]+', b"charset=utf-8", bruto[:4000], flags=re.I) + bruto[4000:]
    m =re.search(rb'charset\s*=\s*["\']?([\w-]+)', bruto[:4000], re.I)
    cs = m.group(1).decode() if m else "utf-8"
    try:
        texto = bruto.decode(cs)
    except (LookupError, UnicodeDecodeError):
        texto = bruto.decode("cp1252", errors="replace")
    # remove scripts, estilos e imagens (brasão etc.)
    texto = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", texto)
    texto = re.sub(r"(?is)<img\b[^>]*>", "", texto)
    return texto


def html_para_md(origem: Path, destino: Path) -> None:
    html = ler_html(origem)
    md = subprocess.run(
        # +RTS ... -RTS: mais pilha/memória para páginas enormes (ex.: CLT, 3,5 MB)
        ["pandoc", "+RTS", "-K1g", "-RTS", "-f", "html", "-t", "gfm-raw_html", "--wrap=none"],
        input=html.encode("utf-8"), capture_output=True, check=True,
    ).stdout.decode("utf-8")
    md = re.sub(r"\n{3,}", "\n\n", md)
    destino.write_text(md, encoding="utf-8")


def pdf_para_md(origem: Path, destino: Path) -> None:
    import pymupdf4llm
    destino.write_text(pymupdf4llm.to_markdown(str(origem)), encoding="utf-8")


def main() -> None:
    MD.mkdir(exist_ok=True)
    for arq in sorted(ORIG.iterdir()):
        conv = {".htm": html_para_md, ".html": html_para_md, ".pdf": pdf_para_md}.get(arq.suffix.lower())
        if not conv:
            continue
        dest = MD / (arq.stem + ".md")
        if dest.exists() and dest.stat().st_mtime >= arq.stat().st_mtime and not FORCAR:
            print(f"ok (atual)   {dest.name}")
            continue
        try:
            conv(arq, dest)
            print(f"convertido   {dest.name} ({dest.stat().st_size // 1024} KB)")
        except Exception as e:  # noqa: BLE001
            print(f"FALHOU       {arq.name}: {e}")


if __name__ == "__main__":
    main()
