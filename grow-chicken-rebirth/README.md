# grow-chicken-rebirth

Ciclo automático no **Grow a Chicken Fighter**, do Roblox: melhora o
comedouro, manda o galo para a torre e renasce quando libera.

O script olha a tela como você olharia e roda três **tarefas**, cada uma no
seu intervalo:

| Tarefa | Padrão | O que faz |
|---|---|---|
| melhorar comedouro | a cada 10 s | aperta **E** 3 vezes; o boneco tem que estar parado ao lado do comedouro |
| mandar galo para a torre | a cada 60 s | se o botão de baixo mostra **TORRE**, clica; se mostra **RECUAR**, o galo já está lá e não faz nada |
| renascer | a cada 30 s | abre o menu Renascimento; se está **RENASCER** (verde), clica; se está **AINDA NÃO**, só fecha o menu |

Com o comedouro subindo, o galo ganha nível. A cada ida à torre ele vai mais
longe, até passar do andar exigido. Aí o RENASCER libera, o script renasce e
o ciclo recomeça do zero.

Ele não injeta script no Roblox, não usa executor e não lê a memória do jogo.
São só cliques e teclas, como um auto clicker que enxerga a tela.

## Antes de usar

- **Feito para Windows**, com Python 3.12 ou mais novo. Foi testado num Linux
  com tela virtual, contra uma imitação do jogo, e o reconhecimento do
  RENASCER x AINDA NÃO foi conferido em prints reais do jogo. No Windows, com
  o Roblox de verdade, ainda não foi rodado.
- **Deixe o boneco parado ao lado do comedouro**, onde aparece "MELHORAR
  COMEDOURO" com o **E**. O E só funciona ali.
- **O Roblox tem que estar visível.** Pode estar em janela, mas não pode estar
  minimizado nem coberto por outra janela. A cada tarefa o script traz o
  Roblox para a frente, move o mouse e aperta teclas. Não dá para usar o PC
  para outra coisa enquanto ele roda.
- **Os recortes dependem do tamanho da janela.** Recorte e rode com o Roblox
  do mesmo tamanho. Maximizado ou em tela cheia é o mais fácil. Se mudar o
  tamanho, recorte de novo.
- **Risco:** os termos do Roblox não permitem automatizar o jogo. Um macro de
  cliques como este não mexe no cliente e é bem menos arriscado que um
  executor (que, aliás, costuma vir com vírus), mas o risco não é zero. Use
  sabendo disso.

## Instalação

Instale o Python em [python.org](https://www.python.org/downloads/) e marque
"Add python.exe to PATH" no instalador. Depois, no PowerShell, dentro desta
pasta:

```powershell
py -m pip install -r requirements.txt
Copy-Item config.example.json config.json
```

## 1. Recortar os botões

O script precisa de uma imagem de cada botão, em `templates/`:

| Arquivo | Botão | Situação |
|---|---|---|
| `renascimento.png` | "Renascimento" na lateral direita da tela | **falta recortar** |
| `botao_torre.png` | **só a palavra TORRE**, embaixo do castelo | **falta recortar** |
| `botao_renascer.png` | RENASCER verde, dentro do menu | já vem pronto |
| `fechar_menu.png` | o X vermelho do menu | já vem pronto |

Os dois que já vêm prontos foram recortados de um print do jogo com a janela
em cerca de 1920 px de largura. Se o seu Roblox está em outro tamanho e o
`check` (passo 2) não achar esses dois, recorte de novo.

Para recortar, deixe o botão visível no Roblox e rode:

```powershell
py auto_rebirth.py capture templates/renascimento.png
py auto_rebirth.py capture templates/botao_torre.png
```

Você tem 4 segundos para pôr o mouse no **canto superior esquerdo** do botão
e mais 4 segundos para pôr no **canto inferior direito**.

Dicas:

- **No TORRE, recorte só a palavra, nunca o castelo.** TORRE e RECUAR usam o
  mesmo castelo, só muda a palavra. Com o castelo no recorte, o script pode
  confundir os dois e clicar em RECUAR, tirando o galo da torre. Por isso esse
  passo também pede nota 0.90, mais alta que os outros.
- O `botao_torre.png` tem que ser recortado com o galo **em casa** (botão
  mostrando TORRE).
- Nos outros botões, pegue o miolo (texto e ícone), sem o cenário 3D em
  volta. O cenário muda quando a câmera mexe e atrapalha a comparação.

## 2. Testar os recortes

```powershell
py auto_rebirth.py check
```

Você tem 3 segundos para trocar para o Roblox. Ele tira um print e diz, para
cada botão da config, se achou ou não. Por exemplo, com o menu aberto e o
botão em AINDA NÃO:

```
renascer:
  ...
  nao achou     botao RENASCER (liberado): formato 0.39 (min 0.85), cor 63 (max 40), melhor lugar (354, 549)
  ACHOU         fechar menu: formato 1.00 (min 0.85), cor 0 (max 40), melhor lugar (629, 72)
```

O `check` só vê o que está na tela no momento. Rode algumas vezes:

1. menu fechado e galo em casa: tem que achar **Renascimento** e **TORRE**;
2. galo na torre (botão mostrando RECUAR): **TORRE** tem que dar "nao achou";
3. menu aberto: tem que achar o **X**, e o RENASCER só se estiver liberado.

Como ler o resultado:

- **"formato" abaixo do mínimo num botão que está na tela:** recorte de novo,
  pegando menos cenário. Ou baixe o `confidence` só desse passo (ex.: `0.75`).
- **"cor" acima do máximo num botão que está na tela:** recorte de novo.
- **TORRE "ACHOU" com o galo na torre:** perigo. Recorte de novo só a
  palavra, ou suba o `confidence` desse passo.

## 3. Rodar

```powershell
py auto_rebirth.py run
```

```
[14:02:11] tarefa "melhorar comedouro": a cada 10s
[14:02:11] tarefa "mandar galo para a torre": a cada 60s
[14:02:11] tarefa "renascer": a cada 30s
[14:02:11] rodando. Para parar: Ctrl+C aqui, ou mouse num canto da tela.
[14:02:11] melhorar comedouro
[14:02:11]   apertando E x3 (E no comedouro)
[14:02:13] mandar galo para a torre
[14:02:13]   clicando em "botao TORRE" (960, 985)
[14:02:15] renascer
[14:02:15]   clicando em "abrir menu Renascimento" (1853, 495)
[14:02:19]   "botao RENASCER (liberado)" nao apareceu, fica para a proxima
[14:02:19]   clicando em "fechar menu" (1220, 205)
...
[14:31:40] "renascer" feito (1x nesta sessao)
```

Para parar, aperte **Ctrl+C** no terminal ou jogue o mouse num **canto da
tela** (o failsafe do pyautogui interrompe na hora). `run --once` roda cada
tarefa uma vez e sai, o que é bom para testar.

## Ajustando o ritmo

Os intervalos ficam em `every_seconds`, no `config.json`:

- **O galo vai para a torre fraco demais e perde cedo:** aumente o intervalo
  da torre (ex.: `300` para 5 minutos). Assim ele passa mais tempo subindo de
  nível entre uma ida e outra.
- **Dinheiro sobrando:** diminua o intervalo do comedouro ou aumente o
  `repeat` do E.
- **Não quer que ele mande para a torre:** apague a tarefa inteira. O mesmo
  vale para as outras.

## Se o botão Renascimento não for achado

Se o ícone tem animação (a chama mexendo, por exemplo), o recorte pode não
bater sempre. Como esse botão fica sempre no mesmo lugar, dá para usar uma
posição fixa no lugar da imagem:

```powershell
py auto_rebirth.py pos
```

Ponha o mouse em cima do botão, anote o `x` e o `y`, e troque o passo no
`config.json`:

```json
{ "name": "abrir menu Renascimento", "pos": [1853, 495], "wait": 0 }
```

A posição fixa só vale enquanto a janela do Roblox não mudar de lugar nem de
tamanho.

## Se o jogo pedir confirmação ao renascer

Pelos prints, o RENASCER renasce direto. Se aparecer uma tela de
confirmação, recorte o botão dela
(`py auto_rebirth.py capture templates/confirmar.png`) e acrescente este
passo depois do RENASCER, nos `steps` da tarefa "renascer":

```json
{ "name": "confirmar", "image": "templates/confirmar.png", "wait": 3, "optional": true }
```

## Config

```json
{
  "window_title": "Roblox",
  "tasks": [
    { "name": "...", "every_seconds": 10, "steps": [ ... ], "cleanup": [ ... ] }
  ]
}
```

| Chave | Padrão | O que faz |
|---|---|---|
| `window_title` | `"Roblox"` | título da janela; a busca fica restrita a ela |
| `interval_seconds` | `30` | intervalo das tarefas que não têm `every_seconds` |
| `confidence` | `0.85` | nota mínima de formato (0 a 1) |
| `color_tolerance` | `40` | diferença máxima de cor (0 a 255) |
| `tasks` | — | as tarefas, rodadas uma de cada vez, na ordem |

Cada tarefa:

| Chave | Padrão | O que faz |
|---|---|---|
| `name` | — | nome que aparece no log |
| `every_seconds` | `interval_seconds` | de quanto em quanto tempo roda |
| `steps` | — | passos, em ordem |
| `cleanup` | `[]` | passos que rodam sempre no fim, deu certo ou não |

Cada passo tem **um** destes: `image`, `pos` ou `key`.

| Chave | Padrão | O que faz |
|---|---|---|
| `name` | — | nome que aparece no log |
| `image` | — | recorte do botão a clicar (caminho relativo à config) |
| `pos` | — | `[x, y]` fixo a clicar |
| `key` | — | tecla a apertar: uma letra ou número (`"e"`), ou `space`, `enter`, `tab`, `esc`, `shift`, `ctrl`, `alt`, setas (`up`...), `f1`...`f12` |
| `hold` | `0` | segundos segurando a tecla (para prompt de "segure E") |
| `repeat` | `1` | quantas vezes clica ou aperta |
| `wait` | `3` | segundos esperando o botão aparecer |
| `after` | `0.8` | pausa depois de cada clique ou tecla |
| `optional` | `false` | se o botão não aparecer, segue em vez de interromper a tarefa |
| `confidence`, `color_tolerance` | os da config | ajuste só para este passo |

Um passo obrigatório que não aparece interrompe a tarefa até a próxima vez.
É assim que o AINDA NÃO faz o script desistir de renascer, e o RECUAR faz ele
não mexer no galo. O `cleanup` nunca interrompe nada: se o botão não está lá,
ele pula.

Além do formato, o script compara a cor média do trecho achado com a do
recorte. Assim um botão parecido, mas de outra cor, não é confundido.

No Windows as teclas vão pelo `pydirectinput`, que manda o mesmo código de
um teclado de verdade. Jogos em DirectX, como o Roblox, costumam ignorar o
jeito mais simples de simular tecla.

O formato antigo da config, com `steps` e `cleanup` direto no topo e sem
`tasks`, continua valendo como uma tarefa só, chamada "renascer".

## Testes

Os testes não precisam do Roblox. Eles usam uma tela simulada com OpenCV e
pedaços de prints reais do menu, em `tests/fixtures/`:

```powershell
py -m unittest discover -s tests
```
