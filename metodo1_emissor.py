# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Emissor do Método 1: transforma texto em quadros e quadros em batidas.

Primeiro decidimos O QUE transmitir (quadros de 9 bits e os instantes de cada
batida). Depois, COMO transmitir: tocando "tocs" sintetizados no alto-falante
ou guiando uma pessoa, pela tela, a bater na mesa no tempo certo.
"""

import time

import numpy as np

import audio
from config import (INTERVALO_BATIDAS, PAUSA_ENTRE_QUADROS, SILENCIO_BITS,
                    TAXA_AMOSTRAGEM)
from quadro import TAMANHO_DADOS, montar_quadro

DURACAO_TOC = 0.025        # s, duração de cada "toc" sintetizado
DECAIMENTO_TOC = 0.006     # s, constante de tempo do decaimento (mais longo = mais energia, mais "rabo")
AMPLITUDE_TOC = 0.8        # pico do "toc" (o sinal vai de -1 a 1)
SILENCIO_BORDAS = 0.3      # s de silêncio antes e depois das batidas
CONTAGEM_REGRESSIVA = 3    # s de contagem antes do modo guiado começar


def quadro_para_instantes(quadro: list[int],
                          intervalo: float = INTERVALO_BATIDAS,
                          silencio: float = SILENCIO_BITS) -> list[float]:
    """Retorna os instantes (em segundos, a partir de 0.0) de cada batida do quadro.

    Regras:
      - bit 0: uma batida no instante t
      - bit 1: duas batidas, em t e em t + intervalo
      - o próximo bit começa `silencio` segundos depois da última batida do bit atual

    Exemplo (intervalo=0.15, silencio=0.6): [1, 0] -> [0.0, 0.15, 0.75]
    """
    instantes = []
    t = 0.0
    for bit in quadro:
        instantes.append(t)
        if bit == 1:
            t = t + intervalo
            instantes.append(t)
        t = t + silencio
    return instantes


def quadros_para_instantes(quadros: list[list[int]],
                           pausa: float = PAUSA_ENTRE_QUADROS) -> list[float]:
    """Instantes de batida de todos os quadros, um depois do outro na linha do tempo.

    Cada quadro começa `pausa` segundos depois da última batida do quadro
    anterior. Assim o receptor tem tempo de fechar um quadro antes do próximo.
    Exemplo (intervalo 0.25, pausa 2.5): [[1], [0]] -> [0.0, 0.25, 2.75]
    """
    todos: list[float] = []
    inicio = 0.0
    for quadro in quadros:
        for instante in quadro_para_instantes(quadro):
            todos.append(inicio + instante)
        inicio = todos[-1] + pausa
    return todos


def texto_para_quadros(texto: str) -> list[list[int]]:
    """Um quadro de 9 bits por caractere. ValueError se houver caractere não-ASCII."""
    quadros = []
    for caractere in texto:
        quadros.append(montar_quadro(caractere))
    return quadros


def inverter_bit(quadro: list[int], posicao: int = 0) -> list[int]:
    """Devolve uma CÓPIA do quadro com o bit `posicao` trocado (0 vira 1, 1 vira 0).

    Usado para simular erro: como a paridade já foi calculada, o receptor
    deve perceber a diferença e acusar FALHA.
    """
    copia = list(quadro)
    copia[posicao] = 1 - copia[posicao]
    return copia


def sintetizar_batidas(instantes: list[float],
                       taxa: int = TAXA_AMOSTRAGEM) -> np.ndarray:
    """Gera o áudio (float32) com um "toc" curto em cada instante.

    O "toc" é ruído com decaimento exponencial: começa no máximo de uma vez
    (fácil de detectar) e some em ~25 ms, para não parecer uma segunda batida.
    """
    # Molde do "toc": ruído branco multiplicado por uma exponencial decrescente.
    # Semente fixa para o som ser sempre o mesmo (testes reproduzíveis).
    gerador = np.random.default_rng(0)
    amostras_toc = int(DURACAO_TOC * taxa)
    tempo_toc = np.arange(amostras_toc) / taxa
    ruido = gerador.uniform(-1.0, 1.0, amostras_toc)
    toc = ruido * np.exp(-tempo_toc / DECAIMENTO_TOC)
    toc = AMPLITUDE_TOC * toc / np.max(np.abs(toc))

    ultimo_instante = max(instantes) if instantes else 0.0
    duracao_total = SILENCIO_BORDAS + ultimo_instante + DURACAO_TOC + SILENCIO_BORDAS
    sinal = np.zeros(int(duracao_total * taxa), dtype=np.float32)

    for instante in instantes:
        inicio = int((SILENCIO_BORDAS + instante) * taxa)
        sinal[inicio:inicio + amostras_toc] += toc

    return sinal


def _esperar_ate(momento: float) -> None:
    """Dorme até o relógio time.perf_counter() chegar em `momento`."""
    restante = momento - time.perf_counter()
    if restante > 0:
        time.sleep(restante)


def _guiar_batidas(quadro: list[int]) -> None:
    """Mostra na tela, no tempo certo, quando a pessoa deve bater na mesa."""
    for segundos in range(CONTAGEM_REGRESSIVA, 0, -1):
        print(f"  Prepare-se... {segundos}")
        time.sleep(1)

    instantes = quadro_para_instantes(quadro)

    # Um rótulo por batida, na mesma ordem dos instantes (bit 1 tem dois)
    rotulos = []
    for posicao, bit in enumerate(quadro):
        rotulos.append(f"bit {posicao + 1} = {bit}")
        if bit == 1:
            rotulos.append(f"bit {posicao + 1} = {bit}")

    # perf_counter é um relógio preciso; medimos tudo a partir do início
    inicio = time.perf_counter()
    for instante, rotulo in zip(instantes, rotulos):
        _esperar_ate(inicio + instante)
        print(f"  TOC!   ({rotulo})")


def transmitir_texto(texto: str, guiado: bool = False,
                     simular_erro: bool = False) -> None:
    """Envia o texto caractere por caractere, um quadro de 9 bits por vez.

    guiado=False: toca os "tocs" no alto-falante.
    guiado=True: mostra na tela quando bater (a pessoa faz o som).
    simular_erro=True: inverte um bit de dados do 1º quadro DEPOIS de calcular a
    paridade, para o receptor acusar FALHA DE TRANSMISSÃO.
    """
    quadros = texto_para_quadros(texto)
    if len(quadros) == 0:
        print("Nada para transmitir: o texto está vazio.")
        return

    for numero, quadro in enumerate(quadros):
        caractere = texto[numero]
        dados = "".join(str(bit) for bit in quadro[:TAMANHO_DADOS])
        paridade = quadro[TAMANHO_DADOS]
        print(f"Quadro {numero + 1}/{len(quadros)}: '{caractere}' -> {dados} {paridade}")

        if simular_erro and numero == 0:
            quadro = inverter_bit(quadro, 0)
            dados = "".join(str(bit) for bit in quadro[:TAMANHO_DADOS])
            print(f"  [SIMULAÇÃO DE ERRO] bit 1 invertido, enviando {dados} {paridade}")

        if guiado:
            _guiar_batidas(quadro)
        else:
            instantes = quadro_para_instantes(quadro)
            audio.tocar(sintetizar_batidas(instantes))

        # Silêncio longo: o receptor fecha o quadro atual antes do próximo começar
        if numero < len(quadros) - 1:
            time.sleep(PAUSA_ENTRE_QUADROS)

    print("Transmissão concluída.")
