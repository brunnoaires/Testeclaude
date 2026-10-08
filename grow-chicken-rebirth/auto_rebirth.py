#!/usr/bin/env python3
"""
auto_rebirth — ciclo automatico no Grow a Chicken Fighter (Roblox):
melhorar comedouro, mandar o galo para a torre e renascer.

Funciona olhando a tela, como voce faria: procura os botoes que voce recortou
em templates/ e clica neles, ou aperta teclas, conforme as tarefas da config.
Nao injeta script no Roblox nem le memoria do jogo.

  python auto_rebirth.py capture templates/botao_torre.png  recorta um botao
  python auto_rebirth.py check                              testa os recortes
  python auto_rebirth.py run                                roda as tarefas
  python auto_rebirth.py pos                                mostra a posicao do mouse
  python auto_rebirth.py clicktest                          testa se o Roblox aceita o clique

Para parar: Ctrl+C no terminal, ou leve o mouse para um canto da tela.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from vision import (Frame, area_box, color_hsv, find_color, find_template, has_detail, load_template,
                    parse_color, save_image)

POLL_SECONDS = 0.3

TOP_KEYS = {'window_title', 'click_method', 'interval_seconds', 'confidence', 'color_tolerance',
            'tasks', 'steps', 'cleanup'}
# sendinput: posiciona com SetCursorPos e mexe/clica por SendInput (padrao no Windows)
# directinput: tudo por SendInput, inclusive o posicionamento (so no monitor principal)
# pyautogui: o jeito antigo; no Roblox a seta chega no botao mas o clique pode nao pegar
CLICK_METHODS = ('sendinput', 'directinput', 'pyautogui')
TASK_KEYS = {'name', 'every_seconds', 'steps', 'cleanup'}
STEP_KEYS = {'name', 'image', 'pos', 'key', 'color', 'pause', 'area', 'min_pixels', 'click', 'hold', 'repeat',
             'wait', 'after', 'optional',
             'confidence', 'color_tolerance'}
KEY_NAMES = {'space', 'enter', 'tab', 'esc', 'shift', 'ctrl', 'alt', 'up', 'down', 'left', 'right',
             *(f'f{i}' for i in range(1, 13))}


class ConfigError(Exception):
    pass


@dataclass
class Step:
    name: str
    image: Path | None = None
    pos: tuple | None = None
    key: str | None = None
    pause: float | None = None   # passo que so espera esses segundos
    color: tuple | None = None   # (b, g, r) da mancha de cor procurada
    area: tuple | None = None    # (esquerda, topo, direita, baixo), fracao da janela
    min_pixels: int = 100        # pixels da cor para contar como achado
    hold: float = 0.0         # segundos segurando a tecla
    repeat: int = 1           # quantas vezes clica / aperta
    wait: float = 3.0         # segundos esperando o botao aparecer
    after: float = 0.8        # pausa depois de cada clique / tecla
    optional: bool = False    # se nao aparecer, segue para o proximo passo
    click: bool = True        # False: so confere se o botao esta na tela
    confidence: float = 0.85
    color_tolerance: float = 40.0
    template: object = None
    mask: object = None       # pixels do botao (True) x cenario (False), da transparencia do PNG


@dataclass
class Task:
    name: str
    every_seconds: float
    steps: list
    cleanup: list = field(default_factory=list)


@dataclass
class Config:
    window_title: str = 'Roblox'
    click_method: str | None = None   # None: sendinput no Windows, pyautogui no resto
    tasks: list = field(default_factory=list)


def log(msg):
    print(f'[{datetime.now():%H:%M:%S}] {msg}', flush=True)


# --------------------------------------------------------------------------
# Config

def _number(raw, key, default, where, lo=0.0, hi=None):
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f'{where}: "{key}" tem que ser numero')
    if value < lo or (hi is not None and value > hi):
        limit = f'entre {lo} e {hi}' if hi is not None else f'>= {lo}'
        raise ConfigError(f'{where}: "{key}" tem que ser {limit}')
    return float(value)


def _parse_step(raw, base, defaults, where):
    if not isinstance(raw, dict):
        raise ConfigError(f'{where}: cada passo tem que ser um objeto {{ ... }}')
    unknown = set(raw) - STEP_KEYS
    if unknown:
        raise ConfigError(f'{where}: chave desconhecida {", ".join(sorted(unknown))}')
    name = str(raw.get('name') or where)
    where = f'{where} ("{name}")'
    if sum(k in raw for k in ('image', 'pos', 'key', 'color', 'pause')) != 1:
        raise ConfigError(f'{where}: use "image", "pos", "key", "color" ou "pause" (exatamente um)')

    step = Step(
        name=name,
        hold=_number(raw, 'hold', 0.0, where),
        repeat=int(_number(raw, 'repeat', 1, where, 1, 100)),
        wait=_number(raw, 'wait', 3.0, where),
        after=_number(raw, 'after', 0.8, where),
        optional=bool(raw.get('optional', False)),
        click=raw.get('click', True),
        confidence=_number(raw, 'confidence', defaults['confidence'], where, 0.0, 1.0),
        color_tolerance=_number(raw, 'color_tolerance', defaults['color_tolerance'], where, 0.0, 255.0),
        min_pixels=int(_number(raw, 'min_pixels', 100, where, 1)),
    )
    if not isinstance(step.click, bool):
        raise ConfigError(f'{where}: "click" tem que ser true ou false')
    if not step.click and 'image' not in raw and 'color' not in raw:
        raise ConfigError(f'{where}: "click": false so vale com "image" ou "color"')
    if 'area' in raw:
        if 'image' not in raw and 'color' not in raw:
            raise ConfigError(f'{where}: "area" so vale com "image" ou "color"')
        area = raw['area']
        if (not isinstance(area, list) or len(area) != 4
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1 for v in area)
                or area[0] >= area[2] or area[1] >= area[3]):
            raise ConfigError(f'{where}: "area" tem que ser [esquerda, topo, direita, baixo], numeros de 0 a 1 '
                              f'(fracao da janela), com esquerda < direita e topo < baixo')
        step.area = tuple(float(v) for v in area)
    if 'color' in raw:
        try:
            step.color = parse_color(raw['color']) if isinstance(raw['color'], str) else None
        except ValueError:
            step.color = None
        if step.color is None:
            raise ConfigError(f'{where}: "color" tem que ser no formato "#RRGGBB" (ex.: "#FF3D02")')
        if color_hsv(step.color)[1] < 100:
            raise ConfigError(f'{where}: a cor {raw["color"]} e apagada demais para achar pela cor; '
                              f'isso funciona com cores vivas, como a bolinha vermelha de notificacao')
        if step.area is None:
            raise ConfigError(f'{where}: passo com "color" precisa de "area": a mesma cor costuma '
                              f'aparecer em outros lugares da tela')
        return step
    if 'image' in raw:
        step.image = (base / raw['image']).resolve()
        if not step.image.is_file():
            raise ConfigError(
                f'{where}: imagem nao encontrada: {step.image}\n'
                f'  recorte com: python auto_rebirth.py capture {raw["image"]}\n'
                f'  ou remova esse passo da config se o jogo nao tiver esse botao')
        try:
            step.template, step.mask = load_template(step.image)
        except ValueError as e:
            raise ConfigError(f'{where}: {e}') from None
        if not has_detail(step.template, step.mask):
            raise ConfigError(f'{where}: {step.image.name} e uma cor lisa, sem detalhe para '
                              f'comparar. Recorte de novo pegando o texto do botao.')
    elif 'pos' in raw:
        pos = raw['pos']
        if (not isinstance(pos, list) or len(pos) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pos)):
            raise ConfigError(f'{where}: "pos" tem que ser [x, y]')
        step.pos = (int(pos[0]), int(pos[1]))
    elif 'pause' in raw:
        step.pause = _number(raw, 'pause', 0, where, 0.1, 3600)
    else:
        key = raw['key']
        if not isinstance(key, str) or not (len(key) == 1 and key.isalnum() or key.lower() in KEY_NAMES):
            raise ConfigError(f'{where}: "key" tem que ser uma letra ou numero ("e"), ou um destes: '
                              f'{", ".join(sorted(KEY_NAMES))}')
        step.key = key.lower()
    return step


def _parse_task(raw, base, defaults, where):
    if not isinstance(raw, dict):
        raise ConfigError(f'{where}: cada tarefa tem que ser um objeto {{ ... }}')
    unknown = set(raw) - TASK_KEYS
    if unknown:
        raise ConfigError(f'{where}: chave desconhecida {", ".join(sorted(unknown))}')
    name = str(raw.get('name') or where)
    where = f'{where} ("{name}")'
    steps = raw.get('steps') or []
    cleanup = raw.get('cleanup') or []
    if not isinstance(steps, list) or not steps:
        raise ConfigError(f'{where}: precisa de uma lista "steps" com pelo menos um passo')
    if not isinstance(cleanup, list):
        raise ConfigError(f'{where}: "cleanup" tem que ser uma lista')
    return Task(
        name=name,
        every_seconds=_number(raw, 'every_seconds', defaults['interval_seconds'], where, 1.0),
        steps=[_parse_step(s, base, defaults, f'{where} steps[{i}]') for i, s in enumerate(steps)],
        cleanup=[_parse_step(s, base, defaults, f'{where} cleanup[{i}]') for i, s in enumerate(cleanup)],
    )


def _click_method(value):
    if value is None:
        return None
    if value not in CLICK_METHODS:
        raise ConfigError(f'"click_method" tem que ser um destes: {", ".join(CLICK_METHODS)}')
    return value


def load_config(path):
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f'config nao encontrada: {path}\n'
                          f'  copie config.example.json para config.json e ajuste')
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ConfigError(f'{path}: JSON invalido na linha {e.lineno}: {e.msg}') from None
    if not isinstance(raw, dict):
        raise ConfigError(f'{path}: a config tem que ser um objeto {{ ... }}')
    unknown = set(raw) - TOP_KEYS
    if unknown:
        raise ConfigError(f'chave desconhecida na config: {", ".join(sorted(unknown))}')

    defaults = {
        'interval_seconds': _number(raw, 'interval_seconds', 30.0, 'config', 1.0),
        'confidence': _number(raw, 'confidence', 0.85, 'config', 0.0, 1.0),
        'color_tolerance': _number(raw, 'color_tolerance', 40.0, 'config', 0.0, 255.0),
    }
    base = path.resolve().parent

    if 'tasks' in raw:
        if 'steps' in raw or 'cleanup' in raw:
            raise ConfigError('use "tasks" ou "steps"/"cleanup" no topo da config, nao os dois')
        tasks = raw['tasks']
        if not isinstance(tasks, list) or not tasks:
            raise ConfigError('"tasks" tem que ser uma lista com pelo menos uma tarefa')
    else:
        # Formato curto: uma tarefa so, com os passos no topo da config.
        tasks = [{'name': 'renascer', 'steps': raw.get('steps'), 'cleanup': raw.get('cleanup', [])}]
    return Config(
        window_title=str(raw.get('window_title', 'Roblox')),
        click_method=_click_method(raw.get('click_method')),
        tasks=[_parse_task(t, base, defaults, f'tasks[{i}]') for i, t in enumerate(tasks)],
    )


# --------------------------------------------------------------------------
# Logica (sem dependencia de tela/mouse/teclado, testavel)

def match_step(step, frame):
    """Procura um passo de imagem ou de cor num print. Devolve (achou, ponto
    na tela, descricao para o check)."""
    img, ox, oy = frame.image, 0, 0
    if step.area:
        x1, y1, x2, y2 = area_box(img.shape, step.area)
        img, ox, oy = img[y1:y2, x1:x2], x1, y1
    if step.color:
        m = find_color(img, step.color, step.min_pixels)
        point = frame.to_screen(m.center[0] + ox, m.center[1] + oy)
        return m.found, point, f'{m.count} pixels da cor na area (min {step.min_pixels}), centro {point}'
    m = find_template(img, step.template, step.confidence, step.color_tolerance, step.mask)
    point = frame.to_screen(m.center[0] + ox, m.center[1] + oy)
    return m.found, point, (f'formato {m.score:.2f} (min {step.confidence:.2f}), '
                            f'cor {m.color_diff:.0f} (max {step.color_tolerance:.0f}), melhor lugar {point}')


class Bot:
    def __init__(self, grab, click, press, sleep=time.sleep, clock=time.monotonic, log=log):
        self.grab = grab
        self.click = click
        self.press = press
        self.sleep = sleep
        self.clock = clock
        self.log = log
        self.last_detail = ''

    def locate(self, step):
        """Procura o passo uma vez. Devolve (x, y) em coordenadas do mouse, ou None.
        Guarda em last_detail a nota que chegou mais perto, para o log."""
        if step.pos:
            return step.pos
        found, point, self.last_detail = match_step(step, self.grab())
        return point if found else None

    def wait_for(self, step):
        deadline = self.clock() + step.wait
        while True:
            point = self.locate(step)
            if point or self.clock() >= deadline:
                return point
            self.sleep(POLL_SECONDS)

    def do_step(self, step):
        times = f' x{step.repeat}' if step.repeat > 1 else ''
        if step.pause:
            self.log(f'  esperando {step.pause:g}s ({step.name})')
            self.sleep(step.pause)
            return True
        if step.key:
            self.log(f'  apertando {step.key.upper()}{times} ({step.name})')
            for _ in range(step.repeat):
                self.press(step.key, step.hold)
                self.sleep(step.after)
            return True
        point = self.wait_for(step)
        if point is None:
            return False
        if not step.click:
            self.log(f'  "{step.name}" esta na tela {point}')
            return True
        self.log(f'  clicando em "{step.name}" {point}{times}')
        for _ in range(step.repeat):
            self.click(*point)
            self.sleep(step.after)
        return True

    def run_task(self, task):
        """Roda uma tarefa. True se todos os passos obrigatorios foram feitos.

        Um passo obrigatorio que nao aparece interrompe a tarefa (ex.: RENASCER
        ainda em AINDA NAO, ou TORRE trocado por RECUAR porque o galo ja esta
        la). O cleanup roda sempre, para o jogo voltar ao estado de partida
        (menu fechado) antes da proxima tarefa.
        """
        done = True
        for step in task.steps:
            if self.do_step(step):
                continue
            why = f' ({self.last_detail})' if self.last_detail and not step.key and not step.pos else ''
            if step.optional:
                self.log(f'  "{step.name}" nao apareceu{why} (opcional), seguindo')
                continue
            self.log(f'  "{step.name}" nao apareceu{why}, fica para a proxima')
            done = False
            break
        for step in task.cleanup:
            self.do_step(step)
        return done


class Runner:
    """Roda cada tarefa no seu intervalo, uma de cada vez, na ordem da config."""

    def __init__(self, cfg, bot, clock=time.monotonic, focus=lambda: None, log=log):
        self.cfg = cfg
        self.bot = bot
        self.clock = clock
        self.focus = focus
        self.log = log
        self.next_run = [0.0] * len(cfg.tasks)
        self.done = [0] * len(cfg.tasks)

    def tick(self):
        """Roda as tarefas vencidas. Devolve quantos segundos esperar ate a proxima."""
        for i, task in enumerate(self.cfg.tasks):
            if self.clock() < self.next_run[i]:
                continue
            self.focus()
            self.log(f'{task.name}')
            if self.bot.run_task(task):
                self.done[i] += 1
                self.log(f'"{task.name}" feito ({self.done[i]}x nesta sessao)')
            self.next_run[i] = self.clock() + task.every_seconds
        return max(0.2, min(self.next_run) - self.clock())

    def summary(self):
        return ', '.join(f'{t.name}: {n}x' for t, n in zip(self.cfg.tasks, self.done))


# --------------------------------------------------------------------------
# Tela, mouse, teclado e janela (so roda na maquina com o Roblox)

def _dpi_aware():
    # Sem isso, com escala de 125%/150% do Windows a captura e o mouse usam
    # coordenadas diferentes e o clique cai fora do botao.
    if sys.platform != 'win32':
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _find_window(title):
    if not title:
        return None
    try:
        import pygetwindow as gw
        wins = [w for w in gw.getAllWindows() if w.title.strip() == title]
        wins = [w for w in wins if not w.isMinimized and w.width > 0 and w.height > 0]
    except Exception:
        return None
    return wins[0] if wins else None


def _window_region(title, screen):
    win = _find_window(title)
    if win is None:
        return None
    left, top = max(win.left, screen['left']), max(win.top, screen['top'])
    right = min(win.left + win.width, screen['left'] + screen['width'])
    bottom = min(win.top + win.height, screen['top'] + screen['height'])
    if right - left < 50 or bottom - top < 50:
        return None
    return {'left': left, 'top': top, 'width': right - left, 'height': bottom - top}


def make_grabber(window_title):
    import mss
    import numpy as np

    sct = (getattr(mss, 'MSS', None) or mss.mss)()  # mss.mss foi renomeado na 10.x

    def grab():
        screen = sct.monitors[0]
        region = _window_region(window_title, screen) or screen
        shot = sct.grab(region)
        image = np.ascontiguousarray(np.asarray(shot)[:, :, :3])  # BGRA -> BGR
        return Frame(image, region['left'], region['top'], shot.width / region['width'])

    return grab


def _directinput():
    import pydirectinput
    pydirectinput.FAILSAFE = False  # o failsafe vale pelo do pyautogui (todos os cantos)
    return pydirectinput


def make_clicker(method=None, park=None):
    """Clica em (x, y). Depois leva o mouse para park() (centro do Roblox):
    parado em cima do botao, o hover do Roblox pode mudar o desenho dele e o
    recorte nao bater mais na proxima vez."""
    import pyautogui
    pyautogui.FAILSAFE = True
    park = park or (lambda: None)

    method = method or ('sendinput' if sys.platform == 'win32' else 'pyautogui')
    if method != 'pyautogui' and sys.platform != 'win32':
        raise SystemExit(f'click_method "{method}" so existe no Windows; use "pyautogui"')

    if method == 'pyautogui':
        def click(x, y):
            pyautogui.moveTo(x, y, duration=0.15)
            pyautogui.moveRel(3, 0, duration=0.05)
            pyautogui.moveRel(-3, 0, duration=0.05)
            pyautogui.mouseDown()
            time.sleep(0.06)
            pyautogui.mouseUp()
            rest = park()
            if rest:
                pyautogui.moveTo(*rest, duration=0.1)
        return click

    di = _directinput()

    def move(x, y):
        if method == 'directinput':
            di.moveTo(x, y)
        else:
            pyautogui.moveTo(x, y, duration=0.15)

    def click(x, y):
        pyautogui.failSafeCheck()
        move(x, y)
        # O Roblox le o mouse em baixo nivel (raw input). SetCursorPos, que o
        # pyautogui usa, teletransporta a seta sem gerar esse evento: a seta
        # chega no botao, mas para o Roblox o mouse nao esta em cima dele e o
        # clique e ignorado. Um empurrao relativo por SendInput gera o evento,
        # como um mouse de verdade. Cada chamada do pydirectinput ja espera
        # 0.1 s depois (PAUSE), o que da tempo do Roblox ver cada passo.
        di.moveRel(2, 0, relative=True)
        di.moveRel(-2, 0, relative=True)
        di.mouseDown()
        di.mouseUp()
        rest = park()
        if rest:
            move(*rest)
            di.moveRel(2, 0, relative=True)  # para o Roblox ver o mouse saindo do botao
            di.moveRel(-2, 0, relative=True)

    return click


def _window_center(title):
    win = _find_window(title)
    if win is None:  # sem a janela, o centro da tela principal
        import pyautogui
        w, h = pyautogui.size()
        return w // 2, h // 2
    return win.left + win.width // 2, win.top + win.height // 2


def _sleep_watching_failsafe(seconds):
    """Espera conferindo o canto da tela a cada 0.2 s, para o failsafe parar
    o script na hora, e nao so na proxima tecla ou clique."""
    import pyautogui
    end = time.monotonic() + seconds
    while True:
        pyautogui.failSafeCheck()
        left = end - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(0.2, left))


def make_presser():
    import pyautogui

    if sys.platform == 'win32':
        # Jogos em DirectX, o Roblox incluso, costumam ignorar a tecla virtual
        # que o pyautogui manda; o pydirectinput manda scan code, como o
        # teclado de verdade.
        keys = _directinput()
    else:
        keys = pyautogui

    def press(key, hold):
        pyautogui.failSafeCheck()  # mouse no canto para tambem as tarefas so de tecla
        keys.keyDown(key)
        time.sleep(max(hold, 0.05))
        keys.keyUp(key)

    return press


def _focus(title):
    """Traz o Roblox para a frente. Devolve False se nao conseguiu.

    Se o Roblox nao estiver na frente, o primeiro clique so foca a janela e o
    jogo nao ve o clique.
    """
    win = _find_window(title)
    if win is None:
        return False
    try:
        win.activate()
    except Exception:
        pass  # pygetwindow as vezes reclama mesmo quando funcionou
    if sys.platform != 'win32':
        return True
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = getattr(win, '_hWnd', None)
    if not hwnd or user32.GetForegroundWindow() == hwnd:
        return True
    # O Windows so deixa trocar a janela da frente quem recebeu a ultima
    # tecla. Um ALT sintetico libera (truque conhecido do SetForegroundWindow).
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    return user32.GetForegroundWindow() == hwnd


def _describe_window(title):
    if not title:
        log('window_title vazio: procurando na tela inteira')
    elif _find_window(title):
        log(f'janela "{title}" encontrada')
    else:
        log(f'AVISO: janela "{title}" nao encontrada (fechada ou minimizada?). '
            f'Procurando na tela inteira.')


# --------------------------------------------------------------------------
# Comandos

def cmd_run(cfg, once):
    import pyautogui

    _describe_window(cfg.window_title)
    clicker = make_clicker(cfg.click_method, park=lambda: _window_center(cfg.window_title))
    bot = Bot(make_grabber(cfg.window_title), clicker, make_presser(), sleep=_sleep_watching_failsafe)
    warned = []

    def focus():
        if not _focus(cfg.window_title) and not warned and _find_window(cfg.window_title):
            warned.append(1)
            log('AVISO: o Windows nao deixou trazer o Roblox para a frente. Clique uma vez '
                'dentro do Roblox; se os cliques nao pegarem, e isso.')

    runner = Runner(cfg, bot, focus=focus)
    for task in cfg.tasks:
        log(f'tarefa "{task.name}": a cada {task.every_seconds:g}s')
    log('rodando. Para parar: Ctrl+C aqui, ou mouse num canto da tela.')
    try:
        while True:
            wait = runner.tick()
            if once:
                break
            _sleep_watching_failsafe(wait)
    except KeyboardInterrupt:
        print()
    except pyautogui.FailSafeException:
        print()
        log('mouse no canto da tela: parado pelo failsafe')
    log(f'fim. {runner.summary()}')


def _countdown(msg, seconds):
    for s in range(seconds, 0, -1):
        print(f'\r{msg}... {s} ', end='', flush=True)
        time.sleep(1)
    print(f'\r{msg}... ok   ')


def cmd_check(cfg, delay):
    grab = make_grabber(cfg.window_title)
    _describe_window(cfg.window_title)
    _countdown('Deixe o Roblox na frente, capturando em', delay)
    frame = grab()
    h, w = frame.image.shape[:2]
    print(f'Captura: {w}x{h} a partir de ({frame.left}, {frame.top})')
    for task in cfg.tasks:
        print(f'\n{task.name}:')
        for step in task.steps + task.cleanup:
            if step.key:
                print(f'  tecla         {step.name}: {step.key.upper()} (o check nao testa tecla)')
                continue
            if step.pause:
                print(f'  espera        {step.name}: {step.pause:g}s')
                continue
            if step.pos:
                print(f'  posicao fixa  {step.name}: {step.pos}')
                continue
            found, _, detail = match_step(step, frame)
            status = 'ACHOU    ' if found else 'nao achou'
            print(f'  {status}     {step.name}: {detail}')
    print('\nSo aparece o que esta na tela agora: abra o menu Renascimento na mao '
          'e rode de novo para testar os botoes de dentro dele.')


def cmd_capture(out, delay):
    import pyautogui

    grab = make_grabber(None)
    print('Deixe o botao visivel na tela do Roblox. Recorte so o miolo do botao '
          '(texto e cor), sem pegar o cenario em volta.')
    _countdown('Mouse no canto SUPERIOR ESQUERDO do botao', delay)
    a = pyautogui.position()
    _countdown('Agora no canto INFERIOR DIREITO do botao', delay)
    b = pyautogui.position()
    x1, y1, x2, y2 = min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)

    # Tira o mouse de cima: com hover o botao muda de cor e o recorte nao
    # bateria depois, quando o mouse estiver em outro lugar.
    pyautogui.moveTo(max(x1 - 80, 20), max(y1 - 80, 20), duration=0.1)
    time.sleep(0.5)

    frame = grab()
    ix1, iy1 = frame.to_image(x1, y1)
    ix2, iy2 = frame.to_image(x2, y2)
    crop = frame.image[max(iy1, 0):iy2, max(ix1, 0):ix2]
    if crop.shape[0] < 8 or crop.shape[1] < 8:
        raise SystemExit(f'recorte muito pequeno ({crop.shape[1]}x{crop.shape[0]}). '
                         f'Tente de novo abrindo mais os cantos.')
    if not has_detail(crop):
        raise SystemExit('o recorte saiu de uma cor so. Pegue o texto ou o icone do botao.')
    save_image(out, crop)
    print(f'Salvo {out} ({crop.shape[1]}x{crop.shape[0]})')


def cmd_clicktest(window_title, method, delay):
    import pyautogui

    shown = method or ('sendinput' if sys.platform == 'win32' else 'pyautogui')
    click = make_clicker(method, park=lambda: _window_center(window_title))
    print(f'Teste de clique (metodo {shown}). Deixe o Roblox aberto, com o menu '
          f'Renascimento FECHADO.')
    _countdown('Ponha o mouse em cima do botao Renascimento', delay)
    p = pyautogui.position()
    _focus(window_title)
    click(p.x, p.y)
    print(f'Cliquei em ({p.x}, {p.y}).')
    print(f'Abriu o menu? Entao o metodo {shown} funciona no seu PC. Para o "run" usar ele, '
          f'coloque no topo do config.json: "click_method": "{shown}",')
    print('Nao abriu? Feche o menu se precisar e teste os outros:')
    for m in CLICK_METHODS:
        if m != shown:
            print(f'  py auto_rebirth.py clicktest --method {m}')


def cmd_pos():
    import pyautogui
    print('Posicao do mouse (use em "pos": [x, y]). Ctrl+C para sair.')
    try:
        while True:
            p = pyautogui.position()
            print(f'\r  x={p.x:5d}  y={p.y:5d}', end='', flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('-c', '--config', default='config.json', help='padrao: config.json')

    parser = argparse.ArgumentParser(description='Ciclo automatico no Grow a Chicken Fighter (Roblox).')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run', parents=[common], help='roda as tarefas')
    p.add_argument('--once', action='store_true', help='roda cada tarefa uma vez e sai')
    p = sub.add_parser('check', parents=[common], help='mostra se cada botao da config esta sendo achado na tela')
    p.add_argument('--delay', type=int, default=3, help='segundos antes de capturar (padrao 3)')
    p = sub.add_parser('capture', help='recorta um botao da tela para templates/')
    p.add_argument('out', help='arquivo de saida, ex.: templates/botao_torre.png')
    p.add_argument('--delay', type=int, default=4, help='segundos para posicionar o mouse (padrao 4)')
    sub.add_parser('pos', help='mostra a posicao do mouse')
    p = sub.add_parser('clicktest', parents=[common], help='clica onde o mouse estiver, para testar se o Roblox aceita')
    p.add_argument('--method', choices=CLICK_METHODS, help='padrao: o da config, ou sendinput no Windows')
    p.add_argument('--delay', type=int, default=5, help='segundos para posicionar o mouse (padrao 5)')
    args = parser.parse_args(argv)

    _dpi_aware()
    try:
        if args.command == 'capture':
            cmd_capture(args.out, args.delay)
        elif args.command == 'pos':
            cmd_pos()
        elif args.command == 'clicktest':
            cfg = load_config(args.config) if Path(args.config).is_file() else Config()
            cmd_clicktest(cfg.window_title, args.method or cfg.click_method, args.delay)
        else:
            cfg = load_config(args.config)
            if args.command == 'check':
                cmd_check(cfg, args.delay)
            else:
                cmd_run(cfg, args.once)
    except ConfigError as e:
        raise SystemExit(f'erro na config: {e}')
    except KeyboardInterrupt:
        print()


if __name__ == '__main__':
    main()
