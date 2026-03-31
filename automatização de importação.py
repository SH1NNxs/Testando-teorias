import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import time
import threading
import pyautogui
import pygetwindow as gw
import win32gui
import win32con
import sys
from datetime import datetime

# --- Configurações do PyAutoGUI ---
pyautogui.PAUSE = 0.2
pyautogui.FAILSAFE = True

# --- Variáveis globais ---
loop_delay = 0.3
countdown_time = 5
retry_delay = 1.0

class AutomationController:
    def __init__(self):
        self.paused = False
        self.running = False
        self.stopped = False
        self.price_value = ""
        self.insertion_count = 0
        self.max_insertions = 1000
        self.field_check_attempts = 0
        self.max_field_checks = 3
        self.is_countdown_active = False
        self.last_field_state = "UNKNOWN"  # UNKNOWN, ENABLED, DISABLED
    
    def pause(self):
        self.paused = True
    
    def resume(self):
        self.paused = False
        self.field_check_attempts = 0
    
    def stop(self):
        self.running = False
        self.stopped = True
        self.paused = False
        self.is_countdown_active = False
    
    def set_price(self, price):
        self.price_value = price

# --- Funções para manipulação de janelas ---
def minimize_control_window():
    try:
        if mini_window:
            mini_window.iconify()
            time.sleep(0.2)
    except:
        pass

def restore_control_window():
    try:
        if mini_window:
            mini_window.deiconify()
            mini_window.lift()
            time.sleep(0.2)
    except:
        pass

# --- Função para detectar se campo está desabilitado ---
def detect_field_state():
    """
    Tenta detectar se o campo está habilitado ou desabilitado
    Retorna: "ENABLED", "DISABLED", ou "UNKNOWN"
    """
    try:
        # Estratégia 1: Tentar obter informações da janela ativa
        active_window = gw.getActiveWindow()
        if not active_window:
            return "UNKNOWN"
        
        # Estratégia 2: Tentar verificar pelo foco
        # Se conseguirmos escrever, provavelmente está habilitado
        try:
            # Tentar uma ação simples para testar
            current_pos = pyautogui.position()
            
            # Tentar obter a cor do pixel na posição atual (pode indicar estado)
            pixel_color = pyautogui.pixel(current_pos.x, current_pos.y)
            
            # Se a cor for muito clara (como cinza claro), pode ser campo desabilitado
            # Isso depende do sistema, você pode ajustar conforme necessário
            brightness = sum(pixel_color) / 3
            
            # Campos desabilitados geralmente são mais claros (cinza)
            if brightness > 200:  # Muito claro - possível campo desabilitado
                print(f"⚠️ Campo possivelmente desabilitado (brilho: {brightness})")
                return "DISABLED"
            
        except:
            pass
        
        # Estratégia 3: Tentar uma ação de escrita
        # Se conseguir escrever, está habilitado
        try:
            # Guardar clipboard atual
            import pyperclip
            original_clipboard = pyperclip.paste()
            
            # Tentar escrever um caractere de teste
            pyautogui.write("a", interval=0.01)
            time.sleep(0.01)
            
            # Verificar se escreveu (apagar se escreveu)
            pyautogui.press('backspace')
            
            return "ENABLED"
        except:
            # Se não conseguiu escrever, pode estar desabilitado
            return "DISABLED"
        
    except Exception as e:
        print(f"❌ Erro ao detectar estado do campo: {e}")
        return "UNKNOWN"

# --- Função de countdown ---
def show_countdown(seconds):
    try:
        for i in range(seconds, 0, -1):
            if not controller.running or controller.stopped or controller.paused:
                show_mini_message("Countdown interrompido", True)
                return False
            
            show_mini_message(f"⏰ {i} segundo{'s' if i != 1 else ''} para selecionar o primeiro item...", False)
            
            if countdown_label:
                countdown_label.config(text=f"⏰ {i}s")
                mini_window.update()
            
            time.sleep(1)
        
        return True
    except:
        return False

# --- Função para focar no sistema ---
def focus_on_system():
    try:
        minimize_control_window()
        time.sleep(0.3)
        time.sleep(0.2)
        return True
    except:
        return False

# --- Função aprimorada para escrever com verificação de estado ---
def write_to_field_with_state_check(price_value):
    """
    Tenta escrever no campo, verificando o estado antes e depois
    Retorna: (success, message, field_state)
    """
    try:
        # 1. Verificar estado do campo ANTES de tentar
        field_state_before = detect_field_state()
        print(f"🔍 Estado do campo antes: {field_state_before}")
        
        if field_state_before == "DISABLED":
            return False, "Campo está DESABILITADO", "DISABLED"
        
        # 2. Tentar escrever
        print(f"✍️ Tentando escrever: {price_value}")
        
        # Limpar campo
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.01)
        pyautogui.press('delete')
        time.sleep(0.01)
        
        # Escrever valor
        pyautogui.write(str(price_value), interval=0.05)
        time.sleep(0.01)
        
        # Pressionar Enter
        pyautogui.press('enter')
        time.sleep(0.01)
        
        # 3. Verificar estado do campo DEPOIS
        field_state_after = detect_field_state()
        print(f"🔍 Estado do campo depois: {field_state_after}")
        
        # Atualizar último estado conhecido
        controller.last_field_state = field_state_after
        
        # 4. Verificar se o campo ficou desabilitado após Enter
        if field_state_after == "DISABLED":
            print("⚠️ Campo ficou desabilitado após inserção!")
            return True, "Valor inserido, mas campo desabilitado após", "DISABLED"
        
        return True, "Sucesso", field_state_after
        
    except Exception as e:
        print(f"❌ Erro ao escrever: {e}")
        return False, str(e), "UNKNOWN"

# --- Função principal da automação ---
def run_automation_loop(controller):
    def automation_loop():
        controller.insertion_count = 0
        controller.field_check_attempts = 0
        controller.last_field_state = "UNKNOWN"
        
        print("🏁 Iniciando loop de automação...")
        print("⚠️ ATENÇÃO: Você tem 5 segundos para selecionar o primeiro item!")
        
        # Passo 1: Preparação
        show_mini_message("🎬 Preparando para iniciar...", False)
        time.sleep(1)
        
        # Passo 2: Focar no sistema
        show_mini_message("🖥️ Mudando foco para o sistema...", False)
        focus_on_system()
        time.sleep(1)
        
        # Passo 3: COUNTDOWN de 5 segundos
        show_mini_message("⏰ PRONTO? Você tem 5 segundos para clicar no primeiro item!", True)
        time.sleep(1)
        
        controller.is_countdown_active = True
        countdown_completed = show_countdown(countdown_time)
        controller.is_countdown_active = False
        
        if not countdown_completed:
            show_mini_message("❌ Countdown interrompido", True)
            restore_control_window()
            return
        
        # Passo 4: Teste inicial
        show_mini_message("🔍 Testando acesso ao campo...", False)
        time.sleep(0.5)
        
        test_success, test_msg, test_state = write_to_field_with_state_check("TEST")
        
        if test_success:
            # Limpar teste
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('delete')
            time.sleep(0.1)
            
            show_mini_message("✅ Campo pronto! Iniciando loop principal...", False)
            controller.last_field_state = test_state
        else:
            show_mini_message(f"⚠️ Campo não acessível: {test_msg}", True)
            restore_control_window()
            messagebox.showwarning("Campo Não Acessível",
                                 f"Não foi possível acessar o campo.\n\n"
                                 f"Motivo: {test_msg}\n\n"
                                 f"Por favor:\n"
                                 f"1. Verifique se o campo está habilitado\n"
                                 f"2. Clique no campo novamente\n"
                                 f"3. Tente novamente")
            controller.stop()
            return
        
        # Passo 5: LOOP PRINCIPAL COM VERIFICAÇÃO DE ESTADO
        show_mini_message("🔄 Iniciando loop principal...", False)
        time.sleep(1)
        
        consecutive_disabled_count = 0
        max_consecutive_disabled = 2  # Se campo ficar desabilitado 2x seguidas, pausa
        
        while controller.running and not controller.stopped:
            
            if controller.paused:
                show_mini_message("⏸️ Pausado - clique PLAY para continuar", True)
                restore_control_window()
                time.sleep(0.5)
                continue
            
            if controller.insertion_count >= controller.max_insertions:
                show_mini_message("🎯 Limite de 1000 inserções atingido", False)
                controller.stop()
                break
            
            try:
                # Verificar estado do campo ANTES de tentar
                current_field_state = detect_field_state()
                print(f"🔄 Estado atual do campo: {current_field_state}")
                
                # Se campo estiver desabilitado
                if current_field_state == "DISABLED":
                    consecutive_disabled_count += 1
                    show_mini_message(f"⛔ Campo DESABILITADO detectado ({consecutive_disabled_count}/{max_consecutive_disabled})", True)
                    
                    if consecutive_disabled_count >= max_consecutive_disabled:
                        show_mini_message("🛑 Campo desabilitado - PAUSANDO automaticamente", True)
                        controller.pause()
                        restore_control_window()
                        
                        # Mostrar mensagem informativa
                        messagebox.showinfo("Campo Desabilitado",
                                          "O campo de edição foi desabilitado pelo sistema.\n\n"
                                          "Possíveis causas:\n"
                                          "• Todos os itens foram processados\n"
                                          "• Sistema está salvando dados\n"
                                          "• Há um pop-up ou alerta\n\n"
                                          "Verifique o sistema e clique em PLAY para continuar.")
                        
                        consecutive_disabled_count = 0
                        continue
                    else:
                        # Aguardar um pouco e tentar novamente
                        time.sleep(retry_delay)
                        continue
                else:
                    consecutive_disabled_count = 0  # Resetar contador se campo estiver habilitado
                
                # Tentar inserção
                current_count = controller.insertion_count + 1
                show_mini_message(f"▶️ Inserindo ({current_count}): {controller.price_value}")
                
                success, message, field_state = write_to_field_with_state_check(controller.price_value)
                
                if success:
                    controller.insertion_count += 1
                    controller.field_check_attempts = 0
                    controller.last_field_state = field_state
                    
                    # Verificar se campo ficou desabilitado após inserção
                    if field_state == "DISABLED":
                        show_mini_message(f"✅ Inserido ({controller.insertion_count}), mas campo DESABILITADO", True)
                        consecutive_disabled_count += 1
                        
                        if consecutive_disabled_count >= max_consecutive_disabled:
                            show_mini_message("🛑 Campo desabilitado após inserção - PAUSANDO", True)
                            controller.pause()
                            restore_control_window()
                            messagebox.showinfo("Campo Desabilitado",
                                              "O campo foi desabilitado após a última inserção.\n\n"
                                              "Isso pode indicar que:\n"
                                              "• O processamento terminou\n"
                                              "• Há um limite atingido\n"
                                              "• O sistema está bloqueando edições\n\n"
                                              "Verifique o sistema antes de continuar.")
                        else:
                            # Aguardar um pouco para ver se campo se reabilita
                            time.sleep(retry_delay * 2)
                    else:
                        show_mini_message(f"✅ Inserido ({controller.insertion_count}): {controller.price_value}")
                        time.sleep(loop_delay)
                    
                else:
                    controller.field_check_attempts += 1
                    show_mini_message(f"⚠️ Falha: {message}", True)
                    
                    # Se falha foi por campo desabilitado
                    if "DESABILITADO" in message.upper():
                        consecutive_disabled_count += 1
                        
                        if consecutive_disabled_count >= max_consecutive_disabled:
                            show_mini_message("🛑 Campo permanece desabilitado - PAUSANDO", True)
                            controller.pause()
                            restore_control_window()
                    
                    if controller.field_check_attempts >= controller.max_field_checks:
                        show_mini_message("🛑 Muitas falhas - Pausando", True)
                        controller.pause()
                        restore_control_window()
                    else:
                        time.sleep(retry_delay)
            
            except Exception as e:
                print(f"❌ Erro no loop: {e}")
                show_mini_message(f"❌ Erro: {str(e)}", True)
                time.sleep(retry_delay)
        
        # Finalização
        print("✅ Loop finalizado")
        restore_control_window()
        
        if controller.stopped:
            show_mini_message("🛑 Processamento finalizado", False)
        else:
            show_mini_message(f"✅ Concluído! Total: {controller.insertion_count} inserções", False)
        
        # Resetar interface
        try:
            play_btn.config(text="▶️ Iniciar Loop", bg="#27ae60")
            price_entry.config(state='normal', bg="white")
            if countdown_label:
                countdown_label.config(text="")
        except:
            pass
    
    # Iniciar thread
    thread = threading.Thread(target=automation_loop, daemon=True)
    thread.start()

# --- Variáveis globais para interface ---
mini_window = None
mini_status_label = None
price_entry = None
play_btn = None
controller = None
counter_label = None
countdown_label = None

# --- Função para mostrar mensagens ---
def show_mini_message(message, is_warning=False):
    try:
        if mini_status_label and mini_window:
            if "▶️" in message or "Inserindo" in message:
                mini_status_label.config(text=message, fg="#3498db")
            elif "✅" in message:
                mini_status_label.config(text=message, fg="#27ae60")
            elif "⏸️" in message or "Pausado" in message:
                mini_status_label.config(text=message, fg="#f39c12")
            elif "🛑" in message:
                mini_status_label.config(text=message, fg="#e74c3c")
            elif "⚠️" in message or "❌" in message:
                mini_status_label.config(text=message, fg="#e67e22")
            elif "⏰" in message or "segundo" in message:
                mini_status_label.config(text=message, fg="#9b59b6")
            elif "🎬" in message or "🔄" in message or "🎯" in message:
                mini_status_label.config(text=message, fg="#1abc9c")
            elif "🖥️" in message or "🔍" in message:
                mini_status_label.config(text=message, fg="#3498db")
            elif "⛔" in message or "DESABILITADO" in message.upper():
                mini_status_label.config(text=message, fg="#e74c3c")  # Vermelho para desabilitado
            else:
                mini_status_label.config(text=message, fg="#2c3e50")
            
            if counter_label and controller:
                counter_label.config(text=f"Inserções: {controller.insertion_count}")
            
            mini_window.update()
    except Exception as e:
        print(f"Erro ao mostrar mensagem: {e}")

# --- Janela de Instruções (similar à anterior) ---
def show_instructions():
    instructions_window = tk.Tk()
    instructions_window.title("Robô de Automação - Instruções")
    instructions_window.geometry("700x650")  # Um pouco maior para nova informação
    
    instructions_window.configure(bg="#f0f0f0")
    
    instructions_window.update_idletasks()
    width = instructions_window.winfo_width()
    height = instructions_window.winfo_height()
    x = (instructions_window.winfo_screenwidth() // 2) - (width // 2)
    y = (instructions_window.winfo_screenheight() // 2) - (height // 2)
    instructions_window.geometry(f'{width}x{height}+{x}+{y}')
    
    main_frame = tk.Frame(instructions_window, bg="#f0f0f0")
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    canvas = tk.Canvas(main_frame, bg="#f0f0f0", highlightthickness=0)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg="#f0f0f0")
    
    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    title_label = tk.Label(scrollable_frame, 
                         text="🤖 ROBÔ INTELIGENTE - DETECÇÃO DE CAMPO", 
                         font=("Arial", 18, "bold"),
                         bg="#f0f0f0",
                         fg="#2c3e50")
    title_label.pack(pady=(0, 20))
    
    frame = tk.Frame(scrollable_frame, bg="white", relief=tk.RAISED, bd=3)
    frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
    
    instructions_text = """🎯 NOVA FUNCIONALIDADE:

🔄 DETECÇÃO AUTOMÁTICA DE CAMPO DESABILITADO

O robô agora detecta automaticamente quando o sistema
desabilita o campo de edição e PAUSA imediatamente.

🔧 COMO FUNCIONA:

1️⃣ INICIE O ROBÔ normalmente
   • 5 segundos para selecionar primeiro item
   • Loop automático de inserção

2️⃣ DETECÇÃO INTELIGENTE
   • Monitora estado do campo continuamente
   • Detecta quando campo fica "cinza" ou desabilitado
   • Verifica antes e depois de cada inserção

3️⃣ PAUSA AUTOMÁTICA
   • Se campo for desabilitado → PAUSA imediata
   • Janela do robô volta para primeiro plano
   • Mensagem explicativa aparece

4️⃣ CONTINUAÇÃO
   • Verifique por que o campo foi desabilitado
   • Clique em PLAY para continuar se necessário
   • Ou STOP para finalizar

⚠️ SITUAÇÕES COMUNS QUE CAUSAM PAUSA:

• ✅ TODOS OS ITENS PROCESSADOS
• 💾 SISTEMA SALVANDO DADOS
• ⚠️ POP-UP OU ALERTA ABERTO
• 🔒 PERMISSÕES ALTERADAS
• 📊 LIMITE DE EDIÇÕES ATINGIDO

🎯 FLUXO RECOMENDADO:
1. Inicie o robô
2. Deixe trabalhar
3. Quando pausar automaticamente → Verifique o sistema
4. Se terminou → Clique STOP
5. Se for temporário → Clique PLAY para continuar"""
    
    instructions_label = tk.Label(frame, 
                                text=instructions_text,
                                font=("Arial", 11),
                                bg="white",
                                justify=tk.LEFT,
                                anchor="w",
                                padx=20,
                                pady=20)
    instructions_label.pack(fill=tk.BOTH, expand=True)
    
    button_frame = tk.Frame(main_frame, bg="#f0f0f0")
    button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
    
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def on_understood():
        instructions_window.destroy()
        show_mini_control_window()
    
    understood_btn = tk.Button(button_frame,
                             text="✅ ENTENDI - VAMOS COMEÇAR",
                             font=("Arial", 12, "bold"),
                             bg="#27ae60",
                             fg="white",
                             padx=40,
                             pady=12,
                             command=on_understood)
    understood_btn.pack(pady=10)
    
    def _on_mouse_wheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    canvas.bind_all("<MouseWheel>", _on_mouse_wheel)
    instructions_window.mainloop()

# --- Mini Janela de Controle ---
def show_mini_control_window():
    global mini_window, mini_status_label, price_entry, play_btn, controller, counter_label, countdown_label
    
    mini_window = tk.Tk()
    mini_window.title("Robô Inteligente - Detecção de Campo")
    mini_window.geometry("450x550")  # Aumentado para mais informações
    
    mini_window.configure(bg="#2c3e50")
    mini_window.attributes('-topmost', True)
    
    mini_window.update_idletasks()
    width = mini_window.winfo_width()
    height = mini_window.winfo_height()
    x = mini_window.winfo_screenwidth() - width - 20
    y = 20
    mini_window.geometry(f'{width}x{height}+{x}+{y}')
    
    # Título
    title = tk.Label(mini_window,
                    text="🤖 Robô Inteligente",
                    font=("Arial", 14, "bold"),
                    bg="#2c3e50",
                    fg="white")
    title.pack(pady=10)
    
    # Subtítulo
    subtitle = tk.Label(mini_window,
                       text="Com detecção automática de campo",
                       font=("Arial", 10),
                       bg="#2c3e50",
                       fg="#bdc3c7")
    subtitle.pack()
    
    # Campo de preço
    price_frame = tk.Frame(mini_window, bg="#34495e", bd=2, relief=tk.RAISED, padx=15, pady=10)
    price_frame.pack(pady=10, padx=20, fill=tk.X)
    
    price_label = tk.Label(price_frame,
                          text="💰 PREÇO A INSERIR:",
                          font=("Arial", 11, "bold"),
                          bg="#34495e",
                          fg="white")
    price_label.pack(side=tk.LEFT, padx=(0, 10))
    
    price_entry = tk.Entry(price_frame,
                          font=("Arial", 12, "bold"),
                          width=12,
                          justify=tk.CENTER,
                          bd=3,
                          relief=tk.SUNKEN,
                          bg="white")
    price_entry.pack(side=tk.LEFT)
    price_entry.insert(0, "0.00")
    
    # Label para countdown
    countdown_frame = tk.Frame(mini_window, bg="#2c3e50")
    countdown_frame.pack(pady=5)
    
    countdown_label = tk.Label(countdown_frame,
                              text="",
                              font=("Arial", 16, "bold"),
                              bg="#2c3e50",
                              fg="#9b59b6")
    countdown_label.pack()
    
    # Status
    mini_status_label = tk.Label(mini_window,
                               text="Digite o preço e clique em Iniciar Loop",
                               font=("Arial", 10),
                               bg="#2c3e50",
                               fg="#7f8c8d",
                               wraplength=400)
    mini_status_label.pack(pady=5)
    
    # Contador de inserções
    counter_label = tk.Label(mini_window,
                           text="Inserções: 0",
                           font=("Arial", 10, "bold"),
                           bg="#2c3e50",
                           fg="#bdc3c7")
    counter_label.pack(pady=2)
    
    # Indicador de estado do campo
    field_state_label = tk.Label(mini_window,
                                text="Estado do campo: Aguardando...",
                                font=("Arial", 9),
                                bg="#2c3e50",
                                fg="#ecf0f1")
    field_state_label.pack(pady=2)
    
    # Função para atualizar estado do campo
    def update_field_state():
        if controller and controller.running and not controller.paused:
            state = controller.last_field_state
            if state == "ENABLED":
                field_state_label.config(text="✅ Campo: HABILITADO", fg="#27ae60")
            elif state == "DISABLED":
                field_state_label.config(text="⛔ Campo: DESABILITADO", fg="#e74c3c")
            else:
                field_state_label.config(text="🔍 Campo: Verificando...", fg="#f39c12")
            
            mini_window.after(1000, update_field_state)
    
    # Frame de controle
    control_frame = tk.Frame(mini_window, bg="#2c3e50")
    control_frame.pack(pady=15)
    
    controller = AutomationController()
    
    # Frame para botões
    button_frame = tk.Frame(control_frame, bg="#2c3e50")
    button_frame.pack(pady=10)
    
    def update_counter():
        if mini_window and counter_label and controller:
            if controller.running and not controller.stopped:
                counter_label.config(text=f"Inserções: {controller.insertion_count}")
                mini_window.after(1000, update_counter)
    
    def on_play():
        if controller.stopped:
            controller.stopped = False
            controller.insertion_count = 0
            controller.field_check_attempts = 0
        
        if not controller.running:
            price = price_entry.get()
            if not price:
                messagebox.showwarning("Atenção", "Digite o preço antes de iniciar!")
                return
            
            try:
                float(price)
            except ValueError:
                messagebox.showwarning("Atenção", "Digite um valor numérico válido!")
                return
            
            confirm = messagebox.askyesno("Confirmar Início",
                                         f"Preço: {price}\n\n"
                                         f"⚠️ NOVA FUNCIONALIDADE:\n"
                                         f"O robô pausará automaticamente se o campo\n"
                                         f"for desabilitado pelo sistema.\n\n"
                                         f"Você terá 5 SEGUNDOS para clicar no primeiro item.\n\n"
                                         f"Pronto para começar?")
            
            if not confirm:
                return
            
            controller.set_price(price)
            controller.running = True
            
            play_btn.config(text="⏸️ Pausar", bg="#e67e22")
            price_entry.config(state='disabled', bg="#ecf0f1")
            stop_btn.config(state='normal')
            
            show_mini_message("🎬 Preparando para iniciar...")
            
            run_automation_loop(controller)
            update_counter()
            update_field_state()  # Iniciar monitoramento de estado
            
        elif controller.paused:
            controller.resume()
            play_btn.config(text="⏸️ Pausar", bg="#e67e22")
            show_mini_message("▶️ Retomando execução...")
            update_field_state()
        else:
            controller.pause()
            play_btn.config(text="▶️ Retomar", bg="#27ae60")
            restore_control_window()
            show_mini_message("⏸️ Execução pausada")
    
    play_btn = tk.Button(button_frame,
                        text="▶️ Iniciar Loop",
                        font=("Arial", 12, "bold"),
                        bg="#27ae60",
                        fg="white",
                        width=14,
                        height=1,
                        command=on_play)
    play_btn.pack(side=tk.LEFT, padx=5)
    
    def on_stop():
        controller.stop()
        play_btn.config(text="▶️ Iniciar Loop", bg="#27ae60")
        counter_label.config(text="Inserções: 0")
        price_entry.config(state='normal', bg="white")
        field_state_label.config(text="Estado do campo: Aguardando...", fg="#ecf0f1")
        if countdown_label:
            countdown_label.config(text="")
        restore_control_window()
        show_mini_message("🛑 Processamento finalizado")
    
    stop_btn = tk.Button(button_frame,
                        text="⏹️ Parar",
                        font=("Arial", 12),
                        bg="#e74c3c",
                        fg="white",
                        width=10,
                        height=1,
                        command=on_stop)
    stop_btn.pack(side=tk.LEFT, padx=5)
    
    # Frame de informações
    info_frame = tk.Frame(mini_window, bg="#34495e", bd=1, relief=tk.SUNKEN)
    info_frame.pack(pady=10, padx=15, fill=tk.X)
    
    info_text = """🔍 DETECÇÃO AUTOMÁTICA:
• ⛔ Campo desabilitado → PAUSA automática
• 🎯 5 segundos para selecionar primeiro item
• 🔄 1 segundo entre inserções
• ⚠️ Verifique sistema quando pausar"""
    
    info_label = tk.Label(info_frame,
                         text=info_text,
                         font=("Arial", 9),
                         bg="#34495e",
                         fg="#ecf0f1",
                         justify=tk.LEFT,
                         padx=10,
                         pady=10)
    info_label.pack()
    
    # Frame de dicas
    tips_frame = tk.Frame(mini_window, bg="#2c3e50")
    tips_frame.pack(pady=5, padx=10)
    
    tips_label = tk.Label(tips_frame,
                         text="💡 Quando o robô pausar automaticamente:\n"
                              "1. Verifique se todos os itens foram processados\n"
                              "2. Confirme se há pop-ups ou alertas\n"
                              "3. Clique PLAY para continuar ou STOP para finalizar",
                         font=("Arial", 8),
                         bg="#2c3e50",
                         fg="#bdc3c7",
                         justify=tk.LEFT)
    tips_label.pack()
    
    # Fechar janela
    def on_closing():
        if controller:
            controller.stop()
        mini_window.destroy()
        sys.exit()
    
    mini_window.protocol("WM_DELETE_WINDOW", on_closing)
    mini_window.mainloop()

# --- Inicialização ---
def main():
    print("=" * 60)
    print("🤖 ROBÔ INTELIGENTE - COM DETECÇÃO DE CAMPO DESABILITADO")
    print("=" * 60)
    print("NOVA FUNCIONALIDADE: Pausa automática quando campo é desabilitado")
    print("=" * 60)
    
    # Instalar pyperclip se necessário
    try:
        import pyperclip
    except ImportError:
        print("Instalando pyperclip...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyperclip"])
        import pyperclip
    
    show_instructions()

if __name__ == "__main__":
    main()