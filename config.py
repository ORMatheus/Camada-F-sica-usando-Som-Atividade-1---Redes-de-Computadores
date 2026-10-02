# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Constantes compartilhadas pelo emissor e pelo receptor.
 
Ficam num lugar só para que emissor e receptor nunca discordem do ritmo.
Ajuste INTERVALO_BATIDAS e SILENCIO_BITS.
"""
 
# Áudio
TAXA_AMOSTRAGEM = 44100                                      # amostras por segundo
DURACAO_JANELA = 0.010                                       # 10 ms
AMOSTRAS_POR_JANELA = int(TAXA_AMOSTRAGEM * DURACAO_JANELA)  # 441
 
# Ritmo do Método 1 (valores provisórios, até medir o vídeo de referência)
INTERVALO_BATIDAS = 0.15  # s, entre as 2 batidas de um bit 1
SILENCIO_BITS = 0.6       # s, da última batida de um bit até a 1ª batida do próximo
 
# Receptor do Método 1
LIMITE_GRUPO = (INTERVALO_BATIDAS + SILENCIO_BITS) / 2  # "ainda é o mesmo bit?"
PERIODO_REFRATARIO = 0.08                               # "ainda é a mesma batida?"
TIMEOUT_QUADRO = 2.0                                    # descarta quadro incompleto
 

