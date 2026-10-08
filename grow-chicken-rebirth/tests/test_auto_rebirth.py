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

from auto_rebirth import Bot, ConfigError, Runner, load_config  # noqa: E402
from vision import Frame, find_template, load_image, save_image  # noqa: E402

GREEN, GRAY, BLUE, RED, YELLOW, BROWN = (
    (40, 190, 60), (130, 130, 130), (200, 120, 30), (40, 40, 210), (30, 200, 230), (40, 90, 150))

# nome: (x, y, largura, altura, texto)
BUTTONS = {
    'menu': (20, 520, 140, 50, 'MENU'),
    'rebirth': (300, 250, 200, 60, 'REBIRTH'),
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


class FakeGame:
    """HUD com botao de menu e botao TORRE/RECUAR; menu com Rebirth (verde
    liberado, cinza nao) e X; dialogo de confirmacao opcional; tecla E sobe
    o comedouro."""

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
            names |= {'rebirth', 'close'}
        if self.confirming:
            names.add('confirm')
        return names

    def grab(self):
        img = self.background.copy()
        colors = {'menu': BLUE, 'tower': BROWN, 'retreat': BROWN, 'close': RED, 'confirm': YELLOW,
                  'rebirth': GREEN if self.ready else GRAY}
        for name in ('menu', 'tower', 'retreat', 'rebirth', 'close', 'confirm'):
            if name in self.visible():
                draw_button(img, name, colors[name])
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

    def test_tower_not_confused_with_retreat(self):
        game = FakeGame()
        game.in_tower = True
        m = find_template(game.grab().image, template_for('tower', BROWN), 0.85, 40)
        self.assertFalse(m.found)


class RealGameTest(unittest.TestCase):
    """Pedacos de prints do jogo de verdade: o menu com RENASCER (verde,
    liberado) e com AINDA NAO (marrom, bloqueado), os dois com MARCOS embaixo."""

    FIXTURES = Path(__file__).resolve().parent / 'fixtures'

    def setUp(self):
        self.template = load_image(self.FIXTURES / 'renascer.png')

    def test_renascer_found_when_unlocked(self):
        m = find_template(load_image(self.FIXTURES / 'menu_liberado.png'), self.template, 0.85, 40)
        self.assertTrue(m.found)

    def test_ainda_nao_rejected(self):
        m = find_template(load_image(self.FIXTURES / 'menu_bloqueado.png'), self.template, 0.85, 40)
        self.assertFalse(m.found)
        self.assertLess(m.score, 0.6, 'texto diferente: o formato ja nao deveria bater')


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
        game = FakeGame(ready=True)
        runner = self.run_for(game, 5)
        self.assertEqual(runner.done[2], 1)
        self.assertEqual(game.rebirths, 1)

    def test_focus_before_each_task(self):
        calls = []
        self.run_for(FakeGame(ready=False), 1, focus=lambda: calls.append(1))
        self.assertEqual(len(calls), 3)

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

    def test_bad_repeat(self):
        config = copy(CONFIG)
        config['steps'][0]['repeat'] = 0
        self.assertConfigError(config, 'repeat')

    def test_missing_image_tells_how_to_capture(self):
        config = copy(CONFIG)
        config['steps'][0]['image'] = 'templates/nao_existe.png'
        self.assertConfigError(config, 'capture templates/nao_existe.png')

    def test_flat_image_rejected(self):
        save_image(self.ws.dir / 'templates/liso.png', np.full((30, 60, 3), 90, np.uint8))
        config = copy(CONFIG)
        config['steps'][0]['image'] = 'templates/liso.png'
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

    def test_example_config_is_valid(self):
        example = json.loads((Path(__file__).resolve().parent.parent / 'config.example.json')
                             .read_text(encoding='utf-8'))
        # Nem todas as imagens do exemplo existem no repo (algumas o usuario
        # recorta); troca pelas de teste e confere que o resto e aceito.
        for task in example['tasks']:
            for step in task.get('steps', []) + task.get('cleanup', []):
                if 'image' in step:
                    step['image'] = 'templates/menu.png'
        self.ws.write(example)
        self.assertGreaterEqual(len(self.ws.load().tasks), 3)


if __name__ == '__main__':
    unittest.main()
