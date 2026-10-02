# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Receptor do Método 1: ouve batidas e remonta os quadros de 9 bits.

O caminho é dividido em três etapas, cada uma testável sem microfone:
  1. DetectorBatidas  : janela de áudio (10 ms) -> "começou uma batida agora?"
  2. MontadorQuadros  : instantes das batidas   -> bits -> quadros de 9 bits
  3. relatar_quadro   : quadro                  -> linha de SUCESSO ou FALHA

Um bit que recebe 3 ou mais batidas não é nem 0 nem 1. Ele é guardado como
BIT_INVALIDO (-1) para que o quadro seja reportado como falha. Atenção:
validar_quadro (de quadro.py) só confere a paridade e pode não perceber o -1,
por isso use sempre quadro_integro() para decidir se o quadro chegou bem.
"""

import math
from collections import deque

import numpy as np

from audio import janelas_do_microfone, rms
from config import (DURACAO_JANELA, DURACAO_MAXIMA_BATIDA, FATOR_LIMIAR, FATOR_SUBIDA,
                    JANELAS_AQUECIMENTO, JANELAS_RUIDO, LIMIAR_MINIMO,
                    LIMITE_GRUPO, PERIODO_REFRATARIO, TAXA_AMOSTRAGEM,
                    TIMEOUT_QUADRO)
from quadro import TAMANHO_DADOS, TAMANHO_QUADRO, bits_para_caractere, validar_quadro

BIT_INVALIDO = -1  # marca um bit que recebeu 3 ou mais batidas


class DetectorBatidas:
    """Decide, janela a janela, se uma nova batida começou.

    Uma batida é um SALTO de volume: a janela passa do limiar e está pelo
    menos FATOR_SUBIDA vezes mais forte que a janela de 20 ms atrás.
    O limiar se adapta ao ruído de fundo da sala.
    """

    def __init__(self, taxa: int = TAXA_AMOSTRAGEM):
        self.taxa = taxa  # as janelas recebidas devem ter DURACAO_JANELA segundos nesta taxa
        # Níveis (RMS) das últimas janelas SEM batida: é daqui que sai o ruído de fundo.
        self.historico_ruido: deque[float] = deque(maxlen=JANELAS_RUIDO)
        # Níveis das duas janelas anteriores (10 ms e 20 ms atrás).
        self.nivel_1_atras = 0.0
        self.nivel_2_atras = 0.0
        self.janelas_seguidas_acima = 0
        self.instante_ultima_batida: float | None = None
        self.max_janelas_batida = round(DURACAO_MAXIMA_BATIDA / DURACAO_JANELA)

    def estimar_ruido(self) -> float:
        """Ruído de fundo = mediana do histórico (a mediana ignora picos isolados)."""
        if len(self.historico_ruido) == 0:
            return 0.0
        return float(np.median(list(self.historico_ruido)))

    def limiar(self) -> float:
        """Nível que uma janela precisa passar para contar como batida."""
        return max(LIMIAR_MINIMO, FATOR_LIMIAR * self.estimar_ruido())

    def lembrar_nivel(self, nivel: float) -> None:
        """Guarda o nível desta janela para comparar com as próximas."""
        self.nivel_2_atras = self.nivel_1_atras
        self.nivel_1_atras = nivel

    def processar(self, janela: np.ndarray, instante: float) -> bool:
        """Recebe uma janela de áudio; devolve True se uma NOVA batida começa nela."""
        nivel = rms(janela)

        # Aquecimento: as primeiras janelas só servem para conhecer o ruído da sala.
        # Sem isso, numa sala barulhenta a primeira janela já viraria uma batida falsa.
        if len(self.historico_ruido) < JANELAS_AQUECIMENTO:
            self.historico_ruido.append(nivel)
            self.lembrar_nivel(nivel)
            return False

        acima = nivel > self.limiar()
        if acima:
            self.janelas_seguidas_acima += 1
        else:
            self.janelas_seguidas_acima = 0

        # Só janelas sem batida entram no histórico; senão as próprias batidas
        # inflariam o "ruído" e o limiar subiria até não detectar mais nada.
        # Exceção: som alto por muito tempo não é batida, é o ruído da sala que aumentou.
        if not acima or self.janelas_seguidas_acima > self.max_janelas_batida:
            self.historico_ruido.append(nivel)

        # Por que exigir um SALTO, e não só "passou do limiar"?
        #  - Numa sala com eco, o "rabo" da 1ª batida de um bit 1 ainda está acima
        #    do limiar quando a 2ª chega; o salto de volume revela a 2ª batida.
        #  - O rabo, ao cair, oscila perto do limiar; sem salto, isso não vira batida.
        # Por que 20 ms atrás, e não 10 ms? A batida pode cair na divisa entre duas
        # janelas e dividir a energia entre elas, sem salto de uma para a outra.
        saltou = nivel > FATOR_SUBIDA * self.nivel_2_atras
        self.lembrar_nivel(nivel)

        if not (acima and saltou):
            return False
        # Período refratário: o eco/rebote da mesma batida não conta como outra.
        if (self.instante_ultima_batida is not None
                and instante - self.instante_ultima_batida < PERIODO_REFRATARIO):
            return False
        self.instante_ultima_batida = instante
        return True


def detectar_batidas(sinal: np.ndarray, taxa: int = TAXA_AMOSTRAGEM) -> list[float]:
    """Versão offline: devolve os instantes (s) em que cada batida começa no sinal."""
    tamanho_janela = round(taxa * DURACAO_JANELA)
    detector = DetectorBatidas(taxa)
    instantes = []
    quantidade_janelas = len(sinal) // tamanho_janela
    for indice in range(quantidade_janelas):
        inicio = indice * tamanho_janela
        janela = sinal[inicio:inicio + tamanho_janela]
        instante = indice * DURACAO_JANELA
        if detector.processar(janela, instante):
            instantes.append(instante)
    return instantes


def valor_do_bit(batidas: int) -> int:
    """1 batida = bit 0; 2 batidas = bit 1; mais que isso não é um bit válido."""
    if batidas == 1:
        return 0
    if batidas == 2:
        return 1
    return BIT_INVALIDO


class MontadorQuadros:
    """Transforma batidas em bits e bits em quadros, em tempo real.

    - Batidas separadas por menos de LIMITE_GRUPO pertencem ao mesmo bit.
    - O bit fecha quando passa LIMITE_GRUPO sem batida: 1 batida -> 0,
      2 batidas -> 1, 3 ou mais -> BIT_INVALIDO.
    - O quadro fecha ao completar 9 bits.
    - Se passar TIMEOUT_QUADRO sem batida, o quadro é fechado incompleto.

    Os dois métodos públicos devolvem a lista de quadros que FECHARAM
    (normalmente vazia, às vezes com um quadro).
    """

    def __init__(self):
        self.bits: list[int] = []          # bits já fechados do quadro atual
        self.batidas_no_bit = 0            # batidas do bit que ainda está aberto
        self.instante_ultima_batida: float | None = None

    def adicionar_batida(self, instante: float) -> list[list[int]]:
        """Registra uma batida. Antes, fecha o que o silêncio anterior já encerrou."""
        fechados = self.verificar_tempo(instante)
        self.batidas_no_bit += 1
        self.instante_ultima_batida = instante
        return fechados

    def verificar_tempo(self, agora: float) -> list[list[int]]:
        """Fecha bit e/ou quadro se já passou silêncio suficiente até `agora`."""
        fechados = []
        if self.instante_ultima_batida is None:
            return fechados
        silencio = agora - self.instante_ultima_batida

        if self.batidas_no_bit > 0 and silencio >= LIMITE_GRUPO:
            self.bits.append(valor_do_bit(self.batidas_no_bit))
            self.batidas_no_bit = 0
            if len(self.bits) == TAMANHO_QUADRO:
                fechados.append(self.bits)
                self.bits = []

        if len(self.bits) > 0 and silencio >= TIMEOUT_QUADRO:
            fechados.append(self.bits)  # quadro incompleto: será reportado como falha
            self.bits = []

        return fechados


def instantes_para_quadros(instantes: list[float]) -> list[list[int]]:
    """Versão offline do montador: lista de instantes -> lista de quadros."""
    montador = MontadorQuadros()
    quadros = []
    for instante in sorted(instantes):
        quadros.extend(montador.adicionar_batida(instante))
    # "Tempo infinito" depois da última batida: fecha o que ainda estiver aberto.
    quadros.extend(montador.verificar_tempo(math.inf))
    return quadros


def quadro_integro(quadro: list[int]) -> bool:
    """True se o quadro chegou completo, sem bit inválido e com a paridade certa."""
    if BIT_INVALIDO in quadro:
        return False
    return validar_quadro(quadro)


def _bits_como_texto(quadro: list[int]) -> str:
    """Ex.: [0,1,0,0,0,0,0,1,0] -> '01000001 0' (bit inválido aparece como '?')."""
    texto = ""
    for posicao, bit in enumerate(quadro):
        if posicao == TAMANHO_DADOS:
            texto += " "  # separa os dados do bit de paridade
        texto += "?" if bit == BIT_INVALIDO else str(bit)
    return texto


def relatar_quadro(quadro: list[int]) -> str:
    """Linha para o terminal dizendo se o quadro chegou com SUCESSO ou FALHA."""
    bits = _bits_como_texto(quadro)
    if len(quadro) < TAMANHO_QUADRO:
        return f"[FALHA DE TRANSMISSÃO] {bits} -> quadro incompleto com {len(quadro)} bits"
    if BIT_INVALIDO in quadro:
        return f"[FALHA DE TRANSMISSÃO] {bits} -> bit inválido (3 ou mais batidas)"
    if not validar_quadro(quadro):
        return f"[FALHA DE TRANSMISSÃO] {bits} -> paridade não confere"
    caractere = bits_para_caractere(quadro[:TAMANHO_DADOS])
    return f"[SUCESSO] {bits} -> {caractere!r}"


def decodificar_audio(sinal: np.ndarray, taxa: int = TAXA_AMOSTRAGEM) -> list[list[int]]:
    """Áudio gravado -> quadros recebidos (sem microfone; usado na simulação)."""
    return instantes_para_quadros(detectar_batidas(sinal, taxa))


def escutar() -> None:
    """Receptor em tempo real: ouve o microfone até Ctrl+C e mostra cada quadro."""
    detector = DetectorBatidas()
    montador = MontadorQuadros()
    texto_recebido = ""
    sucessos = 0
    falhas = 0
    # O tempo é contado pelas janelas recebidas (10 ms cada), não pelo relógio,
    # porque assim ele acompanha exatamente o áudio, mesmo se o PC atrasar.
    janelas_lidas = 0

    print("Escutando batidas... (Ctrl+C para encerrar)")
    try:
        for janela in janelas_do_microfone():
            instante = janelas_lidas * DURACAO_JANELA
            janelas_lidas += 1
            if detector.processar(janela, instante):
                print(".", end="", flush=True)
                fechados = montador.adicionar_batida(instante)
            else:
                fechados = montador.verificar_tempo(instante)

            for quadro in fechados:
                print()
                print(relatar_quadro(quadro))
                if quadro_integro(quadro):
                    sucessos += 1
                    texto_recebido += bits_para_caractere(quadro[:TAMANHO_DADOS])
                else:
                    falhas += 1
    except KeyboardInterrupt:
        print()
        print("Recepção encerrada.")
        print(f"Texto recebido: {texto_recebido!r}")
        print(f"Quadros com sucesso: {sucessos} | quadros com falha: {falhas}")
