# grow-chicken-rebirth

Renascimento (rebirth) automático no **Grow a Chicken Fighter**, do Roblox.

O script olha a tela como você olharia. A cada ciclo ele:

1. clica no botão **Renascimento**, na lateral direita;
2. olha o botão grande do menu: se está **RENASCER** (verde), clica; se está
   **AINDA NÃO** (marrom), não clica;
3. fecha o menu no X e espera o próximo ciclo (padrão: 30 s).

O RENASCER aparece quando a barra "Andar da torre" completa (ex.: 58 / 49).

Ele não injeta script no Roblox, não usa executor e não lê a memória do jogo.
São só cliques de mouse, como um auto clicker que enxerga a tela.

## Antes de usar

- **Feito para Windows**, com Python 3.12 ou mais novo. Foi testado num Linux
  com tela virtual, contra uma imitação do menu do jogo, e o reconhecimento do
  RENASCER x AINDA NÃO foi conferido em prints reais do jogo. No Windows, com
  o Roblox de verdade, ainda não foi rodado.
- **O Roblox tem que estar visível.** Pode estar em janela, mas não pode estar
  minimizado nem coberto por outra janela. A cada ciclo o script traz o Roblox
  para a frente e move o mouse, então use o PC para outra coisa só se não se
  importar com isso.
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
| `botao_renascer.png` | RENASCER verde, dentro do menu | já vem pronto |
| `fechar_menu.png` | o X vermelho do menu | já vem pronto |

Os dois que já vêm prontos foram recortados de um print do jogo com a janela
em cerca de 1920 px de largura. Se o seu Roblox está em outro tamanho e o
`check` (passo 2) não achar esses dois, recorte de novo.

Para recortar, deixe o botão visível no Roblox e rode:

```powershell
py auto_rebirth.py capture templates/renascimento.png
```

Você tem 4 segundos para pôr o mouse no **canto superior esquerdo** do botão
e mais 4 segundos para pôr no **canto inferior direito**.

Dicas:

- Pegue o miolo do botão (texto e ícone), sem o cenário 3D em volta. O
  cenário muda quando a câmera mexe e atrapalha a comparação.
- O `botao_renascer.png` tem que ser o **RENASCER verde**, nunca o AINDA NÃO.

## 2. Testar os recortes

```powershell
py auto_rebirth.py check
```

Você tem 3 segundos para trocar para o Roblox. Ele tira um print e diz, para
cada botão da config, se achou ou não. Com o menu aberto e o botão em AINDA
NÃO, por exemplo:

```
steps:
  ...
  nao achou  botao RENASCER (liberado): formato 0.39 (min 0.85), cor 63 (max 40), melhor lugar (354, 549)
cleanup:
  ACHOU      fechar menu: formato 1.00 (min 0.85), cor 0 (max 40), melhor lugar (629, 72)
```

O `check` só vê o que está na tela no momento. Rode uma vez com o menu
fechado, para testar o botão Renascimento da lateral, e outra com o menu
aberto, para os de dentro. Com o menu aberto, os botões da lateral somem, por
isso "abrir menu" não acha nada nesse caso.

Como ler o resultado:

- **"formato" abaixo do mínimo num botão que está na tela:** recorte de novo,
  pegando menos cenário. Ou baixe o `confidence` só desse passo (ex.: `0.75`).
- **"cor" acima do máximo num botão que está na tela:** recorte de novo.
- **RENASCER "nao achou" enquanto o botão está em AINDA NÃO:** é o certo. É
  assim que o script sabe que ainda não liberou.

## 3. Rodar

```powershell
py auto_rebirth.py run
```

```
[14:02:11] janela "Roblox" encontrada
[14:02:11] rodando: um ciclo a cada 30s. Para parar: Ctrl+C aqui, ou mouse num canto da tela.
[14:02:11] verificando rebirth...
[14:02:11]   clicando em "abrir menu Renascimento" (1853, 495)
[14:02:15]   "botao RENASCER (liberado)" nao apareceu: rebirth ainda nao liberado, tento de novo depois
[14:02:15]   clicando em "fechar menu" (1220, 205)
[14:02:46] verificando rebirth...
...
[14:09:30] rebirth feito (1 nesta sessao)
```

Para parar, aperte **Ctrl+C** no terminal ou jogue o mouse num **canto da
tela** (o failsafe do pyautogui interrompe na hora). `run --once` faz um
ciclo só e sai, o que é bom para testar.

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

## Se o jogo pedir confirmação

Pelos prints, o RENASCER renasce direto. Se aparecer uma tela de
confirmação, recorte o botão dela
(`py auto_rebirth.py capture templates/confirmar.png`) e acrescente este
passo depois do RENASCER, em `steps`:

```json
{ "name": "confirmar", "image": "templates/confirmar.png", "wait": 3, "optional": true }
```

## Config

| Chave | Padrão | O que faz |
|---|---|---|
| `window_title` | `"Roblox"` | título da janela; a busca fica restrita a ela |
| `interval_seconds` | `30` | espera entre um ciclo e outro |
| `confidence` | `0.85` | nota mínima de formato (0 a 1) |
| `color_tolerance` | `40` | diferença máxima de cor (0 a 255) |
| `steps` | — | passos do ciclo, em ordem |
| `cleanup` | `[]` | passos que rodam sempre no fim do ciclo, deu certo ou não |

Cada passo:

| Chave | Padrão | O que faz |
|---|---|---|
| `name` | — | nome que aparece no log |
| `image` | — | recorte do botão (caminho relativo à config) |
| `pos` | — | `[x, y]` fixo, no lugar de `image` |
| `wait` | `3` | segundos esperando o botão aparecer |
| `after` | `0.8` | pausa depois do clique |
| `optional` | `false` | se não aparecer, segue em vez de interromper o ciclo |
| `confidence`, `color_tolerance` | os da config | ajuste só para este passo |

Um passo obrigatório que não aparece interrompe o ciclo. É assim que o AINDA
NÃO faz o script desistir até o próximo ciclo. O `cleanup` nunca interrompe
nada: se o botão não está lá, ele pula.

Além do formato, o script compara a cor média do trecho achado com a do
recorte. Assim um botão parecido, mas de outra cor, não é confundido.

## Testes

Os testes não precisam do Roblox. Eles usam uma tela simulada com OpenCV e
pedaços de prints reais do menu, em `tests/fixtures/`:

```powershell
py -m unittest discover -s tests
```
