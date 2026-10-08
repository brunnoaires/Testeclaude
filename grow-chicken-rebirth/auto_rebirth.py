#!/usr/bin/env python3
"""
auto_rebirth — rebirth automatico no Grow a Chicken Fighter (Roblox).

Funciona olhando a tela, como voce faria: procura os botoes que voce recortou
em templates/ e clica neles na ordem da config. Nao injeta script no Roblox
nem le memoria do jogo.

  python auto_rebirth.py capture templates/abrir_menu.png   recorta um botao
  python auto_rebirth.py check                              testa os recortes
  python auto_rebirth.py run                                roda o loop
  python auto_rebirth.py pos                                mostra a posicao do mouse

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

from vision import Frame, find_template, has_detail, load_image, save_image

POLL_SECONDS = 0.3

TOP_KEYS = {'window_title', 'interval_seconds', 'confidence', 'color_tolerance', 'steps', 'cleanup'}
STEP_KEYS = {'name', 'image', 'pos', 'wait', 'after', 'optional', 'confidence', 'color_tolerance'}


class ConfigError(Exception):
    pass


@dataclass
class Step:
    name: str
    image: Path | None = None
    pos: tuple | None = None
    wait: float = 3.0         # segundos esperando o botao aparecer
    after: float = 0.8        # pausa depois do clique
    optional: bool = False    # se nao aparecer, segue para o proximo passo
    confidence: float = 0.85
    color_tolerance: float = 40.0
    template: object = None


@dataclass
class Config:
    window_title: str = 'Roblox'
    interval_seconds: float = 30.0
    steps: list = field(default_factory=list)
    cleanup: list = field(default_factory=list)


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
    if ('image' in raw) == ('pos' in raw):
        raise ConfigError(f'{where}: use "image" ou "pos" (exatamente um dos dois)')

    step = Step(
        name=name,
        wait=_number(raw, 'wait', 3.0, where),
        after=_number(raw, 'after', 0.8, where),
        optional=bool(raw.get('optional', False)),
        confidence=_number(raw, 'confidence', defaults['confidence'], where, 0.0, 1.0),
        color_tolerance=_number(raw, 'color_tolerance', defaults['color_tolerance'], where, 0.0, 255.0),
    )
    if 'image' in raw:
        step.image = (base / raw['image']).resolve()
        if not step.image.is_file():
            raise ConfigError(
                f'{where}: imagem nao encontrada: {step.image}\n'
                f'  recorte com: python auto_rebirth.py capture {raw["image"]}\n'
                f'  ou remova esse passo da config se o jogo nao tiver esse botao')
        try:
            step.template = load_image(step.image)
        except ValueError as e:
            raise ConfigError(f'{where}: {e}') from None
        if not has_detail(step.template):
            raise ConfigError(f'{where}: {step.image.name} e uma cor lisa, sem detalhe para '
                              f'comparar. Recorte de novo pegando o texto do botao.')
    else:
        pos = raw['pos']
        if (not isinstance(pos, list) or len(pos) != 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pos)):
            raise ConfigError(f'{where}: "pos" tem que ser [x, y]')
        step.pos = (int(pos[0]), int(pos[1]))
    return step


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
        'confidence': _number(raw, 'confidence', 0.85, 'config', 0.0, 1.0),
        'color_tolerance': _number(raw, 'color_tolerance', 40.0, 'config', 0.0, 255.0),
    }
    base = path.resolve().parent
    steps = raw.get('steps') or []
    cleanup = raw.get('cleanup') or []
    if not isinstance(steps, list) or not steps:
        raise ConfigError('a config precisa de uma lista "steps" com pelo menos um passo')
    if not isinstance(cleanup, list):
        raise ConfigError('"cleanup" tem que ser uma lista')
    return Config(
        window_title=str(raw.get('window_title', 'Roblox')),
        interval_seconds=_number(raw, 'interval_seconds', 30.0, 'config', 1.0),
        steps=[_parse_step(s, base, defaults, f'steps[{i}]') for i, s in enumerate(steps)],
        cleanup=[_parse_step(s, base, defaults, f'cleanup[{i}]') for i, s in enumerate(cleanup)],
    )


# --------------------------------------------------------------------------
# Logica do ciclo (sem dependencia de tela/mouse, testavel)

class Bot:
    def __init__(self, cfg, grab, click, sleep=time.sleep, clock=time.monotonic, log=log):
        self.cfg = cfg
        self.grab = grab
        self.click = click
        self.sleep = sleep
        self.clock = clock
        self.log = log

    def locate(self, step):
        """Procura o passo uma vez. Devolve (x, y) em coordenadas do mouse, ou None."""
        if step.pos:
            return step.pos
        frame = self.grab()
        m = find_template(frame.image, step.template, step.confidence, step.color_tolerance)
        return frame.to_screen(*m.center) if m.found else None

    def wait_for(self, step):
        deadline = self.clock() + step.wait
        while True:
            point = self.locate(step)
            if point or self.clock() >= deadline:
                return point
            self.sleep(POLL_SECONDS)

    def do_step(self, step):
        point = self.wait_for(step)
        if point is None:
            return False
        self.log(f'  clicando em "{step.name}" {point}')
        self.click(*point)
        self.sleep(step.after)
        return True

    def cycle(self):
        """Um ciclo de rebirth. True se todos os passos obrigatorios foram clicados.

        O cleanup roda sempre, completo ou nao, para o jogo voltar ao estado de
        partida (menu fechado) antes do proximo ciclo.
        """
        done = True
        for step in self.cfg.steps:
            if self.do_step(step):
                continue
            if step.optional:
                self.log(f'  "{step.name}" nao apareceu (opcional), seguindo')
                continue
            self.log(f'  "{step.name}" nao apareceu: rebirth ainda nao liberado, tento de novo depois')
            done = False
            break
        for step in self.cfg.cleanup:
            self.do_step(step)
        return done


# --------------------------------------------------------------------------
# Tela, mouse e janela (so roda na maquina com o Roblox)

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


def make_clicker():
    import pyautogui
    pyautogui.FAILSAFE = True

    def click(x, y):
        pyautogui.moveTo(x, y, duration=0.15)
        # O Roblox so registra o hover do botao com movimento real do mouse;
        # sem esse chacoalhar o clique as vezes nao pega.
        pyautogui.moveRel(3, 0, duration=0.05)
        pyautogui.moveRel(-3, 0, duration=0.05)
        pyautogui.mouseDown()
        time.sleep(0.06)
        pyautogui.mouseUp()

    return click


def _focus(title):
    win = _find_window(title)
    if win is None:
        return
    try:
        win.activate()
    except Exception:
        pass  # pygetwindow as vezes reclama mesmo quando funcionou


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
    bot = Bot(cfg, make_grabber(cfg.window_title), make_clicker())
    log(f'rodando: um ciclo a cada {cfg.interval_seconds:g}s. '
        f'Para parar: Ctrl+C aqui, ou mouse num canto da tela.')
    total = 0
    try:
        while True:
            _focus(cfg.window_title)
            log('verificando rebirth...')
            if bot.cycle():
                total += 1
                log(f'rebirth feito ({total} nesta sessao)')
            if once:
                break
            time.sleep(cfg.interval_seconds)
    except KeyboardInterrupt:
        print()
    except pyautogui.FailSafeException:
        print()
        log('mouse no canto da tela: parado pelo failsafe')
    log(f'fim. Rebirths nesta sessao: {total}')


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
    print(f'Captura: {w}x{h} a partir de ({frame.left}, {frame.top})\n')
    for group, steps in (('steps', cfg.steps), ('cleanup', cfg.cleanup)):
        print(f'{group}:')
        for step in steps:
            if step.pos:
                print(f'  posicao fixa  {step.name}: {step.pos}')
                continue
            m = find_template(frame.image, step.template, step.confidence, step.color_tolerance)
            status = 'ACHOU    ' if m.found else 'nao achou'
            print(f'  {status}  {step.name}: formato {m.score:.2f} (min {step.confidence:.2f}), '
                  f'cor {m.color_diff:.0f} (max {step.color_tolerance:.0f}), '
                  f'melhor lugar {frame.to_screen(*m.center)}')
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

    parser = argparse.ArgumentParser(description='Rebirth automatico no Grow a Chicken Fighter (Roblox).')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run', parents=[common], help='roda o loop de rebirth')
    p.add_argument('--once', action='store_true', help='faz um ciclo so e sai')
    p = sub.add_parser('check', parents=[common], help='mostra se cada botao da config esta sendo achado na tela')
    p.add_argument('--delay', type=int, default=3, help='segundos antes de capturar (padrao 3)')
    p = sub.add_parser('capture', help='recorta um botao da tela para templates/')
    p.add_argument('out', help='arquivo de saida, ex.: templates/botao_rebirth.png')
    p.add_argument('--delay', type=int, default=4, help='segundos para posicionar o mouse (padrao 4)')
    sub.add_parser('pos', help='mostra a posicao do mouse')
    args = parser.parse_args(argv)

    _dpi_aware()
    try:
        if args.command == 'capture':
            cmd_capture(args.out, args.delay)
        elif args.command == 'pos':
            cmd_pos()
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
