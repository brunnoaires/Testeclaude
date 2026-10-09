"""
Testes sem Roblox: uma tela falsa desenhada com OpenCV faz o papel do jogo.

  python -m unittest discover -s tests
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auto_rebirth import Bot, ConfigError, Runner, load_config, make_snapshotter, match_step  # noqa: E402
from vision import (Frame, area_box, find_color, find_template, load_image, load_template,  # noqa: E402
                    parse_color, save_image, scaled_variants)

GREEN, GRAY, BLUE, RED, YELLOW, BROWN = (
    (40, 190, 60), (130, 130, 130), (200, 120, 30), (40, 40, 210), (30, 200, 230), (40, 90, 150))

# nome: (x, y, largura, altura, texto)
BUTTONS = {
    'menu': (20, 520, 140, 50, 'MENU'),
    'rebirth': (300, 250, 200, 60, 'REBIRTH'),
    'volte': (300, 250, 200, 60, 'VOLTE'),     # no lugar do REBIRTH, com o galo na torre
    'confirm': (340, 360, 120, 50, 'OK'),
    'close': (560, 150, 50, 50, 'X'),
    'tower': (600, 520, 170, 50, 'TORRE'),
    'retreat': (600, 520, 170, 50, 'RECUAR'),  # mesmo lugar: o botao troca de texto
}


def draw_button(img, name, color):
    x, y, w, h, text = BUTTONS[name]
    cv2.rectangle(img, (x, y), (x + w, y + h), color, -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (20, 20, 20), 3)
    cv2.putText(img, text, (x + 12, y + h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)


def template_for(name, color):
    img = np.zeros((600, 800, 3), np.uint8)
    draw_button(img, name, color)
    x, y, w, h, _ = BUTTONS[name]
    return img[y + 5:y + h - 5, x + 5:x + w - 5].copy()  # so o miolo, como o capture recomenda


BADGE_AT, BADGE_COLOR = (170, 512), (2, 61, 255)   # bolinha "!" do botao de menu


class FakeGame:
    """HUD com botao de menu e botao TORRE/RECUAR; menu com Rebirth (verde
    liberado, cinza nao) e X; dialogo de confirmacao opcional; tecla E sobe
    o comedouro. Com o renascimento liberado aparece uma bolinha vermelha no
    botao de menu; se o galo estiver na torre, o menu mostra VOLTE no lugar
    do REBIRTH, como o jogo de verdade."""

    def __init__(self, ready=True, confirm_dialog=True, left=0, top=0, scale=1.0):
        self.ready, self.confirm_dialog = ready, confirm_dialog
        self.left, self.top, self.scale = left, top, scale
        self.menu = self.confirming = self.in_tower = False
        self.rebirths = self.feeder = 0
        self.clicked = []
        self.keys = []
        self.background = np.random.default_rng(7).integers(0, 255, (600, 800, 3), dtype=np.uint8)

    def visible(self):
        names = {'menu', 'retreat' if self.in_tower else 'tower'}
        if self.menu:
            names |= {'volte' if self.ready and self.in_tower else 'rebirth', 'close'}
        if self.confirming:
            names.add('confirm')
        return names

    def grab(self):
        img = self.background.copy()
        colors = {'menu': BLUE, 'tower': BROWN, 'retreat': BROWN, 'close': RED, 'confirm': YELLOW,
                  'rebirth': GREEN if self.ready else GRAY, 'volte': BROWN}
        for name in ('menu', 'tower', 'retreat', 'rebirth', 'volte', 'close', 'confirm'):
            if name in self.visible():
                draw_button(img, name, colors[name])
        if self.ready and not self.menu:
            cv2.circle(img, BADGE_AT, 10, BADGE_COLOR, -1)
        return Frame(img, self.left, self.top, self.scale)

    def _hit(self, x, y):
        for name in self.visible():
            bx, by, w, h, _ = BUTTONS[name]
            if bx <= x < bx + w and by <= y < by + h:
                return name
        return None

    def click(self, x, y):
        frame = Frame(None, self.left, self.top, self.scale)
        name = self._hit(*frame.to_image(x, y))
        self.clicked.append(name)
        if name == 'menu':
            self.menu = not self.menu
        elif name == 'tower':
            self.in_tower = True
        elif name == 'retreat':
            self.in_tower = False
        elif name == 'rebirth' and self.ready:
            if self.confirm_dialog:
                self.confirming = True
            else:
                self._rebirth()
        elif name == 'confirm':
            self._rebirth()
        elif name == 'close':
            self.menu = self.confirming = False

    def press(self, key, hold):
        self.keys.append(key)
        if key == 'e':
            self.feeder += 1

    def _rebirth(self):
        self.rebirths += 1
        self.ready = False
        self.confirming = False


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def sleep(self, s):
        self.t += s

    def now(self):
        return self.t


# Formato curto: so a tarefa de renascer, com os passos no topo.
CONFIG = {
    'window_title': 'Roblox',
    'interval_seconds': 30,
    'steps': [
        {'name': 'abrir menu', 'image': 'templates/menu.png'},
        {'name': 'rebirth', 'image': 'templates/rebirth.png', 'wait': 2},
        {'name': 'confirmar', 'image': 'templates/confirm.png', 'optional': True},
    ],
    'cleanup': [
        {'name': 'fechar', 'image': 'templates/close.png', 'wait': 1},
    ],
}

TASKS_CONFIG = {
    'window_title': 'Roblox',
    'tasks': [
        {'name': 'comedouro', 'every_seconds': 10, 'steps': [{'name': 'E', 'key': 'e', 'repeat': 2}]},
        {'name': 'torre', 'every_seconds': 20, 'steps': [{'name': 'TORRE', 'image': 'templates/tower.png', 'wait': 1}]},
        {'name': 'renascer', 'every_seconds': 30, 'steps': CONFIG['steps'], 'cleanup': CONFIG['cleanup']},
    ],
}


BADGE_STEP = {'name': '!', 'color': '#FF3D02', 'area': [0.19, 0.81, 0.24, 0.89], 'min_pixels': 150,
              'click': False, 'wait': 0}
FLOW_CONFIG = {
    'tasks': [
        {'name': 'recuar', 'every_seconds': 10,
         'steps': [BADGE_STEP,
                   {'name': 'abrir menu', 'image': 'templates/menu.png'},
                   {'name': 'VOLTE', 'image': 'templates/volte.png', 'click': False, 'wait': 0},
                   {'name': 'fechar', 'image': 'templates/close.png'},
                   {'name': 'RECUAR', 'image': 'templates/retreat.png', 'after': 8}],
         'cleanup': [{'name': 'fechar', 'image': 'templates/close.png', 'wait': 0}]},
        {'name': 'renascer', 'every_seconds': 10,
         'steps': [BADGE_STEP,
                   {'name': 'abrir menu', 'image': 'templates/menu.png'},
                   {'name': 'rebirth', 'image': 'templates/rebirth.png'}],
         'cleanup': [{'name': 'fechar', 'image': 'templates/close.png', 'wait': 0}]},
        {'name': 'torre', 'every_seconds': 10,
         'steps': [{'name': 'TORRE', 'image': 'templates/tower.png', 'wait': 0}]},
    ],
}


class Workspace:
    """Pasta temporaria com config.json e os recortes."""

    def __init__(self, config=CONFIG):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        save_image(self.dir / 'templates/menu.png', template_for('menu', BLUE))
        save_image(self.dir / 'templates/rebirth.png', template_for('rebirth', GREEN))
        save_image(self.dir / 'templates/confirm.png', template_for('confirm', YELLOW))
        save_image(self.dir / 'templates/close.png', template_for('close', RED))
        save_image(self.dir / 'templates/tower.png', template_for('tower', BROWN))
        save_image(self.dir / 'templates/retreat.png', template_for('retreat', BROWN))
        save_image(self.dir / 'templates/volte.png', template_for('volte', BROWN))
        self.write(config)

    def write(self, config):
        (self.dir / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        return self.dir / 'config.json'

    def load(self):
        return load_config(self.dir / 'config.json')

    def close(self):
        self._tmp.cleanup()


def make_bot(game, clock=None):
    clock = clock or FakeClock()
    return Bot(game.grab, game.click, game.press, sleep=clock.sleep, clock=clock.now, log=lambda m: None)


def copy(config):
    return json.loads(json.dumps(config))


class VisionTest(unittest.TestCase):
    def test_finds_button_center(self):
        game = FakeGame()
        game.menu = True
        m = find_template(game.grab().image, template_for('rebirth', GREEN), 0.85, 40)
        self.assertTrue(m.found)
        x, y, w, h, _ = BUTTONS['rebirth']
        self.assertLessEqual(abs(m.center[0] - (x + w // 2)), 2)
        self.assertLessEqual(abs(m.center[1] - (y + h // 2)), 2)

    def test_disabled_gray_button_rejected_by_color(self):
        game = FakeGame(ready=False)
        game.menu = True
        m = find_template(game.grab().image, template_for('rebirth', GREEN), 0.85, 40)
        self.assertGreater(m.score, 0.85, 'o formato bate; quem separa e a cor')
        self.assertGreater(m.color_diff, 40)
        self.assertFalse(m.found)

    def test_absent_button(self):
        m = find_template(FakeGame().grab().image, template_for('rebirth', GREEN), 0.85, 40)
        self.assertFalse(m.found)

    def test_flat_template_does_not_crash(self):
        flat = np.full((20, 20, 3), 128, np.uint8)
        m = find_template(FakeGame().grab().image, flat, 0.85, 40)
        self.assertFalse(m.found)

    def test_template_bigger_than_screen(self):
        m = find_template(np.zeros((10, 10, 3), np.uint8), np.zeros((20, 20, 3), np.uint8), 0.85, 40)
        self.assertFalse(m.found)

    def test_mask_ignores_background(self):
        # botao num fundo; depois o mesmo botao em outro fundo
        game = FakeGame()
        x, y, w, h, _ = BUTTONS['tower']
        pad = 12
        region = (slice(y - pad, y + h + pad), slice(x - pad, x + w + pad))
        crop = game.grab().image[region].copy()
        mask = np.zeros(crop.shape[:2], bool)
        mask[pad:-pad, pad:-pad] = True
        other = game.grab().image.copy()
        other[region][~mask] = (250, 250, 250)  # cenario claro e liso em volta
        self.assertFalse(find_template(other, crop, 0.85, 40).found, 'sem mascara o fundo atrapalha')
        m = find_template(other, crop, 0.85, 40, mask)
        self.assertTrue(m.found)
        self.assertGreater(m.score, 0.99)
        self.assertLess(m.color_diff, 5, 'a cor tambem so olha os pixels do botao')

    def test_mask_with_too_few_pixels(self):
        tpl = template_for('tower', BROWN)
        ys, xs = np.nonzero((tpl == 255).all(axis=2))     # letras brancas
        mask = np.zeros(tpl.shape[:2], bool)
        mask[ys[:40:10], xs[:40:10]] = True
        mask[20, :4] = True                                # e um pouco do fundo marrom
        self.assertLess(mask.sum(), 20)
        self.assertGreaterEqual(tpl[mask].std(axis=0).max(), 5, 'tem variacao: quem barra e o minimo de pixels')
        game = FakeGame()
        game.in_tower = True   # TORRE nao esta na tela: 8 pixels batem em qualquer lugar
        self.assertFalse(find_template(game.grab().image, tpl, 0.85, 40, mask).found)

    def test_flat_colored_template_rejected(self):
        green = np.zeros((30, 60, 3), np.uint8)
        green[:] = GREEN   # canais diferentes entre si, mas liso
        game = FakeGame()
        game.menu = True
        self.assertFalse(find_template(game.grab().image, green, 0.85, 40).found)

    def test_load_template_reads_alpha_as_mask(self):
        with tempfile.TemporaryDirectory() as d:
            bgra = np.zeros((10, 12, 4), np.uint8)
            bgra[..., :3] = 90
            bgra[2:8, 3:9, 3] = 255
            save_image(Path(d) / 'a.png', bgra)
            img, mask = load_template(Path(d) / 'a.png')
            self.assertEqual(img.shape, (10, 12, 3))
            self.assertEqual(int(mask.sum()), 36)
            opaque = bgra.copy()
            opaque[..., 3] = 255
            save_image(Path(d) / 'b.png', opaque)
            self.assertIsNone(load_template(Path(d) / 'b.png')[1])
            save_image(Path(d) / 'c.png', bgra[..., :3])
            self.assertIsNone(load_template(Path(d) / 'c.png')[1])

    def test_scaled_variants(self):
        tpl = template_for('rebirth', GREEN)
        variants = scaled_variants(tpl, None, 0.06)
        self.assertEqual([s for s, _, _ in variants], [1.0, 0.98, 1.02, 0.96, 1.04, 0.94, 1.06])
        self.assertIs(variants[0][1], tpl)
        self.assertEqual(variants[-1][1].shape[1], round(tpl.shape[1] * 1.06))
        self.assertEqual(len(scaled_variants(tpl, None, 0)), 1)

    def test_parse_color(self):
        self.assertEqual(parse_color('#FF3D02'), (2, 61, 255))
        self.assertEqual(parse_color('ff3d02'), (2, 61, 255))
        with self.assertRaises(ValueError):
            parse_color('#FFF')

    def test_area_box(self):
        self.assertEqual(area_box((100, 200, 3), (0.5, 0.25, 1.0, 0.75)), (100, 25, 200, 75))

    def test_find_color(self):
        img = np.full((100, 100, 3), 120, np.uint8)
        cv2.circle(img, (70, 30), 10, (2, 61, 255), -1)       # bolinha vermelha
        m = find_color(img, (2, 61, 255), 100)
        self.assertTrue(m.found)
        self.assertLessEqual(abs(m.center[0] - 70) + abs(m.center[1] - 30), 2)
        darker = (img.astype(float) * 0.6).astype(np.uint8)    # mesmo tom, mais escuro
        self.assertTrue(find_color(darker, (2, 61, 255), 100).found)
        self.assertFalse(find_color(img, (2, 61, 255), 1000).found, 'poucos pixels')
        self.assertFalse(find_color(img, (255, 61, 2), 100).found, 'azul nao e vermelho')

    def test_tower_not_confused_with_retreat(self):
        game = FakeGame()
        game.in_tower = True
        m = find_template(game.grab().image, template_for('tower', BROWN), 0.85, 40)
        self.assertFalse(m.found)


FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def window_with(name, at, size=(1014, 1919), scale=1.0, anchor=None):
    """Janela do tamanho do print com o pedaco `name` colado em `at` (y, x),
    no lugar de onde saiu. scale != 1 encolhe ou aumenta o pedaco em volta de
    `anchor` (x, y) na janela, como o HUD faria com outra janela."""
    img = load_image(FIXTURES / f'{name}.png')
    canvas = np.full((*size, 3), 110, np.uint8)
    y, x = at
    canvas[y:y + img.shape[0], x:x + img.shape[1]] = img[:size[0] - y, :size[1] - x]
    if scale != 1.0:
        M = cv2.getRotationMatrix2D(anchor, 0, scale)
        canvas = cv2.warpAffine(canvas, M, (size[1], size[0]), borderMode=cv2.BORDER_REPLICATE)
    return Frame(canvas)


EXAMPLE = load_config(Path(__file__).resolve().parent.parent / 'config.example.json')
EXAMPLE_TASKS = {t.name: t for t in EXAMPLE.tasks}
STEP_TORRE = EXAMPLE_TASKS['mandar galo para a torre'].steps[0]
STEP_ALERTA, STEP_RENASCIMENTO, STEP_RENASCER = EXAMPLE_TASKS['renascer'].steps
_RECUAR_STEPS = {s.name: s for s in EXAMPLE_TASKS['recuar galo para renascer'].steps}
STEP_VOLTE, STEP_RECUAR = _RECUAR_STEPS['VOLTE PRO SEU GALINHEIRO'], _RECUAR_STEPS['botao RECUAR']


def match(step, img):
    """O que o bot calcula para esse passo, com os dados da config de exemplo."""
    return find_template(img, step.template, step.confidence, step.color_tolerance, step.mask)


class RealGameTest(unittest.TestCase):
    """Pedacos de prints do jogo de verdade: o menu com RENASCER (verde,
    liberado), com AINDA NAO (marrom, bloqueado) e com VOLTE PRO SEU
    GALINHEIRO (liberado com o galo na torre), todos com MARCOS embaixo.
    Usa o passo e o recorte que vao para o usuario (config.example.json); os
    pedacos vao para o lugar de onde sairam, numa janela do tamanho do print,
    porque esses passos so procuram numa area (fracao da janela)."""

    WINDOW = (1005, 1919)
    PLACE = {'menu_liberado': (620, 760), 'menu_bloqueado': (623, 761), 'menu_volte': (614, 797),
             'menu_renascimento': (640, 760)}
    # menu_renascimento saiu de um print da janela com a barra de titulo do Windows
    SIZES = {'menu_renascimento': (1040, 1920)}

    def menu(self, name, scale=1.0):
        """Janela com o pedaco do menu; scale != 1 simula o menu em outro
        tamanho (janela diferente, ou botao pulsando)."""
        img = load_image(FIXTURES / f'{name}.png')
        if scale != 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        canvas = np.full((*self.SIZES.get(name, self.WINDOW), 3), 110, np.uint8)
        y, x = self.PLACE[name]
        canvas[y:y + img.shape[0], x:x + img.shape[1]] = img
        return Frame(canvas)

    def test_renascer_found_when_unlocked(self):
        self.assertTrue(match_step(STEP_RENASCER, self.menu('menu_liberado'))[0])

    def test_ainda_nao_rejected(self):
        found, _, detail = match_step(STEP_RENASCER, self.menu('menu_bloqueado'))
        self.assertFalse(found)
        self.assertTrue(detail.startswith('0 pixels'), detail)   # botao marrom: nada do verde

    def test_green_button_with_new_text(self):
        """Relato do usuario: o jogo trocou o texto do botao verde de RENASCER
        para RENASCIMENTO e o recorte da palavra parou de bater (0.74). Pela
        cor, o texto nao importa."""
        for scale in (0.9, 0.95, 1.0, 1.05, 1.1):
            with self.subTest(scale=scale):
                found, point, detail = match_step(STEP_RENASCER, self.menu('menu_renascimento', scale))
                self.assertTrue(found, detail)
        found, point, _ = match_step(STEP_RENASCER, self.menu('menu_renascimento'))
        # o clique vai no centro do botao (no print: x 828-1092, y 668-750)
        self.assertTrue(828 < point[0] < 1092 and 668 < point[1] < 750, point)

    def test_volte_galinheiro(self):
        self.assertTrue(match_step(STEP_VOLTE, self.menu('menu_volte'))[0])
        self.assertFalse(match_step(STEP_RENASCER, self.menu('menu_volte'))[0])
        for other in ('menu_liberado', 'menu_bloqueado'):   # AINDA NAO tem o mesmo marrom
            with self.subTest(other):
                self.assertFalse(match_step(STEP_VOLTE, self.menu(other))[0])

    def test_menu_buttons_in_other_sizes(self):
        """Relato do usuario: VOLTE na tela e o log dizendo que nao apareceu.
        Com um tamanho so, 3% de diferenca ja derrubava o VOLTE para 0.66."""
        for scale in (0.92, 0.95, 0.97, 1.03, 1.06, 1.09):
            with self.subTest(scale=scale):
                self.assertFalse(match(STEP_VOLTE, self.menu('menu_volte', scale).image).found,
                                 'so no tamanho original nao acharia')
                self.assertTrue(match_step(STEP_VOLTE, self.menu('menu_volte', scale))[0])
                self.assertTrue(match_step(STEP_RENASCER, self.menu('menu_liberado', scale))[0])
                for wrong, step in (('menu_bloqueado', STEP_VOLTE), ('menu_bloqueado', STEP_RENASCER),
                                    ('menu_liberado', STEP_VOLTE), ('menu_volte', STEP_RENASCER)):
                    self.assertFalse(match_step(step, self.menu(wrong, scale))[0], (wrong, step.name))

    # hud_recuar (print do botao com o galo na torre) e hud_baixo (TORRE), nos
    # lugares do print do comedouro; a barra de baixo fica presa no centro de baixo
    BOTTOM = (960, 1014)

    def recuar(self, scale=1.0):
        return window_with('hud_recuar', (853, 894), scale=scale, anchor=self.BOTTOM)

    def torre(self, scale=1.0):
        return window_with('hud_baixo', (880, 760), scale=scale, anchor=self.BOTTOM)

    def test_recuar_and_torre_not_confused(self):
        self.assertTrue(match_step(STEP_RECUAR, self.recuar())[0])
        self.assertFalse(match_step(STEP_RECUAR, self.torre())[0])
        self.assertFalse(match_step(STEP_TORRE, self.recuar())[0], 'TORRE nunca pode achar o RECUAR (tiraria o galo)')
        self.assertLess(match(STEP_TORRE, load_image(FIXTURES / 'hud_recuar.png')).score, 0.75)

    def test_recuar_and_torre_in_other_sizes(self):
        for scale in (0.92, 0.96, 1.04, 1.08):
            with self.subTest(scale=scale):
                self.assertTrue(match_step(STEP_RECUAR, self.recuar(scale))[0])
                self.assertTrue(match_step(STEP_TORRE, self.torre(scale))[0])
                self.assertFalse(match_step(STEP_TORRE, self.recuar(scale))[0], 'TORRE nunca pode achar o RECUAR')
                self.assertFalse(match_step(STEP_RECUAR, self.torre(scale))[0])


class RealHudTest(unittest.TestCase):
    """HUD do jogo de verdade, de um print com o renascimento liberado.

    hud_direita: coluna da direita com o ! vermelho no Renascimento.
    hud_direita_sem_alerta: o mesmo print com a bolinha do ! apagada por
      edicao (inpaint) - nao e print real, mas o resto do botao e.
    hud_direita_fundo_trocado: cenario atras do botao trocado por grama,
      como se a camera tivesse girado.
    hud_guilda: Guilda com a bolinha "1", mesmo estilo e mesma cor do !.
    hud_baixo: CHAMAR, TORRE e CAOS PROFISSIONAL.
    ceu: pedaco do ceu do mesmo print, quase liso.

    O ! e procurado pela cor, com o passo exatamente como esta no
    config.example.json. Para a area (fracao da janela) valer, os pedacos sao
    colados numa janela do tamanho do print, nos lugares de onde sairam.
    """

    WINDOW = (1014, 1919)       # altura x largura do print original
    HUD_AT = (340, 1760)        # canto da coluna da direita no print
    GUILD_AT = (530, 240)       # canto do pedaco da Guilda no print
    BADGE = (112, 149, 104, 155)  # bolinha do ! dentro de hud_direita (y1, y2, x1, x2)

    alert = STEP_ALERTA

    def window(self, hud, guild=None):
        canvas = np.full((*self.WINDOW, 3), 110, np.uint8)
        for img, (y, x) in ((hud, self.HUD_AT), (guild, self.GUILD_AT)):
            if img is not None:
                canvas[y:y + img.shape[0], x:x + img.shape[1]] = img
        return Frame(canvas)

    def animated(self, scale=1.0, angle=0.0, dy=0, gain=1.0):
        """Bolinha do print transformada (pulsando, girando, pulando, mais
        escura) e colada no print sem o !."""
        src = load_image(FIXTURES / 'hud_direita.png')
        out = load_image(FIXTURES / 'hud_direita_sem_alerta.png')
        y1, y2, x1, x2 = self.BADGE
        layer = np.zeros_like(src)
        layer[y1:y2, x1:x2] = src[y1:y2, x1:x2]
        M = cv2.getRotationMatrix2D(((x1 + x2) / 2, (y1 + y2) / 2), angle, scale)
        M[1, 2] += dy
        warped = cv2.warpAffine(layer, M, (src.shape[1], src.shape[0]))
        warped = np.clip(warped.astype(float) * gain, 0, 255).astype(np.uint8)
        painted = warped.any(axis=2)
        out[painted] = warped[painted]
        return out

    def test_alert_found(self):
        found, point, _ = match_step(self.alert, self.window(load_image(FIXTURES / 'hud_direita.png')))
        self.assertTrue(found)
        # centro da mancha vermelha cai na bolinha (no print: x 1864-1915, y 452-489)
        self.assertTrue(1864 <= point[0] <= 1915 and 452 <= point[1] <= 489, point)

    def test_alert_found_with_other_background(self):
        hud = load_image(FIXTURES / 'hud_direita_fundo_trocado.png')
        self.assertTrue(match_step(self.alert, self.window(hud))[0])

    def test_alert_absent(self):
        hud = load_image(FIXTURES / 'hud_direita_sem_alerta.png')
        self.assertFalse(match_step(self.alert, self.window(hud))[0])

    def test_alert_ignores_guild_badge(self):
        hud = load_image(FIXTURES / 'hud_direita_sem_alerta.png')
        guild = load_image(FIXTURES / 'hud_guilda.png')
        self.assertFalse(match_step(self.alert, self.window(hud, guild))[0],
                         'a bolinha da Guilda tem a mesma cor, mas fica fora da area')

    def test_alert_survives_animation(self):
        for kw in ({'scale': 0.75}, {'scale': 1.25}, {'angle': 20}, {'angle': -15},
                   {'dy': -10}, {'gain': 0.6}, {'scale': 1.15, 'angle': 8}):
            with self.subTest(**kw):
                self.assertTrue(match_step(self.alert, self.window(self.animated(**kw)))[0])

    def test_rebirth_button_found_with_or_without_alert(self):
        for screen in ('hud_direita', 'hud_direita_sem_alerta', 'hud_direita_fundo_trocado'):
            with self.subTest(screen=screen):
                self.assertTrue(match_step(STEP_RENASCIMENTO, self.window(load_image(FIXTURES / f'{screen}.png')))[0])

    def test_rebirth_button_on_solid_backgrounds(self):
        """So a mascara sobrevive: o cenario em volta do botao vira ceu, branco
        ou noite. Sem mascara (no formato ou na cor), o botao some."""
        hud = load_image(FIXTURES / 'hud_direita.png')
        where = match(STEP_RENASCIMENTO, hud)
        h, w = STEP_RENASCIMENTO.template.shape[:2]
        x, y = where.center[0] - w // 2, where.center[1] - h // 2
        for name, color in (('ceu', (235, 200, 120)), ('branco', (250, 250, 250)), ('noite', (40, 20, 10))):
            with self.subTest(name):
                img = hud.copy()
                img[y:y + h, x:x + w][~STEP_RENASCIMENTO.mask] = color
                self.assertTrue(match_step(STEP_RENASCIMENTO, self.window(img))[0])
                self.assertLess(match(STEP_RENASCIMENTO, img).color_diff, 5)

    @staticmethod
    def next_to_sky(hud):
        """hud com um pedaco do ceu do print a esquerda (ceu.png, repetido
        para cobrir a altura)."""
        sky = load_image(FIXTURES / 'ceu.png')
        reps = -(-hud.shape[0] // sky.shape[0])
        column = np.vstack([sky] * reps)[:hud.shape[0]]
        return np.hstack([column, hud]), sky.shape[1]

    def test_buttons_next_to_real_sky(self):
        """No ceu liso do print, o matchTemplate com mascara solta NaN e +inf
        (0/0). Se isso nao for descartado, o "melhor lugar" vira o ceu e o bot
        clica nele em vez do botao."""
        for step, fixture in ((STEP_RENASCIMENTO, 'hud_direita'), (STEP_TORRE, 'hud_baixo')):
            with self.subTest(step.name):
                hud = load_image(FIXTURES / f'{fixture}.png')
                expected = match(step, hud).center
                canvas, dx = self.next_to_sky(hud)
                m = match(step, canvas)
                self.assertTrue(m.found)
                self.assertEqual(m.center, (expected[0] + dx, expected[1]))

    def test_tower_found_on_the_right_label(self):
        found, point, _ = match_step(STEP_TORRE, window_with('hud_baixo', (880, 760)))
        self.assertTrue(found)
        # TORRE fica no meio: CHAMAR a esquerda, CAOS PROFISSIONAL a direita
        self.assertTrue(930 < point[0] < 990, point)

    def test_rebirth_button_and_alert_in_other_sizes(self):
        """Relato do usuario: parou de reconhecer o botao Renascimento. Com um
        tamanho so, o HUD 5% menor ja derrubava a nota de 1.00 para 0.57. A
        coluna da direita fica presa na borda direita da janela."""
        right_edge = (1919, 507)
        for scale in (0.9, 0.93, 0.96, 1.04, 1.08):
            with self.subTest(scale=scale):
                hud = window_with('hud_direita', self.HUD_AT, scale=scale, anchor=right_edge)
                self.assertFalse(match(STEP_RENASCIMENTO, hud.image).found, 'so no tamanho original nao acharia')
                self.assertTrue(match_step(STEP_RENASCIMENTO, hud)[0])
                self.assertTrue(match_step(STEP_ALERTA, hud)[0])
                sem = window_with('hud_direita_sem_alerta', self.HUD_AT, scale=scale, anchor=right_edge)
                self.assertFalse(match_step(STEP_ALERTA, sem)[0])

    def test_rebirth_button_not_confused_with_shop_or_band(self):
        """Na coluna da direita tambem ficam a Loja e a Banda: tirando o
        Renascimento, nada pode bater em nenhum tamanho."""
        hud = window_with('hud_direita', self.HUD_AT)
        img = hud.image.copy()
        y, x = self.HUD_AT
        img[y + 100:y + 220, x:x + 159] = img[y + 260:y + 380, x:x + 159]   # Banda por cima do Renascimento
        found, _, detail = match_step(STEP_RENASCIMENTO, Frame(img))
        self.assertFalse(found, detail)


class SecondWindowTest(unittest.TestCase):
    """Print do usuario com a janela em 1914x999 (os recortes sairam de uma de
    1919x1014), com o ! no Renascimento e o galo na torre (RECUAR). Os pedacos
    vao para os mesmos lugares numa janela desse tamanho, para a area do ! (em
    fracao da janela) valer."""

    SIZE = (999, 1914)

    def window(self, name, y, x):
        canvas = np.full((*self.SIZE, 3), 110, np.uint8)
        img = load_image(FIXTURES / f'{name}.png')
        canvas[y:y + img.shape[0], x:x + img.shape[1]] = img
        return Frame(canvas)

    def test_alert_and_rebirth_button(self):
        right = self.window('janela2_direita', 330, 1755)
        self.assertTrue(match_step(STEP_ALERTA, right)[0])
        self.assertTrue(match_step(STEP_RENASCIMENTO, right)[0])

    def test_recuar_found_tower_not(self):
        bottom = self.window('janela2_baixo', 870, 760)
        found, point, _ = match_step(STEP_RECUAR, bottom)
        self.assertTrue(found)
        self.assertTrue(940 < point[0] < 980 and 970 < point[1] < 995, point)
        self.assertFalse(match_step(STEP_TORRE, bottom)[0], 'com o galo na torre, TORRE nao pode ser achado')
        # folga: a nota real do RECUAR aqui fica abaixo de 1.00 (0.95), longe do minimo
        self.assertGreater(match(STEP_RECUAR, bottom.image).score - STEP_RECUAR.confidence, 0.1)


class TaskTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.task = self.ws.load().tasks[0]

    def tearDown(self):
        self.ws.close()

    def test_full_rebirth_with_confirm(self):
        game = FakeGame()
        self.assertTrue(make_bot(game).run_task(self.task))
        self.assertEqual(game.rebirths, 1)
        self.assertEqual(game.clicked, ['menu', 'rebirth', 'confirm', 'close'])
        self.assertFalse(game.menu)

    def test_not_ready_aborts_and_closes_menu(self):
        game = FakeGame(ready=False)
        self.assertFalse(make_bot(game).run_task(self.task))
        self.assertEqual(game.rebirths, 0)
        self.assertEqual(game.clicked, ['menu', 'close'])
        self.assertFalse(game.menu)

    def test_optional_confirm_missing(self):
        game = FakeGame(confirm_dialog=False)
        self.assertTrue(make_bot(game).run_task(self.task))
        self.assertEqual(game.rebirths, 1)
        self.assertEqual(game.clicked, ['menu', 'rebirth', 'close'])

    def test_waits_until_ready_across_runs(self):
        game = FakeGame(ready=False)
        bot = make_bot(game)
        self.assertFalse(bot.run_task(self.task))
        game.ready = True
        self.assertTrue(bot.run_task(self.task))
        self.assertFalse(bot.run_task(self.task), 'depois do rebirth o botao volta a ficar cinza')
        self.assertEqual(game.rebirths, 1)

    def test_window_offset_and_scale(self):
        game = FakeGame(left=300, top=120, scale=2.0)
        self.assertTrue(make_bot(game).run_task(self.task))
        self.assertEqual(game.rebirths, 1)
        self.assertNotIn(None, game.clicked)

    def test_fixed_position_step(self):
        x, y, w, h, _ = BUTTONS['menu']
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'abrir menu', 'pos': [x + w // 2, y + h // 2]}
        self.ws.write(config)
        game = FakeGame()
        self.assertTrue(make_bot(game).run_task(self.ws.load().tasks[0]))
        self.assertEqual(game.clicked[0], 'menu')

    def test_key_step_with_repeat(self):
        config = copy(CONFIG)
        config['steps'] = [{'name': 'comedouro', 'key': 'E', 'repeat': 3, 'after': 0.5}]
        config['cleanup'] = []
        self.ws.write(config)
        game = FakeGame()
        clock = FakeClock()
        self.assertTrue(make_bot(game, clock).run_task(self.ws.load().tasks[0]))
        self.assertEqual(game.keys, ['e', 'e', 'e'])
        self.assertEqual(clock.t, 1.5)

    def test_check_only_step(self):
        config = copy(CONFIG)
        config['steps'] = [
            {'name': 'menu na tela', 'image': 'templates/menu.png', 'click': False, 'wait': 0},
            {'name': 'abrir menu', 'image': 'templates/menu.png'},
        ]
        config['cleanup'] = []
        self.ws.write(config)
        game = FakeGame()
        self.assertTrue(make_bot(game).run_task(self.ws.load().tasks[0]))
        self.assertEqual(game.clicked, ['menu'], 'o primeiro passo so olha, nao clica')

    def test_log_says_how_close_a_missing_step_got(self):
        logs = []
        game = FakeGame(ready=False)   # REBIRTH cinza: nao bate pela cor
        game.menu = True
        config = copy(CONFIG)
        config['steps'] = [{'name': 'rebirth', 'image': 'templates/rebirth.png', 'wait': 0}]
        config['cleanup'] = []
        self.ws.write(config)
        clock = FakeClock()
        Bot(game.grab, game.click, game.press, sleep=clock.sleep, clock=clock.now,
            log=logs.append).run_task(self.ws.load().tasks[0])
        line = next(m for m in logs if 'nao apareceu' in m)
        self.assertIn('formato', line)
        self.assertIn('(max 40)', line)

    def test_snapshot_when_a_middle_step_fails(self):
        saved = []
        game = FakeGame(ready=False)     # abre o menu, mas o REBIRTH esta cinza
        clock = FakeClock()
        bot = Bot(game.grab, game.click, game.press, sleep=clock.sleep, clock=clock.now, log=lambda m: None,
                  snapshot=lambda task, step, frame: saved.append((step.name, frame.image.shape)) or 'x.png')
        self.assertFalse(bot.run_task(self.task))
        self.assertEqual([n for n, _ in saved], ['rebirth'])

    def test_no_snapshot_when_first_step_fails(self):
        saved = []
        config = copy(CONFIG)
        config['steps'] = [{'name': 'rebirth', 'image': 'templates/rebirth.png', 'wait': 0}]
        config['cleanup'] = []
        self.ws.write(config)
        clock = FakeClock()
        bot = Bot(FakeGame().grab, FakeGame().click, FakeGame().press, sleep=clock.sleep, clock=clock.now,
                  log=lambda m: None, snapshot=lambda *a: saved.append(a))
        self.assertFalse(bot.run_task(self.ws.load().tasks[0]))
        self.assertEqual(saved, [], 'falhar no primeiro passo e o normal ("ainda nao")')

    def test_snapshotter_keeps_the_last_ones(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            snap = make_snapshotter(Path(d) / 'debug', keep=3)
            frame = Frame(np.zeros((10, 10, 3), np.uint8))
            for i in range(5):
                snap(SimpleNamespace(name=f'tarefa {i}'), SimpleNamespace(name='VOLTE PRO SEU GALINHEIRO'), frame)
            files = sorted((Path(d) / 'debug').glob('*.png'))
            self.assertEqual(len(files), 3)
            self.assertIn('volte-pro-seu-galinheiro', files[-1].name)

    def test_check_only_step_absent_stops_task(self):
        config = copy(CONFIG)
        config['steps'] = [
            {'name': 'rebirth liberado', 'image': 'templates/rebirth.png', 'click': False, 'wait': 0},
            {'name': 'abrir menu', 'image': 'templates/menu.png'},
        ]
        config['cleanup'] = []
        self.ws.write(config)
        game = FakeGame()  # menu fechado: o botao rebirth nao aparece
        self.assertFalse(make_bot(game).run_task(self.ws.load().tasks[0]))
        self.assertEqual(game.clicked, [])

    def test_color_step_in_task(self):
        config = copy(CONFIG)
        # o botao REBIRTH verde (40, 190, 60) fica na metade de cima/esquerda
        config['steps'] = [
            {'name': 'verde no menu', 'color': '#3CBE28', 'area': [0.3, 0.35, 0.7, 0.6],
             'min_pixels': 500, 'click': False, 'wait': 0},
            {'name': 'fechar', 'image': 'templates/close.png'},
        ]
        config['cleanup'] = []
        self.ws.write(config)
        task = self.ws.load().tasks[0]
        game = FakeGame()
        self.assertFalse(make_bot(game).run_task(task), 'menu fechado: nada verde na area')
        game.menu = True
        self.assertTrue(make_bot(game).run_task(task))
        self.assertEqual(game.clicked, ['close'])

    def test_image_area_limits_search(self):
        config = copy(CONFIG)
        config['steps'] = [{'name': 'menu', 'image': 'templates/menu.png', 'wait': 0,
                            'area': [0.5, 0, 1, 1]}]   # o botao MENU fica na esquerda
        config['cleanup'] = []
        self.ws.write(config)
        game = FakeGame()
        self.assertFalse(make_bot(game).run_task(self.ws.load().tasks[0]))
        config['steps'][0]['area'] = [0, 0.5, 0.5, 1]
        self.ws.write(config)
        self.assertTrue(make_bot(game).run_task(self.ws.load().tasks[0]))
        self.assertEqual(game.clicked, ['menu'])

    def test_pause_step(self):
        config = copy(CONFIG)
        config['steps'] = [{'name': 'esperar', 'pause': 2.5}]
        config['cleanup'] = []
        self.ws.write(config)
        clock = FakeClock()
        logs = []
        game = FakeGame()
        bot = Bot(game.grab, game.click, game.press, sleep=clock.sleep, clock=clock.now, log=logs.append)
        self.assertTrue(bot.run_task(self.ws.load().tasks[0]))
        self.assertEqual(clock.t, 2.5)
        self.assertEqual(game.clicked, [])
        self.assertIn('esperando 2.5s', logs[0])

    def test_click_repeat(self):
        config = copy(CONFIG)
        config['steps'] = [{'name': 'menu', 'image': 'templates/menu.png', 'repeat': 2}]
        config['cleanup'] = []
        self.ws.write(config)
        game = FakeGame()
        make_bot(game).run_task(self.ws.load().tasks[0])
        self.assertEqual(game.clicked, ['menu', 'menu'])


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace(TASKS_CONFIG)
        self.cfg = self.ws.load()

    def tearDown(self):
        self.ws.close()

    def run_for(self, game, seconds, focus=lambda: None):
        clock = FakeClock()
        runner = Runner(self.cfg, make_bot(game, clock), clock=clock.now, focus=focus, log=lambda m: None)
        while clock.t < seconds:
            clock.sleep(runner.tick())
        return runner

    def test_each_task_on_its_own_interval(self):
        game = FakeGame(ready=False)
        runner = self.run_for(game, 61)
        feeder_runs, tower_runs, rebirth_runs = runner.done
        # comedouro a cada 10s: ~6 vezes em 60s (cada rodada tambem gasta tempo)
        self.assertGreaterEqual(feeder_runs, 5)
        self.assertEqual(game.feeder, 2 * feeder_runs)
        # torre: clicou TORRE uma vez; depois o botao virou RECUAR
        self.assertEqual(game.clicked.count('tower'), 1)
        self.assertEqual(tower_runs, 1)
        # renascer nunca liberou
        self.assertEqual(rebirth_runs, 0)
        self.assertEqual(game.rebirths, 0)

    def test_rebirth_when_ready(self):
        config = copy(TASKS_CONFIG)
        by_name = {t['name']: t for t in config['tasks']}
        config['tasks'] = [by_name['renascer'], by_name['torre'], by_name['comedouro']]
        self.ws.write(config)
        self.cfg = self.ws.load()
        game = FakeGame(ready=True)
        runner = self.run_for(game, 5)
        self.assertEqual(runner.done[0], 1)
        self.assertEqual(game.rebirths, 1)

    def test_tower_before_rebirth_blocks_it(self):
        # ordem antiga (torre antes de renascer): a torre manda o galo e o menu
        # passa a mostrar VOLTE no lugar do REBIRTH
        game = FakeGame(ready=True)
        self.run_for(game, 5)
        self.assertEqual(game.rebirths, 0)
        self.assertIn('tower', game.clicked)

    def test_focus_before_each_task(self):
        calls = []
        self.run_for(FakeGame(ready=False), 1, focus=lambda: calls.append(1))
        self.assertEqual(len(calls), 3)

    def test_rebirth_and_feeder_before_each_tower_run(self):
        # ordem do config.example.json: renascer, comedouro (E + espera), torre
        config = copy(TASKS_CONFIG)
        by_name = {t['name']: t for t in config['tasks']}
        by_name['comedouro']['steps'].append({'name': 'esperar', 'pause': 2})
        config['tasks'] = [by_name['renascer'], by_name['comedouro'], by_name['torre']]
        for t in config['tasks']:
            t['every_seconds'] = 10
        self.ws.write(config)
        cfg = self.ws.load()
        clock = FakeClock()
        logs = []
        game = FakeGame(ready=False)
        runner = Runner(cfg, make_bot(game, clock), clock=clock.now, log=logs.append)
        while clock.t < 60:
            clock.sleep(runner.tick())
            game.in_tower = False   # o galo volta logo: TORRE aparece de novo
        runs = [m for m in logs if m in ('renascer', 'torre', 'comedouro')]
        self.assertGreaterEqual(runs.count('torre'), 4)
        for i, name in enumerate(runs):
            if name == 'torre':
                self.assertTrue(i > 1 and runs[i - 2:i] == ['renascer', 'comedouro'], runs)

    def test_after_rebirth_feeder_then_wait_then_tower(self):
        """Pedido do usuario: depois de renascer, cria o comedouro (E), espera
        2 s e so entao manda a galinha para a torre."""
        config = copy(TASKS_CONFIG)
        by_name = {t['name']: t for t in config['tasks']}
        by_name['comedouro']['steps'].append({'name': 'esperar o comedouro', 'pause': 2})
        config['tasks'] = [by_name['renascer'], by_name['comedouro'], by_name['torre']]
        self.ws.write(config)
        cfg = self.ws.load()
        clock = FakeClock()
        events = []
        game = FakeGame(ready=True, confirm_dialog=False)

        def click(x, y):
            game.click(x, y)
            events.append((game.clicked[-1], clock.t))

        def press(key, hold):
            game.press(key, hold)
            events.append(('E', clock.t))

        bot = Bot(game.grab, click, press, sleep=clock.sleep, clock=clock.now, log=lambda m: None)
        Runner(cfg, bot, clock=clock.now, log=lambda m: None).tick()
        names = [n for n, _ in events]
        self.assertEqual(names, ['menu', 'rebirth', 'close', 'E', 'E', 'tower'])
        self.assertEqual(game.rebirths, 1)
        self.assertGreaterEqual(events[-1][1] - events[-2][1], 2, '2 s entre o ultimo E e a TORRE')

    def run_flow(self, game, seconds=30):
        self.ws.write(FLOW_CONFIG)
        cfg = self.ws.load()
        clock = FakeClock()
        when = []

        def click(x, y):
            game.click(x, y)
            when.append((game.clicked[-1], clock.t))

        bot = Bot(game.grab, click, game.press, sleep=clock.sleep, clock=clock.now, log=lambda m: None)
        runner = Runner(cfg, bot, clock=clock.now, log=lambda m: None)
        while clock.t < seconds:
            clock.sleep(runner.tick())
        return when

    def test_rebirth_with_chicken_in_tower(self):
        """Pedido do usuario: com VOLTE PRO SEU GALINHEIRO no menu, fecha o
        menu, clica em RECUAR, espera 8 s e renasce; depois o galo novo vai
        para a torre."""
        game = FakeGame(ready=True, confirm_dialog=False)
        game.in_tower = True
        when = self.run_flow(game)
        names = [n for n, _ in when]
        self.assertEqual(names[:7], ['menu', 'close', 'retreat', 'menu', 'rebirth', 'close', 'tower'])
        self.assertEqual(game.rebirths, 1)
        t_retreat, t_reopen = when[2][1], when[3][1]
        self.assertGreaterEqual(t_reopen - t_retreat, 8, 'espera 8 s depois do RECUAR')
        self.assertTrue(game.in_tower, 'o galo novo foi mandado para a torre')
        self.assertNotIn(None, names, 'nenhum clique fora de botao')

    def test_rebirth_with_chicken_home(self):
        game = FakeGame(ready=True, confirm_dialog=False)
        names = [n for n, _ in self.run_flow(game)]
        # "recuar" abre o menu, nao ve VOLTE e fecha; "renascer" renasce
        self.assertEqual(names[:6], ['menu', 'close', 'menu', 'rebirth', 'close', 'tower'])
        self.assertNotIn('retreat', names)
        self.assertEqual(game.rebirths, 1)

    def test_no_alert_no_menu(self):
        game = FakeGame(ready=False)
        game.in_tower = True
        names = [n for n, _ in self.run_flow(game)]
        self.assertEqual(names, [], 'sem o !, nao abre menu nem tira o galo da torre')

    def test_tick_returns_time_until_next_task(self):
        clock = FakeClock()
        runner = Runner(self.cfg, make_bot(FakeGame(ready=False), clock), clock=clock.now, log=lambda m: None)
        wait = runner.tick()
        self.assertGreater(wait, 0)
        self.assertAlmostEqual(clock.t + wait, min(runner.next_run))


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def assertConfigError(self, config, fragment):
        self.ws.write(config)
        with self.assertRaises(ConfigError) as ctx:
            self.ws.load()
        self.assertIn(fragment, str(ctx.exception))

    def test_short_form_becomes_one_task(self):
        cfg = self.ws.load()
        self.assertEqual(len(cfg.tasks), 1)
        task = cfg.tasks[0]
        self.assertEqual(task.every_seconds, 30)
        self.assertEqual(task.steps[0].image, (self.ws.dir / 'templates/menu.png').resolve())
        self.assertEqual(task.steps[1].wait, 2)
        self.assertTrue(task.steps[2].optional)
        self.assertEqual(task.steps[0].confidence, 0.85)
        self.assertEqual(len(task.cleanup), 1)

    def test_tasks_form(self):
        self.ws.write(TASKS_CONFIG)
        cfg = self.ws.load()
        self.assertEqual([t.name for t in cfg.tasks], ['comedouro', 'torre', 'renascer'])
        self.assertEqual([t.every_seconds for t in cfg.tasks], [10, 20, 30])
        self.assertEqual(cfg.tasks[0].steps[0].key, 'e')
        self.assertEqual(cfg.tasks[0].steps[0].repeat, 2)

    def test_task_interval_defaults_to_top_level(self):
        config = copy(TASKS_CONFIG)
        config['interval_seconds'] = 45
        del config['tasks'][0]['every_seconds']
        self.ws.write(config)
        self.assertEqual(self.ws.load().tasks[0].every_seconds, 45)

    def test_tasks_and_steps_together(self):
        self.assertConfigError({**TASKS_CONFIG, 'steps': CONFIG['steps']}, 'nao os dois')

    def test_empty_tasks(self):
        self.assertConfigError({'tasks': []}, 'pelo menos uma tarefa')

    def test_task_without_steps(self):
        self.assertConfigError({'tasks': [{'name': 'x'}]}, 'pelo menos um passo')

    def test_unknown_task_key(self):
        config = copy(TASKS_CONFIG)
        config['tasks'][0]['loop'] = True
        self.assertConfigError(config, 'loop')

    def test_per_step_override(self):
        config = copy(CONFIG)
        config['confidence'] = 0.9
        config['steps'][1]['confidence'] = 0.7
        self.ws.write(config)
        steps = self.ws.load().tasks[0].steps
        self.assertEqual(steps[0].confidence, 0.9)
        self.assertEqual(steps[1].confidence, 0.7)

    def test_unknown_key(self):
        self.assertConfigError({**CONFIG, 'loop': True}, 'loop')

    def test_unknown_step_key(self):
        config = copy(CONFIG)
        config['steps'][0]['clicks'] = 3
        self.assertConfigError(config, 'clicks')

    def test_image_and_pos_together(self):
        config = copy(CONFIG)
        config['steps'][0]['pos'] = [10, 10]
        self.assertConfigError(config, 'exatamente um')

    def test_key_and_image_together(self):
        config = copy(CONFIG)
        config['steps'][0]['key'] = 'e'
        self.assertConfigError(config, 'exatamente um')

    def test_bad_key(self):
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'key': 'abc'}
        self.assertConfigError(config, '"key"')

    def test_named_key(self):
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'key': 'Space'}
        self.ws.write(config)
        self.assertEqual(self.ws.load().tasks[0].steps[0].key, 'space')

    def test_click_method(self):
        self.assertIsNone(self.ws.load().click_method)
        self.ws.write({**CONFIG, 'click_method': 'directinput'})
        self.assertEqual(self.ws.load().click_method, 'directinput')

    def test_bad_click_method(self):
        self.assertConfigError({**CONFIG, 'click_method': 'mouse'}, 'click_method')

    def color_step(self, **kw):
        step = {'name': 'alerta', 'color': '#FF3D02', 'area': [0.5, 0, 1, 0.5], 'click': False}
        step.update(kw)
        return {**CONFIG, 'steps': [step], 'cleanup': []}

    def test_color_step(self):
        self.ws.write(self.color_step(min_pixels=40))
        step = self.ws.load().tasks[0].steps[0]
        self.assertEqual(step.color, (2, 61, 255))
        self.assertEqual(step.area, (0.5, 0.0, 1.0, 0.5))
        self.assertEqual(step.min_pixels, 40)
        self.assertFalse(step.click)

    def test_color_step_needs_area(self):
        config = self.color_step()
        del config['steps'][0]['area']
        self.assertConfigError(config, '"area"')

    def test_bad_color(self):
        self.assertConfigError(self.color_step(color='vermelho'), '#RRGGBB')
        self.assertConfigError(self.color_step(color='#ZZ0000'), '#RRGGBB')

    def test_dull_color_rejected(self):
        self.assertConfigError(self.color_step(color='#808080'), 'apagada')

    def test_bad_area(self):
        self.assertConfigError(self.color_step(area=[0.9, 0, 0.5, 1]), 'esquerda < direita')
        self.assertConfigError(self.color_step(area=[0, 0, 2, 1]), 'de 0 a 1')

    def test_area_needs_image_or_color(self):
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'key': 'e', 'area': [0, 0, 1, 1]}
        self.assertConfigError(config, '"area" so vale')

    def test_color_and_image_together(self):
        config = copy(CONFIG)
        config['steps'][0]['color'] = '#FF3D02'
        self.assertConfigError(config, 'exatamente um')

    def test_bad_pause(self):
        for value in (0, -1, 'dois'):
            with self.subTest(value=value):
                config = copy(CONFIG)
                config['steps'][0] = {'name': 'x', 'pause': value}
                self.assertConfigError(config, 'pause')

    def test_pause_and_key_together(self):
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'pause': 2, 'key': 'e'}
        self.assertConfigError(config, 'exatamente um')

    def test_size_range(self):
        config = copy(CONFIG)
        config['steps'][1]['size_range'] = 0.1
        self.ws.write(config)
        step = self.ws.load().tasks[0].steps[1]
        self.assertEqual(step.size_range, 0.1)
        self.assertEqual(len(step.variants), 11)
        self.assertEqual(len(self.ws.load().tasks[0].steps[0].variants), 1)

    def test_bad_size_range(self):
        config = copy(CONFIG)
        config['steps'][1]['size_range'] = 0.9
        self.assertConfigError(config, 'size_range')
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'key': 'e', 'size_range': 0.1}
        self.assertConfigError(config, '"size_range" so vale')

    def test_bad_click(self):
        config = copy(CONFIG)
        config['steps'][0]['click'] = 'nao'
        self.assertConfigError(config, '"click"')

    def test_click_false_needs_image(self):
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'key': 'e', 'click': False}
        self.assertConfigError(config, '"click": false')

    def test_bad_repeat(self):
        config = copy(CONFIG)
        config['steps'][0]['repeat'] = 0
        self.assertConfigError(config, 'repeat')

    def test_missing_image_tells_how_to_capture(self):
        config = copy(CONFIG)
        config['steps'][0]['image'] = 'templates/nao_existe.png'
        self.assertConfigError(config, 'capture templates/nao_existe.png')

    def test_flat_image_rejected(self):
        for name, color in (('cinza', (90, 90, 90)), ('verde', GREEN)):
            with self.subTest(name):
                flat = np.zeros((30, 60, 3), np.uint8)
                flat[:] = color
                save_image(self.ws.dir / f'templates/{name}.png', flat)
                config = copy(CONFIG)
                config['steps'][0]['image'] = f'templates/{name}.png'
                self.assertConfigError(config, 'cor lisa')

    def test_no_steps(self):
        self.assertConfigError({**CONFIG, 'steps': []}, 'steps')

    def test_bad_confidence(self):
        self.assertConfigError({**CONFIG, 'confidence': 2}, 'confidence')

    def test_bad_pos(self):
        config = copy(CONFIG)
        config['steps'][0] = {'name': 'x', 'pos': [1]}
        self.assertConfigError(config, '[x, y]')

    def test_invalid_json(self):
        (self.ws.dir / 'config.json').write_text('{ "steps": [ }', encoding='utf-8')
        with self.assertRaises(ConfigError):
            self.ws.load()

    def test_example_config_steps_used_by_real_tests(self):
        self.assertIsNone(STEP_RENASCER.image)
        self.assertEqual(STEP_RENASCER.color, parse_color('#2EAF3D'))
        self.assertEqual(STEP_RENASCIMENTO.image.name, 'renascimento.png')
        self.assertEqual(STEP_TORRE.image.name, 'botao_torre.png')
        self.assertIsNotNone(STEP_RENASCIMENTO.mask)
        self.assertIsNotNone(STEP_TORRE.mask)

    def test_example_config_loads_as_is(self):
        # Todos os recortes do exemplo vem prontos em templates/.
        cfg = load_config(Path(__file__).resolve().parent.parent / 'config.example.json')
        names = [t.name for t in cfg.tasks]
        # recuar logo antes de renascer (o renascer roda depois dos 8 s); depois
        # de renascer cria o comedouro, espera 2 s e so entao manda para a torre
        self.assertEqual(names, ['recuar galo para renascer', 'renascer', 'melhorar comedouro',
                                 'mandar galo para a torre'])
        self.assertEqual(STEP_VOLTE.size_range, 0.1)
        self.assertIsNotNone(STEP_VOLTE.area)
        self.assertEqual(STEP_RENASCER.min_pixels, 7000)
        self.assertIsNotNone(STEP_RENASCER.area)
        feeder = EXAMPLE_TASKS['melhorar comedouro'].steps
        self.assertEqual([s.key for s in feeder], ['e', None])
        self.assertEqual(feeder[-1].pause, 2)
        self.assertEqual({t.every_seconds for t in cfg.tasks}, {10}, 'mesmo ritmo: a ordem vale em toda rodada')
        self.assertEqual(STEP_RECUAR.after, 8)
        alert = cfg.tasks[1].steps[0]
        self.assertFalse(alert.click)
        self.assertEqual(alert.color, parse_color('#FF3D02'))
        self.assertIsNotNone(alert.area)


if __name__ == '__main__':
    unittest.main()
