import os
import flask
import threading
import atexit
import logging
import json
import time
import random

from revChatGPT.V1 import Chatbot
from bot_utils import config_reader
PORT = 5001  #if '--port' not in sys.argv else int(sys.argv[sys.argv.index('--port') + 1])

"""


NEXT: ADD FITUR SUPER ADMIN: done

- ALLOW AND BLOCK NOMOR CLIENT
- TAMBAH TOKEN
- TAMBAH NOMOR BARU CLIENT DAN BISA CHAT DULUAN

- RETRIEVE CURRENT BOT APP STATUS -- token terpakai, total client aktif

"""

# Get the directory path of the current file
current_dir = os.path.dirname(os.path.abspath(__file__))
log_file_path = os.path.join(current_dir, 'app_debug.log')


app = flask.Flask(__name__)
app.debug = True

# Create a logger and the handler --> log messages to 'app_debug.log'
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(log_file_path)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

cache_timeout =  300 # 5 menit
backup_timeout = cache_timeout  * 10
error_occured = 0

chat_ids_file = os.path.join(current_dir, 'xchat_ids.json')
xtokens_file = os.path.join(current_dir, 'xtokens.json')

dummy_ids_path = "dummy_ids.json"
dummy_tokens_path = "dummy_tokens.json"

# superadmin
superadmin_password = "hakunamatata" 

xtokens = config_reader(xtokens_file)
chat_ids = config_reader(chat_ids_file)

chatbots_dict = {}
thread_timers = []

def check_chatbots_health():
    global chatbots_dict
    for bot, bot_class in chatbots_dict.copy().items():
        if bot_class.is_expired():
            del chatbots_dict[bot]

def save_ids_json(filename):    
    logger.debug('def save ids json called.')
    global chat_ids
    try:        
        logger.debug('try opening file and saving chatis.')
        with open(filename, "w") as f:
            logger.debug('saving chat_ids file.')
            json.dump(chat_ids, f)
            logger.info('chat_ids file updated.')
        threading.Timer(cache_timeout, save_ids_json, args=[filename]).start()
    except Exception as e:
        logging.error(f"Error saving chat_ids JSON file: {e}", exc_info=True)

def save_token_json(filename):
    global xtokens
    logger.debug('save token def called.')
    try:
        logger.debug('try opening file and sayoken')
        with open(filename, "w") as f:
            logger.debug('saving xtoken file.')
            json.dump(xtokens, f)
            logger.info('xtoken file updated.')
        threading.Timer(cache_timeout, save_token_json, args=[filename]).start()
    except Exception as e:
        logging.error(f"Error saving xtokens JSON file: {e}", exc_info=True)

def save_json_backup(file_names):
    # Load the data from the input JSON file
    for file_name in file_names:
        with open(file_name, 'r') as f:
            data = json.load(f)
        backup_file_name = 'backup/backup-' + os.path.basename(file_name)
        with open(backup_file_name, 'w') as f:
            json.dump(data, f)

    logger.info("DATA BACKUPS success.")
    threading.Timer(backup_timeout, save_json_backup, args=[file_names]).start()

@app.before_first_request
def start_timers():
    logger.debug('start timer.')
    try:
        # schedule the first execution of save_json for file1.json in 5 minutes
        t1 = threading.Timer(cache_timeout, save_ids_json, args=[chat_ids_file])  
        t2 = threading.Timer(cache_timeout, save_token_json, args=[xtokens_file])
        t3 = threading.Timer(backup_timeout, save_json_backup, args=[[chat_ids_file, xtokens_file]])
        t4 = threading.Timer(cache_timeout,check_chatbots_health)
        thread_timers.append(t1)  
        thread_timers.append(t2)
        thread_timers.append(t3)
        thread_timers.append(t4)
        t1.start()
        t2.start()
        t3.start()
        t4.start()
    except Exception as e:
        logging.error(f"Error start save_json timer: {e}", exc_info=True)

# @app.teardown_appcontext
def stop_timers(error=None):
    logging.debug('Stopping and tearing down timers.')
    try:
        for t in thread_timers:
            t.cancel()
    except Exception as e:
        if error:
            logging.error(f'{error}: {e}', exc_info=True)
        else:
            logging.error(f'Error occurred while stopping timers: {e}', exc_info=True)

class xChatbot:
    """ 
    saat pertama kali assign, chatbot berstatus none
    saat ask, akan bikin chatbot baru
    next ask make chat lama    
    """
    def __init__(self, phone_number):  
        self.phone_number = phone_number
        self.chatbot = None  
        self.token = None
        self.current_token_name = None        
        self.last_used = time.time()   
        self.time_out = 1800 # 30 minutes in second
        self.ask_limit_per_minute = 50
        self.bot_total_used = 0 # used for token usage counting        
        
        self.convo_id = None
        self.parent_id = None
        self.refresh_convo = False  

    def __repr__(self):
        return f"xChatbotGPT"
    
    def is_expired(self):
        return time.time() - self.last_used > self.time_out
        
    def ask(self, prompt): 
        global xtokens
        global chat_ids 

        if self.is_bot_ready():        
            respons = self.chatbot.ask(prompt, conversation_id=self.convo_id, parent_id=self.parent_id)
            self.bot_total_used +=1
            if self.current_token_name != None:
                xtokens[self.current_token_name]['total_used'] += 1
                xtokens[self.current_token_name]['grand_total_used'] += 1
            for data in respons:
                response = data["message"]                
                convo_id = data['conversation_id']
                parent_id = data['parent_id']

            tokens_info = {}        
            for key, value in xtokens.items():
                tokens_info[key] = {
                    "total use": value.get('total_used'),
                    "grand total": value.get('grand_total_used')
                }              
            print("token dict info")
            print(tokens_info)

            self.convo_id = convo_id
            self.parent_id = parent_id
            self.last_used = time.time() 
            return response
        
        else:
            if self.refresh_convo:
                self.convo_id = None
                self.parent_id = None

            respons = self.chatbot.ask(prompt, conversation_id=self.convo_id, parent_id=self.parent_id)
            self.bot_total_used +=1
            if self.current_token_name != None:
                xtokens[self.current_token_name]['total_used'] += 1
                xtokens[self.current_token_name]['grand_total_used'] += 1
            for data in respons:
                response = data["message"]                
                convo_id = data['conversation_id']
                parent_id = data['parent_id']

            tokens_info = {}        
            for key, value in xtokens.items():
                tokens_info[key] = {
                    "total use": value.get('total_used'),
                    "grand total": value.get('grand_total_used')
                }              
            print("token dict info")
            print(tokens_info)

            user_info = {}        
            for key, value in chat_ids.items():
                user_info[key] = {
                    "name": value.get('username'),
                    "subscribe": value.get('subscribe'),
                    "tot ask":value.get("total_asked"),
                    "bot_changed" : value.get('total_bot_changed')
                }  
            print(user_info)

            self.convo_id = convo_id
            self.parent_id = parent_id

            return response        
        
    def is_bot_ready(self):        
        if  self.bot_total_used >= self.ask_limit_per_minute or self.chatbot == None:
            self.set_new_user()
            
            self.convo_id = None
            self.parent_id = None
            
            self.chatbot = Chatbot(config={"access_token":self.token})
            return True
        else:
            return False    

    def set_new_user(self): 
        global xtokens
        global chat_ids 
        phone_number = self.phone_number

        if 'total_bot_changed' not in chat_ids[phone_number]:
            chat_ids[phone_number]['total_bot_changed'] = 0
        if 'total_asked' not in chat_ids[phone_number]:
            chat_ids[phone_number]['total_asked'] = 0

        self.current_token_name = chat_ids.get(phone_number, {}).get('token_name', None)

        if not self.get_new_tokens():
            raise "error generating token"
        chat_ids[phone_number]['total_bot_changed'] += 1

    def get_new_tokens(self):
        """ xtokens : xtokens.json"""
        global xtokens
        print("get new tokens")
        print("old token name")
        print(self.current_token_name)

        min_total_use = min(d['total_used'] for d in xtokens.values())
        min_dicts = [d for d in xtokens.values() if d['total_used'] == min_total_use]
        min_dicts.sort(key=lambda d: d['last_used'])        

        selected_dict = random.choice([d for d in min_dicts if d['last_used'] == min_dicts[0]['last_used']])
        selected_dict['last_used'] = time.time()

        # Get the key name of the selected dictionary
        new_token_key_name =[k for k, v in xtokens.items() if id(v) == id(selected_dict)][0]
        print("new token yielded. key name below shold be the SAME!!!")
        # Print the key name
        print("new token name")
        print(new_token_key_name)
        self.current_token_name = new_token_key_name 
        
        self.token = selected_dict["token"]
        print(self.current_token_name)
        self.bot_total_used = 0
        
        return selected_dict
    


pesan_error = "Sorry, can you resend your last message?\nMaaf, boleh kirim ulang chat terakhir Anda? \nAtau boleh balas : refresh"
         

async def ask_question(phone_number, message): 
    global xtokens
    global chat_ids
    global error_occured

    phone_number_datas = chat_ids.get(phone_number, {})
    username = phone_number_datas.get('username', None)
    subscribe = phone_number_datas.get('subscribe', False)
    bot_changed = phone_number_datas.get('total_bot_changed', None)
    asked = phone_number_datas.get('total_asked', None)

    check_message = message.lower()
    print(username)
    print(message)
    logger.info(f'{username} asked : {message} || asked : {asked} and bot change : {bot_changed}')

    if check_message.startswith("add me :"):
        colon_index = message.find(':')
        newname = message[colon_index+1:].strip()

        print("new name : "+newname)
        print("inside chat_ids upadate")

        chat_ids.update({phone_number:{}})

        chat_ids[phone_number]['username'] = newname
        chat_ids[phone_number]['subscribe'] = True
        chat_ids[phone_number]['allow_to_ask'] = True
        chat_ids[phone_number]['last_time_asked'] = int(time.time() / 60)

        if 'total_asked' not in chat_ids[phone_number]:
            chat_ids[phone_number]['total_asked'] = 0

        return f"Hai {newname}, selamat datang di BetaGPT. Gunakan dengan bijak yaa."

    if subscribe == False :
        print("new number: "+str(username)+" "+str(phone_number))
        return "Selamat datang di ChatGPT WhatsApp Beta. Jika setuju untuk join versi beta, balas chat ini dengan cara = add me : nama kamu"

    try :
        check = chat_ids.get(phone_number, {}).get('allow_to_ask', None)
        last_time_asked = chat_ids.get(phone_number, {}).get('last_time_asked', 0)
        
        print("allow to ask : "+ str(check))
        if check == False: 
            if not int(time.time() / 60) - last_time_asked > 2:
                return "Tarik napas dulu yaa. Chat satu-satu, dan tunggu chat sebelumnya terjawab dulu :)"     
        
        isblocked = chat_ids.get(phone_number, {}).get('blocked', False)

        if isblocked:
            return "Hello there. Forgive me, seems like you have no access to the Madinah GPT yet"
  
        if phone_number not in chatbots_dict:
            print("in the assigning new bot")
            xchatbot = xChatbot(phone_number)
            chatbots_dict[phone_number] = xchatbot
            logger.info(f"len xchatbot lists : {len(chatbots_dict)}")
        else:
            xchatbot = chatbots_dict[phone_number]
            logger.info(f"len xchatbot lists : {len(chatbots_dict)}")

        if check_message == "setnewbot" or check_message == "refresh":
            print("init new chat bot account")
            # chat_ids[phone_number]['token_name'] = None
            xchatbot.chatbot = None
            chat_ids[phone_number]['allow_to_ask'] = True
            chat_ids[phone_number]['total_asked'] += 1 
            return "Thank you. Chat sudah ter-refresh. Silakan lanjut chat Anda yaa~"   
        
        # input_string = "#superadmin 1234 blokir 0983"
        if check_message.find('#') != -1:
            words = check_message.split()
            
            if words[0] == "#superadmin":
                try :
                    try:
                        pwd = words[1] 
                        task = words[2]
                        target = words[3]
                    except:
                        pwd = words[1] 
                        task = words[2]

                    if pwd == superadmin_password:
                        if task == "block" :
                            if 'blocked' not in chat_ids[target]:
                                chat_ids[target]['blocked'] = True
                            chat_ids[target]['blocked'] = False
                            target_name = chat_ids.get(target, {}).get('username', None)
                            return f"command to {task} {target_name}'s number {target} has been executed."

                        elif task == "unblock":
                            if 'blocked' not in chat_ids[target]:
                                chat_ids[target]['blocked'] = False
                            chat_ids[target]['blocked'] = False
                            target_name = chat_ids.get(target, {}).get('username', None)
                            return f"command to {task} {target_name}'s number {target} has been executed."
                        
                        elif task == "healthcheck":
                            return f"Health Check\nBots active : {len(chatbots_dict)}\nError occured : {error_occured}"

                except KeyError as e:
                    error_occured += 1
                    return f"command error. \n\nprobably because the target are not in chat_ids yet.\n\n prefered command format = '#superadmin 1234 block/unblock 0983' \n\n {e}. [code error info]"
            # password incorrect, pass to the next and treat like ordinary chat
            pass

        chat_ids[phone_number]['allow_to_ask'] = False
        response = xchatbot.ask(message)

        if response == "":

            print("ok kosong")            
            chat_ids[phone_number]['allow_to_ask'] = True
            chat_ids[phone_number]['total_asked'] += 1 
            response = "Pardon, Can you resend your last message?\nMaaf, boleh kirim ulang chat terakhir Anda?\n\njika di-refresh 3 kali belum beres, lapor admin yaa"
            logger.info(f"a ZERO response occured. client :{username}, total asked:{asked}, bot changed:{bot_changed}, phone:{phone_number}")
            error_occured += 1

        print("chatbot responding this prompt ...")      
        print(phone_number)
        print(response)

        chat_ids[phone_number]['allow_to_ask'] = True
        chat_ids[phone_number]['total_asked'] += 1    
        chat_ids[phone_number]['last_time_asked'] = int(time.time() / 60)
        logger.info(f'{username} got answered : {response}')
        return response
    
    except IndexError as e:
        print(e)
        logger.error(f"Error IndexError : {e}", exc_info=True)
        # app.logger.error(f"Error Index error 400 in chatbot.ask: {e}")        
        chat_ids[phone_number]['allow_to_ask'] = True
        error_occured += 1
        return pesan_error  #"Sorry, can you resend your last message?\n\nMaaf, boleh kirim ulang chat terakhir Anda?"

    except Exception as e:
        print(e)
        logger.error(f"Exception Error 500 : {e}", exc_info=True)
        # app.logger.error(f"Error 500 in vhatbot: {e}")
        chat_ids[phone_number]['allow_to_ask'] = True
        error_occured += 1
        return  pesan_error #"Sorry, error 500 occured.\n\nCan you resend your last message?\n\nMaaf, boleh kirim ulang chat terakhir Anda?"

@app.route("/chat", methods=["GET"])
async def chat():
    global chat_ids
    global xtokens 

    message = flask.request.args.get("q")
    print(message)
    phone_number = flask.request.args.get("user")
    print(phone_number)
    
    try :
        response = await ask_question(phone_number, message)
        return response

    except IndexError as e:        
        logger.error(f"Error IndexError at @app.route(/chat: {e}", exc_info=True)
        # app.logger.error(f"Error Index error 400 in chatbot.ask: {e}") 
        error_occured += 1
        return pesan_error #"Sorry, can you resend your last message?\nMaaf, boleh kirim ulang chat terakhir Anda?\nAtau boleh balas : refresh"

    except Exception as e:
        logger.error(f"Exception Error 500 at @app.route(/chat: {e}", exc_info=True)
        # app.logger.error(f"Error 500 in vhatbot: {e}")
        error_occured += 1
        return pesan_error #"Sorry, can you resend your last message?\nMaaf, boleh kirim ulang chat terakhir Anda? \nAtau boleh balas : refresh"

logger.info("app run")

if __name__ == "__main__":    
    app.run(port=PORT, threaded=True)
    atexit.register(stop_timers)
    logger.info("app terminated")
    
    