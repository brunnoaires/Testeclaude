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


def _decode(path, flags):
    # imdecode em vez de imread: imread falha com acento no caminho no Windows
    # (ex.: C:\Users\Joao com til).
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, flags) if data.size else None
    if img is None:
        raise ValueError(f'nao consegui abrir a imagem {path}')
    return img


def load_image(path):
    return _decode(path, cv2.IMREAD_COLOR)


def load_template(path):
    """Recorte e mascara. A mascara vem da transparencia do PNG: o que e
    transparente e cenario e fica de fora da comparacao. Sem transparencia,
    a mascara e None e o recorte inteiro conta."""
    img = _decode(path, cv2.IMREAD_UNCHANGED)
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), None
    if img.shape[2] == 4:
        alpha = img[..., 3]
        bgr = np.ascontiguousarray(img[..., :3])
        return bgr, (alpha > 127) if (alpha < 255).any() else None
    return img, None


def save_image(path, image):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or '.png', image)
    if not ok:
        raise ValueError(f'nao consegui salvar {path}')
    buf.tofile(str(path))


def _pixels(image, mask):
    return image[mask] if mask is not None else image.reshape(-1, image.shape[-1])


def has_detail(image, mask=None):
    pixels = _pixels(image, mask)
    return len(pixels) >= 20 and float(pixels.std()) >= MIN_DETAIL


def find_template(screen, template, confidence, color_tolerance, mask=None):
    """Melhor posicao do template na tela.

    O formato sozinho nao separa botao liberado de botao desabilitado: os dois
    tem o mesmo texto e borda, so muda a cor (verde x cinza). Por isso, alem do
    score de formato, a cor media do trecho achado tem que bater com a do
    recorte.

    Com mascara (True = botao, False = cenario), formato e cor so olham os
    pixels do botao: o cenario 3D atras dele pode mudar a vontade.
    """
    th, tw = template.shape[:2]
    sh, sw = screen.shape[:2]
    if th > sh or tw > sw or not has_detail(template, mask):
        return Match(0.0, 255.0, (0, 0), False)

    if mask is None:
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    else:
        cv_mask = np.repeat(mask.astype(np.uint8)[..., None] * 255, 3, axis=2)
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED, mask=cv_mask)
    # Trecho de tela de cor lisa da divisao por zero e vira NaN/inf; com
    # mascara, tambem pode sair um valor bem acima de 1. Nenhum deles e acerto.
    result[~np.isfinite(result) | (result > 1.0001)] = 0.0
    _, score, _, (x, y) = cv2.minMaxLoc(result)

    patch = screen[y:y + th, x:x + tw]
    color_diff = float(np.abs(_pixels(patch, mask).mean(axis=0) - _pixels(template, mask).mean(axis=0)).max())
    found = score >= confidence and color_diff <= color_tolerance
    return Match(min(float(score), 1.0), color_diff, (x + tw // 2, y + th // 2), found)
