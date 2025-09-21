#!/usr/bin/env python3
"""
Auto Profiler - Análise automática de performance e memória
Dependências mínimas: apenas bibliotecas padrão do Python
"""
import requests
import os
from pathlib import Path

from pid_provider.monitor import AutoProfiler
from pid_provider.base_pid_provider import BasePidProvider

from django.contrib.auth import get_user_model


from pid_provider.provider import PidProvider

# from django.utils.translation import gettext as _


User = get_user_model()



def run():
    # Cria profiler
    profiler = AutoProfiler(
        top_functions=5,
        memory_threshold_mb=0.5,
        time_threshold_seconds=0.05
    )
    
    # Exemplo 1: Função com problema de performance
    @profiler.profile
    def processar_items(n=10000):
        """Exemplo de código ineficiente"""
        pp = PidProvider()
        user = get_user_model().objects.get(pk=1)
        print(user)
        for i in range(n):
            for item in pp.provide_pid_for_xml_zip(
                "/app/core/media/1688-1249-adp-84-04-300.zip",
                user,
            ):
                print(item)
        
    # Executa funções
    print("Executando análise...")
    processar_items(1000)
    
    # Gera relatório
    profiler.analyze_and_report()
    
    # Salva em arquivo
    profiler.save_report()




