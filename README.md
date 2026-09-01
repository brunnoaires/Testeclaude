# mcsurvey-assist

Preenchimento assistido de formulário de pesquisa. Abre o navegador, preenche os
campos a partir de uma configuração sua, e **para no envio final para você
revisar e confirmar**.

Uma execução envia no máximo uma pesquisa.

## O que a ferramenta não faz

Isso é parte do projeto, não uma limitação a contornar:

- **Não rotaciona IP nem usa proxy.** A requisição sai com a identidade de rede
  real da máquina que rodou. Chaves como `proxy` ou `proxyList` na config fazem
  o comando falhar com erro.
- **Não repete envios.** Não há `--count`, `--repeat`, laço ou paralelismo.
  Uma execução, uma pesquisa. Chaves como `repeat` ou `concurrency` também
  fazem o comando falhar.
- **Não envia sozinha.** O envio final sempre exige confirmação digitada no
  terminal. Não existe flag para desligar isso, e sem terminal interativo
  (cron, CI, pipe) o envio é recusado.
- **Não inventa respostas.** `answers.scalePolicy` não tem valor padrão: você
  precisa declarar a nota. Campos sem regra correspondente ficam pendentes para
  você preencher à mão no navegador.
- **Não gera nem adivinha códigos de cupom.** O código vem do seu cupom, escrito
  por você na config.

Use com um cupom seu, para registrar a sua avaliação. As notas devem refletir a
visita que você realmente fez.

## Instalação

```bash
npm install
npx playwright install chromium
```

Se a máquina já tem um Chromium do Playwright instalado e a versão não bate com
a do pacote, aponte para ele em vez de baixar outro:

```bash
export MCSA_CHROMIUM=/caminho/para/chromium
```

ou coloque `browser.executablePath` na config.

## Uso

```bash
cp config.example.json config.json
$EDITOR config.json          # url, dados do cupom, política de nota
```

**1. Veja a estrutura do formulário antes de preencher pra valer:**

```bash
node src/cli.js inspect
```

Percorre as páginas imprimindo cada campo, cada alternativa e o botão de avanço
de cada tela. Nunca clica em botão de envio. Use a saída para escrever os
`overrides` das perguntas que a heurística não resolve sozinha.

**2. Preencha, revise, confirme:**

```bash
node src/cli.js fill
```

O navegador abre visível. Cada campo preenchido aparece no terminal com a
justificativa (`receipt.cnpj`, `override "..."`, `escala com extremo positivo no
fim`). No fim, o resumo completo é mostrado e o envio espera sua confirmação.

### Opções

| Opção | Efeito |
|---|---|
| `-c, --config <arquivo>` | caminho da config (padrão `config.json`) |
| `-o, --out <dir>` | onde salvar screenshots e logs (padrão `runs/`) |
| `--url <endereço>` | sobrescreve a url da config |
| `--headless` | roda sem janela — não recomendado, você não vê o preenchimento |
| `-n, --dry-run` | preenche mas nunca clica no envio final |
| `--step` | pede confirmação a cada troca de página |

Cada execução grava em `runs/<timestamp>/`: screenshot de cada página, `log.txt`
e `summary.json` com tudo que foi preenchido.

## Configuração

```jsonc
{
  "url": "https://exemplo.com/pesquisa",

  "answers": {
    // "most-positive" | "most-negative" | "neutral" | { "index": N }
    // Sem padrão: a nota é escolha sua.
    "scalePolicy": "most-positive",

    // "auto" deduz pelos rótulos ("Muito satisfeito" no fim => extremo
    // positivo no fim). Se a escala for só estrelas ou números sem rótulo,
    // rode `inspect`, veja a ordem, e fixe "first" ou "last".
    "scaleDirection": "auto",

    // Dados do cupom. A chave é casada contra o rótulo visível do campo
    // (sem acento, sem maiúscula). O rótulo tem prioridade sobre o atributo
    // name do input.
    "receipt": {
      "cnpj": "42591651136479",
      "numero do pedido": "0142",
      "valor": "39,90"
    },

    // Texto para campos de comentário livre. Vazio => você preenche à mão.
    "comment": "",

    // Regras por pergunta, na ordem; a primeira que casar vence.
    "overrides": [
      { "match": "tipo de atendimento", "option": "Balcão" },
      { "match": "sorteio", "option": "Não" },
      { "match": "e-mail", "skip": true },
      { "match": "^Qual .* nota", "regex": true, "option": 4 }
    ]
  }
}
```

Campos de um override:

- `match` — trecho do enunciado (ou regex, com `"regex": true`)
- `option` — rótulo da alternativa, ou índice numérico
- `text` — conteúdo, para campo de texto
- `skip: true` — não mexe no campo, deixa para você

## Como funciona

Não há seletor CSS chumbado para nenhum site. A cada página, `src/enumerate.js`
roda dentro do navegador, marca cada controle com um atributo próprio e devolve
um descritor: tipo, enunciado, alternativas, obrigatoriedade. O enunciado sai de
`aria-labelledby`, `aria-label`, `<label>`, `<legend>` — nessa ordem — e só cai
em heurística de texto próximo como último recurso.

Isso significa que a ferramenta sobrevive a mudança de layout e funciona com o
questionário dentro de um iframe (o frame com mais controles é escolhido
automaticamente). Em compensação, formulários muito fora do padrão vão precisar
de `overrides` — é para isso que existe o `inspect`.

Depois de clicar em avançar, a página é comparada por impressão digital
(URL + enunciados visíveis). Se nada mudou, a ferramenta procura mensagens de
validação, salva um screenshot `-bloqueado.png` e para em vez de insistir.

## Testando sem tocar em site nenhum

Há um formulário falso de três páginas no repositório:

```bash
node test/mock-survey.js 8787 &
MCSA_CHROMIUM=/opt/pw-browsers/chromium \
  node src/cli.js fill --config test/config.test.json --headless --dry-run
```

Ele exercita os dois sentidos de escala Likert, casamento de campos de cupom,
override por rótulo, comentário livre e o portão de confirmação.
