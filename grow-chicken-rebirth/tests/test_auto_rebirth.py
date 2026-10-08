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

from auto_rebirth import Bot, ConfigError, load_config  # noqa: E402
from vision import Frame, find_template, save_image  # noqa: E402

GREEN, GRAY, BLUE, RED, YELLOW = (40, 190, 60), (130, 130, 130), (200, 120, 30), (40, 40, 210), (30, 200, 230)

# nome: (x, y, largura, altura, texto)
BUTTONS = {
    'menu': (20, 520, 140, 50, 'MENU'),
    'rebirth': (300, 250, 200, 60, 'REBIRTH'),
    'confirm': (340, 360, 120, 50, 'OK'),
    'close': (560, 150, 50, 50, 'X'),
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


class FakeGame:
    """HUD com botao de menu; menu com Rebirth (verde liberado, cinza nao) e X;
    dialogo de confirmacao opcional."""

    def __init__(self, ready=True, confirm_dialog=True, left=0, top=0, scale=1.0):
        self.ready, self.confirm_dialog = ready, confirm_dialog
        self.left, self.top, self.scale = left, top, scale
        self.menu = self.confirming = False
        self.rebirths = 0
        self.clicked = []
        self.background = np.random.default_rng(7).integers(0, 255, (600, 800, 3), dtype=np.uint8)

    def grab(self):
        img = self.background.copy()
        draw_button(img, 'menu', BLUE)
        if self.menu:
            draw_button(img, 'rebirth', GREEN if self.ready else GRAY)
            draw_button(img, 'close', RED)
        if self.confirming:
            draw_button(img, 'confirm', YELLOW)
        return Frame(img, self.left, self.top, self.scale)

    def _hit(self, x, y):
        visible = {'menu'}
        if self.menu:
            visible |= {'rebirth', 'close'}
        if self.confirming:
            visible.add('confirm')
        for name in visible:
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
        elif name == 'rebirth' and self.ready:
            if self.confirm_dialog:
                self.confirming = True
            else:
                self._rebirth()
        elif name == 'confirm':
            self._rebirth()
        elif name == 'close':
            self.menu = self.confirming = False

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


class Workspace:
    """Pasta temporaria com config.json e os recortes."""

    def __init__(self, config=CONFIG):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        save_image(self.dir / 'templates/menu.png', template_for('menu', BLUE))
        save_image(self.dir / 'templates/rebirth.png', template_for('rebirth', GREEN))
        save_image(self.dir / 'templates/confirm.png', template_for('confirm', YELLOW))
        save_image(self.dir / 'templates/close.png', template_for('close', RED))
        self.write(config)

    def write(self, config):
        (self.dir / 'config.json').write_text(json.dumps(config), encoding='utf-8')
        return self.dir / 'config.json'

    def load(self):
        return load_config(self.dir / 'config.json')

    def close(self):
        self._tmp.cleanup()


def make_bot(cfg, game):
    clock = FakeClock()
    return Bot(cfg, game.grab, game.click, sleep=clock.sleep, clock=clock.now, log=lambda m: None)


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


class CycleTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.cfg = self.ws.load()

    def tearDown(self):
        self.ws.close()

    def test_full_rebirth_with_confirm(self):
        game = FakeGame()
        self.assertTrue(make_bot(self.cfg, game).cycle())
        self.assertEqual(game.rebirths, 1)
        self.assertEqual(game.clicked, ['menu', 'rebirth', 'confirm', 'close'])
        self.assertFalse(game.menu)

    def test_not_ready_aborts_and_closes_menu(self):
        game = FakeGame(ready=False)
        self.assertFalse(make_bot(self.cfg, game).cycle())
        self.assertEqual(game.rebirths, 0)
        self.assertEqual(game.clicked, ['menu', 'close'])
        self.assertFalse(game.menu)

    def test_optional_confirm_missing(self):
        game = FakeGame(confirm_dialog=False)
        self.assertTrue(make_bot(self.cfg, game).cycle())
        self.assertEqual(game.rebirths, 1)
        self.assertEqual(game.clicked, ['menu', 'rebirth', 'close'])

    def test_waits_until_ready_across_cycles(self):
        game = FakeGame(ready=False)
        bot = make_bot(self.cfg, game)
        self.assertFalse(bot.cycle())
        game.ready = True
        self.assertTrue(bot.cycle())
        self.assertFalse(bot.cycle(), 'depois do rebirth o botao volta a ficar cinza')
        self.assertEqual(game.rebirths, 1)

    def test_window_offset_and_scale(self):
        game = FakeGame(left=300, top=120, scale=2.0)
        self.assertTrue(make_bot(self.cfg, game).cycle())
        self.assertEqual(game.rebirths, 1)
        self.assertNotIn(None, game.clicked)

    def test_fixed_position_step(self):
        x, y, w, h, _ = BUTTONS['menu']
        config = json.loads(json.dumps(CONFIG))
        config['steps'][0] = {'name': 'abrir menu', 'pos': [x + w // 2, y + h // 2]}
        self.ws.write(config)
        game = FakeGame()
        self.assertTrue(make_bot(self.ws.load(), game).cycle())
        self.assertEqual(game.clicked[0], 'menu')


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

    def test_example_values_and_paths(self):
        cfg = self.ws.load()
        self.assertEqual(cfg.interval_seconds, 30)
        self.assertEqual(cfg.steps[0].image, (self.ws.dir / 'templates/menu.png').resolve())
        self.assertEqual(cfg.steps[1].wait, 2)
        self.assertTrue(cfg.steps[2].optional)
        self.assertEqual(cfg.steps[0].confidence, 0.85)

    def test_per_step_override(self):
        config = json.loads(json.dumps(CONFIG))
        config['confidence'] = 0.9
        config['steps'][1]['confidence'] = 0.7
        self.ws.write(config)
        cfg = self.ws.load()
        self.assertEqual(cfg.steps[0].confidence, 0.9)
        self.assertEqual(cfg.steps[1].confidence, 0.7)

    def test_unknown_key(self):
        self.assertConfigError({**CONFIG, 'loop': True}, 'loop')

    def test_unknown_step_key(self):
        config = json.loads(json.dumps(CONFIG))
        config['steps'][0]['clicks'] = 3
        self.assertConfigError(config, 'clicks')

    def test_image_and_pos_together(self):
        config = json.loads(json.dumps(CONFIG))
        config['steps'][0]['pos'] = [10, 10]
        self.assertConfigError(config, 'exatamente um')

    def test_missing_image_tells_how_to_capture(self):
        config = json.loads(json.dumps(CONFIG))
        config['steps'][0]['image'] = 'templates/nao_existe.png'
        self.assertConfigError(config, 'capture templates/nao_existe.png')

    def test_flat_image_rejected(self):
        save_image(self.ws.dir / 'templates/liso.png', np.full((30, 60, 3), 90, np.uint8))
        config = json.loads(json.dumps(CONFIG))
        config['steps'][0]['image'] = 'templates/liso.png'
        self.assertConfigError(config, 'cor lisa')

    def test_no_steps(self):
        self.assertConfigError({**CONFIG, 'steps': []}, 'steps')

    def test_bad_confidence(self):
        self.assertConfigError({**CONFIG, 'confidence': 2}, 'confidence')

    def test_bad_pos(self):
        config = json.loads(json.dumps(CONFIG))
        config['steps'][0] = {'name': 'x', 'pos': [1]}
        self.assertConfigError(config, '[x, y]')

    def test_invalid_json(self):
        (self.ws.dir / 'config.json').write_text('{ "steps": [ }', encoding='utf-8')
        with self.assertRaises(ConfigError):
            self.ws.load()

    def test_example_config_is_valid_shape(self):
        example = json.loads((Path(__file__).resolve().parent.parent / 'config.example.json')
                             .read_text(encoding='utf-8'))
        # As imagens do exemplo nao existem no repo; troca pelas de teste e
        # confere que o resto da config e aceito.
        for group in ('steps', 'cleanup'):
            for step in example.get(group, []):
                if 'image' in step:
                    step['image'] = 'templates/menu.png'
        self.ws.write(example)
        self.ws.load()


if __name__ == '__main__':
    unittest.main()
