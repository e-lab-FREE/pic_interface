#!/usr/bin/python3

import serial
import json
import re

serial_port = None
#status, config

def print_serial():
    global serial_port

    while True:
        pic_message = serial_port.read_until(b'\r')
        pic_message = pic_message.decode(encoding='ascii')
        if len(pic_message.strip()) > 1: #Apanha os casos em que o pic manda /n/r
            print(pic_message.strip())

def receive_data_from_exp():
    global serial_port

    print("A PROCURA DE INFO NA PORTA SERIE\n")
    pic_message = serial_port.read_until(b'\r')
    pic_message = pic_message.decode(encoding='ascii')
    print("MENSAGEM DO PIC:\n")
    print(pic_message)
    print("\-------- --------/\n")
    if "DAT" in pic_message:
        print("ENCONTREI INFO\nEXPERIENCIA COMECOU")
        return "DATA_START"
    elif "END" in pic_message:
        print("ENCONTREI INFO\nEXPERIENCIA ACABOU")
        return "DATA_END"
    else:
        #1       3.1911812       9.7769165       21.2292843      25.72
        print("ENCONTREI INFO\nDADOS NA PORTA")
        pic_message = pic_message.strip()
        pic_message = pic_message.split("\t")
        pic_message = '{"Sample_number":"'+str(pic_message[0])+\
            '","Val1":"'+str(pic_message[1])+'","Val2":"'+str(pic_message[2])+\
            '","Val3":"'+str(pic_message[3])+'","Val4":"'+str(pic_message[4])+'"}'
        return pic_message
    
#ALGURES AQUI HA BUG QUANDO NAO ESTA EM NENHUMA DAS PORTAS
def try_to_lock_experiment(config_json, serial_port):
    #LOG_INFO
    print("AH PROCURA DO PIC NA PORTA SERIE")
    pic_message = serial_port.read_until(b'\r')
    pic_message = pic_message.decode(encoding='ascii')
    pic_message = pic_message.strip()
    print("MENSAGEM DO PIC:\n")
    print(pic_message)
    print("\-------- --------/\n")
    match = re.search(r"^(IDS)\s(?P<exp_name>[^ \t]+)\s(?P<exp_state>[^ \t]+)$",pic_message)
    print(config_json['id'])
    print(match.group("exp_name"))
    if match.group("exp_name") == config_json['id']:
        #LOG_INFO
        print("ENCONTREI O PIC QUE QUERIA NA PORTA SERIE")
        if match.group("exp_state") == "STOPED":
            return True
        else:
            if do_stop():
                return True
            else:
                return False
    else:
        #LOG INFO
        print("NAO ENCONTREI O PIC QUE QUERIA NA PORTA SERIE")
        return False

#DO_INIT - Abre a ligacao com a porta serie
#NOTAS: possivelmente os returns devem ser jsons com mensagens de erro
#melhores, por exemplo, as portas não existem ou não está o pic em nenhuma
#delas outra hipotese é retornar ao cliente exito ou falha
#e escrever detalhes no log do sistema
def do_init(config_json):
    global serial_port

    if 'serial_port' in config_json:
        for exp_port in config_json['serial_port']['ports_restrict']:
            print("A tentar abrir a porta"+exp_port+"\n")
            try:
                #alterar esta função para aceitar mais definições do json
                #é preciso uma função para mapear os valores para as constantes da porta série
                #e.g. - 8 bits de data -> serial.EIGHTBITS; 1 stopbit -> serial.STOPBITS_ONE
                serial_port = serial.Serial(port = exp_port,\
                                                    baudrate=int(config_json['serial_port']['baud']),\
                                                    timeout = int(config_json['serial_port']['death_timeout']))
            except serial.SerialException:
                #LOG_WARNING: couldn't open serial port exp_port. Port doesnt exist or is in use
                pass
            else:
                if try_to_lock_experiment(config_json, serial_port) :
                    break
                else:
                    serial_port.close()
        
        if serial_port.is_open :
            #LOG_INFO : EXPERIMENT FOUND. INITIALIZING EXPERIMENT
            print("Consegui abrir a porta e encontrar a experiencia\n")
            #Mudar para números. Return 0 e mandar status
            return True
        else:
            #SUBSTITUIR POR LOG_ERROR : couldn't find the experiment in any of the configured serial ports
            print("Nao consegui abrir a porta e encontrar a experiencia\n")
            #return -1
            return False
    else:
        #LOG_ERROR - Serial port not configured on json.
        #return -2
        return False

def do_config(config_json) :
    global serial_port

    cmd ="cfg\t"+str(config_json["config"]["deltaX"])+"\t"+str(config_json["config"]["samples"])+"\r"
    cmd = cmd.encode(encoding="ascii")
    #Deita fora as mensagens recebidas que não
    #interessam
    serial_port.reset_input_buffer()
    serial_port.write(cmd)
    print("A tentar configurar experiência")
    while True :
        pic_message = serial_port.read_until(b'\r')
        print("MENSAGEM DO PIC DE CONFIGURACAO:\n")
        print(pic_message.decode(encoding='ascii'))
        print("\-------- --------/\n")
        if "CFG" in pic_message.decode(encoding='ascii') :
            pic_message = pic_message.decode(encoding='ascii')
            #Remover os primeiros 4 caracteres para tirar o "CFG\t" 
            pic_message = pic_message[4:]
            pic_message = pic_message.replace("\t"," ")
            break
        elif re.search(r"(STOPED|RESETED){1}$",pic_message.decode(encoding='ascii')) != None:
            return -1,False
    status_confirmation = serial_port.read_until(b'\r')
    status_confirmation = status_confirmation.decode(encoding='ascii')
    print("MENSAGEM DO PIC A CONFIRMAR CFGOK:\n")
    print(status_confirmation)
    print("\-------- --------/\n")
    if "CFGOK" in status_confirmation:
        return pic_message, True
    else:
        return -1, False

def do_start() :
    global serial_port

    print("A tentar comecar a experiencia\n")
    cmd = "str\r"
    cmd = cmd.encode(encoding='ascii')
    serial_port.reset_input_buffer()
    serial_port.write(cmd)
    while True :
        pic_message = serial_port.read_until(b'\r')
        print("MENSAGEM DO PIC A CONFIRMAR STROK:\n")
        print(pic_message.decode(encoding='ascii'))
        print("\-------- --------/\n")
        if "STROK" in pic_message.decode(encoding='ascii') :
            return True
        elif re.search(r"(STOPED|CONFIGURED|RESETED){1}$",pic_message.decode(encoding='ascii')) != None:
            return False
        #elif "STOPED" or "CONFIGURED" or "RESETED" in pic_message.decode(encoding='ascii') :
        #    return False
        #Aqui não pode ter else: false senão rebenta por tudo e por nada
        #tem de se apontar aos casos especificos -_-
    

def do_stop() :
    global serial_port

    print("A tentar parar experiencia\n")
    cmd = "stp\r"
    cmd = cmd.encode(encoding='ascii')
    serial_port.reset_input_buffer()
    serial_port.write(cmd)
    while True :
        pic_message = serial_port.read_until(b'\r')
        print("MENSAGEM DO PIC A CONFIRMAR STPOK:\n")
        print(pic_message.decode(encoding='ascii'))
        print("\-------- --------/\n")
        if "STPOK" in pic_message.decode(encoding='ascii') :
            return True
        elif re.search(r"(CONFIGURED|RESETED){1}$",pic_message.decode(encoding='ascii')) != None :
            return False
        #Aqui não pode ter else: false senão rebenta por tudo e por nada
        #tem de se apontar aos casos especificos -_-
        
    

def do_reset() :
    global serial_port

    print("A tentar fazer reset da experiencia\n")
    cmd = "rst\r"
    cmd = cmd.encode(encoding='ascii')
    serial_port.reset_input_buffer()
    serial_port.write(cmd)
    while True :
        pic_message = serial_port.read_until(b'\r')
        print("MENSAGEM DO PIC A CONFIRMAR RSTOK:\n")
        print(pic_message.decode(encoding='ascii'))
        print("\-------- --------/\n")
        if "RSTOK" in pic_message.decode(encoding='ascii') :
            return True
        elif re.search(r"(STOPED|CONFIGURED){1}$",pic_message.decode(encoding='ascii')) != None :
            return False
        #Aqui não pode ter else: false senão rebenta por tudo e por nada
        #tem de se apontar aos casos especificos -_-

#get_status placeholder
def get_status():
    global serial_port

    print("Esta funcao ainda nao faz nada\n")
    return True



if __name__ == "__main__":
    import sys
    import threading
    
    fp = open("./exp_config.json","r")
    config_json = json.load(fp)
    #config_json = json.loads('{}')
    if not do_init(config_json):
        sys.exit("Não deu para abrir a porta. F")
    printer_thread = threading.Thread(target=print_serial)
    printer_thread.start()
    while True:
        cmd = input()+"\r"
        cmd = cmd.encode(encoding='ascii')
        serial_port.write(cmd)