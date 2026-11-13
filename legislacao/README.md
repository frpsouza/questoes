# Legislação do edital – Orientador Educacional (Fundação Liberato 001/2026)

Textos obtidos em sites oficiais. Sempre que possível foi usada a versão **compilada**, com as alterações já no corpo do texto: Planalto para as normas federais, MEC, CEEd-RS e AL-RS/LEGIS para as estaduais.

- [`fontes.csv`](fontes.csv): lista de normas e URLs.
- [`originais/`](originais/): arquivos baixados (HTML ou PDF).
- [`md/`](md/): versões em Markdown para estudo.

## Como atualizar

```powershell
pwsh -File legislacao\baixar.ps1          # baixa o que falta (-Forcar para baixar tudo de novo)
python legislacao\converter.py            # converte o que mudou (--forcar para tudo)
```

A conversão é local e usa ferramentas de código aberto:

- HTML → Markdown: **pandoc**.
- PDF → Markdown: **pymupdf4llm**. Instale com `pip install pymupdf4llm`. Usa OCR com Tesseract quando a página é imagem.

O download usa o `Invoke-WebRequest` do PowerShell. O Planalto recusa conexões do `curl` do Git Bash e do `urllib` do Python.

## Observações

- **Texto riscado (`~~assim~~`)** é redação revogada ou alterada. Vale a redação logo abaixo.
- **AL-RS (LEGIS):** a página da norma é só um envelope. O texto está num PDF em `ww3.al.rs.gov.br/filerepository/repLegis/arquivos/`.
- **Normas estaduais em PDF:** os PDFs da AL-RS trazem o texto original, não compilado. Para a Lei 14.498/2014, confira as alterações no registro do LEGIS ([ficha da norma](https://www.al.rs.gov.br/legis/M010/M0100018.asp?Hid_IdNorma=60730)).
- **Estatuto da Fundação (Decreto 18.446/1967):** não há arquivo digital no LEGIS. Baixei o Decreto 52.101/2014, que altera o estatuto e traz o texto das partes alteradas. O texto completo pode ser pedido à Fundação ou procurado no DOE de 21/03/1967.
- **BNCC:** é o documento integral. Estude a parte do **Ensino Médio**.
- **Resolução nº 365/2021 (tópico h do programa):** foi identificada como a Resolução CEEd-RS 365/2021, que trata do Ensino Médio e suas modalidades no RS.
