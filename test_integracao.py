# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Testes de integração: emissor -> ruído -> receptor, sem microfone nem alto-falante.

Os testes de main.py rodam o programa de verdade (subprocess), como a
equipe faria no terminal, e conferem o que aparece na tela.
"""

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import metodo1_emissor
import metodo1_receptor
import metodo2
from quadro import TAMANHO_DADOS, bits_para_caractere

PASTA_DO_PROJETO = Path(__file__).parent
RUIDO = 0.02  # mesmo desvio padrão usado por padrão no main.py


def somar_ruido(sinal: np.ndarray, desvio: float, semente: int) -> np.ndarray:
    """Ruído gaussiano com semente fixa, para o teste dar sempre o mesmo resultado."""
    gerador = np.random.default_rng(semente)
    return (sinal + gerador.normal(0.0, desvio, len(sinal))).astype(np.float32)


def transmitir_metodo1(texto: str, simular_erro: bool) -> list[list[int]]:
    """Faz o caminho completo do Método 1 e devolve os quadros recebidos."""
    quadros = metodo1_emissor.texto_para_quadros(texto)
    if simular_erro:
        quadros[0] = metodo1_emissor.inverter_bit(quadros[0])
    instantes = metodo1_emissor.quadros_para_instantes(quadros)
    sinal = metodo1_emissor.sintetizar_batidas(instantes)
    sinal = somar_ruido(sinal, RUIDO, semente=1)
    return metodo1_receptor.decodificar_audio(sinal)


def rodar_main(*argumentos: str) -> subprocess.CompletedProcess:
    """Roda `python main.py ...` e devolve a saída (texto em UTF-8)."""
    ambiente = dict(os.environ)
    ambiente["PYTHONIOENCODING"] = "utf-8"  # acentos certos mesmo no console do Windows
    return subprocess.run([sys.executable, "main.py", *argumentos],
                          cwd=PASTA_DO_PROJETO, env=ambiente, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


# ---------------------------------------------------------------- Método 1

def test_metodo1_ponta_a_ponta_com_ruido():
    recebidos = transmitir_metodo1("Oi!", simular_erro=False)
    assert len(recebidos) == 3
    texto = ""
    for quadro in recebidos:
        assert metodo1_receptor.quadro_integro(quadro)
        texto += bits_para_caractere(quadro[:TAMANHO_DADOS])
    assert texto == "Oi!"


def test_metodo1_erro_simulado_so_no_primeiro_quadro():
    recebidos = transmitir_metodo1("Oi!", simular_erro=True)
    assert len(recebidos) == 3
    assert not metodo1_receptor.quadro_integro(recebidos[0])
    assert "paridade não confere" in metodo1_receptor.relatar_quadro(recebidos[0])
    assert metodo1_receptor.relatar_quadro(recebidos[1]) == "[SUCESSO] 01101001 0 -> 'i'"
    assert metodo1_receptor.relatar_quadro(recebidos[2]) == "[SUCESSO] 00100001 0 -> '!'"


# ---------------------------------------------------------------- Método 2

def test_metodo2_ponta_a_ponta_com_ruido_e_acentos():
    texto = "Camada Física: ação!"
    sinal = metodo2.modular(texto.encode("utf-8"))
    sinal = somar_ruido(sinal, RUIDO, semente=2)
    dados, crc_ok = metodo2.demodular(sinal)
    assert crc_ok
    assert dados.decode("utf-8") == texto


def test_metodo2_erro_simulado_e_detectado_pelo_crc():
    sinal = metodo2.modular("Olá".encode("utf-8"), simular_erro=True)
    sinal = somar_ruido(sinal, RUIDO, semente=3)
    dados, crc_ok = metodo2.demodular(sinal)
    assert dados is not None
    assert not crc_ok


# ---------------------------------------------------------------- main.py

def test_main_m1_simular_sucesso():
    resultado = rodar_main("m1-simular", "Oi")
    assert resultado.returncode == 0
    assert resultado.stdout.count("[SUCESSO]") == 2
    assert "FALHA DE TRANSMISSÃO" not in resultado.stdout
    assert "Texto recebido: 'Oi'" in resultado.stdout


def test_main_m1_simular_com_erro():
    resultado = rodar_main("m1-simular", "Oi", "--erro")
    assert resultado.returncode == 0
    assert resultado.stdout.count("[FALHA DE TRANSMISSÃO]") == 1
    assert resultado.stdout.count("[SUCESSO]") == 1
    assert "Texto recebido: '?i'" in resultado.stdout


def test_main_m1_simular_nao_ascii_sem_traceback():
    resultado = rodar_main("m1-simular", "Olá")
    assert resultado.returncode == 0
    assert "Erro na entrada" in resultado.stdout
    assert "ASCII" in resultado.stdout
    assert "Traceback" not in resultado.stdout + resultado.stderr


def test_main_m2_simular_sucesso():
    resultado = rodar_main("m2-simular", "Camada Física!")
    assert resultado.returncode == 0
    assert "[SUCESSO] 'Camada Física!'" in resultado.stdout
    assert "FALHA DE TRANSMISSÃO" not in resultado.stdout


def test_main_m2_simular_com_erro():
    resultado = rodar_main("m2-simular", "Camada Física!", "--erro")
    assert resultado.returncode == 0
    assert "[FALHA DE TRANSMISSÃO] CRC não confere" in resultado.stdout
    assert "[SUCESSO]" not in resultado.stdout


def test_main_ajuda_de_cada_subcomando():
    for subcomando in ["m1-enviar", "m1-receber", "m1-simular",
                       "m2-enviar", "m2-receber", "m2-simular"]:
        resultado = rodar_main(subcomando, "--help")
        assert resultado.returncode == 0
        assert "usage" in resultado.stdout
