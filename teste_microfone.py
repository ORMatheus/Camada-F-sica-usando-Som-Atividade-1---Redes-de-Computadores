# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Confere o microfone: mostra o nível do som em tempo real e o limiar do Método 1.

Não é um teste do pytest; rode à mão com:  python teste_microfone.py
Fique em silêncio nos primeiros 2 segundos (medição do ruído de fundo) e
depois bata na mesa para ver se a batida passa do limiar. Ctrl+C encerra.
"""

from statistics import median

from audio import janelas_do_microfone, rms
from config import DURACAO_JANELA, FATOR_LIMIAR, LIMIAR_MINIMO

SEGUNDOS_CALIBRACAO = 2.0  # tempo em silêncio para medir o ruído de fundo
JANELAS_POR_LINHA = 10     # 10 janelas de 10 ms = 1 linha a cada 0,1 s
NIVEL_MAXIMO_BARRA = 0.3   # RMS que enche a barra inteira
LARGURA_BARRA = 50         # caracteres da barra


def desenhar_barra(nivel: float) -> str:
    """Barra de texto proporcional ao nível (cheia em NIVEL_MAXIMO_BARRA)."""
    tamanho = int(nivel / NIVEL_MAXIMO_BARRA * LARGURA_BARRA)
    tamanho = min(tamanho, LARGURA_BARRA)
    return "#" * tamanho + "-" * (LARGURA_BARRA - tamanho)


def principal() -> None:
    """Calibra o ruído de fundo e depois mostra o nível do microfone até Ctrl+C."""
    janelas_calibracao = int(SEGUNDOS_CALIBRACAO / DURACAO_JANELA)
    niveis_calibracao: list[float] = []
    limiar = LIMIAR_MINIMO
    pico_da_linha = 0.0
    janelas_na_linha = 0

    print(f"Fique em silêncio por {SEGUNDOS_CALIBRACAO:.0f} s: medindo o ruído de fundo...")
    try:
        for janela in janelas_do_microfone():
            nivel = rms(janela)

            # Fase 1: só acumula os níveis do silêncio
            if len(niveis_calibracao) < janelas_calibracao:
                niveis_calibracao.append(nivel)
                if len(niveis_calibracao) == janelas_calibracao:
                    # mediana, como no DetectorBatidas: um barulho isolado não estraga a medida
                    ruido = median(niveis_calibracao)
                    limiar = max(LIMIAR_MINIMO, FATOR_LIMIAR * ruido)
                    print(f"Ruído de fundo: {ruido:.4f}   Limiar do Método 1: {limiar:.4f}")
                    print("Agora bata na mesa. Ctrl+C para sair.\n")
                continue

            # Fase 2: guarda o maior nível de 10 janelas e imprime uma linha.
            # Usamos o pico (e não a média) porque uma batida dura poucas janelas
            # e sumiria na média.
            pico_da_linha = max(pico_da_linha, nivel)
            janelas_na_linha += 1
            if janelas_na_linha == JANELAS_POR_LINHA:
                marca = "  <-- BATIDA (passou do limiar)" if pico_da_linha > limiar else ""
                print(f"{pico_da_linha:.4f} |{desenhar_barra(pico_da_linha)}|{marca}")
                pico_da_linha = 0.0
                janelas_na_linha = 0
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    principal()
