import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import traceback

# --- CONSTANTES E PARAMETROS ---
# Definição de comportamentos esperados e limites para a análise
CONSTANTES = {
    'R2_MINIMO': 0.85,           # Qualidade mínima do ajuste (0 a 1)
    'AMPLITUDE_MINIMA': 0.05,    # Amplitude mínima para considerar que houve excitação relevante
    'JANELA_ANALISE_S': 30,      # Segundos finais de cada frequência a serem analisados
    'ARQUIVO_PADRAO': 'dados.csv',
    # Lista de colunas que OBRIGATORIAMENTE devem existir no CSV
    'COLUNAS_OBRIGATORIAS': ['DataHora', 'Período', 'Setpoint', 'Variavel_Controlada']
}

def encaixar_senoide(tempo, sinal, frequencia_hz):
    """
    Encaixa uma senoide aos dados experimentais usando o método dos Mínimos Quadrados.
    Retorna: Amplitude, Fase (radianos) e R² (qualidade).
    """
    frequencia_angular = 2 * np.pi * frequencia_hz
    
    # Matriz de design: [sin(wt), cos(wt), 1]
    matriz_design = np.column_stack([
        np.sin(frequencia_angular * tempo), 
        np.cos(frequencia_angular * tempo), 
        np.ones_like(tempo)
    ])
    
    try:
        coeficientes, _, _, _ = np.linalg.lstsq(matriz_design, sinal, rcond=None)
        A, B, offset = coeficientes
    except Exception:
        return 0, 0, 0
    
    amplitude = np.sqrt(A**2 + B**2)
    fase_rad = np.arctan2(B, A)
    
    # --- Cálculo do R² ---
    sinal_ajustado = A * np.sin(frequencia_angular * tempo) + B * np.cos(frequencia_angular * tempo) + offset
    soma_residuos_quadraticos = np.sum((sinal - sinal_ajustado) ** 2)
    soma_total_quadrados = np.sum((sinal - np.mean(sinal)) ** 2)
    
    if soma_total_quadrados == 0:
        r2 = 0.0
    else:
        r2 = 1 - (soma_residuos_quadraticos / soma_total_quadrados)
        
    return amplitude, fase_rad, r2

def carregar_e_preparar_dados(caminho_arquivo):
    """
    Tenta ler o arquivo CSV com diferentes codificações e checa se todas as colunas obrigatórias estão presentes.
    """
    print(f"Lendo arquivo: {caminho_arquivo}...")
    
    encodings_para_testar = ['utf-8-sig', 'latin-1', 'cp1252']
    df = None
    
    for encoding in encodings_para_testar:
        try:
            df = pd.read_csv(caminho_arquivo, sep=';', decimal=',', encoding=encoding)
            print(f"Sucesso! Arquivo lido com encoding: {encoding}")
            break 
        except UnicodeDecodeError:
            continue 
        except Exception as e:
            raise e 
            
    if df is None:
        raise ValueError("Falha ao ler o arquivo. Verifique se é um CSV válido.")

    # --- VALIDAÇÃO DE COLUNAS ---
    for col_obrigatoria in CONSTANTES['COLUNAS_OBRIGATORIAS']:
        if col_obrigatoria not in df.columns:
            raise KeyError(f"A coluna '{col_obrigatoria}' não foi encontrada no arquivo. "
                           f"Colunas encontradas: {list(df.columns)}")

    # Converte tempo
    df['DataHora'] = pd.to_datetime(df['DataHora'], format='%d/%m/%Y - %H:%M:%S,%f')
    
    tempo_inicial = df['DataHora'].iloc[0]
    df['Tempo_Segundos'] = (df['DataHora'] - tempo_inicial).dt.total_seconds()
    
    return df

def calcular_resposta_frequencia(df):
    """
    Calcula magnitude e fase para cada frequência testada.
    """
    resultados = []
    janela_segundos = CONSTANTES['JANELA_ANALISE_S']
    
    print(f"\nProcessando... Analisando os últimos {janela_segundos}s de cada frequência.")

    # Agrupa diretamente pela coluna 'Período'
    grupos = df.groupby('Período')

    for periodo, dados_grupo in grupos:
        if periodo <= 0: continue
        
        freq_hz = 1.0 / periodo
        
        # --- FILTRAGEM TEMPORAL ---
        tempo_fim = dados_grupo['Tempo_Segundos'].max()
        tempo_inicio_janela = tempo_fim - janela_segundos
        
        dados_estaveis = dados_grupo[dados_grupo['Tempo_Segundos'] >= tempo_inicio_janela]
        
        if len(dados_estaveis) < 10: continue

        tempo = dados_estaveis['Tempo_Segundos'].values
        # Acesso direto às colunas pelo nome string
        sinal_u = dados_estaveis['Setpoint'].values
        sinal_y = dados_estaveis['Variavel_Controlada'].values

        amp_u, fase_u, r2_u = encaixar_senoide(tempo, sinal_u, freq_hz)
        amp_y, fase_y, r2_y = encaixar_senoide(tempo, sinal_y, freq_hz)

        if amp_u == 0: continue
        
        # --- CÁLCULO DE BODE ---
        ganho_db = 20 * np.log10(amp_y / amp_u)
        diferenca_fase_graus = np.degrees(fase_y - fase_u)
        
        # Normaliza a fase (-180 a +180)
        while diferenca_fase_graus > 180: diferenca_fase_graus -= 360
        while diferenca_fase_graus <= -180: diferenca_fase_graus += 360

        # --- CRITÉRIOS DE VALIDAÇÃO ---
        # Separação clara: O dado é valido se tiver boa qualidade (R²) E amplitude suficiente
        tem_amplitude_suficiente = (amp_y >= CONSTANTES['AMPLITUDE_MINIMA'])
        tem_bom_ajuste = (r2_y >= CONSTANTES['R2_MINIMO'])
        
        dados_validos = tem_amplitude_suficiente and tem_bom_ajuste

        resultados.append({
            'freq_hz': freq_hz, 
            'magnitude_db': ganho_db, 
            'fase_graus': diferenca_fase_graus,
            'r2': r2_y,
            'aceito': dados_validos
        })
        
        status = "[OK]" if dados_validos else "[DESCARTADO]"
        print(f"{status} T={periodo}s | Freq={freq_hz:.2f}Hz | R²={r2_y:.2f} | Mag={ganho_db:.1f}dB | Fase={diferenca_fase_graus:.1f}°")

    return pd.DataFrame(resultados).sort_values('freq_hz')

def plotar_bode(df_resultados):
    """
    Gera o gráfico de Bode separando dados válidos e descartados.
    """
    if df_resultados.empty:
        print("Nenhum resultado para plotar.")
        return

    fig, (ax_mag, ax_fase) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Filtra usando termos mais formais
    df_validos = df_resultados[df_resultados['aceito'] == True]
    df_descartados = df_resultados[df_resultados['aceito'] == False]
    
    # --- GRÁFICO 1: MAGNITUDE ---
    ax_mag.semilogx(df_validos['freq_hz'], df_validos['magnitude_db'], 'o-', color='blue', label='Dados Válidos')
    if not df_descartados.empty:
        ax_mag.semilogx(df_descartados['freq_hz'], df_descartados['magnitude_db'], 'x', color='red', alpha=0.5, label='Descartados')
        
    ax_mag.set_title(f"Diagrama de Bode Experimental (Janela: Últimos {CONSTANTES['JANELA_ANALISE_S']}s)")
    ax_mag.set_ylabel('Magnitude (dB)')
    ax_mag.grid(True, which="both", ls="-", alpha=0.3)
    ax_mag.legend()

    # --- GRÁFICO 2: FASE ---
    ax_fase.semilogx(df_validos['freq_hz'], df_validos['fase_graus'], 'o-', color='blue')
    if not df_descartados.empty:
        ax_fase.semilogx(df_descartados['freq_hz'], df_descartados['fase_graus'], 'x', color='red', alpha=0.5)

    ax_fase.set_ylabel('Fase (graus)')
    ax_fase.set_xlabel('Frequência (Hz)')
    ax_fase.grid(True, which="both", ls="-", alpha=0.3)
    
    plt.tight_layout()
    plt.show()

def main():
    entrada_usuario = input(f"Digite o caminho do arquivo .csv (Padrão: {CONSTANTES['ARQUIVO_PADRAO']}): ")
    caminho_csv = entrada_usuario if entrada_usuario.strip() else CONSTANTES['ARQUIVO_PADRAO']
    
    try:
        # 1. Carregar
        df_dados = carregar_e_preparar_dados(caminho_csv)
        
        # 2. Processar
        df_resultados = calcular_resposta_frequencia(df_dados)
        
        # 3. Plotar
        plotar_bode(df_resultados)

    except FileNotFoundError:
        print(f"ERRO: O arquivo '{caminho_csv}' não foi encontrado.")
    except OSError:
        # Captura erros de nome de arquivo inválido (ex: caracteres proibidos ou sintaxe errada)
        print(f"ERRO: O nome do arquivo ou caminho é inválido: '{caminho_csv}'")
        print("Dica: Verifique se não há caracteres especiais ou aspas no meio do nome.")
    except KeyError as e:
        print(f"ERRO: Coluna não encontrada no CSV: {e}")
        print(f"Colunas esperadas: {list(CONSTANTES['COLUNAS_OBRIGATORIAS'].values())}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()