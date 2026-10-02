# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Testes do receptor do Método 1. Rode com: python -m pytest -v

Os sinais são gerados aqui mesmo (cliques sintéticos + ruído), sem microfone
e sem depender do emissor.
"""

import math

import numpy as np

import metodo1_receptor
from config import (AMOSTRAS_POR_JANELA, DURACAO_JANELA, INTERVALO_BATIDAS,
                    LIMITE_GRUPO, SILENCIO_BITS, TAXA_AMOSTRAGEM, TIMEOUT_QUADRO)
from metodo1_receptor import (BIT_INVALIDO, DetectorBatidas, MontadorQuadros,
                              decodificar_audio, detectar_batidas,
                              instantes_para_quadros, quadro_integro, relatar_quadro)

TOLERANCIA = DURACAO_JANELA + 0.001  # uma janela de erro no instante detectado


def gerar_cliques(instantes: list[float], duracao: float, ruido: float = 0.0,
                  semente: int = 0) -> np.ndarray:
    """Sinal com um "toc" curto (ruído com decaimento rápido) em cada instante."""
    gerador = np.random.default_rng(semente)
    total = int(duracao * TAXA_AMOSTRAGEM)
    sinal = ruido * gerador.standard_normal(total)
    tamanho_toc = int(0.025 * TAXA_AMOSTRAGEM)
    tempo = np.arange(tamanho_toc) / TAXA_AMOSTRAGEM
    for instante in instantes:
        toc = 0.8 * gerador.standard_normal(tamanho_toc) * np.exp(-tempo / 0.005)
        inicio = int(instante * TAXA_AMOSTRAGEM)
        sinal[inicio:inicio + tamanho_toc] += toc
    return sinal.astype(np.float32)


def instantes_do_quadro(quadro: list[int], comeco: float = 0.5,
                        intervalo: float = INTERVALO_BATIDAS,
                        silencio: float = SILENCIO_BITS) -> list[float]:
    """Mesma regra do enunciado, escrita aqui para o teste não depender do emissor."""
    instantes = []
    t = comeco
    for bit in quadro:
        instantes.append(t)
        if bit == 1:
            t += intervalo
            instantes.append(t)
        t += silencio
    return instantes


def janela_constante(nivel: float) -> np.ndarray:
    """Janela de 10 ms cujo RMS é exatamente `nivel`."""
    return np.full(AMOSTRAS_POR_JANELA, nivel, dtype=np.float32)


# --- Detector de batidas ---

def test_detecta_batidas_com_ruido_moderado():
    esperados = [0.5, 0.65, 1.25, 1.85, 2.0]
    sinal = gerar_cliques(esperados, duracao=3.0, ruido=0.02)
    detectados = detectar_batidas(sinal)
    assert len(detectados) == len(esperados)
    for detectado, esperado in zip(detectados, esperados):
        assert abs(detectado - esperado) <= TOLERANCIA


def test_detecta_batida_logo_no_comeco():
    # Bem antes de juntar JANELAS_RUIDO janelas de histórico (1 s)
    sinal = gerar_cliques([0.15], duracao=0.5, ruido=0.01)
    detectados = detectar_batidas(sinal)
    assert len(detectados) == 1
    assert abs(detectados[0] - 0.15) <= TOLERANCIA


def test_silencio_digital_nao_gera_batida():
    assert detectar_batidas(np.zeros(TAXA_AMOSTRAGEM, dtype=np.float32)) == []


def test_ruido_puro_nao_gera_batida():
    for nivel in [0.005, 0.02, 0.1]:
        sinal = gerar_cliques([], duracao=3.0, ruido=nivel, semente=7)
        assert detectar_batidas(sinal) == []


def alimentar(detector: DetectorBatidas, niveis: list[float]) -> list[float]:
    """Passa janelas consecutivas com esses níveis; devolve os instantes detectados."""
    detectados = []
    for indice, nivel in enumerate(niveis):
        instante = round(indice * DURACAO_JANELA, 3)
        if detector.processar(janela_constante(nivel), instante):
            detectados.append(instante)
    return detectados


def test_periodo_refratario_evita_batida_dupla():
    niveis = [0.001] * 20              # 0,00 a 0,19 s: silêncio de fundo
    niveis += [0.5, 0.001, 0.001]      # 0,20 s: batida
    niveis += [0.5]                    # 0,23 s: rebote 30 ms depois (mesma batida)
    niveis += [0.001] * 11             # 0,24 a 0,34 s: silêncio
    niveis += [0.5, 0.001]             # 0,35 s: 150 ms depois, outra batida
    assert alimentar(DetectorBatidas(), niveis) == [0.20, 0.35]


def test_batidas_nao_contaminam_o_ruido_de_fundo():
    detector = DetectorBatidas()
    instante = 0.0
    for repeticao in range(60):  # muitas batidas seguidas
        nivel = 0.5 if repeticao % 3 == 0 else 0.002
        detector.processar(janela_constante(nivel), instante)
        instante += DURACAO_JANELA
    assert math.isclose(detector.estimar_ruido(), 0.002, rel_tol=0.01)


def test_ruido_alto_e_constante_vira_fundo():
    # Um ventilador liga: não pode virar uma batida eterna, o limiar precisa subir.
    detector = DetectorBatidas()
    deteccoes = 0
    instante = 0.0
    for indice in range(300):
        nivel = 0.002 if indice < 20 else 0.2
        if detector.processar(janela_constante(nivel), instante):
            deteccoes += 1
        instante += DURACAO_JANELA
    assert deteccoes == 1
    assert detector.limiar() > 0.2


# --- Montador de quadros ---

def test_agrupa_batidas_em_bits():
    # bit 1 (duas batidas próximas) e depois bit 0 (uma batida)
    montador = MontadorQuadros()
    segunda = INTERVALO_BATIDAS
    proximo_bit = segunda + SILENCIO_BITS
    montador.adicionar_batida(0.0)
    montador.adicionar_batida(segunda)
    montador.adicionar_batida(proximo_bit)
    montador.verificar_tempo(proximo_bit + LIMITE_GRUPO + 0.01)
    assert montador.bits == [1, 0]


def test_quadro_fecha_com_nove_bits():
    quadro = [0, 1, 0, 0, 0, 0, 0, 1, 0]
    montador = MontadorQuadros()
    fechados = []
    for instante in instantes_do_quadro(quadro):
        fechados.extend(montador.adicionar_batida(instante))
    assert fechados == []  # o último bit ainda pode receber uma 2ª batida
    ultima = instantes_do_quadro(quadro)[-1]
    assert montador.verificar_tempo(ultima + LIMITE_GRUPO / 2) == []
    assert montador.verificar_tempo(ultima + LIMITE_GRUPO) == [quadro]
    assert montador.bits == []


def test_timeout_fecha_quadro_incompleto():
    montador = MontadorQuadros()
    montador.adicionar_batida(0.0)
    montador.adicionar_batida(0.6)
    montador.adicionar_batida(0.75)
    assert montador.verificar_tempo(1.5) == []  # bits [0, 1] esperando o resto
    assert montador.verificar_tempo(0.75 + TIMEOUT_QUADRO) == [[0, 1]]


def test_tres_batidas_invalidam_o_bit():
    quadro_enviado = [0, 1, 0, 0, 0, 0, 0, 1, 0]
    instantes = instantes_do_quadro(quadro_enviado)
    instantes.append(instantes[0] + 0.1)  # 1º bit (0) ganha mais duas batidas
    instantes.append(instantes[0] + 0.2)
    quadros = instantes_para_quadros(instantes)
    assert len(quadros) == 1
    assert quadros[0][0] == BIT_INVALIDO
    assert not quadro_integro(quadros[0])
    assert "bit inválido" in relatar_quadro(quadros[0])


def test_varios_quadros_seguidos():
    quadro_a = [0, 1, 0, 0, 0, 0, 0, 1, 0]
    quadro_b = [0, 1, 0, 0, 0, 0, 1, 0, 0]
    instantes = instantes_do_quadro(quadro_a, comeco=0.0)
    instantes += instantes_do_quadro(quadro_b, comeco=instantes[-1] + 2.5)
    assert instantes_para_quadros(instantes) == [quadro_a, quadro_b]


# --- Relatório no terminal ---

def test_relatar_sucesso():
    linha = relatar_quadro([0, 1, 0, 0, 0, 0, 0, 1, 0])
    assert linha == "[SUCESSO] 01000001 0 -> 'A'"


def test_relatar_falha_de_paridade():
    linha = relatar_quadro([1, 1, 0, 0, 0, 0, 0, 1, 0])
    assert linha.startswith("[FALHA DE TRANSMISSÃO]")
    assert "paridade não confere" in linha


def test_relatar_quadro_incompleto():
    linha = relatar_quadro([0, 1, 0, 0])
    assert linha.startswith("[FALHA DE TRANSMISSÃO]")
    assert "incompleto com 4 bits" in linha


def test_quadro_integro():
    assert quadro_integro([0, 1, 0, 0, 0, 0, 0, 1, 0])
    assert not quadro_integro([0, 1, 0, 0, 0, 0, 0, 1, 1])
    assert not quadro_integro([0, 1, 0, 0])
    # paridade "bate" se o -1 contar como 0, mas o bit inválido derruba o quadro
    assert not quadro_integro([BIT_INVALIDO, 1, 0, 0, 0, 0, 0, 1, 0])


# --- Do áudio até o caractere ---

def test_decodificar_letra_A_com_ruido():
    quadro_a = [0, 1, 0, 0, 0, 0, 0, 1, 0]  # 'A' = 01000001, paridade 0
    instantes = instantes_do_quadro(quadro_a, comeco=0.3)
    sinal = gerar_cliques(instantes, duracao=instantes[-1] + 0.5, ruido=0.02)
    quadros = decodificar_audio(sinal)
    assert quadros == [quadro_a]
    assert relatar_quadro(quadros[0]) == "[SUCESSO] 01000001 0 -> 'A'"


def test_decodificar_quadro_com_erro_simulado():
    quadro_errado = [1, 1, 0, 0, 0, 0, 0, 1, 0]  # 1º bit invertido depois da paridade
    instantes = instantes_do_quadro(quadro_errado, comeco=0.3)
    sinal = gerar_cliques(instantes, duracao=instantes[-1] + 0.5, ruido=0.02)
    quadros = decodificar_audio(sinal)
    assert quadros == [quadro_errado]
    assert "paridade não confere" in relatar_quadro(quadros[0])


# --- Casos difíceis (revisão): tentam quebrar o receptor ---

def test_segunda_batida_no_rabo_da_primeira():
    # Sala com eco: o som da 1ª batida ainda está ACIMA do limiar quando a
    # 2ª batida de um bit 1 chega (150 ms depois). Ela não pode ser perdida.
    rabo = [0.2, 0.15, 0.1, 0.08, 0.07, 0.06, 0.05, 0.045, 0.04, 0.035, 0.03, 0.028, 0.025, 0.022]
    niveis = [0.002] * 20 + [0.3] + rabo + [0.3] + rabo + [0.002] * 30
    assert alimentar(DetectorBatidas(), niveis) == [0.20, 0.35]


def test_rabo_oscilando_perto_do_limiar_nao_vira_batida():
    # Depois da batida o som cai devagar e "treme" em volta do limiar (0,01).
    rabo = [0.1, 0.05, 0.03, 0.02, 0.015, 0.012, 0.009, 0.011, 0.0095, 0.0105,
            0.009, 0.0108, 0.0092, 0.0104, 0.009, 0.0102]
    niveis = [0.002] * 20 + [0.3] + rabo + [0.002] * 20
    assert alimentar(DetectorBatidas(), niveis) == [0.20]


def test_batida_na_divisa_entre_duas_janelas():
    # A energia da batida se divide: a 1ª janela fica logo abaixo do limiar e a
    # 2ª logo acima, sem dobrar de uma para a outra. Ainda é uma batida.
    niveis = [0.002] * 20 + [0.009, 0.012] + [0.002] * 20
    assert alimentar(DetectorBatidas(), niveis) == [0.21]


def test_som_que_cresce_devagar_nao_e_batida():
    # Ex.: alguém aumentando o volume de uma música. Não há salto, não há batida.
    niveis = [0.002] * 20
    nivel = 0.002
    while nivel < 0.3:
        nivel *= 1.1
        niveis.append(nivel)
    niveis += [0.3] * 100
    assert alimentar(DetectorBatidas(), niveis) == []


def test_sinal_vazio_ou_curto():
    assert detectar_batidas(np.zeros(0, dtype=np.float32)) == []
    assert detectar_batidas(np.zeros(100, dtype=np.float32)) == []  # menos de 1 janela
    assert decodificar_audio(np.zeros(0, dtype=np.float32)) == []
    assert instantes_para_quadros([]) == []
    assert MontadorQuadros().verificar_tempo(100.0) == []


def test_ganho_baixo_do_microfone():
    # Microfone longe: as batidas chegam 10x mais fracas.
    quadro_a = [0, 1, 0, 0, 0, 0, 0, 1, 0]
    instantes = instantes_do_quadro(quadro_a, comeco=0.3)
    sinal = 0.1 * gerar_cliques(instantes, duracao=instantes[-1] + 0.5)
    sinal = sinal + 0.0005 * np.random.default_rng(1).standard_normal(len(sinal))
    assert decodificar_audio(sinal.astype(np.float32)) == [quadro_a]


def test_sala_com_reverberacao():
    # Reverberação de 1 s (sala grande): cada batida deixa um "rabo" longo.
    quadro_z = [0, 1, 0, 1, 1, 0, 1, 0, 0]  # 'Z', paridade 0
    instantes = instantes_do_quadro(quadro_z, comeco=0.3)
    seco = gerar_cliques(instantes, duracao=instantes[-1] + 1.0).astype(np.float64)
    gerador = np.random.default_rng(2)
    tempo = np.arange(TAXA_AMOSTRAGEM) / TAXA_AMOSTRAGEM
    resposta = gerador.standard_normal(len(tempo)) * 10 ** (-3 * tempo)  # cai 60 dB em 1 s
    resposta /= np.sqrt(np.sum(resposta ** 2))
    tamanho = len(seco) + len(resposta)
    eco = np.fft.irfft(np.fft.rfft(seco, tamanho) * np.fft.rfft(resposta, tamanho), tamanho)
    sinal = seco + eco[:len(seco)] + 0.002 * gerador.standard_normal(len(seco))
    assert decodificar_audio(sinal.astype(np.float32)) == [quadro_z]


def test_batida_extra_depois_do_quadro_vira_quadro_incompleto():
    quadro_a = [0, 1, 0, 0, 0, 0, 0, 1, 0]
    instantes = instantes_do_quadro(quadro_a, comeco=0.0)
    instantes.append(instantes[-1] + 1.0)  # alguém bateu na mesa sem querer
    quadros = instantes_para_quadros(instantes)
    assert quadros == [quadro_a, [0]]
    assert "incompleto com 1 bits" in relatar_quadro(quadros[1])


def test_relatar_caractere_de_controle_nao_quebra_o_terminal():
    linha = relatar_quadro([0, 0, 0, 0, 1, 0, 1, 0, 0])  # '\n'
    assert linha == "[SUCESSO] 00001010 0 -> " + repr("\n")  # aparece como '\n', sem quebrar a linha


def test_escutar_em_tempo_real_sem_microfone(monkeypatch, capsys):
    # Troca o microfone por um gerador que entrega o áudio de 'A' e depois
    # simula o Ctrl+C. Assim testamos o laço de escutar() de verdade.
    quadro_a = [0, 1, 0, 0, 0, 0, 0, 1, 0]
    instantes = instantes_do_quadro(quadro_a, comeco=0.3)
    sinal = gerar_cliques(instantes, duracao=instantes[-1] + LIMITE_GRUPO + 0.2, ruido=0.01)

    def microfone_falso():
        for inicio in range(0, len(sinal) - AMOSTRAS_POR_JANELA + 1, AMOSTRAS_POR_JANELA):
            yield sinal[inicio:inicio + AMOSTRAS_POR_JANELA]
        raise KeyboardInterrupt

    monkeypatch.setattr(metodo1_receptor, "janelas_do_microfone", microfone_falso)
    metodo1_receptor.escutar()
    saida = capsys.readouterr().out
    assert "[SUCESSO] 01000001 0 -> 'A'" in saida
    assert "Texto recebido: 'A'" in saida
    assert "Quadros com sucesso: 1 | quadros com falha: 0" in saida
