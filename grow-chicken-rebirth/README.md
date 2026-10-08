# grow-chicken-rebirth

Ciclo automático no **Grow a Chicken Fighter**, do Roblox: melhora o
comedouro, manda o galo para a torre e renasce quando libera.

O script olha a tela como você olharia e roda três **tarefas**, cada uma no
seu intervalo:

| Tarefa | Padrão | O que faz |
|---|---|---|
| melhorar comedouro | a cada 10 s | aperta **E** 3 vezes; o boneco tem que estar parado ao lado do comedouro |
| mandar galo para a torre | a cada 10 s | se o botão de baixo mostra **TORRE**, clica; se mostra **RECUAR**, o galo já está lá e não faz nada |
| renascer | a cada 20 s | olha se o botão **Renascimento** está com o **!** vermelho; só então abre o menu, clica em **RENASCER** e fecha |

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
| `renascimento_alerta.png` | o **!** vermelho em cima do Renascimento, com um pedaço da chama |
| `renascimento.png` | o botão Renascimento, na lateral direita |
| `botao_torre.png` | **só a palavra TORRE**, embaixo do castelo |
| `botao_renascer.png` | RENASCER verde, dentro do menu |
| `fechar_menu.png` | o X vermelho do menu |

Confira se eles batem com a sua tela:

```powershell
py auto_rebirth.py check
```

Você tem 3 segundos para trocar para o Roblox. Ele tira um print e diz, para
cada botão da config, se achou ou não. Esta é a saída com o seu print do
comedouro (menu fechado, galo em casa, renascimento liberado):

```
melhorar comedouro:
  tecla         E no comedouro: E (o check nao testa tecla)

mandar galo para a torre:
  ACHOU         botao TORRE: formato 1.00 (min 0.90), cor 0 (max 40), melhor lugar (960, 992)

renascer:
  ACHOU         ! vermelho no Renascimento: formato 1.00 (min 0.85), cor 0 (max 40), melhor lugar (1881, 477)
  ACHOU         abrir menu Renascimento: formato 1.00 (min 0.85), cor 0 (max 40), melhor lugar (1853, 520)
  nao achou     botao RENASCER (liberado): formato 0.30 (min 0.85), cor 73 (max 40), melhor lugar (546, 576)
  nao achou     fechar menu: formato 0.45 (min 0.85), cor 69 (max 40), melhor lugar (1045, 360)
```

O `check` só vê o que está na tela no momento. Rode algumas vezes:

1. **menu fechado e galo em casa:** tem que achar **Renascimento** e
   **TORRE**; o **!** só se o renascimento estiver liberado;
2. **galo na torre** (botão mostrando RECUAR): **TORRE** tem que dar "nao
   achou";
3. **menu Renascimento aberto:** tem que achar o **X**, e o **RENASCER** só se
   estiver liberado.

Os botões de dentro do menu dão "nao achou" com o menu fechado, e vice-versa.
Isso é normal.

Como ler o resultado:

- **"formato" abaixo do mínimo num botão que está na tela:** o recorte não
  bate com a sua tela. Veja "Recortar de novo".
- **"cor" acima do máximo num botão que está na tela:** idem.
- **TORRE "ACHOU" com o galo na torre:** perigo, ele tiraria o galo da torre.
  Recorte de novo só a palavra, ou suba o `confidence` desse passo.
- **! "ACHOU" sem o ! na tela:** suba o `confidence` desse passo.

## 2. Rodar

Deixe o boneco parado ao lado do comedouro e rode:

```powershell
py auto_rebirth.py run
```

```
[14:02:11] tarefa "melhorar comedouro": a cada 10s
[14:02:11] tarefa "mandar galo para a torre": a cada 10s
[14:02:11] tarefa "renascer": a cada 20s
[14:02:11] rodando. Para parar: Ctrl+C aqui, ou mouse num canto da tela.
[14:02:11] melhorar comedouro
[14:02:11]   apertando E x3 (E no comedouro)
[14:02:13] mandar galo para a torre
[14:02:13]   clicando em "botao TORRE" (960, 992)
[14:02:15] renascer
[14:02:15]   "! vermelho no Renascimento" nao apareceu, fica para a proxima
...
[14:31:40] renascer
[14:31:40]   "! vermelho no Renascimento" esta na tela (1881, 477)
[14:31:40]   clicando em "abrir menu Renascimento" (1853, 520)
[14:31:42]   clicando em "botao RENASCER (liberado)" (960, 682)
[14:31:43]   clicando em "fechar menu" (1220, 205)
[14:31:44] "renascer" feito (1x nesta sessao)
```

Para parar, aperte **Ctrl+C** no terminal ou jogue o mouse num **canto da
tela** (o failsafe do pyautogui interrompe na hora). `run --once` roda cada
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

Os intervalos ficam em `every_seconds`, no `config.json`:

- **O galo vai para a torre fraco demais e perde cedo:** aumente o intervalo
  da torre (ex.: `300` para 5 minutos). Assim ele passa mais tempo subindo de
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
- **No !, pegue a bolinha vermelha e só um pedacinho da chama.** A bolinha
  sozinha é igual à da Guilda (que mostra "1"), e a chama é o que diz que é a
  do Renascimento.
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

Cada passo tem **um** destes: `image`, `pos` ou `key`.

| Chave | Padrão | O que faz |
|---|---|---|
| `name` | — | nome que aparece no log |
| `image` | — | recorte do botão (caminho relativo à config) |
| `click` | `true` | com `false`, só confere se o botão está na tela, sem clicar |
| `pos` | — | `[x, y]` fixo a clicar |
| `key` | — | tecla a apertar: uma letra ou número (`"e"`), ou `space`, `enter`, `tab`, `esc`, `shift`, `ctrl`, `alt`, setas (`up`...), `f1`...`f12` |
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
