# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Testes do emissor do Método 1. Rode com: python -m pytest -v"""

import numpy as np
import pytest
from pytest import approx

from audio import rms
from config import AMOSTRAS_POR_JANELA, TAXA_AMOSTRAGEM
from metodo1_emissor import (SILENCIO_BORDAS, inverter_bit, quadro_para_instantes,
                             sintetizar_batidas, texto_para_quadros)
import metodo1_emissor
from metodo1_receptor import decodificar_audio, relatar_quadro
from quadro import montar_quadro, validar_quadro

I, S = 0.15, 0.6  # valores fixos nos testes, independentes do config.py


def test_um_bit():
    assert quadro_para_instantes([0], I, S) == approx([0.0])
    assert quadro_para_instantes([1], I, S) == approx([0.0, 0.15])


def test_dois_bits():
    assert quadro_para_instantes([0, 1], I, S) == approx([0.0, 0.6, 0.75])
    assert quadro_para_instantes([1, 0], I, S) == approx([0.0, 0.15, 0.75])


def test_tres_bits():
    assert quadro_para_instantes([1, 1, 0], I, S) == approx([0.0, 0.15, 0.75, 0.9, 1.5])


def test_quadro_da_letra_A():
    # 'A' = 01000001 + paridade 0
    esperado = [0.0, 0.6, 0.75, 1.35, 1.95, 2.55, 3.15, 3.75, 4.35, 4.5, 5.1]
    assert quadro_para_instantes(montar_quadro("A"), I, S) == approx(esperado)


def test_quantidade_de_batidas():
    # cada bit tem 1 batida, e cada bit 1 tem uma batida a mais
    for caractere in "Matheus!":
        quadro = montar_quadro(caractere)
        assert len(quadro_para_instantes(quadro, I, S)) == 9 + sum(quadro)


# --- Testes acrescentados: texto_para_quadros, inverter_bit, sintetizar_batidas ---

def test_texto_para_quadros():
    quadros = texto_para_quadros("Aa")
    assert quadros == [[0, 1, 0, 0, 0, 0, 0, 1, 0],
                       [0, 1, 1, 0, 0, 0, 0, 1, 1]]


def test_texto_para_quadros_nao_ascii():
    with pytest.raises(ValueError):
        texto_para_quadros("ação")


def test_inverter_bit_nao_altera_original():
    original = montar_quadro("A")
    copia = original.copy()
    invertido = inverter_bit(original, 0)
    assert original == copia
    assert invertido[0] == 1 - original[0]
    assert invertido[1:] == original[1:]


def test_inverter_bit_quebra_paridade():
    quadro = montar_quadro("M")
    assert validar_quadro(quadro)
    assert not validar_quadro(inverter_bit(quadro, 3))


def test_sintetizar_batidas_comprimento_e_tipo():
    sinal = sintetizar_batidas([0.0, 0.15, 0.75])
    assert sinal.dtype == np.float32
    duracao = len(sinal) / TAXA_AMOSTRAGEM
    # 0.3 s antes + 0.75 s + o toc + 0.3 s depois
    assert duracao == approx(0.3 + 0.75 + 0.3, abs=0.05)
    assert np.max(np.abs(sinal)) <= 1.0


def test_sintetizar_batidas_energia_nos_instantes_certos():
    instantes = [0.0, 0.15, 0.75]
    sinal = sintetizar_batidas(instantes)
    energias = []
    for inicio in range(0, len(sinal) - AMOSTRAS_POR_JANELA + 1, AMOSTRAS_POR_JANELA):
        energias.append(rms(sinal[inicio:inicio + AMOSTRAS_POR_JANELA]))

    janelas_com_som = []
    for indice, energia in enumerate(energias):
        if energia > 0.05:
            janelas_com_som.append(indice)

    # Janela onde cada batida começa (o áudio tem SILENCIO_BORDAS s antes da 1ª)
    esperadas = []
    for t in instantes:
        esperadas.append(round((SILENCIO_BORDAS + t) * TAXA_AMOSTRAGEM / AMOSTRAS_POR_JANELA))
    for janela in esperadas:
        assert janela in janelas_com_som
    # Cada toc ocupa no máximo 2 janelas acima do limiar: nada de "rabo" longo
    assert len(janelas_com_som) <= 2 * len(instantes)
    # Silêncio de verdade antes da primeira batida
    assert max(energias[:esperadas[0]]) == 0.0


# --- Testes do revisor: casos de borda e emissor -> receptor ---

def test_sintetizar_sem_batidas_e_so_silencio():
    sinal = sintetizar_batidas([])
    assert sinal.dtype == np.float32
    assert np.max(np.abs(sinal)) == 0.0


def test_sintetizar_com_outra_taxa():
    sinal = sintetizar_batidas([0.0, 0.15], taxa=8000)
    assert len(sinal) / 8000 == approx(0.3 + 0.15 + 0.3, abs=0.05)
    assert np.max(np.abs(sinal)) == approx(0.8, abs=0.01)


def test_texto_vazio_nao_gera_quadros():
    assert texto_para_quadros("") == []


def test_emissor_para_receptor_texto_inteiro():
    # Cada quadro sintetizado e decodificado pelo receptor deve voltar igual
    for caractere in "Oi, Redes! ~0":
        quadro = montar_quadro(caractere)
        sinal = sintetizar_batidas(quadro_para_instantes(quadro))
        assert decodificar_audio(sinal) == [quadro]


def test_emissor_para_receptor_com_ruido_e_toc_fora_da_janela():
    # Ruído de fundo e batidas que não começam no início de uma janela de 10 ms
    gerador = np.random.default_rng(1)
    quadro = montar_quadro("U")  # 01010101 0: alterna bits 0 e 1
    instantes = []
    for t in quadro_para_instantes(quadro):
        instantes.append(t + 0.0037)
    sinal = sintetizar_batidas(instantes)
    sinal = sinal + gerador.normal(0.0, 0.03, len(sinal)).astype(np.float32)
    assert decodificar_audio(sinal) == [quadro]


def test_erro_simulado_vira_falha_no_receptor():
    quadro = inverter_bit(montar_quadro("H"), 0)
    recebidos = decodificar_audio(sintetizar_batidas(quadro_para_instantes(quadro)))
    assert recebidos == [quadro]
    assert relatar_quadro(recebidos[0]).startswith("[FALHA DE TRANSMISSÃO]")


@pytest.fixture
def sem_som_e_sem_espera(monkeypatch):
    """Troca audio.tocar e time.sleep por versões falsas; devolve os sinais 'tocados'."""
    tocados = []
    monkeypatch.setattr(metodo1_emissor.audio, "tocar", lambda sinal, taxa=0: tocados.append(sinal))
    monkeypatch.setattr(metodo1_emissor.time, "sleep", lambda segundos: None)
    return tocados


def test_transmitir_texto_toca_um_audio_por_caractere(sem_som_e_sem_espera, capsys):
    metodo1_emissor.transmitir_texto("Oi")
    assert len(sem_som_e_sem_espera) == 2
    saida = capsys.readouterr().out
    assert "'O' -> 01001111 1" in saida
    assert "'i' -> 01101001 0" in saida


def test_transmitir_texto_simular_erro_so_no_primeiro_quadro(sem_som_e_sem_espera, capsys):
    metodo1_emissor.transmitir_texto("HH", simular_erro=True)
    assert "[SIMULAÇÃO DE ERRO]" in capsys.readouterr().out
    primeiro = decodificar_audio(sem_som_e_sem_espera[0])
    segundo = decodificar_audio(sem_som_e_sem_espera[1])
    assert primeiro == [inverter_bit(montar_quadro("H"), 0)]
    assert not validar_quadro(primeiro[0])
    assert segundo == [montar_quadro("H")]


def test_transmitir_texto_nao_ascii_falha_antes_de_tocar(sem_som_e_sem_espera):
    with pytest.raises(ValueError):
        metodo1_emissor.transmitir_texto("Oç")
    assert sem_som_e_sem_espera == []


def test_transmitir_texto_vazio(sem_som_e_sem_espera, capsys):
    metodo1_emissor.transmitir_texto("")
    assert sem_som_e_sem_espera == []
    assert "vazio" in capsys.readouterr().out


def test_modo_guiado_mostra_um_toc_por_batida(sem_som_e_sem_espera, capsys):
    metodo1_emissor.transmitir_texto("A", guiado=True)
    saida = capsys.readouterr().out
    quadro = montar_quadro("A")
    assert saida.count("TOC!") == 9 + sum(quadro)
    assert sem_som_e_sem_espera == []  # no modo guiado a pessoa faz o som
