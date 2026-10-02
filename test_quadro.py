# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Testes do quadro de 9 bits do Método 1 (sem áudio). Rode com: python -m pytest -v"""

import pytest

from quadro import (
    TAMANHO_DADOS,
    TAMANHO_QUADRO,
    bits_para_caractere,
    calcular_paridade_par,
    caractere_para_bits,
    montar_quadro,
    validar_quadro,
)


def test_tamanhos():
    assert TAMANHO_DADOS == 8
    assert TAMANHO_QUADRO == 9


def test_caractere_para_bits_msb_primeiro():
    # 'A' = 65 = 0b01000001: o bit mais significativo vem primeiro
    assert caractere_para_bits("A") == [0, 1, 0, 0, 0, 0, 0, 1]
    assert caractere_para_bits("a") == [0, 1, 1, 0, 0, 0, 0, 1]


def test_paridade_com_quantidade_par_de_uns():
    # exemplo do enunciado: 11000000 tem dois 1s -> paridade 0
    assert calcular_paridade_par([1, 1, 0, 0, 0, 0, 0, 0]) == 0


def test_paridade_com_quantidade_impar_de_uns():
    # exemplo do enunciado: 11100000 tem três 1s -> paridade 1
    assert calcular_paridade_par([1, 1, 1, 0, 0, 0, 0, 0]) == 1


def test_paridade_de_tudo_zero_e_tudo_um():
    assert calcular_paridade_par([0] * 8) == 0
    assert calcular_paridade_par([1] * 8) == 0


def test_montar_quadro_da_letra_A():
    # 'A' tem dois 1s (par) -> bit de paridade 0
    assert montar_quadro("A") == [0, 1, 0, 0, 0, 0, 0, 1, 0]


def test_montar_quadro_da_letra_a_termina_em_1():
    # 'a' tem três 1s (ímpar) -> bit de paridade 1
    quadro = montar_quadro("a")
    assert len(quadro) == 9
    assert quadro[-1] == 1


def test_validar_quadro_correto():
    for caractere in "Aa0 !~":
        assert validar_quadro(montar_quadro(caractere))


@pytest.mark.parametrize("posicao", range(9))
def test_validar_rejeita_um_bit_invertido(posicao):
    # inverter qualquer um dos 9 bits muda a quantidade de 1s em uma unidade,
    # então a paridade deixa de conferir
    quadro = montar_quadro("A")
    quadro[posicao] = 1 - quadro[posicao]
    assert not validar_quadro(quadro)


def test_validar_rejeita_tamanho_errado():
    quadro = montar_quadro("A")
    assert not validar_quadro(quadro[:8])        # faltou o bit de paridade
    assert not validar_quadro(quadro + [0])      # bit sobrando


def test_bits_para_caractere_desfaz_caractere_para_bits():
    for codigo in range(128):
        caractere = chr(codigo)
        assert bits_para_caractere(caractere_para_bits(caractere)) == caractere


def test_caractere_nao_ascii_levanta_erro():
    for caractere in "çé€":
        with pytest.raises(ValueError):
            caractere_para_bits(caractere)
        with pytest.raises(ValueError):
            montar_quadro(caractere)


def test_paridade_confere_com_contagem_de_uns_em_todo_ascii():
    for codigo in range(128):
        quadro = montar_quadro(chr(codigo))
        quantidade_uns = bin(codigo).count("1")
        assert quadro[-1] == quantidade_uns % 2
        assert quadro[:8].count(1) + quadro[-1] in (0, 2, 4, 6, 8)  # total de 1s sempre par


def test_paridade_nao_detecta_dois_bits_invertidos():
    # Limitação da paridade (bom saber para a apresentação): dois erros se
    # cancelam, a quantidade de 1s continua par e o quadro "passa".
    quadro = montar_quadro("A")
    quadro[0] = 1 - quadro[0]
    quadro[1] = 1 - quadro[1]
    assert validar_quadro(quadro)
    assert bits_para_caractere(quadro[:8]) != "A"


def test_validar_rejeita_quadro_vazio():
    assert not validar_quadro([])
