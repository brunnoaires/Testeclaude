# grow-chicken-rebirth

Ciclo automático no **Grow a Chicken Fighter**, do Roblox: melhora o
comedouro, manda o galo para a torre e renasce quando libera.

O script olha a tela como você olharia e roda quatro **tarefas**, nesta
ordem, a cada 10 segundos:

| Ordem | Tarefa | O que faz |
|---|---|---|
| 1 | recuar galo para renascer | com o **!** vermelho no **Renascimento**, abre o menu; se está escrito **VOLTE PRO SEU GALINHEIRO** (liberou, mas o galo está na torre), fecha o menu, clica em **RECUAR** e espera 8 s |
| 2 | renascer | com o **!** vermelho, abre o menu, clica em **RENASCER** e fecha |
| 3 | melhorar comedouro | aperta **E** 3 vezes e espera 2 s; o boneco tem que estar parado ao lado do comedouro |
| 4 | mandar galo para a torre | se o botão de baixo mostra **TORRE**, clica; se mostra **RECUAR**, o galo já está lá e não faz nada |

A ordem importa:

- O "recuar" vem logo antes do "renascer": depois dos 8 s do RECUAR ele já
  renasce, antes que a tarefa da torre mande o galo de volta.
- O renascimento vem antes da torre: com o **!** na tela, ele renasce em vez
  de mandar o galo à toa.
- O comedouro vem entre os dois: depois de renascer o galinheiro zera, então
  o E cria o comedouro de novo, ele espera 2 s e só então manda a galinha
  para a torre.

Com o comedouro subindo, o galo ganha nível. A cada ida à torre ele vai mais
longe, até passar do andar exigido. Aí aparece o **!** no Renascimento, o
script renasce e o ciclo recomeça do zero. Enquanto não tem **!**, ele nem
abre o menu.

Ele não injeta script no Roblox, não usa executor e não lê a memória do jogo.
São só cliques e teclas, como um auto clicker que enxerga a tela.

## Antes de usar

- **Feito para Windows**, com Python 3.11 ou mais novo. Foi testado num Linux
  com tela virtual, contra uma imitação do jogo. O reconhecimento de cada
  botão (o **!**, Renascimento, TORRE, RENASCER x AINDA NÃO e o X) foi
  conferido em prints reais do jogo. No Windows, com o Roblox de verdade,
  ainda não foi rodado.
- **Deixe o boneco parado ao lado do comedouro**, onde aparece "MELHORAR
  COMEDOURO" com o **E**. O E só funciona ali.
- **O Roblox tem que estar visível.** Pode estar em janela, mas não pode estar
  minimizado nem coberto por outra janela. A cada tarefa o script traz o
  Roblox para a frente, move o mouse e aperta teclas. Não dá para usar o PC
  para outra coisa enquanto ele roda.
- **Os recortes dependem do tamanho da janela.** Os que vêm prontos foram
  tirados com o Roblox maximizado, em cerca de 1920 px de largura. Rode do
  mesmo jeito. Se o seu está em outro tamanho, veja "Recortar de novo".
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

## 1. Testar os recortes

Os recortes de todos os botões já vêm prontos em `templates/`:

| Arquivo | Botão |
|---|---|
| `renascimento.png` | o botão Renascimento, na lateral direita |
| `botao_torre.png` | **só a palavra TORRE**, embaixo do castelo |
| `botao_recuar.png` | **só a palavra RECUAR**, que aparece no lugar do TORRE com o galo na torre |
| `botao_renascer.png` | RENASCER verde, dentro do menu |
| `volte_galinheiro.png` | VOLTE PRO SEU GALINHEIRO, que aparece no lugar do RENASCER com o galo na torre |
| `fechar_menu.png` | o X vermelho do menu |

O **!** vermelho não usa recorte: o script procura a cor da bolinha
(`#FF3D02`) numa área pequena em volta do Renascimento. Assim não importa se
a bolinha pulsa, pula, gira ou pisca. A área é necessária porque a bolinha
da Guilda tem a mesma cor.

Confira se eles batem com a sua tela:

```powershell
py auto_rebirth.py check
```

Você tem 3 segundos para trocar para o Roblox. Ele tira um print e diz, para
cada botão da config, se achou ou não. Esta é a saída com o seu print do
comedouro (menu fechado, galo em casa, renascimento liberado):

```
recuar galo para renascer:
  ACHOU         ! vermelho no Renascimento: 916 pixels da cor na area (min 150), centro (1887, 469)
  ACHOU         abrir menu Renascimento: formato 1.00 (min 0.75), cor 0 (max 40), melhor lugar (1853, 520)
  nao achou     VOLTE PRO SEU GALINHEIRO: formato 0.20 (min 0.75), cor 72 (max 40), melhor lugar (1069, 237)
  nao achou     fechar menu: formato 0.45 (min 0.75), cor 69 (max 40), melhor lugar (1045, 360)
  nao achou     botao RECUAR: formato 0.59 (min 0.80), cor 37 (max 40), melhor lugar (126, 10)
  nao achou     fechar menu: formato 0.45 (min 0.75), cor 69 (max 40), melhor lugar (1045, 360)

renascer:
  ACHOU         ! vermelho no Renascimento: 916 pixels da cor na area (min 150), centro (1887, 469)
  ACHOU         abrir menu Renascimento: formato 1.00 (min 0.75), cor 0 (max 40), melhor lugar (1853, 520)
  nao achou     botao RENASCER (liberado): formato 0.30 (min 0.75), cor 73 (max 40), melhor lugar (546, 576)
  nao achou     fechar menu: formato 0.45 (min 0.75), cor 69 (max 40), melhor lugar (1045, 360)

melhorar comedouro:
  tecla         E no comedouro: E (o check nao testa tecla)
  espera        esperar o comedouro: 2s

mandar galo para a torre:
  ACHOU         botao TORRE: formato 1.00 (min 0.80), cor 0 (max 40), melhor lugar (960, 992)
```

O `check` só vê o que está na tela no momento. Rode algumas vezes:

1. **menu fechado e galo em casa:** tem que achar **Renascimento** e
   **TORRE**; o **!** só se o renascimento estiver liberado;
2. **galo na torre** (botão mostrando RECUAR): tem que achar o **RECUAR**, e o
   **TORRE** tem que dar "nao achou";
3. **menu Renascimento aberto:** tem que achar o **X**; o **RENASCER** só se
   estiver liberado com o galo em casa, e o **VOLTE PRO SEU GALINHEIRO** só se
   estiver liberado com o galo na torre.

Os botões de dentro do menu dão "nao achou" com o menu fechado, e vice-versa.
Isso é normal.

Como ler o resultado:

- **"formato" abaixo do mínimo num botão que está na tela:** o recorte não
  bate com a sua tela. Veja "Recortar de novo".
- **"cor" acima do máximo num botão que está na tela:** idem.
- **TORRE "ACHOU" com o galo na torre:** perigo, ele tiraria o galo da torre.
  Recorte de novo só a palavra, ou suba o `confidence` desse passo.
- **! "nao achou" com o ! na tela:** veja "Se o ! não for achado".

## 2. Rodar

Deixe o boneco parado ao lado do comedouro e rode:

```powershell
py auto_rebirth.py run
```

```
[14:02:11] janela "Roblox" encontrada
[14:02:11] tarefa "recuar galo para renascer": a cada 10s
[14:02:11] tarefa "renascer": a cada 10s
[14:02:11] tarefa "melhorar comedouro": a cada 10s
[14:02:11] tarefa "mandar galo para a torre": a cada 10s
[14:02:11] rodando. Para parar: Ctrl+C aqui, ou mouse num canto da tela.
[14:02:11] recuar galo para renascer
[14:02:13]   "! vermelho no Renascimento" nao apareceu (36 pixels da cor na area (min 150), centro (1863, 457)), fica para a proxima
[14:02:13] renascer
[14:02:14]   "! vermelho no Renascimento" nao apareceu (36 pixels da cor na area (min 150), centro (1863, 457)), fica para a proxima
[14:02:15] melhorar comedouro
[14:02:15]   apertando E x3 (E no comedouro)
[14:02:17]   esperando 2s (esperar o comedouro)
[14:02:19] "melhorar comedouro" feito (1x nesta sessao)
[14:02:19] mandar galo para a torre
[14:02:19]   clicando em "botao TORRE" (960, 992)
[14:02:20] "mandar galo para a torre" feito (1x nesta sessao)
...
[14:31:40] renascer
[14:31:40]   "! vermelho no Renascimento" esta na tela (1887, 469)
[14:31:41]   clicando em "abrir menu Renascimento" (1853, 520)
[14:31:43]   clicando em "botao RENASCER (liberado)" (960, 682)
[14:31:45]   clicando em "fechar menu" (1220, 205)
[14:31:46] "renascer" feito (1x nesta sessao)
[14:31:46] melhorar comedouro
[14:31:46]   apertando E x3 (E no comedouro)
[14:31:48]   esperando 2s (esperar o comedouro)
[14:31:50] "melhorar comedouro" feito (95x nesta sessao)
[14:31:50] mandar galo para a torre
[14:31:50]   clicando em "botao TORRE" (960, 992)
```

Quando libera com o galo ainda na torre:

```
[15:10:02] recuar galo para renascer
[15:10:02]   "! vermelho no Renascimento" esta na tela (1887, 469)
[15:10:02]   clicando em "abrir menu Renascimento" (1853, 520)
[15:10:03]   "VOLTE PRO SEU GALINHEIRO" esta na tela (962, 680)
[15:10:03]   clicando em "fechar menu" (1220, 205)
[15:10:04]   clicando em "botao RECUAR" (960, 992)
[15:10:13] "recuar galo para renascer" feito (1x nesta sessao)
[15:10:13] renascer
[15:10:13]   "! vermelho no Renascimento" esta na tela (1887, 469)
[15:10:13]   clicando em "abrir menu Renascimento" (1853, 520)
[15:10:14]   clicando em "botao RENASCER (liberado)" (960, 682)
[15:10:15]   clicando em "fechar menu" (1220, 205)
[15:10:16] "renascer" feito (2x nesta sessao)
[15:10:16] melhorar comedouro
[15:10:16]   apertando E x3 (E no comedouro)
[15:10:18]   esperando 2s (esperar o comedouro)
[15:10:20] "melhorar comedouro" feito (210x nesta sessao)
[15:10:20] mandar galo para a torre
[15:10:20]   clicando em "botao TORRE" (960, 992)
```

Se o galo demorar mais de 8 s para voltar para casa no seu jogo, aumente o
`"after": 8` do passo "botao RECUAR" no `config.json`.

As linhas "nao apareceu, fica para a proxima" são normais: o **!** ainda não
apareceu, ou o TORRE virou RECUAR porque o galo já está na torre. Entre
parênteses vem a nota que chegou mais perto. Se um botão que está na tela não
for achado, essa linha mostra o quanto faltou. Depois de
cada clique o mouse volta para o meio da janela, para não ficar parado em
cima de um botão.

Para parar, aperte **Ctrl+C** no terminal ou jogue o mouse num **canto da
tela** (ele confere o canto a cada 0,2 s enquanto espera, e antes de cada
clique ou tecla). `run --once` roda cada
tarefa uma vez e sai, o que é bom para testar.

## Se a seta vai no botão mas não clica

O Roblox lê o mouse num nível mais baixo que a maioria dos programas, e
alguns jeitos de simular clique levam a seta até o botão sem que o jogo
perceba. No Windows, o script usa por padrão o jeito que o Roblox costuma
aceitar (`sendinput`): posiciona a seta, dá um empurrãozinho de 2 pixels e
clica, tudo como um mouse de verdade.

Para testar rápido, sem rodar tudo:

```powershell
py auto_rebirth.py clicktest
```

Com o menu Renascimento **fechado**, você tem 5 segundos para pôr o mouse em
cima do botão Renascimento. O script traz o Roblox para a frente e clica ali.
Se o menu abrir, está funcionando. Se não abrir, teste os outros jeitos:

```powershell
py auto_rebirth.py clicktest --method directinput
py auto_rebirth.py clicktest --method pyautogui
```

O que funcionar, coloque no topo do `config.json`, logo depois de
`"window_title": "Roblox",`:

```json
  "click_method": "directinput",
```

Se aparecer no log "o Windows nao deixou trazer o Roblox para a frente",
clique uma vez dentro do Roblox. Um clique numa janela que não está na
frente só serve para trazê-la para a frente, e o jogo não vê esse clique.

## Ajustando o ritmo

Os intervalos ficam em `every_seconds`, no `config.json`. As tarefas rodam
na ordem em que aparecem lá; deixe as quatro com o mesmo intervalo, para que
essa ordem valha em toda rodada.

- **O galo vai para a torre fraco demais e perde cedo:** aumente o intervalo
  das quatro (ex.: `300` para 5 minutos). Assim ele passa mais tempo subindo de
  nível entre uma ida e outra.
- **Dinheiro sobrando:** diminua o intervalo do comedouro ou aumente o
  `repeat` do E.
- **Não quer que ele mande para a torre:** apague a tarefa inteira. O mesmo
  vale para as outras.

## Recortar de novo

Só é preciso se o `check` não achar algum botão que está na tela (por
exemplo, Roblox em outro tamanho de janela). Deixe o botão visível e rode,
trocando o nome do arquivo:

```powershell
py auto_rebirth.py capture templates/botao_torre.png --delay 6
```

Você tem 6 segundos para trocar para o Roblox e pôr o mouse no **canto
superior esquerdo** do botão, e mais 6 para pôr no **canto inferior
direito**.

Dicas:

- **No TORRE, recorte só a palavra, nunca o castelo.** TORRE e RECUAR usam o
  mesmo castelo, só muda a palavra. Com o castelo no recorte, o script pode
  confundir os dois e clicar em RECUAR, tirando o galo da torre. Recorte com o
  galo **em casa**.
- Pegue o mínimo possível de cenário. Os recortes que vêm prontos têm o
  cenário transparente (ignorado na comparação); os feitos pelo `capture`
  não, e por isso o cenário que mudar atrás do botão baixa a nota. Se um
  recorte seu ficar no limite, baixe o `confidence` só daquele passo (ex.:
  `0.75`).
- O `botao_renascer.png` tem que ser o **RENASCER verde**, nunca o AINDA NÃO.

Se não quiser recortar o Renascimento, dá para usar a posição fixa dele. Rode
`py auto_rebirth.py pos`, ponha o mouse em cima do botão, anote o `x` e o `y`
e troque o passo no `config.json`:

```json
{ "name": "abrir menu Renascimento", "pos": [1853, 520], "wait": 0 }
```

A posição fixa só vale enquanto a janela do Roblox não mudar de lugar nem de
tamanho.

## Se o ! não for achado

Rode o `check` com o **!** aparecendo no jogo e olhe a linha dele:

```
  nao achou     ! vermelho no Renascimento: 40 pixels da cor na area (min 150), centro (1890, 470)
```

- **Alguns pixels, mas menos que o mínimo:** a bolinha está menor na sua
  tela. Baixe o `min_pixels` do passo (ex.: `80`). Sem o **!**, a área tem uns
  40 pixels parecidos (da borda da chama); fique acima disso.
- **0 pixels:** a área não está pegando a bolinha, o que normalmente quer
  dizer que a janela é de outro tamanho. Aumente a `area` do passo, por
  exemplo `[0.85, 0.30, 1.0, 0.65]`. Os números são frações da janela do
  Roblox: `[esquerda, topo, direita, baixo]`, onde 0 é a borda
  esquerda/de cima e 1 é a direita/de baixo.

Se a área crescer a ponto de pegar a bolinha de outro botão (Loja, Banda), o
pior que acontece é o script abrir o menu Renascimento à toa: sem o RENASCER
verde, ele fecha o menu e não renasce.

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
| `click_method` | `sendinput` no Windows | jeito de clicar: `sendinput`, `directinput` (só no monitor principal) ou `pyautogui`; veja "Se a seta vai no botão mas não clica" |
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

Cada passo tem **um** destes: `image`, `color`, `pos`, `key` ou `pause`.

| Chave | Padrão | O que faz |
|---|---|---|
| `name` | — | nome que aparece no log |
| `image` | — | recorte do botão (caminho relativo à config) |
| `color` | — | cor viva a procurar, `"#RRGGBB"` (ex.: a bolinha `"#FF3D02"`); exige `area` |
| `area` | a janela toda | `[esquerda, topo, direita, baixo]` em fração da janela (0 a 1); com `image` ou `color`, só procura ali |
| `min_pixels` | `100` | com `color`: quantos pixels da cor contam como achado |
| `click` | `true` | com `false`, só confere se o botão (ou a cor) está na tela, sem clicar |
| `pos` | — | `[x, y]` fixo a clicar |
| `key` | — | tecla a apertar: uma letra ou número (`"e"`), ou `space`, `enter`, `tab`, `esc`, `shift`, `ctrl`, `alt`, setas (`up`...), `f1`...`f12` |
| `pause` | — | só espera esses segundos (ex.: `2`), sem olhar a tela |
| `hold` | `0` | segundos segurando a tecla (para prompt de "segure E") |
| `repeat` | `1` | quantas vezes clica ou aperta |
| `wait` | `3` | segundos esperando o botão aparecer (`0`: olha uma vez só) |
| `after` | `0.8` | pausa depois de cada clique ou tecla |
| `optional` | `false` | se o botão não aparecer, segue em vez de interromper a tarefa |
| `confidence`, `color_tolerance` | os da config | ajuste só para este passo |

Um passo obrigatório que não aparece interrompe a tarefa até a próxima vez.
É assim que a falta do **!** faz o script nem abrir o menu, e o RECUAR faz ele
não mexer no galo. O `cleanup` nunca interrompe nada: se o botão não está lá,
ele pula. Ele roda até quando a tarefa para no primeiro passo, e por isso
fecha o menu se alguém o deixou aberto.

## Como ele reconhece os botões

- **Formato:** compara o recorte com cada pedaço da tela (OpenCV) e pega o
  lugar mais parecido. A nota vai de 0 a 1.
- **Cor:** a cor média do trecho achado tem que bater com a do recorte. É o
  que separa, por exemplo, um botão aceso de um escurecido pelo menu aberto.
- **Transparência:** se o PNG do recorte tem partes transparentes, elas ficam
  de fora da comparação. Os recortes prontos usam isso para ignorar o cenário
  3D atrás dos botões da lateral e da barra de baixo, que muda quando a
  câmera gira.
- **Passo de cor:** conta os pixels do mesmo tom (matiz) da cor pedida dentro
  da área. Compara o tom e não o brilho, então uma bolinha que pisca mais
  clara ou mais escura continua contando. Serve para coisas animadas, como a
  bolinha do **!**: um recorte de tamanho fixo só bate nos quadros em que a
  animação está igual ao print.

No Windows as teclas vão pelo `pydirectinput`, que manda o mesmo código de
um teclado de verdade. Jogos em DirectX, como o Roblox, costumam ignorar o
jeito mais simples de simular tecla.

O formato antigo da config, com `steps` e `cleanup` direto no topo e sem
`tasks`, continua valendo como uma tarefa só, chamada "renascer".

## Testes

Os testes não precisam do Roblox. Eles usam uma tela simulada com OpenCV e
pedaços de prints reais do jogo, em `tests/fixtures/`:

```powershell
py -m unittest discover -s tests
```
