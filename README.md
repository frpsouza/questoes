# Questões — Concurso Fundação Liberato 001/2026

Material de estudo para **Analista Educacional: Orientador Educacional** (Fundação Escola Técnica Liberato Salzano Vieira da Cunha, banca Legalle). Prova teórico-objetiva provável em 07/03/2027.

## 📖 [Abrir o Material de Estudos – Orientador Educacional](https://frpsouza.github.io/questoes/)

Apostila com Língua Portuguesa, Legislação (textos oficiais, com alterações recentes destacadas) e Conhecimentos Específicos, organizada pelos tópicos do edital. Na Legislação, as questões de prova da banca Legalle aparecem logo abaixo do dispositivo que cobram (artigo, parágrafo, inciso ou alínea), com o gabarito recolhido.

O link abre o índice geral. O material está dividido em [português](https://frpsouza.github.io/questoes/apostilas/orientador-educacional/portugues.html), [legislação](https://frpsouza.github.io/questoes/apostilas/orientador-educacional/legislacao.html) (uma página por lei) e [específicos](https://frpsouza.github.io/questoes/apostilas/orientador-educacional/especificos.html). Também existe a [versão em arquivo único](https://frpsouza.github.io/questoes/apostilas/orientador-educacional.html).

## Conteúdo do repositório

| Pasta/arquivo | O que é |
|---|---|
| [apostilas/](apostilas/) | Gerador da apostila (`gerar_orientador.py`) e a versão HTML |
| [edital/](edital/) | Edital dividido por itens; `anexo-II/` traz o programa de cada cargo |
| [legislacao/](legislacao/) | Normas oficiais em Markdown e scripts de download e conversão |
| [plano-de-estudos/](plano-de-estudos/README.md) | Cronograma semanal de 16/11/2026 a 06/03/2027, dividido em [português](plano-de-estudos/portugues.md), [legislação](plano-de-estudos/legislacao.md) e [específicos](plano-de-estudos/especificos.md) |
| [banca-legalle.md](banca-legalle.md) | A banca: contato, atuação no concurso, editais e onde treinar questões |

Para regenerar a apostila: `python apostilas/gerar_orientador.py` (requer Python 3 e pandoc).

### Questões de legislação (uso pessoal, não publicado)

1. `python q/leg/gerar_leg.py` — lê `q/leg/dump.json` (salvo do navegador) e gera `q/leg/questoes.json` e `q/leg/md/Q#######.md` com o gabarito comentado.
2. `python q/leg/artigos.py` — monta a base artigo de lei → questões (`q/leg/artigos.json` e `q/leg/artigos.md`). As questões sem gabarito comentado entram pela análise feita à mão em `q/leg/analises.json` (artigo cobrado, por que cada alternativa está certa ou errada, texto da questão × texto legal e alterações legislativas).
3. `python apostilas/gerar_orientador.py` — a versão publicada traz, abaixo de cada dispositivo (artigo, parágrafo, inciso ou alínea), as questões que o cobram, com enunciado, alternativas, gabarito e as análises próprias, sem o texto dos comentários do Qconcursos; a versão local (`apostilas/orientador-educacional-local.html` e, dividida, `apostilas/orientador-educacional/index-local.html`, `legislacao-local.html` e uma página `leg-*-local.html` por lei) traz a questão e o trecho do gabarito comentado.

