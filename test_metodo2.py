# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Testes do Método 2 (MFSK + CRC-16). Rode com: python -m pytest -v test_metodo2.py

Nenhum teste usa microfone ou alto-falante: o "ar" é simulado com numpy
(ruído, atraso, volume baixo, eco).
"""

import numpy as np
import pytest
from pytest import approx

from config import TAXA_AMOSTRAGEM
from metodo2 import (BANCOS, DURACAO_PREAMBULO, DURACAO_SIMBOLO, PAUSA_APOS_PREAMBULO,
                     QUANTIDADE_TONS, SILENCIO_BORDAS, TAMANHO_MAXIMO, amostras,
                     bytes_para_simbolos, crc16_ccitt, demodular, frequencia_do_simbolo,
                     gerar_tom, modular, montar_pacote, relatar_mensagem,
                     simbolos_para_bytes, taxa_teorica_bps)

MENSAGEM = "Redes de Computadores".encode("utf-8")


def gerador() -> np.random.Generator:
    """Gerador aleatório com semente fixa: o teste dá sempre o mesmo resultado."""
    return np.random.default_rng(2026)


# --- CRC e pacote ---

def test_crc16_valor_de_referencia():
    # valor "check" oficial do CRC-16/CCITT-FALSE
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_vazio_e_valor_inicial():
    assert crc16_ccitt(b"") == 0xFFFF


def test_crc16_muda_com_um_bit():
    assert crc16_ccitt(b"A") != crc16_ccitt(b"@")  # 'A' e '@' diferem em 1 bit


def test_montar_pacote():
    pacote = montar_pacote(b"Oi")
    crc = crc16_ccitt(b"\x02Oi")
    assert pacote == b"\x02Oi" + bytes([crc >> 8, crc & 0xFF])
    assert len(pacote) == 1 + 2 + 2


def test_montar_pacote_grande_demais():
    with pytest.raises(ValueError):
        montar_pacote(bytes(TAMANHO_MAXIMO + 1))


# --- Bytes, símbolos e frequências ---

def test_bytes_e_simbolos_ida_e_volta():
    assert bytes_para_simbolos(b"\xA5") == [0xA, 0x5]
    dados = bytes(range(256))
    assert simbolos_para_bytes(bytes_para_simbolos(dados)) == dados


def test_frequencias_distintas_dentro_da_faixa():
    frequencias = set()
    for posicao in range(BANCOS):
        for simbolo in range(QUANTIDADE_TONS):
            frequencias.add(frequencia_do_simbolo(simbolo, posicao))
    assert len(frequencias) == BANCOS * QUANTIDADE_TONS  # nenhum tom repetido
    assert min(frequencias) >= 500
    assert max(frequencias) <= 6000


def test_taxa_teorica():
    assert taxa_teorica_bps() == approx(4 / 0.030)


# --- Modulação e demodulação ---

def test_modular_formato():
    sinal = modular(MENSAGEM)
    assert sinal.dtype == np.float32
    assert np.max(np.abs(sinal)) <= 1.0


def test_loopback_sem_ruido():
    dados, crc_ok = demodular(modular(MENSAGEM))
    assert crc_ok
    assert dados == MENSAGEM


def test_mensagem_vazia():
    assert demodular(modular(b"")) == (b"", True)


def test_texto_com_acentos():
    texto = "Ação, coração e pão! Ñ ü 123"
    dados, crc_ok = demodular(modular(texto.encode("utf-8")))
    assert crc_ok
    assert dados.decode("utf-8") == texto


def test_com_ruido_gaussiano():
    sinal = modular(MENSAGEM)
    # desvio 0,4 contra tons de amplitude 0,8: ruído forte, audível como chiado
    ruidoso = sinal + gerador().normal(0, 0.4, len(sinal))
    assert demodular(ruidoso) == (MENSAGEM, True)


def test_com_atraso_aleatorio():
    rng = gerador()
    antes = np.zeros(rng.integers(1, 2 * TAXA_AMOSTRAGEM))
    depois = np.zeros(rng.integers(1, TAXA_AMOSTRAGEM))
    sinal = np.concatenate([antes, modular(MENSAGEM), depois])
    sinal = sinal + rng.normal(0, 0.01, len(sinal))
    assert demodular(sinal) == (MENSAGEM, True)


def test_volume_baixo():
    sinal = 0.1 * modular(MENSAGEM)
    sinal = sinal + gerador().normal(0, 0.01, len(sinal))
    assert demodular(sinal) == (MENSAGEM, True)


def test_polaridade_invertida():
    assert demodular(-modular(MENSAGEM)) == (MENSAGEM, True)


def test_com_eco():
    sinal = modular(MENSAGEM)
    for atraso_ms in (5, 8, 10):
        atraso = int(atraso_ms / 1000 * TAXA_AMOSTRAGEM)
        com_eco = np.concatenate([sinal, np.zeros(atraso)])
        com_eco[atraso:] += 0.5 * sinal  # cópia atrasada e mais fraca
        assert demodular(com_eco) == (MENSAGEM, True), f"eco de {atraso_ms} ms"


def test_simular_erro_e_detectado():
    dados, crc_ok = demodular(modular(MENSAGEM, simular_erro=True))
    assert not crc_ok
    assert dados != MENSAGEM
    assert len(dados) == len(MENSAGEM)


def test_ruido_puro_nao_e_mensagem():
    ruido = gerador().normal(0, 0.1, 3 * TAXA_AMOSTRAGEM)
    assert demodular(ruido) == (None, False)


def test_silencio_nao_e_mensagem():
    assert demodular(np.zeros(TAXA_AMOSTRAGEM)) == (None, False)


def test_audio_cortado_no_meio():
    sinal = modular(MENSAGEM)
    assert demodular(sinal[:len(sinal) // 2]) == (None, False)


# --- Mensagem para o terminal ---

def test_relatar_mensagem():
    assert relatar_mensagem(b"Oi", True).startswith("[SUCESSO]")
    assert relatar_mensagem(b"Oi", False).startswith("[FALHA DE TRANSMISSÃO]")
    assert relatar_mensagem(None, False).startswith("[FALHA DE TRANSMISSÃO]")


# --- Testes que tentam quebrar o receptor ---

def trocar_simbolo(sinal: np.ndarray, posicao: int, novo_simbolo: int) -> np.ndarray:
    """Cópia do áudio com o tom do símbolo `posicao` trocado: simula um erro "no ar"."""
    inicio = (amostras(SILENCIO_BORDAS, TAXA_AMOSTRAGEM)
              + amostras(DURACAO_PREAMBULO, TAXA_AMOSTRAGEM)
              + amostras(PAUSA_APOS_PREAMBULO, TAXA_AMOSTRAGEM)
              + posicao * amostras(DURACAO_SIMBOLO, TAXA_AMOSTRAGEM))
    tom = gerar_tom(frequencia_do_simbolo(novo_simbolo, posicao), DURACAO_SIMBOLO, TAXA_AMOSTRAGEM)
    alterado = sinal.copy()
    alterado[inicio:inicio + len(tom)] = tom
    return alterado


def test_sinal_vazio_ou_curto():
    assert demodular(np.zeros(0)) == (None, False)
    assert demodular(np.zeros(10)) == (None, False)


def test_gravacao_com_formato_amostras_por_canais():
    # sounddevice entrega (amostras, 1); antes isso estourava a memória na FFT
    sinal = modular(MENSAGEM).reshape(-1, 1)
    assert demodular(sinal) == (MENSAGEM, True)


def test_gravacao_em_int16():
    sinal = (modular(MENSAGEM) * 20000).astype(np.int16)
    assert demodular(sinal) == (MENSAGEM, True)


def test_erro_num_simbolo_de_dados_e_detectado():
    sinal = modular(MENSAGEM)
    simbolo_original = bytes_para_simbolos(montar_pacote(MENSAGEM))[5]
    corrompido = trocar_simbolo(sinal, 5, (simbolo_original + 1) % QUANTIDADE_TONS)
    dados, crc_ok = demodular(corrompido)
    assert not crc_ok
    assert dados != MENSAGEM


def test_erro_no_byte_de_comprimento_nunca_vira_sucesso():
    sinal = modular(MENSAGEM)  # 21 bytes = 0x15
    # comprimento vira 0x05: pacote mais curto, CRC não confere
    assert demodular(trocar_simbolo(sinal, 0, 0x0))[1] is False
    # comprimento vira 0xF5 = 245: o áudio acaba antes, mensagem incompleta
    assert demodular(trocar_simbolo(sinal, 0, 0xF)) == (None, False)


def test_crc_detecta_qualquer_erro_de_1_ou_2_bits():
    pacote = montar_pacote(b"Oi!")
    total_bits = 8 * len(pacote)
    for i in range(total_bits):
        for j in range(i, total_bits):
            alterado = bytearray(pacote)
            alterado[i // 8] ^= 1 << (i % 8)
            if j != i:
                alterado[j // 8] ^= 1 << (j % 8)
            crc_recebido = (alterado[-2] << 8) | alterado[-1]
            assert crc16_ccitt(bytes(alterado[:-2])) != crc_recebido


def test_simular_erro_com_mensagem_vazia():
    assert demodular(modular(b"", simular_erro=True)) == (b"", False)


def test_modular_mensagem_grande_demais():
    with pytest.raises(ValueError):
        modular(bytes(TAMANHO_MAXIMO + 1))


def test_mensagem_maxima_com_relogios_diferentes():
    # placas de som diferentes nunca têm exatamente a mesma taxa; 300 ppm é exagerado
    dados = bytes(range(TAMANHO_MAXIMO))
    sinal = modular(dados).astype(np.float64)
    passo = 1 + 300e-6
    reamostrado = np.interp(np.arange(0, len(sinal) - 1, passo), np.arange(len(sinal)), sinal)
    assert demodular(reamostrado) == (dados, True)


def test_receptor_gravando_em_48000_hz():
    sinal = modular(MENSAGEM).astype(np.float64)
    duracao = len(sinal) / TAXA_AMOSTRAGEM
    instantes = np.arange(int(duracao * 48000)) / 48000
    reamostrado = np.interp(instantes, np.arange(len(sinal)) / TAXA_AMOSTRAGEM, sinal)
    assert demodular(reamostrado, 48000) == (MENSAGEM, True)


def test_offset_dc_e_zumbido_da_rede_eletrica():
    sinal = modular(MENSAGEM).astype(np.float64)
    t = np.arange(len(sinal)) / TAXA_AMOSTRAGEM
    zumbido = 0.5 * np.sin(2 * np.pi * 60 * t)
    assert demodular(0.5 * sinal + zumbido + 0.2) == (MENSAGEM, True)


def test_tons_sem_preambulo_nao_sao_mensagem():
    sinal = modular(MENSAGEM)
    sem_preambulo = sinal[amostras(SILENCIO_BORDAS + DURACAO_PREAMBULO, TAXA_AMOSTRAGEM):]
    assert demodular(sem_preambulo) == (None, False)


def test_relatar_mensagem_com_bytes_invalidos_em_utf8():
    linha = relatar_mensagem(b"\xff\xfe", False)
    assert linha.startswith("[FALHA DE TRANSMISSÃO]")
