import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import traceback

# --- CONSTANTES ---
CONSTANTES = {
    'JANELA_ANALISE_S': 30,      # Analisa apenas os últimos 30 segundos
    'ARQUIVO_PADRAO': 'dados.csv',
    'AMPLITUDE_MINIMA': 0.05,
    # Lista usada apenas para validação e mensagem de erro
    'COLUNAS_OBRIGATORIAS': ['DataHora', 'Período', 'Setpoint', 'Variavel_Controlada']
}

def encaixar_senoide(tempo, sinal, frequencia_hz):
    """
    Ajusta uma senoide e retorna: sinal reconstruído, amplitude, fase e R².
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
        return np.zeros_like(sinal), 0, 0, 0
    
    # Recalcula o sinal ideal (curva de ajuste)
    sinal_ajustado = A * np.sin(frequencia_angular * tempo) + B * np.cos(frequencia_angular * tempo) + offset
    
    amplitude = np.sqrt(A**2 + B**2)
    fase_rad = np.arctan2(B, A)
    
    # Cálculo do R²
    soma_residuos = np.sum((sinal - sinal_ajustado) ** 2)
    soma_total = np.sum((sinal - np.mean(sinal)) ** 2)
    r2 = 1 - (soma_residuos / soma_total) if soma_total != 0 else 0.0
    
    return sinal_ajustado, amplitude, fase_rad, r2

def carregar_dados(caminho_arquivo):
    """
    Lê o CSV tentando diferentes encodings.
    """
    print(f"Lendo arquivo: {caminho_arquivo}...")
    
    encodings = ['utf-8-sig', 'latin-1', 'cp1252']
    df = None
    
    for enc in encodings:
        try:
            df = pd.read_csv(caminho_arquivo, sep=';', decimal=',', encoding=enc)
            print(f"Sucesso! Arquivo lido com encoding: {enc}")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            raise e

    if df is None:
        raise ValueError("Falha ao ler o arquivo. Verifique o formato CSV.")

    df.columns = [str(c).strip() for c in df.columns]
    
    # Validação das colunas
    for col in CONSTANTES['COLUNAS_OBRIGATORIAS']:
        if col not in df.columns:
            raise KeyError(f"{col}")

    df['DataHora'] = pd.to_datetime(df['DataHora'], format='%d/%m/%Y - %H:%M:%S,%f')
    t0 = df['DataHora'].iloc[0]
    df['Tempo_Segundos'] = (df['DataHora'] - t0).dt.total_seconds()
    
    return df

def obter_periodo_usuario(df):
    """
    Mostra opções e pede input do usuário.
    """
    periodos_disponiveis = sorted([float(p) for p in df['Período'].unique()])
    print(f"\nPeríodos encontrados: {periodos_disponiveis}")
    
    entrada = input("Digite o período que deseja visualizar (ex: 6): ")
    try:
        return float(entrada.replace(',', '.'))
    except ValueError:
        return None

def filtrar_e_ajustar_dados(df, periodo_alvo):
    """
    Processa os dados e JÁ CALCULA as métricas de Bode (Ganho, Fase, Atraso).
    """
    grupo = df[df['Período'] == periodo_alvo].copy()
    if grupo.empty:
        return None

    tempo_final = grupo['Tempo_Segundos'].max()
    inicio_janela = tempo_final - CONSTANTES['JANELA_ANALISE_S']
    dados_estaveis = grupo[grupo['Tempo_Segundos'] >= inicio_janela]
    
    if len(dados_estaveis) < 10:
        print("Aviso: Poucos dados para análise neste período.")
        return None

    t = dados_estaveis['Tempo_Segundos'].values
    u_real = dados_estaveis['Setpoint'].values
    y_real = dados_estaveis['Variavel_Controlada'].values
    
    freq_hz = 1.0 / periodo_alvo
    
    # Ajustes
    u_fit, amp_u, fase_u, r2_u = encaixar_senoide(t, u_real, freq_hz)
    y_fit, amp_y, fase_y, r2_y = encaixar_senoide(t, y_real, freq_hz)

    # --- CÁLCULOS DE BODE E ATRASO ---
    if amp_u > 0:
        ganho_db = 20 * np.log10(amp_y / amp_u)
        defasagem = np.degrees(fase_y - fase_u)
        
        # Normalização (-180 a 180)
        while defasagem > 180: defasagem -= 360
        while defasagem < -180: defasagem += 360
        
        # Atraso temporal (Defasagem negativa = Atraso positivo)
        atraso_tempo = - (defasagem / 360.0) * periodo_alvo
    else:
        ganho_db, defasagem, atraso_tempo = 0, 0, 0

    return {
        't': t,
        'u_real': u_real, 'u_fit': u_fit,
        'y_real': y_real, 'y_fit': y_fit,
        'r2_u': r2_u, 'r2_y': r2_y,
        'freq_hz': freq_hz,
        'ganho_db': ganho_db,
        'defasagem': defasagem,
        'atraso_tempo': atraso_tempo
    }

def exibir_resultados_terminal(dados, periodo):
    """Imprime os dados no console."""
    print(f"\n--- ANÁLISE DETALHADA (T={periodo}s | F={dados['freq_hz']:.3f}Hz) ---")
    print(f"Qualidade do Ajuste (R²): Entrada={dados['r2_u']:.3f} | Saída={dados['r2_y']:.3f}")
    print(f"Magnitude: {dados['ganho_db']:.3f} dB")
    print(f"Fase:      {dados['defasagem']:.3f}°")
    print(f"Atraso Temporal: {dados['atraso_tempo']:.3f} s")

def plotar_grafico_unificado(dados, periodo):
    """Gera gráfico com curvas e métricas escritas."""
    t = dados['t']
    
    plt.figure(figsize=(12, 7))
    
    # Curvas de Entrada (Azul)
    plt.plot(t, dados['u_real'], color='skyblue', alpha=0.5, linewidth=1.5, label='Setpoint (Real)')
    # Linha contínua conforme solicitado
    plt.plot(t, dados['u_fit'], color='navy', linewidth=2, linestyle='-', label='Setpoint (Ajuste)')
    
    # Curvas de Saída (Laranja/Vermelho)
    plt.plot(t, dados['y_real'], color='orange', alpha=0.5, linewidth=1.5, label='Posição (Real)')
    plt.plot(t, dados['y_fit'], color='red', linewidth=2, linestyle='-', label='Posição (Ajuste)')

    # --- CAIXA DE INFORMAÇÕES NO GRÁFICO ---
    texto_info = (
        f"Frequência: {dados['freq_hz']:.3f} Hz\n"
        f"Ganho: {dados['ganho_db']:.2f} dB\n"
        f"Fase: {dados['defasagem']:.2f}°\n"
        f"Atraso: {dados['atraso_tempo']:.3f} s\n"
        f"R² (Ent/Sai): {dados['r2_u']:.2f} / {dados['r2_y']:.2f}"
    )
    
    # bbox cria a caixa branca de fundo
    plt.gca().text(0.02, 0.95, texto_info, transform=plt.gca().transAxes,
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    plt.title(f"Resposta Temporal: Entrada vs Saída (T = {periodo}s)", fontsize=14)
    plt.ylabel('Amplitude')
    plt.xlabel('Tempo (s)')
    plt.legend(loc='upper right', framealpha=0.9)
    plt.grid(True, which='both', linestyle='-', alpha=0.3)
    
    plt.tight_layout()
    plt.show()

def main():
    """Função principal que orquestra a análise de um período específico."""
    entrada = input(f"Digite o nome do arquivo CSV (Enter para '{CONSTANTES['ARQUIVO_PADRAO']}'): ")
    caminho_csv = entrada.strip().strip('"').strip("'")
    if not caminho_csv:
        caminho_csv = CONSTANTES['ARQUIVO_PADRAO']
    
    try:
        # 1. Carregar Dados
        df = carregar_dados(caminho_csv)
        
        # 2. Selecionar Período
        periodo_selecionado = obter_periodo_usuario(df)
        if periodo_selecionado is None:
            print("Período inválido.")
            return

        # 3. Processar Dados
        dados_proc = filtrar_e_ajustar_dados(df, periodo_selecionado)
        if dados_proc is None:
            return

        # 4. Mostrar Resultados
        exibir_resultados_terminal(dados_proc, periodo_selecionado)
        plotar_grafico_unificado(dados_proc, periodo_selecionado)

    # --- TRATAMENTO DE ERROS ---
    except FileNotFoundError:
        print(f"ERRO: O arquivo '{caminho_csv}' não foi encontrado.")
    except OSError:
        print(f"ERRO: O nome do arquivo ou caminho é inválido: '{caminho_csv}'")
        print("Dica: Verifique se não há caracteres especiais ou aspas no meio do nome.")
    except KeyError as e:
        print(f"ERRO: Coluna não encontrada no CSV: {e}")
        print(f"Colunas esperadas: {CONSTANTES['COLUNAS_OBRIGATORIAS']}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()