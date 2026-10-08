"""
Busca de botao na tela por template matching (OpenCV).

Modulo puro: recebe imagens BGR e diz onde o recorte casou. Nao captura tela
nem mexe no mouse, para poder ser testado sem o Roblox aberto.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

# Desvio padrao minimo dos pixels do recorte. Recorte de cor lisa da score 1.0
# em qualquer lugar da tela (o OpenCV nao tem formato para comparar).
MIN_DETAIL = 5.0


@dataclass
class Frame:
    """Uma captura de tela e onde ela fica nas coordenadas do mouse."""
    image: np.ndarray   # BGR
    left: int = 0
    top: int = 0
    scale: float = 1.0  # pixels da imagem por unidade de coordenada do mouse

    def to_screen(self, x, y):
        return round(self.left + x / self.scale), round(self.top + y / self.scale)

    def to_image(self, x, y):
        return round((x - self.left) * self.scale), round((y - self.top) * self.scale)


@dataclass
class Match:
    score: float        # 0..1, quanto o formato bate
    color_diff: float   # maior diferenca de cor media por canal, 0..255
    center: tuple       # (x, y) na imagem buscada
    found: bool


def load_image(path):
    # imdecode em vez de imread: imread falha com acento no caminho no Windows
    # (ex.: C:\Users\Joao com til).
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if img is None:
        raise ValueError(f'nao consegui abrir a imagem {path}')
    return img


def save_image(path, image):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or '.png', image)
    if not ok:
        raise ValueError(f'nao consegui salvar {path}')
    buf.tofile(str(path))


def has_detail(image):
    return float(image.std()) >= MIN_DETAIL


def find_template(screen, template, confidence, color_tolerance):
    """Melhor posicao do template na tela.

    O formato sozinho nao separa botao liberado de botao desabilitado: os dois
    tem o mesmo texto e borda, so muda a cor (verde x cinza). Por isso, alem do
    score de formato, a cor media do trecho achado tem que bater com a do
    recorte.
    """
    th, tw = template.shape[:2]
    sh, sw = screen.shape[:2]
    if th > sh or tw > sw or not has_detail(template):
        return Match(0.0, 255.0, (0, 0), False)

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    # Trecho de tela de cor lisa da divisao por zero e pode virar NaN/inf.
    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    _, score, _, (x, y) = cv2.minMaxLoc(result)

    patch = screen[y:y + th, x:x + tw]
    color_diff = float(np.abs(patch.mean(axis=(0, 1)) - template.mean(axis=(0, 1))).max())
    found = score >= confidence and color_diff <= color_tolerance
    return Match(float(score), color_diff, (x + tw // 2, y + th // 2), found)
