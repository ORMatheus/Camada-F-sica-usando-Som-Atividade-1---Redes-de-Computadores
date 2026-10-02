# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Acesso à placa de som: único módulo que fala com o microfone e o alto-falante.

Os demais módulos trabalham só com vetores numpy (float32, entre -1 e 1),
o que permite testá-los sem microfone.
"""

import queue
from collections.abc import Iterator

import numpy as np
import sounddevice as sd

from config import AMOSTRAS_POR_JANELA, TAXA_AMOSTRAGEM


def rms(janela: np.ndarray) -> float:
    """Energia média (raiz do valor quadrático médio) de um trecho de áudio."""
    return float(np.sqrt(np.mean(np.square(janela, dtype=np.float64))))


def tocar(sinal: np.ndarray, taxa: int = TAXA_AMOSTRAGEM) -> None:
    """Toca o sinal no alto-falante e espera terminar."""
    sd.play(np.asarray(sinal, dtype=np.float32), taxa)
    sd.wait()


def gravar(duracao: float, taxa: int = TAXA_AMOSTRAGEM) -> np.ndarray:
    """Grava `duracao` segundos do microfone e devolve um vetor mono."""
    gravacao = sd.rec(int(duracao * taxa), samplerate=taxa, channels=1, dtype="float32")
    sd.wait()
    return gravacao[:, 0]


def janelas_do_microfone(taxa: int = TAXA_AMOSTRAGEM,
                         tamanho: int = AMOSTRAS_POR_JANELA) -> Iterator[np.ndarray]:
    """Gerador sem fim: entrega blocos de `tamanho` amostras conforme chegam do microfone.

    O sounddevice chama `ao_receber` numa thread própria; a fila passa os blocos
    para quem está consumindo o gerador. Interrompa com Ctrl+C.
    """
    fila: queue.Queue[np.ndarray] = queue.Queue()

    def ao_receber(dados, quadros, tempo, status):
        fila.put(dados[:, 0].copy())

    with sd.InputStream(samplerate=taxa, channels=1, blocksize=tamanho,
                        dtype="float32", callback=ao_receber):
        while True:
            yield fila.get()
