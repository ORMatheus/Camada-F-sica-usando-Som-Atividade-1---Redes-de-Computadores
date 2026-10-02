# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores

"""Montagem e validação do quadro de 9 bits do Método 1 (8 dados + paridade par)."""

TAMANHO_DADOS =8 
TAMANHO_QUADRO=9

def caractere_para_bits(caractere: str) -> list[int]:
    """Converte um caractere em uma lista de bits (0 ou 1) de tamanho 8."""
    codigo = ord(caractere)
    if codigo > 127:
        raise ValueError(f"'{caractere}' não é um caractere ASCII")
    return [(codigo >> deslocamento) & 1 for deslocamento in range(7, -1, -1)]

def calcular_paridade_par(dados: list[int]) -> int:
    """Calcula o bit de paridade par para uma lista de bits (0 ou 1)."""
    quantidade_uns = 0
    for i in range(TAMANHO_DADOS):
        if dados[i] == 1:
            quantidade_uns += 1
    return 0 if quantidade_uns % 2 == 0 else 1



def montar_quadro(caractere: str) -> list[int]:
    """Retorna os 9 bits do quadro: 8 bits de dados + bit de paridade par."""
    dados = caractere_para_bits(caractere)
    paridade = calcular_paridade_par(dados)
    return dados + [paridade]

def validar_quadro(quadro: list[int]) -> bool:
    """True se o quadro tem 9 bits e o 9º bit confere com a paridade dos 8 primeiros."""
    if len(quadro) != TAMANHO_QUADRO:
        return False
    dados = quadro[:TAMANHO_DADOS]
    paridade = quadro[TAMANHO_DADOS]
    return paridade == calcular_paridade_par(dados)

def bits_para_caractere(dados: list[int]) -> str:
    """Caminho inverso de caractere_para_bits: 8 bits -> caractere.
 
    Exemplo: [0, 1, 1, 0, 0, 0, 0, 1] -> 'a'
    """
    codigo = 0
    for bit in dados:
        codigo = codigo * 2 + bit
    return chr(codigo)